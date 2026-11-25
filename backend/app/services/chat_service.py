import os
import re
import logging
from typing import Optional
from ..models.chat import ChatRequest, ChatResponse
from .document_processor import (
    SingleDocConsentManager,
    LocalExplanationEngine,
    _classify_provider_error,
    _call_gemini_with_503_retry,
    GEMINI_TIMEOUT_MS,
)

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL_ID", "gemini-3.5-flash-lite")


class LocalChatEngine:
    """
    Deterministic offline Q&A engine for single documents.
    Operates with zero external network requests.
    Supports English, Hindi, and Hinglish.
    """

    ADVICE_PATTERNS = re.compile(
        r"\b(?:should\s+i\s+(?:buy|sell|hold|invest)|is\s+(?:this|it)\s+a\s+good\s+(?:buy|stock|investment)|"
        r"target\s+price|price\s+target|which\s+stock|predict|future\s+returns?|multibagger|guaranteed)\b",
        re.IGNORECASE
    )

    CONCEPT_KEYWORDS = {
        "ebitda": "EBITDA",
        "revenue": "Revenue",
        "turnover": "Revenue",
        "profit": "Net Profit",
        "pat": "Net Profit",
        "debt": "Total Debt",
        "borrowing": "Total Debt",
        "cash flow": "Operating Cash Flow",
        "assets": "Total Assets",
    }

    @classmethod
    def answer(cls, request: ChatRequest) -> ChatResponse:
        msg = request.message.strip()
        lang_key = "hi" if request.language == "Hindi" else "hinglish" if request.language == "Hinglish" else "en"

        # 1. Check for Prohibited Investment Advice
        if cls.ADVICE_PATTERNS.search(msg):
            refusal_msg = {
                "en": "Bharat Investor Copilot is strictly an educational tool. We help you understand the document's reported figures, but we do not provide buy, sell, or hold recommendations, stock tips, or price targets.",
                "hi": "भारत इन्वेस्टर कोपायलट विशुद्ध रूप से एक शैक्षणिक उपकरण है। हम आपको दस्तावेज़ में रिपोर्ट किए गए आंकड़ों को समझने में मदद करते हैं, लेकिन हम खरीदने, बेचने या रखने की सिफारिशें या मूल्य लक्ष्य नहीं देते हैं।",
                "hinglish": "Bharat Investor Copilot purely ek educational tool hai. Hum document ke reported figures samajhne mein madad karte hain, lekin buy, sell ya hold recommendations ya target prices nahi dete."
            }[lang_key]

            return ChatResponse(
                answer=refusal_msg,
                intent_classified="PROHIBITED_INVESTMENT_ADVICE",
                answer_type="REFUSAL",
                safety_state="SAFE",
                mode="LOCAL_MODE"
            )

        # 2. Check for Document Facts Q&A (prioritize if context contains numerical disclosure for the asked metric)
        context = request.document_context or ""
        msg_lower = msg.lower()
        if context:
            for kw, term_name in cls.CONCEPT_KEYWORDS.items():
                if kw in msg_lower and not any(w in msg_lower for w in ["meaning of", "define", "concept of", "ka matlab kya hai"]):
                    lines = context.split("\n")
                    matching_lines = [l.strip() for l in lines if kw in l.lower() and re.search(r"\d+", l)]
                    if matching_lines:
                        excerpt = matching_lines[0]
                        answer_text = {
                            "en": f"Based on the document context, the reported disclosure for **{term_name}** is:\n> {excerpt}",
                            "hi": f"दस्तावेज़ के संदर्भ के अनुसार, **{term_name}** का रिपोर्ट किया गया विवरण है:\n> {excerpt}",
                            "hinglish": f"Document context ke mutabiq, **{term_name}** ka reported figure hai:\n> {excerpt}"
                        }[lang_key]

                        return ChatResponse(
                            answer=answer_text,
                            intent_classified="DOCUMENT_QA",
                            answer_type="DOCUMENT_FACT",
                            evidence_snippet=excerpt[:200],
                            source_reference="Document Text",
                            safety_state="SAFE",
                            mode="LOCAL_MODE"
                        )

        # 3. Check for Financial Education Concepts
        for kw, term_name in cls.CONCEPT_KEYWORDS.items():
            if kw in msg_lower and any(w in msg_lower for w in ["what is", "kya hai", "explain", "meaning", "define", "ka matlab"]):
                gloss = LocalExplanationEngine.GLOSSARY.get(term_name, {}).get(lang_key)
                if gloss:
                    answer = f"**{term_name}**: {gloss['plain']}\n\n*Why it matters:* {gloss['why']}"
                    return ChatResponse(
                        answer=answer,
                        intent_classified="FINANCIAL_EDUCATION",
                        answer_type="EDUCATIONAL_EXPLANATION",
                        source_reference="Educational Glossary",
                        safety_state="SAFE",
                        mode="LOCAL_MODE"
                    )


        # 4. General / Unsupported in Local Analysis
        general_answer = {
            "en": "Local analysis answers questions using the document's extracted tables, key facts, and financial definitions. Ask about specific reported figures or financial terms from the filing.",
            "hi": "स्थानीय विश्लेषण दस्तावेज़ की निकाली गई तालिकाओं, मुख्य तथ्यों और वित्तीय परिभाषाओं के आधार पर उत्तर देता है। कृपया फ़ाइलिंग से संबंधित विशिष्ट आंकड़ों या वित्तीय शब्दों के बारे में पूछें।",
            "hinglish": "Local analysis document ke extracted tables, key facts aur financial definitions ke basis par jawab deta hai. Filing ke specific figures ya financial terms ke baare mein poochhein."
        }[lang_key]

        return ChatResponse(
            answer=general_answer,
            intent_classified="UNSUPPORTED_OR_AMBIGUOUS",
            answer_type="UNCERTAIN",
            safety_state="SAFE",
            mode="LOCAL_MODE"
        )


class ChatService:
    @classmethod
    def answer_question(cls, request: ChatRequest) -> ChatResponse:
        # Strict Local Mode default: zero outbound network requests
        if request.mode == "local":
            return LocalChatEngine.answer(request)

        # External AI Chat requested: enforce backend session AI token OR operation-specific consent token
        has_session_auth = bool(request.ai_session_id and request.ai_session_token)
        has_single_auth = bool(request.consent_token)

        if has_session_auth:
            is_authorized = SingleDocConsentManager.verify_ai_session(
                request.ai_session_id,
                request.ai_session_token,
            )
        elif has_single_auth:
            doc_id = request.document_id or ""
            challenge_id = request.challenge_id or ""
            token = request.consent_token or ""
            payload_to_verify = f"Chat Document Context: {(request.document_context or '')[:2500]}"
            is_authorized = SingleDocConsentManager.verify_and_consume(
                challenge_id=challenge_id,
                doc_id=doc_id,
                operation="CHAT",
                consent_token=token,
                payload_to_send=payload_to_verify
            )
        else:
            is_authorized = False

        if not is_authorized:
            logger.warning("External AI chat rejected: invalid, disabled, or unconfirmed authorization. Falling back locally.")
            fallback = LocalChatEngine.answer(request)
            fallback.mode = "LOCAL_MODE"
            fallback.fallback_triggered = True
            fallback.fallback_message = "External AI authorization is not active. Answer provided by local analysis."
            return fallback

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY missing; falling back cleanly to local chat")
            fallback = LocalChatEngine.answer(request)
            fallback.mode = "LOCAL_MODE_FALLBACK"
            fallback.fallback_triggered = True
            fallback.fallback_message = "Gemini AI is unavailable. Answer provided by local analysis."
            return fallback

        model_id = os.environ.get("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
            )
            system_prompt = (
                f"You are an Educational Financial Understanding Assistant for Bharat Investor Copilot. "
                f"Strict Rules: NEVER provide investment recommendations, buy/sell/hold advice, stock picks, or price targets. "
                f"NEVER invent financial figures, reporting periods, or page references. "
                f"Answer the user's question using ONLY the provided context in {request.language}.\n\n"
                f"Context: {request.document_context[:2500]}"
            )

            contents = [system_prompt]
            for m in request.history[-4:]:
                contents.append(f"{m.role.capitalize()}: {m.content}")
            contents.append(f"User: {request.message}")

            response = _call_gemini_with_503_retry(
                lambda: client.models.generate_content(
                    model=model_id,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ChatResponse
                    )
                )
            )
            if not response or not getattr(response, "text", None):
                raise ValueError("Empty provider response")

            ai_resp = ChatResponse.model_validate_json(response.text)
            ai_resp.mode = "AI_CONSENTED"
            ai_resp.fallback_triggered = False
            ai_resp.fallback_message = None
            return ai_resp

        except Exception as e:
            fail_code = _classify_provider_error(str(e), model_id)
            logger.warning(f"External chat fallback triggered ({fail_code})")
            fallback = LocalChatEngine.answer(request)
            fallback.mode = "LOCAL_MODE_FALLBACK"
            fallback.fallback_triggered = True
            fallback.fallback_message = "Gemini AI is temporarily unavailable. Answer provided by local analysis."
            return fallback
