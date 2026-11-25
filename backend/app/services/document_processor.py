import os
import io
import re
import time
import uuid
import hashlib
import hmac
import logging
from typing import Tuple, List, Optional, Dict, Any
from decimal import Decimal
import fitz  # PyMuPDF
from fastapi import UploadFile, HTTPException

from ..models.document import (
    Document, DocumentSection, DocumentChunk, DocumentProcessResult, DocumentIntelligence,
    KeyFact, FinancialTerm, MetricChange, Relationship, AreaToUnderstand, InvestigationPath,
    ConsentPreviewResponse, ConsentConfirmResponse,
    AISessionPreviewResponse, AISessionActivateResponse, AISessionStatusResponse,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB per file limit
CONSENT_SECRET = os.environ.get("SINGLE_DOC_CONSENT_SECRET", "bharat-single-doc-consent-secret-2026")
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL_ID", "gemini-3.5-flash-lite")
AI_SESSION_TTL_SECONDS = 3600  # Bounded 1-hour session TTL (never permanent)
GEMINI_TIMEOUT_MS = 20000


def _classify_provider_error(error_str: str, model_id: str) -> str:
    """Classify provider exceptions into safe user-facing error codes without leaking secrets."""
    lower = error_str.lower()
    if "401" in error_str or "403" in error_str or "api_key" in lower or "permission" in lower or "unauthenticated" in lower:
        return "INVALID_CREDENTIALS: External AI authentication failed"
    if "503" in error_str or "unavailable" in lower:
        return "PROVIDER_OUTAGE_503: Provider temporarily unavailable"
    if "429" in error_str or "quota" in lower or "rate" in lower:
        return "RATE_LIMIT_429: API quota or rate limit exceeded"
    if "404" in error_str or "400" in error_str or "not found" in lower:
        return f"INVALID_MODEL_IDENTIFIER: Model {model_id} unavailable"
    if "timeout" in lower or "deadline" in lower or "timed out" in lower:
        return "PROVIDER_TIMEOUT: Request to external provider timed out"
    if "validation" in lower or "json" in lower or "empty" in lower:
        return "MALFORMED_PROVIDER_RESPONSE: Invalid AI response format"
    return "NETWORK_UNAVAILABLE: External provider communication error"


def _is_transient_503_error(error_str: str) -> bool:
    """Return True only for HTTP 503 service-unavailable errors; never retry 400/401/403/404 or invalid keys."""
    if any(code in error_str for code in ("400", "401", "403", "404")):
        return False
    lower = error_str.lower()
    if any(marker in lower for marker in ("api_key", "api key", "not found", "unauthenticated", "invalid argument")):
        return False
    return bool(re.search(r"(?<!\d)503(?!\d)", error_str))


def _call_gemini_with_503_retry(fn, retry_delay_seconds: float = 0.5):
    """Execute a Gemini API call and retry exactly once after a brief delay on HTTP 503."""
    try:
        return fn()
    except Exception as first_err:
        if not _is_transient_503_error(str(first_err)):
            raise
        logger.warning("Gemini returned HTTP 503; waiting briefly and retrying once.")
        time.sleep(retry_delay_seconds)
        return fn()


class SingleDocConsentManager:
    """
    Cryptographic, session-scoped consent & AI activation manager for single document external operations.
    Supports both:
    - Bounded, explicit one-time AI session activation (ai_session_id + HMAC ai_session_token, 1h TTL, revocable)
    - Operation-specific single-use challenge consent (EXPLAIN, CHAT, TRANSLATE)
    """
    _challenges: Dict[str, Dict[str, Any]] = {}
    _documents: Dict[str, Dict[str, Any]] = {}
    _activation_challenges: Dict[str, Dict[str, Any]] = {}
    _ai_sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def create_ai_session_preview(cls) -> AISessionPreviewResponse:
        activation_id = str(uuid.uuid4())
        expires_at = time.time() + 600
        cls._activation_challenges[activation_id] = {
            "activation_id": activation_id,
            "expires_at": expires_at,
            "consumed": False,
        }
        disclosure_items = [
            "Uploaded document text and relevant extracted excerpts may be sent to Google's Gemini API.",
            "Questions you ask in Ask Bharat and relevant document context may be transmitted to Gemini API.",
            "Purpose: Educational document explanation, financial question answering, and multilingual translation.",
            "Google's Gemini API processes transmitted data under Google API data handling terms.",
            "If Gemini is unavailable, fails, or is disabled, Bharat Investor Copilot automatically falls back to deterministic local processing without losing extracted facts.",
        ]
        disclosure_statement = (
            "Enabling AI processing allows document excerpts, user questions, and relevant context to be sent to "
            "Google's Gemini API for educational analysis and translation. Google processes transmitted data per "
            "API terms. Local deterministic fallback runs automatically whenever Gemini is unavailable or disabled."
        )
        return AISessionPreviewResponse(
            activation_id=activation_id,
            recipient="Google Gemini API",
            purpose="AI-first educational document explanation, Q&A, and translation with automatic local fallback.",
            disclosure_items=disclosure_items,
            disclosure_statement=disclosure_statement,
            expires_in_seconds=600,
        )

    @classmethod
    def activate_ai_session(cls, activation_id: str) -> AISessionActivateResponse:
        challenge = cls._activation_challenges.get(activation_id)
        if not challenge:
            raise HTTPException(status_code=400, detail="Invalid or unknown AI activation challenge")
        if challenge["consumed"]:
            raise HTTPException(status_code=400, detail="AI activation challenge already consumed")
        if time.time() > challenge["expires_at"]:
            cls._activation_challenges.pop(activation_id, None)
            raise HTTPException(status_code=400, detail="AI activation challenge expired")

        challenge["consumed"] = True
        ai_session_id = str(uuid.uuid4())
        created_at = time.time()
        expires_at = created_at + AI_SESSION_TTL_SECONDS
        token_data = f"AI_SESSION:{ai_session_id}:{created_at}:{expires_at}"
        ai_session_token = hmac.new(CONSENT_SECRET.encode(), token_data.encode(), hashlib.sha256).hexdigest()

        cls._ai_sessions[ai_session_id] = {
            "ai_session_id": ai_session_id,
            "token": ai_session_token,
            "created_at": created_at,
            "expires_at": expires_at,
            "active": True,
            "revoked": False,
        }
        return AISessionActivateResponse(
            ai_session_id=ai_session_id,
            ai_session_token=ai_session_token,
            expires_in_seconds=AI_SESSION_TTL_SECONDS,
            active=True,
        )

    @classmethod
    def verify_ai_session(cls, ai_session_id: Optional[str], ai_session_token: Optional[str]) -> bool:
        if not ai_session_id or not ai_session_token:
            return False
        session = cls._ai_sessions.get(ai_session_id)
        if not session:
            return False
        if not session.get("active") or session.get("revoked"):
            return False
        if time.time() > session["expires_at"]:
            session["active"] = False
            return False
        if not hmac.compare_digest(session["token"], ai_session_token):
            return False
        return True

    @classmethod
    def disable_ai_session(cls, ai_session_id: str, ai_session_token: str) -> AISessionStatusResponse:
        session = cls._ai_sessions.get(ai_session_id)
        if session and hmac.compare_digest(session["token"], ai_session_token):
            session["active"] = False
            session["revoked"] = True
        return AISessionStatusResponse(active=False, expires_in_seconds=0)

    @classmethod
    def get_ai_session_status(cls, ai_session_id: str, ai_session_token: str) -> AISessionStatusResponse:
        if not cls.verify_ai_session(ai_session_id, ai_session_token):
            return AISessionStatusResponse(active=False, expires_in_seconds=0)
        session = cls._ai_sessions[ai_session_id]
        remaining = max(0, int(session["expires_at"] - time.time()))
        return AISessionStatusResponse(active=True, expires_in_seconds=remaining)

    @classmethod
    def register_document(
        cls,
        doc_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
        text_content: str,
        intelligence: DocumentIntelligence
    ) -> None:
        cls._documents[doc_id] = {
            "filename": filename,
            "content": content,
            "mime_type": mime_type,
            "text": text_content,
            "intelligence": intelligence,
            "created_at": time.time(),
        }

    @classmethod
    def get_document(cls, doc_id: str) -> Optional[Dict[str, Any]]:
        return cls._documents.get(doc_id)

    @classmethod
    def create_preview(cls, doc_id: str, operation: str) -> ConsentPreviewResponse:
        doc_info = cls._documents.get(doc_id)
        if not doc_info:
            raise HTTPException(status_code=404, detail="Document not found or session expired")

        op_upper = operation.upper().strip()
        if op_upper not in ("EXPLAIN", "CHAT", "TRANSLATE"):
            raise HTTPException(status_code=400, detail=f"Unsupported operation: {operation}")

        # Construct operation-specific payload proposed for external transmission
        if op_upper == "EXPLAIN":
            raw_text = doc_info["text"][:2500]
            payload = f"Explain Document Narrative: {raw_text}"
            purpose = "External AI narrative explanation generation based on extracted text excerpts."
        elif op_upper == "CHAT":
            raw_text = doc_info["text"][:2500]
            payload = f"Chat Document Context: {raw_text}"
            purpose = "External AI question answering using extracted document context."
        else:  # TRANSLATE
            intel = doc_info["intelligence"]
            payload = f"Translation Payload: {intel.simple_summary} | {intel.document_story or ''}"
            purpose = "External AI multilingual translation of document summary fields."

        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        challenge_id = str(uuid.uuid4())
        expires_at = time.time() + 600  # 10 minutes TTL

        # Store challenge as UNCONFIRMED (preview alone does NOT authorize transmission)
        cls._challenges[challenge_id] = {
            "challenge_id": challenge_id,
            "document_id": doc_id,
            "operation": op_upper,
            "payload": payload,
            "payload_hash": payload_hash,
            "expires_at": expires_at,
            "confirmed": False,
            "token": None,
            "is_consumed": False,
        }

        disclosure = (
            "Approved information (document text excerpt) will leave your device and be sent to "
            "Google Gemini API for narrative generation. External transmission is subject to Google API "
            "standard data handling terms. You may decline and continue using 100% offline Local Mode."
        )

        return ConsentPreviewResponse(
            challenge_id=challenge_id,
            document_id=doc_id,
            operation=op_upper,
            recipient="Google Gemini API",
            purpose=purpose,
            payload_preview=payload[:500] + ("..." if len(payload) > 500 else ""),
            payload_hash=payload_hash,
            expires_in_seconds=600,
            disclosure_statement=disclosure,
        )

    @classmethod
    def confirm_consent(
        cls,
        challenge_id: str,
        doc_id: str,
        operation: str,
        payload_hash: str
    ) -> ConsentConfirmResponse:
        challenge = cls._challenges.get(challenge_id)
        if not challenge:
            raise HTTPException(status_code=400, detail="Invalid or expired consent challenge")

        if challenge["document_id"] != doc_id:
            raise HTTPException(status_code=400, detail="Consent challenge document mismatch")

        if challenge["operation"] != operation.upper().strip():
            raise HTTPException(status_code=400, detail="Consent challenge operation mismatch")

        if challenge["payload_hash"] != payload_hash:
            raise HTTPException(status_code=400, detail="Payload hash mismatch; consent rejected")

        if time.time() > challenge["expires_at"]:
            cls._challenges.pop(challenge_id, None)
            raise HTTPException(status_code=400, detail="Consent challenge has expired")

        # Generate HMAC-SHA256 consent token
        token_data = f"{challenge_id}:{doc_id}:{operation.upper()}:{payload_hash}:{challenge['expires_at']}"
        consent_token = hmac.new(CONSENT_SECRET.encode(), token_data.encode(), hashlib.sha256).hexdigest()

        challenge["confirmed"] = True
        challenge["token"] = consent_token
        challenge["is_consumed"] = False

        return ConsentConfirmResponse(
            challenge_id=challenge_id,
            consent_token=consent_token,
            expires_in_seconds=int(challenge["expires_at"] - time.time()),
            operation=operation.upper(),
            document_id=doc_id,
        )

    @classmethod
    def verify_and_consume(
        cls,
        challenge_id: str,
        doc_id: str,
        operation: str,
        consent_token: str,
        payload_to_send: str
    ) -> bool:
        challenge = cls._challenges.get(challenge_id)
        if not challenge:
            logger.warning(f"Consent rejected: challenge {challenge_id} not found")
            return False

        if not challenge["confirmed"]:
            logger.warning("Consent rejected: challenge preview was not confirmed")
            return False

        if challenge["is_consumed"]:
            logger.warning("Consent rejected: token was already consumed (single-use enforced)")
            return False

        if time.time() > challenge["expires_at"]:
            logger.warning("Consent rejected: challenge expired")
            cls._challenges.pop(challenge_id, None)
            return False

        if challenge["document_id"] != doc_id or challenge["operation"] != operation.upper().strip():
            logger.warning("Consent rejected: document or operation mismatch")
            return False

        if not hmac.compare_digest(challenge["token"], consent_token):
            logger.warning("Consent rejected: invalid token signature")
            return False

        # Re-hash outgoing payload to verify it matches what the user confirmed
        current_hash = hashlib.sha256(payload_to_send.encode("utf-8")).hexdigest()
        if current_hash != challenge["payload_hash"]:
            logger.warning("Consent rejected: outgoing payload does not match approved hash")
            return False

        # Mark single-use token consumed
        challenge["is_consumed"] = True
        return True


class LocalExplanationEngine:
    """
    Deterministic, 100% offline explanation engine.
    Extracts text, metadata, and core financial numbers locally, generates grounded explanations
    with source page references, and provides educational definitions without cloud AI.
    """

    GLOSSARY = {
        "Revenue": {
            "en": {
                "plain": "Total money earned from selling goods or services before deducting any costs.",
                "why": "Shows the overall scale and top-line commercial activity of the business."
            },
            "hi": {
                "plain": "किसी भी खर्च को घटाने से पहले सामान या सेवाओं की बिक्री से अर्जित कुल धनराशि।",
                "why": "यह व्यवसाय के समग्र स्तर और वाणिज्यिक गतिविधि को दर्शाता है।"
            },
            "hinglish": {
                "plain": "Kisi bhi kharche ko ghatane se pehle goods ya services bech kar kamayi gayi total income.",
                "why": "Yeh business ke overall scale aur commercial activity ko darshata hai."
            }
        },
        "Net Profit": {
            "en": {
                "plain": "The actual profit remaining after paying all operating expenses, taxes, and interest costs.",
                "why": "Indicates bottom-line profitability and the funds available for reinvestment or dividends."
            },
            "hi": {
                "plain": "सभी परिचालन व्यय, कर और ब्याज लागतों का भुगतान करने के बाद बचा वास्तविक लाभ।",
                "why": "यह कंपनी की अंतिम लाभप्रदता और पुनर्निवेश हेतु उपलब्ध धनराशि को दर्शाता है।"
            },
            "hinglish": {
                "plain": "Saare operating expenses, taxes aur interest dene ke baad bacha hua actual profit.",
                "why": "Yeh company ki bottom-line profitability ko darshata hai."
            }
        },
        "EBITDA": {
            "en": {
                "plain": "Operating profit before deducting interest, taxes, depreciation, and amortization.",
                "why": "Measures core operational profitability independent of capital structure and tax rates."
            },
            "hi": {
                "plain": "ब्याज, कर, मूल्यह्रास और परिशोधन में कटौती से पहले परिचालन लाभ।",
                "why": "यह पूंजी संरचना और कर दरों से अलग मुख्य परिचालन दक्षता को मापता है।"
            },
            "hinglish": {
                "plain": "Interest, taxes, depreciation aur amortization se pehle ka core operating profit.",
                "why": "Yeh company ke core business ki operational performance ko measure karta hai."
            }
        },
        "Total Debt": {
            "en": {
                "plain": "The total amount of borrowed money (short-term and long-term loans) the company owes.",
                "why": "Helps assess financial leverage, solvency risk, and interest payment obligations."
            },
            "hi": {
                "plain": "कंपनी द्वारा लिए गए ऋण (अल्पकालिक और दीर्घकालिक) की कुल राशि।",
                "why": "यह वित्तीय उत्तोलन, शोधन जोखिम और ब्याज भुगतान देनदारियों का आकलन करने में मदद करता है।"
            },
            "hinglish": {
                "plain": "Company par total borrowed loan (short-term aur long-term) ki kul rashi.",
                "why": "Yeh financial leverage aur solvency risk samajhne mein madad karta hai."
            }
        },
        "Operating Cash Flow": {
            "en": {
                "plain": "The actual cash generated from the company's core day-to-day business operations.",
                "why": "Demonstrates whether the company generates real cash rather than just accounting profits."
            },
            "hi": {
                "plain": "कंपनी के दैनिक मुख्य व्यावसायिक कार्यों से अर्जित वास्तविक नकद धनराशि।",
                "why": "यह दर्शाता है कि क्या कंपनी केवल कागजी लाभ के बजाय वास्तविक नकद कमा रही है।"
            },
            "hinglish": {
                "plain": "Company ke core day-to-day operations se generate hua actual cash.",
                "why": "Yeh check karta hai ki company real cash generate kar rahi hai ya sirf accounting profit."
            }
        },
        "Total Assets": {
            "en": {
                "plain": "Everything of financial value owned by the company, including property, equipment, inventory, and cash.",
                "why": "Represents the total economic resources deployed to generate revenue."
            },
            "hi": {
                "plain": "कंपनी के स्वामित्व वाली सभी वित्तीय संपत्तियां, जैसे भूमि, भवन, उपकरण, इन्वेंटरी और नकदी।",
                "why": "यह राजस्व उत्पन्न करने के लिए तैनात किए गए कुल आर्थिक संसाधनों को दर्शाता है।"
            },
            "hinglish": {
                "plain": "Company ki saari valuable properties, equipment, cash aur resources jo uske paas hain.",
                "why": "Yeh business ko run karne aur income generate karne ke resources ko darshata hai."
            }
        }
    }

    @classmethod
    def generate_intelligence(
        cls,
        document_id: str,
        text_content: str,
        sections: List[DocumentSection],
        language: str = "English"
    ) -> DocumentIntelligence:
        lang_key = "hi" if language == "Hindi" else "hinglish" if language == "Hinglish" else "en"

        clean_text = text_content.strip()
        if not clean_text:
            # Honest disclosure for empty / unreadable / scanned documents
            story_empty = {
                "en": "The uploaded document contains unreadable content or appears to be a scanned image without an embedded digital text layer. Figures could not be reliably extracted offline. Please inspect the original document directly.",
                "hi": "अपलोड किए गए दस्तावेज़ में डिजिटल टेक्स्ट परत नहीं है या यह एक स्कैन की गई छवि है। ऑफ़लाइन मोड में आंकड़े विश्वसनीय रूप से नहीं निकाले जा सके। कृपया मूल दस्तावेज़ का सीधे निरीक्षण करें।",
                "hinglish": "Uploaded document mein digital text layer nahi hai ya yeh ek scanned image hai. Offline mode mein figures extract nahi ho sake. Kripya original document directly inspect karein."
            }[lang_key]

            return DocumentIntelligence(
                document_type="Scanned / Unreadable Document",
                simple_summary=story_empty,
                document_story=story_empty,
                key_facts=[],
                financial_terms=[],
                changes=[],
                relationships=[],
                areas_to_understand=[],
                investigation_paths=[],
                uncertainty_notes=["No selectable digital text layer was detected in this document."],
                mode="LOCAL_MODE",
                fallback_triggered=False
            )

        # 1. Detect Metadata locally
        company_name = cls._detect_company(clean_text) or (doc.filename.split('.')[0].replace('_', ' ') if doc.filename else "the company")
        period = cls._detect_period(clean_text) or "Recent Reporting Period"
        currency = cls._detect_currency(clean_text) or "INR"
        scale = cls._detect_scale(clean_text) or "Crores"
        scope = cls._detect_scope(clean_text) or "Disclosed"

        # 2. Extract Reported Metrics deterministically from text/sections
        extracted_facts = cls._extract_facts(sections)

        # 3. Build Key Facts
        key_facts: List[KeyFact] = []
        for fact in extracted_facts:
            term_name = fact["label"]
            explanation = cls.GLOSSARY.get(term_name, {}).get(lang_key, {}).get("plain", f"Reported {term_name} figure.")
            key_facts.append(KeyFact(
                label=term_name,
                value=fact["value"],
                unit=f"{currency} {scale}",
                explanation=explanation,
                evidence_reference=f"Page {fact['page']}"
            ))

        # 4. Build Impact Lens (Financial Terms)
        financial_terms: List[FinancialTerm] = []
        for fact in extracted_facts[:4]:
            term_name = fact["label"]
            gloss = cls.GLOSSARY.get(term_name, {}).get(lang_key)
            if gloss:
                financial_terms.append(FinancialTerm(
                    term=term_name,
                    plain_language_definition=gloss["plain"],
                    why_it_matters_general=gloss["why"],
                    document_context=f"Reported at {fact['value']} {currency} {scale} on Page {fact['page']}.",
                    evidence_reference=f"Page {fact['page']}"
                ))

        # If no specific metrics matched, populate educational foundation terms
        if not financial_terms:
            for term_name in ["Revenue", "Net Profit", "Operating Cash Flow"]:
                gloss = cls.GLOSSARY[term_name][lang_key]
                financial_terms.append(FinancialTerm(
                    term=term_name,
                    plain_language_definition=gloss["plain"],
                    why_it_matters_general=gloss["why"],
                    document_context="Key financial indicator disclosed in corporate annual and quarterly reports.",
                    evidence_reference="Standard Financial Disclosure"
                ))

        # 5. Build What Changed? (MetricChange)
        changes = cls._detect_changes(sections, currency, scale, lang_key)

        # 6. Build Narrative Document Story
        metrics_summary = ", ".join([f"{f['label']}: {f['value']} {currency} {scale} (Page {f['page']})" for f in extracted_facts[:3]])
        if not metrics_summary:
            metrics_summary = "general financial narrative disclosures"

        page_count = len(sections)
        if lang_key == "hi":
            story = (
                f"यह दस्तावेज़ {company_name} का आधिकारिक {scope} वित्तीय विवरण है, जो {period} को "
                f"{currency} {scale} में दर्शाता है। स्थानीय ऑफ़लाइन विश्लेषण ने {page_count} पृष्ठों की जांच की। "
                f"मुख्य रिपोर्ट किए गए आंकड़ों में शामिल हैं: {metrics_summary}। "
                f"यह विवरण विशुद्ध रूप से शैक्षणिक है और किसी भी प्रकार की निवेश सलाह नहीं है।"
            )
        elif lang_key == "hinglish":
            story = (
                f"Yeh document {company_name} ka official {scope} financial disclosure hai jo {period} ko "
                f"{currency} {scale} mein cover karta hai. Local offline analysis ne {page_count} pages process kiye. "
                f"Key reported figures: {metrics_summary}. "
                f"Yeh analysis purely educational hai aur koi buy ya sell recommendation nahi deta."
            )
        else:
            story = (
                f"This filing is an official {scope} financial disclosure for {company_name} covering {period} "
                f"in {currency} {scale}. Local deterministic analysis processed {page_count} page(s) and identified "
                f"key reported figures: {metrics_summary}. "
                f"This analysis is strictly educational and does not constitute investment advice."
            )

        # 7. Areas to Understand & Investigation Paths
        areas = [
            AreaToUnderstand(
                title="Operational Scale" if lang_key == "en" else "परिचालन स्तर" if lang_key == "hi" else "Operational Scale",
                description="Core business volume and gross income reported in this period.",
                related_facts=[f["label"] for f in extracted_facts[:2]],
                questions=["How does current revenue compare to historical performance?"],
                evidence_references=[f"Page {f['page']}" for f in extracted_facts[:2]]
            ),
            AreaToUnderstand(
                title="Financial Leverage & Solvency" if lang_key == "en" else "वित्तीय ऋण एवं शोधन क्षमता" if lang_key == "hi" else "Financial Leverage",
                description="Obligations and borrowing levels disclosed in the balance sheet.",
                related_facts=[f["label"] for f in extracted_facts if "Debt" in f["label"]],
                questions=["What are the company's debt repayment schedules?"],
                evidence_references=["Balance Sheet"]
            )
        ]

        paths = [
            InvestigationPath(
                question="What are the key drivers of operating profit reported in this document?",
                related_facts=[f["label"] for f in extracted_facts[:2]],
                evidence_references=["Financial Statement Notes"]
            ),
            InvestigationPath(
                question="Are there significant contingent liabilities or footnote restatements?",
                related_facts=[],
                evidence_references=["Notes to Accounts"]
            )
        ]

        return DocumentIntelligence(
            document_type=f"{scope} Financial Disclosure",
            simple_summary=story,
            document_story=story,
            key_facts=key_facts,
            financial_terms=financial_terms,
            changes=changes,
            relationships=[],
            areas_to_understand=areas,
            investigation_paths=paths,
            uncertainty_notes=["Analysis generated deterministically in Local Mode from digital text and tables."],
            source_references=[f"Page {s.page_number}" for s in sections[:5]],
            mode="LOCAL_MODE",
            fallback_triggered=False,
            fallback_message=None
        )

    @classmethod
    def _detect_company(cls, text: str) -> Optional[str]:
        # Scan first 3000 chars for corporate markers with case-insensitivity and suffix variations
        m = re.search(
            r"\b([A-Z0-9][A-Za-z0-9\s,&.'()-]{2,60}?(?:Private\s+Limited|Pvt\.?\s*Ltd\.?|Public\s+Limited|Limited|Ltd\.?|LLP|L\.L\.P\.|Corporation|Enterprises|Industries|Bank|Services|Technologies))\b",
            text[:3000],
            re.IGNORECASE,
        )
        if m:
            clean = m.group(1).strip()
            # Eliminate generic phrases
            if not any(g in clean.lower() for g in ["auditor", "statement", "contents", "independent", "report of", "notice of", "board of"]):
                return clean
        return None

    @classmethod
    def _detect_period(cls, text: str) -> Optional[str]:
        m = re.search(r"\b(FY\s*20\d{2}(?:-\d{2,4})?|Q[1-4]\s*FY\s*20\d{2}|Quarter\s+ended\s+[A-Za-z0-9,\s]{4,25}|Year\s+ended\s+[A-Za-z0-9,\s]{4,25})\b", text[:2500], re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    @classmethod
    def _detect_currency(cls, text: str) -> Optional[str]:
        if re.search(r"(?:₹|INR|Rs\.?|Rupees)", text[:3000], re.IGNORECASE):
            return "INR (₹)"
        if re.search(r"(?:\$|USD|Dollars)", text[:3000], re.IGNORECASE):
            return "USD ($)"
        return "INR (₹)"

    @classmethod
    def _detect_scale(cls, text: str) -> Optional[str]:
        m = re.search(r"\b(Crores?|Lakhs?|Millions?|Billions?|Thousands?)\b", text[:3000], re.IGNORECASE)
        if m:
            return m.group(1).capitalize()
        return "Crores"

    @classmethod
    def _detect_scope(cls, text: str) -> Optional[str]:
        # Prioritize statement headings / title lines
        sample = text[:3000]
        if re.search(r"\bstatement\s+of\s+standalone\b|\bstandalone\s+(?:financial\s+)?results\b", sample, re.IGNORECASE):
            return "Standalone"
        if re.search(r"\bstatement\s+of\s+consolidated\b|\bconsolidated\s+(?:financial\s+)?results\b", sample, re.IGNORECASE):
            return "Consolidated"
        has_standalone = bool(re.search(r"\bStandalone\b", sample, re.IGNORECASE))
        has_consolidated = bool(re.search(r"\bConsolidated\b", sample, re.IGNORECASE))
        if has_standalone and not has_consolidated:
            return "Standalone"
        if has_consolidated and not has_standalone:
            return "Consolidated"
        if has_standalone and has_consolidated:
            stand_pos = sample.lower().find("standalone")
            cons_pos = sample.lower().find("consolidated")
            return "Standalone" if stand_pos < cons_pos else "Consolidated"
        return "Disclosed"

    @classmethod
    def _extract_facts(cls, sections: List[DocumentSection]) -> List[Dict[str, Any]]:
        metric_patterns = [
            ("Revenue", re.compile(r"(?:revenue\s+(?:from\s+operations)?|total\s+income|turnover|net\s+sales)\s*[:\-\s]+\D*?([\d,]+(?:\.\d+)?)", re.I)),
            ("Net Profit", re.compile(r"(?:net\s+profit|profit\s+after\s+tax(?:es)?|PAT|profit\s+for\s+the\s+period)\s*[:\-\s]+\D*?([\d,]+(?:\.\d+)?)", re.I)),
            ("EBITDA", re.compile(r"(?:EBITDA|operating\s+profit)\s*[:\-\s]+\D*?([\d,]+(?:\.\d+)?)", re.I)),
            ("Total Debt", re.compile(r"(?:total\s+debt|borrowings|total\s+borrowings)\s*[:\-\s]+\D*?([\d,]+(?:\.\d+)?)", re.I)),
            ("Total Assets", re.compile(r"(?:total\s+assets|assets\s+total)\s*[:\-\s]+\D*?([\d,]+(?:\.\d+)?)", re.I)),
            ("Operating Cash Flow", re.compile(r"(?:cash\s+from\s+operations|operating\s+cash\s+flow|net\s+cash\s+from\s+operating\s+activities)\s*[:\-\s]+\D*?([\d,]+(?:\.\d+)?)", re.I)),
        ]

        found: List[Dict[str, Any]] = []
        seen_metrics = set()

        for sec in sections:
            for label, pattern in metric_patterns:
                if label in seen_metrics:
                    continue
                match = pattern.search(sec.content)
                if match:
                    raw_val = match.group(1).strip()
                    found.append({
                        "label": label,
                        "value": raw_val,
                        "page": sec.page_number
                    })
                    seen_metrics.add(label)

        return found

    @classmethod
    def _detect_changes(
        cls,
        sections: List[DocumentSection],
        currency: str,
        scale: str,
        lang_key: str
    ) -> List[MetricChange]:
        # Heuristic detection of comparative metrics
        changes: List[MetricChange] = []
        change_pattern = re.compile(r"(Revenue|Net Profit|EBITDA|PAT)\s+(?:increased|grew|decreased|fell)\s+(?:by\s+)?([+\-]?[\d,]+(?:\.\d+)?%?)", re.I)

        for sec in sections:
            for match in change_pattern.finditer(sec.content):
                metric = match.group(1).strip()
                diff_str = match.group(2).strip()
                is_growth = not ("decreased" in match.group(0).lower() or "fell" in match.group(0).lower() or diff_str.startswith("-"))
                direction = "INCREASE" if is_growth else "DECREASE"
                prefix = "+" if is_growth and not diff_str.startswith("+") else ""

                exp = f"Reported {direction.lower()} in {metric}."
                if lang_key == "hi":
                    exp = f"{metric} में {direction.lower()} दर्ज की गई।"
                elif lang_key == "hinglish":
                    exp = f"{metric} mein {direction.lower()} report hua."

                changes.append(MetricChange(
                    metric=metric,
                    change=f"{prefix}{diff_str}",
                    change_type=direction,
                    period="Reported Period",
                    explanation=exp,
                    evidence_reference=f"Page {sec.page_number}"
                ))
                if len(changes) >= 3:
                    break
            if len(changes) >= 3:
                break
        return changes


class DocumentProcessor:
    @staticmethod
    async def validate_file(file: UploadFile) -> None:
        """Validate uploaded file size and content type."""
        allowed_types = ["application/pdf", "image/png", "image/jpeg", "text/plain"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

        if size == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024 * 1024)}MB")

    @classmethod
    async def process_upload(
        cls,
        file: UploadFile,
        language: str = "English",
        mode: str = "local",
        ai_session_id: Optional[str] = None,
        ai_session_token: Optional[str] = None,
    ) -> DocumentProcessResult:
        """
        Main pipeline entry point for single document upload.
        Always performs local extraction first. Automatically runs Gemini explanation ONLY when
        mode == 'ai' AND a valid server-issued AI session token is verified; falls back locally on failure.
        """
        await cls.validate_file(file)
        content = await file.read()

        document = Document(
            id=str(uuid.uuid4()),
            filename=file.filename or "unknown",
            file_type=file.content_type or "unknown",
            file_size_bytes=len(content),
            status="processing"
        )

        try:
            if file.content_type == "application/pdf":
                document = cls.process_pdf(content, document, language)
            elif file.content_type == "text/plain":
                document = cls.process_text(content, document, language)
            elif file.content_type in ["image/png", "image/jpeg"]:
                document = cls.process_image(content, document, language)

            # Register document in single-doc consent manager for session traceability
            all_text = "\n".join([sec.content for sec in document.sections])
            SingleDocConsentManager.register_document(
                doc_id=document.id,
                filename=document.filename,
                content=content,
                mime_type=document.file_type,
                text_content=all_text,
                intelligence=document.intelligence or DocumentIntelligence(
                    document_type="Document",
                    simple_summary="Processing complete.",
                    mode="LOCAL_MODE"
                )
            )

            # Auto-explain with Gemini ONLY if AI session is validly activated (never before activation)
            if mode == "ai" and SingleDocConsentManager.verify_ai_session(ai_session_id, ai_session_token):
                document.intelligence = cls.execute_external_ai_analysis(
                    document_id=document.id,
                    language=language,
                    ai_session_id=ai_session_id,
                    ai_session_token=ai_session_token,
                )

            document.status = "ready"
            return DocumentProcessResult(document=document)

        except Exception as e:
            logger.error(f"Error processing single document upload: {e}")
            document.status = "error"
            return DocumentProcessResult(
                document=document,
                message="Processing failed",
                error=str(e)
            )

    @classmethod
    def process_pdf(cls, content: bytes, document: Document, language: str = "English") -> Document:
        """Extract text and structure using PyMuPDF and generate deterministic local intelligence."""
        try:
            pdf_doc = fitz.open(stream=content, filetype="pdf")
            document.page_count = len(pdf_doc)
            all_text_parts = []

            for page_num in range(len(pdf_doc)):
                page = pdf_doc.load_page(page_num)
                text = page.get_text()

                if text.strip():
                    section = DocumentSection(
                        document_id=document.id,
                        page_number=page_num + 1,
                        content=text.strip()
                    )
                    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                    for p in paragraphs:
                        chunk = DocumentChunk(
                            document_id=document.id,
                            page_number=page_num + 1,
                            content=p
                        )
                        section.chunks.append(chunk)
                    document.sections.append(section)
                    all_text_parts.append(text.strip())

            pdf_doc.close()
            full_text = "\n\n".join(all_text_parts)

            # Generate deterministic local explanation (zero cloud requests)
            document.intelligence = LocalExplanationEngine.generate_intelligence(
                document_id=document.id,
                text_content=full_text,
                sections=document.sections,
                language=language
            )
            return document

        except Exception as e:
            logger.error(f"Failed in process_pdf: {e}")
            raise ValueError(f"Failed to process PDF: {str(e)}")

    @classmethod
    def process_text(cls, content: bytes, document: Document, language: str = "English") -> Document:
        """Extract plain text and generate local intelligence."""
        text = content.decode("utf-8", errors="replace")
        document.page_count = 1

        if text.strip():
            section = DocumentSection(
                document_id=document.id,
                page_number=1,
                content=text.strip()
            )
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in paragraphs:
                section.chunks.append(DocumentChunk(
                    document_id=document.id,
                    page_number=1,
                    content=p
                ))
            document.sections.append(section)

        document.intelligence = LocalExplanationEngine.generate_intelligence(
            document_id=document.id,
            text_content=text,
            sections=document.sections,
            language=language
        )
        return document

    @classmethod
    def process_image(cls, content: bytes, document: Document, language: str = "English") -> Document:
        """Process image file locally without cloud AI in Local Mode."""
        document.page_count = 1
        # In offline local mode, honestly report that OCR requires selectable text
        document.intelligence = DocumentIntelligence(
            document_type="Image Disclosure",
            simple_summary="Image file uploaded. Text and financial extraction requires a digital text layer in offline Local Mode.",
            document_story="Image file uploaded. In offline Local Mode, automatic extraction from raster images without embedded text is unsupported.",
            uncertainty_notes=["Image OCR is not available offline."],
            mode="LOCAL_MODE",
            fallback_triggered=False
        )
        return document

    @classmethod
    def execute_external_ai_analysis(
        cls,
        document_id: str,
        challenge_id: Optional[str] = None,
        consent_token: Optional[str] = None,
        language: str = "English",
        ai_session_id: Optional[str] = None,
        ai_session_token: Optional[str] = None,
    ) -> DocumentIntelligence:
        """
        Executes external AI explanation ONLY when authorized by a verified session AI token
        or verified single-use consent token. Preserves locally extracted facts on error,
        enforces timeout limits, and never leaks raw provider errors or API keys.
        """
        doc_info = SingleDocConsentManager.get_document(document_id)
        if not doc_info:
            raise HTTPException(status_code=404, detail="Document not found")

        local_intel = doc_info["intelligence"]
        payload_to_send = f"Explain Document Narrative: {doc_info['text'][:2500]}"

        # Verify backend authorization (single-use consent token OR bounded active AI session)
        if challenge_id and consent_token:
            is_valid = SingleDocConsentManager.verify_and_consume(
                challenge_id=challenge_id,
                doc_id=document_id,
                operation="EXPLAIN",
                consent_token=consent_token,
                payload_to_send=payload_to_send
            )
        elif ai_session_id and ai_session_token:
            is_valid = SingleDocConsentManager.verify_ai_session(ai_session_id, ai_session_token)
        else:
            is_valid = False

        if not is_valid:
            logger.warning("External AI transmission blocked: invalid, unconfirmed, or disabled authorization")
            raise HTTPException(status_code=403, detail="AI authorization invalid or expired. Local processing preserved.")

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY is not configured; falling back cleanly to local intelligence")
            fallback_intel = local_intel.model_copy()
            fallback_intel.mode = "LOCAL_MODE_FALLBACK"
            fallback_intel.fallback_triggered = True
            fallback_intel.fallback_reason = "MISSING_CREDENTIALS: External AI API key is not configured"
            fallback_intel.fallback_message = "Gemini AI is currently unavailable. Displaying local document analysis grounded in your document's text and tables."
            return fallback_intel

        model_id = os.environ.get("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
            )
            prompt = (
                f"You are Bharat Investor Copilot. Provide an educational narrative summary of this document in {language}. "
                f"Strict Rules: Educational only. NEVER provide buy/sell/hold recommendations, stock picks, price targets, "
                f"or guaranteed returns. NEVER invent financial numbers, company names, reporting periods, or page numbers. "
                f"Cite only exact facts present in the excerpt.\n\n"
                f"{payload_to_send}"
            )

            response = _call_gemini_with_503_retry(
                lambda: client.models.generate_content(
                    model=model_id,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DocumentIntelligence
                    )
                )
            )
            if not response or not getattr(response, "text", None):
                raise ValueError("Empty provider response")

            ai_intel = DocumentIntelligence.model_validate_json(response.text)
            ai_intel.mode = "AI_CONSENTED"
            ai_intel.fallback_triggered = False
            ai_intel.fallback_reason = None
            ai_intel.fallback_message = None

            # Preserve locally verified key facts, definitions, and page references
            if not ai_intel.key_facts and local_intel.key_facts:
                ai_intel.key_facts = local_intel.key_facts
            if not ai_intel.financial_terms and local_intel.financial_terms:
                ai_intel.financial_terms = local_intel.financial_terms
            if not ai_intel.source_references and local_intel.source_references:
                ai_intel.source_references = local_intel.source_references

            return ai_intel

        except Exception as e:
            fail_code = _classify_provider_error(str(e), model_id)
            logger.warning(f"External AI explanation fallback triggered ({fail_code})")

            fallback_intel = local_intel.model_copy()
            fallback_intel.mode = "LOCAL_MODE_FALLBACK"
            fallback_intel.fallback_triggered = True
            fallback_intel.fallback_reason = fail_code
            fallback_intel.fallback_message = (
                "Gemini AI is temporarily unavailable. "
                "Displaying local document analysis grounded in your document's text and tables."
            )
            return fallback_intel

    @classmethod
    def translate_intelligence(
        cls,
        intelligence: DocumentIntelligence,
        language: str,
        mode: str = "local",
        challenge_id: Optional[str] = None,
        consent_token: Optional[str] = None,
        doc_id: Optional[str] = None,
        ai_session_id: Optional[str] = None,
        ai_session_token: Optional[str] = None,
    ) -> DocumentIntelligence:
        """
        Translates structured intelligence.
        In Local Mode (or when unauthorized): translates deterministic dictionary fields locally with zero external calls.
        In External Mode: requires valid session AI token OR valid TRANSLATE consent token; falls back cleanly on error.
        """
        target_lang = "hi" if language == "Hindi" else "hinglish" if language == "Hinglish" else "en"

        has_session_auth = bool(ai_session_id and ai_session_token)
        has_single_auth = bool(consent_token)

        if mode == "local" or (not has_session_auth and not has_single_auth):
            translated = intelligence.model_copy(deep=True)
            translated.mode = "LOCAL_MODE"
            translated.fallback_triggered = False

            for ft in translated.financial_terms:
                gloss = LocalExplanationEngine.GLOSSARY.get(ft.term, {}).get(target_lang)
                if gloss:
                    ft.plain_language_definition = gloss["plain"]
                    ft.why_it_matters_general = gloss["why"]

            for kf in translated.key_facts:
                gloss = LocalExplanationEngine.GLOSSARY.get(kf.label, {}).get(target_lang)
                if gloss:
                    kf.explanation = gloss["plain"]

            return translated

        # Verify authorization before any external provider call
        if has_session_auth:
            is_valid = SingleDocConsentManager.verify_ai_session(ai_session_id, ai_session_token)
        elif challenge_id and doc_id and consent_token:
            payload = f"Translation Payload: {intelligence.simple_summary} | {intelligence.document_story or ''}"
            is_valid = SingleDocConsentManager.verify_and_consume(
                challenge_id=challenge_id,
                doc_id=doc_id,
                operation="TRANSLATE",
                consent_token=consent_token,
                payload_to_send=payload
            )
        else:
            is_valid = False

        if not is_valid:
            logger.warning("External translation authorization invalid or disabled; falling back to local translation")
            fallback = cls.translate_intelligence(intelligence, language, mode="local")
            fallback.mode = "LOCAL_MODE_FALLBACK" if mode == "ai" else "LOCAL_MODE"
            fallback.fallback_triggered = True
            fallback.fallback_message = "AI processing is not active. Local translation applied."
            return fallback

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            fallback = cls.translate_intelligence(intelligence, language, mode="local")
            fallback.mode = "LOCAL_MODE_FALLBACK"
            fallback.fallback_triggered = True
            fallback.fallback_reason = "MISSING_CREDENTIALS: External AI API key is not configured"
            fallback.fallback_message = "Gemini AI is unavailable. Local translation applied."
            return fallback

        model_id = os.environ.get("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
            )
            prompt = (
                f"Translate the text fields of this financial summary into {language}. "
                f"Keep numbers, company names, dates, page citations, and currency symbols exactly as they are. "
                f"Do not add investment advice.\n\n"
                f"{intelligence.model_dump_json()}"
            )
            response = _call_gemini_with_503_retry(
                lambda: client.models.generate_content(
                    model=model_id,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DocumentIntelligence
                    )
                )
            )
            if not response or not getattr(response, "text", None):
                raise ValueError("Empty provider response")

            res = DocumentIntelligence.model_validate_json(response.text)
            res.mode = "AI_CONSENTED"
            res.fallback_triggered = False
            res.fallback_reason = None
            res.fallback_message = None
            return res

        except Exception as e:
            fail_code = _classify_provider_error(str(e), model_id)
            logger.warning(f"External translation fallback triggered ({fail_code})")
            fallback = cls.translate_intelligence(intelligence, language, mode="local")
            fallback.mode = "LOCAL_MODE_FALLBACK"
            fallback.fallback_triggered = True
            fallback.fallback_reason = fail_code
            fallback.fallback_message = "Gemini translation unavailable. Local translation applied."
            return fallback
