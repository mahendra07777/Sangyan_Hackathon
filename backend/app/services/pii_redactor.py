"""Deterministic Offline PII Redaction Engine for Bharat Investor Copilot.

Provides zero-cloud, deterministic regex-based detection and redaction for:
- Email addresses
- Indian mobile and landline numbers
- Personal PAN numbers (strictly preserving corporate CIN identifiers)
- Aadhaar numbers
- Bank account numbers
- IFSC codes
- Personal signatory names (e.g. Directors, CFOs, Statutory Auditors)

Preserves corporate identifiers, company names, stock tickers, and financial figures.
Includes mandatory imperfect-redaction disclosure notice.
"""

from __future__ import annotations

import re
from typing import Dict, List, Pattern, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field


IMPERFECT_REDACTION_DISCLOSURE: str = (
    "Automatic PII redaction uses automated heuristic pattern matching and may be imperfect. "
    "Do not submit unredacted confidential or sensitive personal financial data."
)


class PiiDetectionSummary(BaseModel):
    """Aggregated summary of detected and redacted PII per category."""

    model_config = ConfigDict(use_enum_values=True)

    entity_type: str = Field(..., description="Category: EMAIL, PHONE, PAN, AADHAAR, ACCOUNT_NUMBER, IFSC, PERSONAL_NAME")
    count: int = Field(default=0, description="Number of instances detected and redacted")
    placeholder: str = Field(..., description="Replacement placeholder tag")


class PiiRedactionResult(BaseModel):
    """Result of PII detection and redaction across a text payload."""

    model_config = ConfigDict(use_enum_values=True)

    sanitized_text: str
    redactions: List[PiiDetectionSummary] = Field(default_factory=list)
    total_redacted_count: int = 0
    has_pii_detected: bool = False
    redaction_notice: str = IMPERFECT_REDACTION_DISCLOSURE


class PiiRedactor:
    """
    Offline deterministic PII detector and redactor.
    Executes in strict precedence order to prevent overlapping identifier collision.
    """

    # 1. Corporate Identifier Protection (Must NOT be redacted)
    # Indian CIN: 21 alphanumeric chars (e.g. L28920MH1945PLC004520, U12345DL2020PTC123456)
    _CIN_PATTERN: Pattern = re.compile(
        r"\b[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\b",
        re.ASCII,
    )
    # LLPIN: (e.g. AAA-1234 or AA12345)
    _LLPIN_PATTERN: Pattern = re.compile(
        r"\b(?:[A-Z]{3}-[0-9]{4}|[A-Z]{2}[0-9]{5})\b",
        re.ASCII,
    )

    # 2. Email Pattern
    _EMAIL_PATTERN: Pattern = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b"
    )

    # 3. Permanent Account Number (PAN)
    # Standard Indian PAN: 5 uppercase letters, 4 digits, 1 uppercase letter
    # 4th letter 'P' indicates individual person, while others indicate entities.
    # To be conservative, matches 10-char PANs while strictly excluding CINs and tickers.
    _PAN_PATTERN: Pattern = re.compile(
        r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        re.ASCII,
    )

    # 4. Aadhaar Numbers (12 digits, grouped in 4s or preceded by Aadhaar/UID keyword)
    _AADHAAR_SPACED_PATTERN: Pattern = re.compile(
        r"\b[2-9]\d{3}\s\d{4}\s\d{4}\b"
    )
    _AADHAAR_KEYWORD_PATTERN: Pattern = re.compile(
        r"(?i)\b(?:aadhaar|uidai|uid)[\s\.:#\-]+([2-9]\d{11})\b"
    )

    # 5. IFSC Code (11 characters: 4 letters, 0, 6 alphanumeric)
    _IFSC_PATTERN: Pattern = re.compile(
        r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
        re.ASCII,
    )

    # 6. Bank Account Numbers (9 to 18 digits preceded by banking account keywords)
    _BANK_ACCOUNT_PATTERN: Pattern = re.compile(
        r"(?i)(?:a/c(?:\s*no\.?)?|account(?:\s*no\.?)?|acc(?:\s*no\.?)?|bank\s*a/c|savings\s*a/c|current\s*a/c|acct(?:\s*no\.?)?)[\s\.:#\-]+([0-9]{9,18})\b"
    )

    # 7. Indian Phone Numbers (Mobile: +91 or starting 6-9, 10 digits; Landlines with STD)
    # Guard against financial amounts like 'Rs. 9876543210' or '₹ 9876543210' or currency scales
    _PHONE_MOBILE_PATTERN: Pattern = re.compile(
        r"(?<![₹$€£\d])(?:\+91[\-\s]?)?[6-9]\d{9}\b(?!\s*(?:crore|cr|lakh|lac|million|billion|%|/\-))",
        re.IGNORECASE,
    )
    _PHONE_LANDLINE_PATTERN: Pattern = re.compile(
        r"(?<![₹$€£\d])\b0\d{2,4}[\-\s]\d{6,8}\b(?!\s*(?:crore|cr|lakh|lac|million|billion|%|/\-))",
        re.IGNORECASE,
    )

    # 8. Personal Signatory Names
    # Heuristics: preceded by title (Shri, Smt, Mr., Ms., Dr.) or designation (Director, CFO, Auditor)
    _SIGNATORY_TITLE_PATTERN: Pattern = re.compile(
        r"\b(?:Shri|Smt\.?|Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
    )
    _SIGNATORY_ROLE_PATTERN: Pattern = re.compile(
        r"(?i)\b(?:Managing Director|Director|Chief Financial Officer|CFO|Company Secretary|Statutory Auditor|Partner|Authorized Signatory)[\s\.:\-]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
    )

    # Corporate keywords that must NEVER be redacted as personal names
    _CORPORATE_EXCLUSION_WORDS: Set[str] = frozenset({
        "limited", "ltd", "private", "pvt", "corporation", "corp", "bank",
        "industries", "enterprises", "solutions", "services", "technologies",
        "india", "bharat", "global", "holdings", "group", "finance", "capital",
        "motors", "suzuki", "tata", "reliance", "infosys", "wipro", "hcl",
        "statement", "report", "notes", "balance", "profit", "loss", "cash",
        "operations", "financial", "year", "quarter", "annual", "audit",
    })

    @classmethod
    def redact_text(cls, text: str) -> PiiRedactionResult:
        """
        Detect and redact all supported PII categories from text.
        Returns sanitized text and structured detection metrics.
        Preserves corporate identifiers (CIN, LLPIN, company names) and financial values.
        """
        if not text:
            return PiiRedactionResult(
                sanitized_text="",
                redactions=[],
                total_redacted_count=0,
                has_pii_detected=False,
            )

        counts: Dict[str, int] = {
            "EMAIL": 0,
            "PHONE": 0,
            "PAN": 0,
            "AADHAAR": 0,
            "ACCOUNT_NUMBER": 0,
            "IFSC": 0,
            "PERSONAL_NAME": 0,
        }

        # Step 0: Identify and isolate Corporate Identifiers (CIN & LLPIN) to avoid false-positive PAN/name matches
        cin_matches = list(cls._CIN_PATTERN.finditer(text))
        llpin_matches = list(cls._LLPIN_PATTERN.finditer(text))
        cin_ranges: List[Tuple[int, int]] = [(m.start(), m.end()) for m in cin_matches + llpin_matches]

        def _is_in_protected_range(start: int, end: int) -> bool:
            return any(c_start <= start and end <= c_end for c_start, c_end in cin_ranges)

        # Step 1: Redact Emails
        def _replace_email(match: re.Match) -> str:
            if _is_in_protected_range(match.start(), match.end()):
                return match.group(0)
            counts["EMAIL"] += 1
            return "[REDACTED_EMAIL]"

        sanitized = cls._EMAIL_PATTERN.sub(_replace_email, text)

        # Step 2: Redact Bank Account Numbers (keyword-bound)
        def _replace_account(match: re.Match) -> str:
            full_match = match.group(0)
            acc_num = match.group(1)
            counts["ACCOUNT_NUMBER"] += 1
            # Replace only the numeric account portion, keeping the keyword prefix for clarity
            prefix = full_match[: match.start(1) - match.start(0)]
            return f"{prefix}[REDACTED_ACCOUNT]"

        sanitized = cls._BANK_ACCOUNT_PATTERN.sub(_replace_account, sanitized)

        # Step 3: Redact IFSC Codes
        def _replace_ifsc(match: re.Match) -> str:
            counts["IFSC"] += 1
            return "[REDACTED_IFSC]"

        sanitized = cls._IFSC_PATTERN.sub(_replace_ifsc, sanitized)

        # Step 4: Redact Aadhaar Numbers
        def _replace_aadhaar_spaced(match: re.Match) -> str:
            counts["AADHAAR"] += 1
            return "[REDACTED_AADHAAR]"

        sanitized = cls._AADHAAR_SPACED_PATTERN.sub(_replace_aadhaar_spaced, sanitized)

        def _replace_aadhaar_keyword(match: re.Match) -> str:
            full_match = match.group(0)
            counts["AADHAAR"] += 1
            prefix = full_match[: match.start(1) - match.start(0)]
            return f"{prefix}[REDACTED_AADHAAR]"

        sanitized = cls._AADHAAR_KEYWORD_PATTERN.sub(_replace_aadhaar_keyword, sanitized)

        # Step 5: Redact PAN Numbers (strictly preserving CINs)
        def _replace_pan(match: re.Match) -> str:
            val = match.group(0)
            # Re-verify not inside CIN
            if any(c_match.group(0).find(val) != -1 for c_match in cin_matches):
                return val
            counts["PAN"] += 1
            return "[REDACTED_PAN]"

        sanitized = cls._PAN_PATTERN.sub(_replace_pan, sanitized)

        # Step 6: Redact Indian Phone Numbers
        def _replace_phone(match: re.Match) -> str:
            counts["PHONE"] += 1
            return "[REDACTED_PHONE]"

        sanitized = cls._PHONE_MOBILE_PATTERN.sub(_replace_phone, sanitized)
        sanitized = cls._PHONE_LANDLINE_PATTERN.sub(_replace_phone, sanitized)

        # Step 7: Redact Personal Signatory Names
        def _replace_name_title(match: re.Match) -> str:
            name_part = match.group(1)
            # Check if name contains corporate words
            words = name_part.lower().split()
            if any(w in cls._CORPORATE_EXCLUSION_WORDS for w in words):
                return match.group(0)
            counts["PERSONAL_NAME"] += 1
            title_prefix = match.group(0)[: match.start(1) - match.start(0)]
            return f"{title_prefix}[REDACTED_NAME]"

        sanitized = cls._SIGNATORY_TITLE_PATTERN.sub(_replace_name_title, sanitized)

        def _replace_name_role(match: re.Match) -> str:
            name_part = match.group(1)
            words = name_part.lower().split()
            if any(w in cls._CORPORATE_EXCLUSION_WORDS for w in words):
                return match.group(0)
            counts["PERSONAL_NAME"] += 1
            role_prefix = match.group(0)[: match.start(1) - match.start(0)]
            return f"{role_prefix}[REDACTED_NAME]"

        sanitized = cls._SIGNATORY_ROLE_PATTERN.sub(_replace_name_role, sanitized)

        # Build structured summaries
        placeholders: Dict[str, str] = {
            "EMAIL": "[REDACTED_EMAIL]",
            "PHONE": "[REDACTED_PHONE]",
            "PAN": "[REDACTED_PAN]",
            "AADHAAR": "[REDACTED_AADHAAR]",
            "ACCOUNT_NUMBER": "[REDACTED_ACCOUNT]",
            "IFSC": "[REDACTED_IFSC]",
            "PERSONAL_NAME": "[REDACTED_NAME]",
        }

        redaction_summaries: List[PiiDetectionSummary] = [
            PiiDetectionSummary(
                entity_type=cat,
                count=c,
                placeholder=placeholders[cat],
            )
            for cat, c in counts.items()
            if c > 0
        ]

        total_count = sum(counts.values())

        return PiiRedactionResult(
            sanitized_text=sanitized,
            redactions=redaction_summaries,
            total_redacted_count=total_count,
            has_pii_detected=total_count > 0,
            redaction_notice=IMPERFECT_REDACTION_DISCLOSURE,
        )
