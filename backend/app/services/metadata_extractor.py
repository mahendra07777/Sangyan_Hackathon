"""Deterministic, explainable metadata extraction engine for Bharat Investor Copilot Compare Documents.
Extracts company identity, document type, financial periods, currency, accounting standard, audit status,
and reporting scope from Slice 2 structured extractions without cloud AI or guessing.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.comparison import (
    AuditStatus,
    ComparisonDocument,
    DocumentExtractionResult,
    DocumentMetadata,
    DocumentType,
    EvidenceReference,
    ExtractedTable,
    ExtractedTextBlock,
    ReportingPeriodType,
    ReportingScope,
    SupportedFileFormat,
)

logger = logging.getLogger(__name__)

# Regex Patterns for Indian Corporate Filings

_CORP_SUFFIX_PATTERN = (
    r"(?:(?:(?:\([A-Za-z\s]+\)|[A-Za-z]+)\s+)?(?:Private\s+Limited|Pvt\.?\s*Ltd\.?|Public\s+Limited|Limited|Ltd\.?)|"
    r"Private\s+Limited|Pvt\.?\s*Ltd\.?|Public\s+Limited|Limited|Ltd\.?|LLP|L\.L\.P\.|"
    r"Limited\s+Liability\s+Partnership|Corporation|Corp\.?|Industries|Enterprises|Bank|"
    r"Company\s+Limited|Co\.?\s*Ltd\.?)"
)

_CIN_PATTERN = re.compile(
    r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b",
    re.IGNORECASE,
)

_COMPANY_PATTERNS = [
    # Explicit company name declarations
    re.compile(
        r"(?:name\s+of\s+(?:the\s+)?company|company\s+name)\s*[:\-]?\s*([A-Z0-9][A-Za-z0-9&.,'()\s]{2,60}?(?:" + _CORP_SUFFIX_PATTERN + r"|Bank))",
        re.IGNORECASE,
    ),
    # Company ending in terminal corporate designator (e.g. HDFC Bank Limited, ICICI Securities Limited, TATA MOTORS LIMITED)
    re.compile(
        r"\b([A-Z0-9][A-Za-z0-9&.,'()\s]{2,60}?\s+" + _CORP_SUFFIX_PATTERN + r")\b",
        re.IGNORECASE,
    ),
    # Standalone Bank fallback (e.g. Canara Bank, State Bank of India)
    re.compile(
        r"\b([A-Z0-9][A-Za-z0-9&.,'()\s]{2,50}?\s+Bank(?:\s+of\s+[A-Za-z]+)?)\b",
        re.IGNORECASE,
    ),
]

_COMMON_ABBREVIATIONS: Dict[str, str] = {
    "TATA MOTORS": "TML",
    "MARUTI SUZUKI": "MSIL",
    "TATA CONSULTANCY SERVICES": "TCS",
    "INFOSYS": "INFY",
    "RELIANCE INDUSTRIES": "RIL",
    "HINDUSTAN UNILEVER": "HUL",
    "STATE BANK OF INDIA": "SBI",
    "HOUSING DEVELOPMENT FINANCE": "HDFC",
    "ICICI BANK": "ICICI",
}

_FY_CANONICAL_PATTERN = re.compile(
    r"(?:FY|Financial\s+Year|F\.Y\.)\s*[:\-]?\s*(20\d{2})[-–/](20\d{2}|\d{2})",
    re.IGNORECASE,
)

_FY_SINGLE_YEAR_PATTERN = re.compile(
    r"(?:FY|Financial\s+Year|F\.Y\.)\s*[:\-]?\s*['’]?(2\d{3}|[0-9]{2})\b",
    re.IGNORECASE,
)

_PERIOD_ENDED_MONTH_WORD_PATTERN = re.compile(
    r"(?:quarter|three\s+months?|half\s+year|six\s+months?|nine\s+months?|year|period)\s+ended\s+(?:on\s+)?(?:([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})|(\d{1,2})(?:st|nd|rd|th)?[\s\.\-\/]+([A-Za-z]+)[\s,\.\-\/]+(20\d{2}))",
    re.IGNORECASE,
)

_PERIOD_ENDED_NUMERIC_PATTERN = re.compile(
    r"(?:quarter|three\s+months?|half\s+year|six\s+months?|nine\s+months?|year|period)\s+ended\s+(?:on\s+)?(\d{1,2})[\.\-\/](\d{1,2})[\.\-\/](20\d{2})",
    re.IGNORECASE,
)

_MONTH_NAMES_TO_QUARTERS = {
    "june": "Q1",
    "september": "Q2",
    "december": "Q3",
    "march": "Q4",
}

_NUMERIC_MONTH_TO_QUARTERS = {
    6: "Q1",
    9: "Q2",
    12: "Q3",
    3: "Q4",
}

_MONTH_TO_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_INDUSTRY_PATTERN = re.compile(
    r"\b(?:industry|sector|primary\s+(?:business\s+)?segment|primary\s+business|line\s+of\s+business|operating\s+segment|principal\s+activities?|principal\s+activity)\s*(?::|\s+-\s+)\s*([A-Za-z0-9\s,\/&\-]{3,50})(?:[\r\n\.,;]|$)",
    re.IGNORECASE,
)

_GENERIC_INDUSTRY_TERMS = {
    "none", "n/a", "na", "not applicable", "single segment", "one segment",
    "total", "various", "others", "refer note", "as per note", "unallocated", "all segments",
}

_INVALID_INDUSTRY_WORDS = {
    "leading", "profitability", "margins", "slowdown", "growth", "revenue", "loss", "ebitda",
    "standard", "wide", "level", "average", "peers", "first", "benchmark", "specific", "resilience",
}


def _clean_company_name(name: str) -> str:
    """Strip scope noise, assurance markers, and trailing artifacts without damaging legitimate company names."""
    if not name or name == "Unknown":
        return name
    cleaned = re.sub(
        r"\s*[\-\(]\s*(?:Standalone|Consolidated|Audited|Unaudited|Un-audited|Provisional|Results)[^\)]*\)?$",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r"[\s\-,:]+$", "", cleaned).strip()
    if cleaned.endswith(".") and not cleaned.lower().endswith(("ltd.", "pvt.", "co.")):
        cleaned = cleaned[:-1].strip()
    return cleaned


def _make_evidence(
    doc_id: str,
    doc_name: str,
    field_name: str,
    text: str,
    page_number: Optional[int] = None,
    bounding_box: Optional[List[float]] = None,
    structural_ref: Optional[str] = None,
    sheet_name: Optional[str] = None,
    cell_range: Optional[str] = None,
) -> EvidenceReference:
    """Helper to construct an EvidenceReference for metadata provenance."""
    snippet = text.strip()
    if len(snippet) > 200:
        snippet = snippet[:197] + "..."
    return EvidenceReference(
        evidence_id=f"{doc_id}_meta_{field_name}",
        doc_id=doc_id,
        document_name=doc_name,
        page_number=page_number,
        bounding_box=bounding_box,
        sheet_name=sheet_name,
        cell_range=cell_range,
        structural_ref=structural_ref,
        verbatim_snippet=snippet,
        table_context=f"Metadata field: {field_name}",
    )


class MetadataExtractor:
    """Deterministic, explainable extractor that parses institutional metadata from structured extraction output."""

    @classmethod
    def extract_metadata(
        cls,
        doc: ComparisonDocument,
        extraction: DocumentExtractionResult,
    ) -> DocumentMetadata:
        """Extract all 9 metadata categories from local extraction results without guessing or hallucinating."""
        doc_id = doc.doc_id
        doc_name = doc.original_filename
        notes: List[str] = []
        evidence_sources: Dict[str, EvidenceReference] = {}
        conflicting_candidates: Dict[str, List[str]] = {}

        # Handle scanned or visual extraction limitations
        if extraction.extraction_status == "OCR_UNAVAILABLE_LOCAL_MODE":
            notes.append("Scanned PDF detected. Optical Character Recognition (OCR) is unavailable in Local Mode.")
            return DocumentMetadata(
                doc_id=doc_id,
                company_name="Unknown",
                document_type=DocumentType.UNKNOWN.value,
                financial_year="Unknown",
                reporting_period=ReportingPeriodType.UNKNOWN.value,
                currency="INR",
                accounting_standard="Unknown",
                reporting_scope=ReportingScope.UNKNOWN,
                audit_status=AuditStatus.UNKNOWN,
                confidence_category="UNKNOWN",
                extraction_notes=notes,
            )

        if extraction.extraction_status == "VISION_EXTRACTION_REQUIRED":
            notes.append("Image document. Visual tabular extraction requires Gemini Vision (Slice 5) under user consent.")
            return DocumentMetadata(
                doc_id=doc_id,
                company_name="Unknown",
                document_type=DocumentType.UNKNOWN.value,
                financial_year="Unknown",
                reporting_period=ReportingPeriodType.UNKNOWN.value,
                currency="INR",
                accounting_standard="Unknown",
                reporting_scope=ReportingScope.UNKNOWN,
                audit_status=AuditStatus.UNKNOWN,
                confidence_category="UNKNOWN",
                extraction_notes=notes,
            )

        # Collect text corpus with spatial/structural references
        blocks = extraction.text_blocks
        tables = extraction.tables

        # 1. Company Identification
        company_name, company_cin, company_alts, comp_ev = cls._detect_company(doc_name, blocks, tables, doc_id)
        if comp_ev:
            evidence_sources["company_name"] = comp_ev

        # 1b. Industry Identification (only when explicitly evidenced in text; never assumed)
        industry, ind_ev = cls._detect_industry(blocks, tables, doc_id, doc_name)
        if ind_ev:
            evidence_sources["industry"] = ind_ev

        # 2. Document Type
        doc_type, doc_type_ev = cls._detect_document_type(doc_name, blocks, tables, doc_id)
        if doc_type_ev:
            evidence_sources["document_type"] = doc_type_ev

        # 3. Financial Year
        fy_str, fy_start, fy_end, is_inferred_fy, fy_ev = cls._detect_financial_year(doc_name, blocks, tables, doc_id)
        if fy_ev:
            evidence_sources["financial_year"] = fy_ev

        # 4 & 5. Reporting Period & Quarter
        period, period_disp, quarter, p_start, p_end, period_ev = cls._detect_period_and_quarter(
            doc_type, blocks, tables, doc_id, doc_name
        )
        if period_ev:
            evidence_sources["reporting_period"] = period_ev

        # 6. Currency & Reporting Scale
        currency, curr_symbol, scale, curr_ev = cls._detect_currency_and_scale(blocks, tables, doc_id, doc_name)
        if curr_ev:
            evidence_sources["currency"] = curr_ev

        # 7. Accounting Standard
        acct_std, acct_disclosure, acct_ev = cls._detect_accounting_standard(blocks, doc_id, doc_name)
        if acct_ev:
            evidence_sources["accounting_standard"] = acct_ev

        # 8. Audit Status
        audit_stat, audit_ev = cls._detect_audit_status(blocks, tables, doc_id, doc_name)
        if audit_ev:
            evidence_sources["audit_status"] = audit_ev

        # 9. Reporting Scope
        scope, conflicting_scopes, scope_ev = cls._detect_reporting_scope(blocks, tables, doc_id, doc_name)
        if scope_ev:
            evidence_sources["reporting_scope"] = scope_ev
        if conflicting_scopes:
            conflicting_candidates["reporting_scope"] = conflicting_scopes

        # Confidence category calculation
        known_count = sum([
            company_name != "Unknown",
            doc_type != DocumentType.UNKNOWN.value,
            fy_str != "Unknown",
            period != ReportingPeriodType.UNKNOWN.value,
            currency != "Unknown",
            audit_stat != AuditStatus.UNKNOWN,
        ])
        if known_count >= 5 or (company_cin and company_name != "Unknown"):
            confidence = "HIGH"
        elif known_count >= 3:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        metadata = DocumentMetadata(
            doc_id=doc_id,
            company_name=company_name,
            company_identifier=company_cin,
            alternative_names=company_alts,
            industry=industry,
            document_type=doc_type,
            financial_year=fy_str,
            fy_start=fy_start,
            fy_end=fy_end,
            is_inferred_year=is_inferred_fy,
            reporting_period=period,
            reporting_period_display=period_disp,
            quarter=quarter,
            period_start_date=p_start,
            period_end_date=p_end,
            currency=currency,
            currency_symbol=curr_symbol,
            reporting_scale=scale,
            accounting_standard=acct_std,
            accounting_standard_disclosure=acct_disclosure,
            reporting_scope=scope,
            audit_status=audit_stat,
            is_user_overridden=False,
            confidence_category=confidence,
            evidence_sources=evidence_sources,
            conflicting_candidates=conflicting_candidates,
            original_detected_values={
                "company_name": company_name,
                "industry": industry,
                "document_type": doc_type,
                "financial_year": fy_str,
                "reporting_period": period,
                "quarter": quarter,
                "currency": currency,
                "accounting_standard": acct_std,
                "reporting_scope": scope.value if isinstance(scope, ReportingScope) else str(scope),
                "audit_status": audit_stat.value if isinstance(audit_stat, AuditStatus) else str(audit_stat),
            },
            extraction_notes=notes,
        )
        return metadata

    # -----------------------------------------------------------------------
    # Detection Sub-routines
    # -----------------------------------------------------------------------

    @classmethod
    def _detect_company(
        cls,
        filename: str,
        blocks: List[ExtractedTextBlock],
        tables: List[ExtractedTable],
        doc_id: str,
    ) -> Tuple[str, Optional[str], List[str], Optional[EvidenceReference]]:
        """Identify company name, explicit CIN, and abbreviations with corporate suffix and CIN proximity."""
        detected_name = "Unknown"
        detected_cin = None
        evidence = None
        alts: List[str] = []

        # 1. Search for explicit CIN across blocks
        cin_block_idx = -1
        for idx, b in enumerate(blocks):
            cin_match = _CIN_PATTERN.search(b.text)
            if cin_match:
                detected_cin = cin_match.group(1).upper()
                cin_block_idx = idx
                break

        # 2. If CIN found, check lines in that block and immediately preceding block (CIN proximity)
        if detected_cin and cin_block_idx >= 0:
            proximity_blocks = []
            if cin_block_idx > 0:
                proximity_blocks.append(blocks[cin_block_idx - 1])
            proximity_blocks.append(blocks[cin_block_idx])

            for pb in proximity_blocks:
                for line in pb.text.split("\n"):
                    line_clean = line.strip()
                    for pat in _COMPANY_PATTERNS:
                        m = pat.search(line_clean)
                        if m:
                            cand = _clean_company_name(m.group(1).strip())
                            if len(cand) >= 4 and not cand.lower().startswith(("independent", "statutory", "auditor", "report", "board of", "notice of", "statement of")):
                                detected_name = cand
                                evidence = _make_evidence(
                                    doc_id, filename, "company_name", cand,
                                    page_number=pb.page_number,
                                    bounding_box=pb.bounding_box,
                                    structural_ref=pb.structural_ref,
                                )
                                break
                    if detected_name != "Unknown":
                        break
                if detected_name != "Unknown":
                    break

        # 3. Search first 8 text blocks (cover page / header) for company names
        if detected_name == "Unknown":
            early_blocks = blocks[:8] if blocks else []
            for b in early_blocks:
                for pat in _COMPANY_PATTERNS:
                    m = pat.search(b.text)
                    if m:
                        cand = _clean_company_name(m.group(1).strip())
                        if len(cand) >= 4 and not cand.lower().startswith(("independent", "statutory", "auditor", "report", "board of", "notice of", "statement of")):
                            detected_name = cand
                            evidence = _make_evidence(
                                doc_id, filename, "company_name", cand,
                                page_number=b.page_number,
                                bounding_box=b.bounding_box,
                                structural_ref=b.structural_ref,
                            )
                            break
                if detected_name != "Unknown":
                    break

        # 4. Fallback: inspect table headers or sheet names
        if detected_name == "Unknown":
            for t in tables[:3]:
                if t.title:
                    for pat in _COMPANY_PATTERNS:
                        m = pat.search(t.title)
                        if m:
                            cand = _clean_company_name(m.group(1).strip())
                            if len(cand) >= 4 and not cand.lower().startswith(("independent", "statutory", "auditor", "report")):
                                detected_name = cand
                                evidence = _make_evidence(doc_id, filename, "company_name", cand, page_number=t.page_number)
                                break
                if detected_name != "Unknown":
                    break

        # 5. Fallback: inspect filename (e.g. TataMotors_Q3.pdf)
        if detected_name == "Unknown":
            clean_stem = filename.split(".")[0].replace("_", " ").replace("-", " ")
            for pat in _COMPANY_PATTERNS:
                m = pat.search(clean_stem)
                if m:
                    cand = _clean_company_name(m.group(1).strip())
                    if len(cand) >= 4:
                        detected_name = cand
                        evidence = _make_evidence(doc_id, filename, "company_name", cand)
                        break

        # Build abbreviations
        if detected_name != "Unknown":
            upper_name = detected_name.upper()
            for key, abbr in _COMMON_ABBREVIATIONS.items():
                if key in upper_name:
                    alts.append(abbr)

        return detected_name, detected_cin, alts, evidence

    @classmethod
    def _detect_document_type(
        cls,
        filename: str,
        blocks: List[ExtractedTextBlock],
        tables: List[ExtractedTable],
        doc_id: str,
    ) -> Tuple[str, Optional[EvidenceReference]]:
        """Identify document type with strict precedence hierarchy."""
        search_texts: List[Tuple[str, Optional[int], Optional[str]]] = []
        for b in blocks[:15]:
            search_texts.append((b.text, b.page_number, b.structural_ref))
        for t in tables[:3]:
            if t.headers:
                search_texts.append((" ".join(t.headers), t.page_number, t.structural_ref))

        search_texts.append((filename.replace("_", " "), None, "Filename"))

        # Precedence 1: DRHP, RHP, IPO Prospectus
        for text, page, s_ref in search_texts:
            t_lower = text.lower()
            if "draft red herring prospectus" in t_lower or "drhp" in t_lower:
                return (
                    DocumentType.DRAFT_RED_HERRING_PROSPECTUS.value,
                    _make_evidence(doc_id, filename, "document_type", "Draft Red Herring Prospectus", page_number=page, structural_ref=s_ref),
                )
            if "red herring prospectus" in t_lower or "rhp" in t_lower:
                return (
                    DocumentType.RED_HERRING_PROSPECTUS.value,
                    _make_evidence(doc_id, filename, "document_type", "Red Herring Prospectus", page_number=page, structural_ref=s_ref),
                )
            if "ipo prospectus" in t_lower or ("prospectus" in t_lower and "initial public offer" in t_lower):
                return (
                    DocumentType.IPO_PROSPECTUS.value,
                    _make_evidence(doc_id, filename, "document_type", "IPO Prospectus", page_number=page, structural_ref=s_ref),
                )

        # Primary Title Check (Block 0/1 or Filename)
        early_title_text = " ".join([b.text for b in blocks[:2]]).lower()
        clean_fn = filename.lower().replace("_", "").replace(" ", "").replace("-", "")

        is_cover_annual = (
            "annual report" in early_title_text
            or "integrated annual report" in early_title_text
            or "annualreport" in clean_fn
        )
        is_cover_quarterly = any(
            p in early_title_text
            for p in ["quarter ended", "quarterly", "three months ended", "limited review report", "unaudited financial results"]
        )

        # If cover explicitly declares Annual Report, do not downgrade due to comparative tables
        if is_cover_annual and not is_cover_quarterly:
            for text, page, s_ref in search_texts:
                t_lower = text.lower()
                if "annual report" in t_lower or "integrated annual report" in t_lower or "audited annual accounts" in t_lower:
                    return (
                        DocumentType.ANNUAL_REPORT.value,
                        _make_evidence(doc_id, filename, "document_type", "Annual Report", page_number=page, structural_ref=s_ref),
                    )

        # If cover explicitly declares Quarterly / Interim, prioritize Quarterly over subordinate Annual Report mentions
        if is_cover_quarterly:
            for text, page, s_ref in search_texts:
                t_lower = text.lower()
                if (
                    "quarterly" in t_lower
                    or "quarter ended" in t_lower
                    or "three months ended" in t_lower
                    or "unaudited financial results" in t_lower
                    or "limited review report" in t_lower
                ):
                    return (
                        DocumentType.QUARTERLY_RESULTS.value,
                        _make_evidence(doc_id, filename, "document_type", "Quarterly Financial Results", page_number=page, structural_ref=s_ref),
                    )

        # Precedence 2: Annual Report (General search: reject incidental mentions in notes)
        for text, page, s_ref in search_texts:
            t_lower = text.lower()
            if "annual report" in t_lower or "integrated annual report" in t_lower or "audited annual accounts" in t_lower:
                if re.search(r"(?:latest|previous|prior|refer|in\s+the|from\s+the|with\s+the)\s+(?:integrated\s+)?annual\s+report", t_lower):
                    continue
                return (
                    DocumentType.ANNUAL_REPORT.value,
                    _make_evidence(doc_id, filename, "document_type", "Annual Report", page_number=page, structural_ref=s_ref),
                )

        # Precedence 3: Quarterly Financial Results / Limited Review
        for text, page, s_ref in search_texts:
            t_lower = text.lower()
            if (
                "quarterly" in t_lower
                or "quarter ended" in t_lower
                or "three months ended" in t_lower
                or "unaudited financial results" in t_lower
                or "limited review report" in t_lower
            ):
                return (
                    DocumentType.QUARTERLY_RESULTS.value,
                    _make_evidence(doc_id, filename, "document_type", "Quarterly Financial Results", page_number=page, structural_ref=s_ref),
                )

        # Precedence 4: Half-Yearly
        for text, page, s_ref in search_texts:
            t_lower = text.lower()
            if "half year" in t_lower or "half-year" in t_lower or "six months ended" in t_lower:
                return (
                    DocumentType.HALF_YEARLY_RESULTS.value,
                    _make_evidence(doc_id, filename, "document_type", "Half-Yearly Financial Results", page_number=page, structural_ref=s_ref),
                )

        # Precedence 5: Investor Presentation
        for text, page, s_ref in search_texts:
            t_lower = text.lower()
            if "investor presentation" in t_lower or "earnings presentation" in t_lower or "analyst presentation" in t_lower:
                return (
                    DocumentType.INVESTOR_PRESENTATION.value,
                    _make_evidence(doc_id, filename, "document_type", "Investor Presentation", page_number=page, structural_ref=s_ref),
                )

        # Precedence 6: General Financial Statements
        for text, page, s_ref in search_texts:
            t_lower = text.lower()
            if "balance sheet" in t_lower or "financial statements" in t_lower or "statement of profit and loss" in t_lower:
                return (
                    DocumentType.FINANCIAL_STATEMENTS.value,
                    _make_evidence(doc_id, filename, "document_type", "Financial Statements", page_number=page, structural_ref=s_ref),
                )

        return DocumentType.UNKNOWN.value, None

    @classmethod
    def _detect_financial_year(
        cls,
        filename: str,
        blocks: List[ExtractedTextBlock],
        tables: List[ExtractedTable],
        doc_id: str,
    ) -> Tuple[str, Optional[str], Optional[str], bool, Optional[EvidenceReference]]:
        """Identify financial year using confirmed period end dates and Indian April–March financial calendar."""
        candidates = [(b.text, b.page_number, b.structural_ref) for b in blocks[:25]]
        for t in tables[:3]:
            if t.headers:
                candidates.append((" ".join(t.headers), t.page_number, t.structural_ref))
        candidates.append((filename.replace("_", " "), None, "Filename"))

        # 1. Canonical FY pattern: "FY 2023-24", "Financial Year 2024-25"
        for text, page, s_ref in candidates:
            m = _FY_CANONICAL_PATTERN.search(text)
            if m:
                start_y = int(m.group(1))
                end_raw = m.group(2)
                end_y = int(end_raw) if len(end_raw) == 4 else (start_y // 100 * 100 + int(end_raw))
                fy_label = f"FY {start_y}-{str(end_y)[-2:]}"
                evidence = _make_evidence(doc_id, filename, "financial_year", m.group(0), page_number=page, structural_ref=s_ref)
                return fy_label, f"{start_y}-04-01", f"{end_y}-03-31", False, evidence

        # 2. Date-ended word pattern: "year ended March 31, 2024", "quarter ended 30th September 2023"
        for text, page, s_ref in candidates:
            m_ended = _PERIOD_ENDED_MONTH_WORD_PATTERN.search(text)
            if m_ended:
                month_word = (m_ended.group(1) or m_ended.group(5) or "").lower()
                year_str = m_ended.group(3) or m_ended.group(6)
                if month_word in _MONTH_TO_NUM and year_str:
                    month_num = _MONTH_TO_NUM[month_word]
                    year_val = int(year_str)
                    if month_num >= 4:
                        start_y = year_val
                        end_y = year_val + 1
                    else:
                        start_y = year_val - 1
                        end_y = year_val
                    fy_label = f"FY {start_y}-{str(end_y)[-2:]}"
                    evidence = _make_evidence(doc_id, filename, "financial_year", m_ended.group(0), page_number=page, structural_ref=s_ref)
                    return fy_label, f"{start_y}-04-01", f"{end_y}-03-31", False, evidence

        # 3. Numeric date-ended pattern: "period ended 31-12-2023", "quarter ended 30.06.2024"
        for text, page, s_ref in candidates:
            m_num = _PERIOD_ENDED_NUMERIC_PATTERN.search(text)
            if m_num:
                p1, p2, year_str = int(m_num.group(1)), int(m_num.group(2)), m_num.group(3)
                year_val = int(year_str)
                month_num = None
                if 1 <= p2 <= 12 and (p1 > 12 or p1 in (30, 31)):
                    month_num = p2
                elif 1 <= p1 <= 12 and (p2 > 12 or p2 in (30, 31)):
                    month_num = p1

                if month_num:
                    if month_num >= 4:
                        start_y = year_val
                        end_y = year_val + 1
                    else:
                        start_y = year_val - 1
                        end_y = year_val
                    fy_label = f"FY {start_y}-{str(end_y)[-2:]}"
                    evidence = _make_evidence(doc_id, filename, "financial_year", m_num.group(0), page_number=page, structural_ref=s_ref)
                    return fy_label, f"{start_y}-04-01", f"{end_y}-03-31", False, evidence

        # 4. Single year: FY24 or FY2024
        for text, page, s_ref in candidates:
            m_single = _FY_SINGLE_YEAR_PATTERN.search(text)
            if m_single:
                val = int(m_single.group(1))
                end_y = val if val > 2000 else (2000 + val)
                start_y = end_y - 1
                fy_label = f"FY {start_y}-{str(end_y)[-2:]}"
                evidence = _make_evidence(doc_id, filename, "financial_year", m_single.group(0), page_number=page, structural_ref=s_ref)
                return fy_label, f"{start_y}-04-01", f"{end_y}-03-31", True, evidence

        return "Unknown", None, None, False, None

    @classmethod
    def _detect_period_and_quarter(
        cls,
        doc_type: str,
        blocks: List[ExtractedTextBlock],
        tables: List[ExtractedTable],
        doc_id: str,
        doc_name: str,
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[EvidenceReference]]:
        """Identify reporting period, quarter (Q1-Q4), and actual period dates, distinguishing Annual from Q4."""
        all_text = " ".join([b.text for b in blocks[:20]])
        for t in tables[:3]:
            if t.headers:
                all_text += " " + " ".join(t.headers)
            if t.title:
                all_text += " " + t.title

        # If document type is Annual Report, it is strictly Annual / Full Year
        if doc_type == DocumentType.ANNUAL_REPORT.value:
            ev = _make_evidence(doc_id, doc_name, "reporting_period", "Annual Report")
            return ReportingPeriodType.ANNUAL.value, "Full Year", None, None, None, ev

        # 1. Word-based period ended pattern
        m_ended = _PERIOD_ENDED_MONTH_WORD_PATTERN.search(all_text)
        if m_ended:
            period_phrase = m_ended.group(0)
            month_word = (m_ended.group(1) or m_ended.group(5) or "").lower()
            day_str = m_ended.group(2) or m_ended.group(4) or "30"
            year_str = m_ended.group(3) or m_ended.group(6)
            month_num = _MONTH_TO_NUM.get(month_word, 12)
            p_end_date = f"{year_str}-{month_num:02d}-{int(day_str):02d}"

            # Check if explicit Annual in period phrase
            if "year ended" in period_phrase.lower() and "quarter" not in period_phrase.lower():
                ev = _make_evidence(doc_id, doc_name, "reporting_period", period_phrase)
                return ReportingPeriodType.ANNUAL.value, f"Year ended {month_word.capitalize()} {year_str}", None, None, p_end_date, ev

            # Quarterly
            q = _MONTH_NAMES_TO_QUARTERS.get(month_word)
            if q:
                ev = _make_evidence(doc_id, doc_name, "reporting_period", period_phrase)
                return ReportingPeriodType.QUARTERLY.value, f"Quarter ended {month_word.capitalize()} {year_str}", q, None, p_end_date, ev

            if "nine" in period_phrase.lower() or "9m" in period_phrase.lower():
                ev = _make_evidence(doc_id, doc_name, "reporting_period", period_phrase)
                return ReportingPeriodType.NINE_MONTHS.value, f"Nine Months ended {month_word.capitalize()} {year_str}", None, None, p_end_date, ev

            if "half" in period_phrase.lower() or "six" in period_phrase.lower():
                ev = _make_evidence(doc_id, doc_name, "reporting_period", period_phrase)
                return ReportingPeriodType.HALF_YEARLY.value, f"Half-Year ended {month_word.capitalize()} {year_str}", None, None, p_end_date, ev

        # 2. Numeric period ended pattern
        m_num = _PERIOD_ENDED_NUMERIC_PATTERN.search(all_text)
        if m_num:
            period_phrase = m_num.group(0)
            p1, p2, year_str = int(m_num.group(1)), int(m_num.group(2)), m_num.group(3)
            month_num = p2 if 1 <= p2 <= 12 and p1 in (30, 31) else (p1 if 1 <= p1 <= 12 and p2 in (30, 31) else None)
            day_num = p1 if month_num == p2 else p2
            if month_num:
                p_end_date = f"{year_str}-{month_num:02d}-{day_num:02d}"
                q = _NUMERIC_MONTH_TO_QUARTERS.get(month_num)

                if "year ended" in period_phrase.lower() and "quarter" not in period_phrase.lower():
                    ev = _make_evidence(doc_id, doc_name, "reporting_period", period_phrase)
                    return ReportingPeriodType.ANNUAL.value, f"Year ended {p_end_date}", None, None, p_end_date, ev

                if q:
                    ev = _make_evidence(doc_id, doc_name, "reporting_period", period_phrase)
                    return ReportingPeriodType.QUARTERLY.value, f"Quarter ended {p_end_date}", q, None, p_end_date, ev

        # 3. Explicit Q1, Q2, Q3, Q4 tokens
        q_match = re.search(r"\b(Q[1-4])\b", all_text, re.IGNORECASE)
        if q_match:
            q_token = q_match.group(1).upper()
            ev = _make_evidence(doc_id, doc_name, "reporting_period", q_token)
            return ReportingPeriodType.QUARTERLY.value, q_token, q_token, None, None, ev

        # 4. Half-Year or Nine-Month tokens
        if "half year" in all_text.lower() or "h1" in all_text.lower() or "h2" in all_text.lower():
            ev = _make_evidence(doc_id, doc_name, "reporting_period", "Half-Yearly")
            return ReportingPeriodType.HALF_YEARLY.value, "Half-Yearly", None, None, None, ev

        return ReportingPeriodType.UNKNOWN.value, None, None, None, None, None

    @classmethod
    def _detect_currency_and_scale(
        cls,
        blocks: List[ExtractedTextBlock],
        tables: List[ExtractedTable],
        doc_id: str,
        doc_name: str,
    ) -> Tuple[str, str, str, Optional[EvidenceReference]]:
        """Identify currency (INR, USD, EUR, GBP) and reporting scale (Crores, Lakhs, Millions, Billions, Thousands, Units)."""
        corpus = " ".join([b.text for b in blocks[:20]])
        for t in tables[:3]:
            corpus += " " + " ".join(t.headers)

        c_lower = corpus.lower()

        # Currency
        if "usd" in c_lower or "u.s. dollar" in c_lower or "$" in corpus:
            currency = "USD"
            symbol = "$"
            ev_curr = "USD ($)"
        elif "eur" in c_lower or "euro" in c_lower or "€" in corpus:
            currency = "EUR"
            symbol = "€"
            ev_curr = "EUR (€)"
        elif "gbp" in c_lower or "pound" in c_lower or "£" in corpus:
            currency = "GBP"
            symbol = "£"
            ev_curr = "GBP (£)"
        else:
            currency = "INR"
            symbol = "₹"
            ev_curr = "INR (₹)"

        # Scale detection with precise boundaries
        if re.search(r"\b(?:in\s+)?(?:crores?|cr\.?)\b", c_lower):
            scale = "CRORE"
            ev_scale = "in Crores"
        elif re.search(r"\b(?:in\s+)?(?:lakhs?|lacs?)\b", c_lower):
            scale = "LAKH"
            ev_scale = "in Lakhs"
        elif re.search(r"\b(?:in\s+)?(?:millions?|mn\.?)\b", c_lower):
            scale = "MILLION"
            ev_scale = "in Millions"
        elif re.search(r"\b(?:in\s+)?(?:billions?|bn\.?)\b", c_lower):
            scale = "BILLION"
            ev_scale = "in Billions"
        elif re.search(r"\b(?:in\s+)?(?:thousands?|th\.?)\b", c_lower):
            scale = "THOUSAND"
            ev_scale = "in Thousands"
        else:
            scale = "UNITS"
            ev_scale = ev_curr

        evidence = _make_evidence(doc_id, doc_name, "currency", f"{ev_curr}, {ev_scale}")
        return currency, symbol, scale, evidence

    @classmethod
    def _detect_accounting_standard(
        cls,
        blocks: List[ExtractedTextBlock],
        doc_id: str,
        doc_name: str,
    ) -> Tuple[str, Optional[str], Optional[EvidenceReference]]:
        """Identify accounting standard from notes or auditor reports."""
        full_text = " ".join([b.text for b in blocks[:50]])
        ft_lower = full_text.lower()

        if "ind as" in ft_lower or "indian accounting standards" in ft_lower:
            m = re.search(r"((?:Indian\s+Accounting\s+Standards|Ind\s*AS)\s*(?:Rules,?\s*2015|specified\s+under\s+section\s+133)?)", full_text, re.IGNORECASE)
            disclosure = m.group(1).strip() if m else "Ind AS"
            evidence = _make_evidence(doc_id, doc_name, "accounting_standard", disclosure)
            return "Ind AS", disclosure, evidence

        if "indian gaap" in ft_lower or "accounting standards rules 2006" in ft_lower or "as 1" in ft_lower:
            evidence = _make_evidence(doc_id, doc_name, "accounting_standard", "Indian GAAP")
            return "Indian GAAP", "Indian GAAP", evidence

        if "ifrs" in ft_lower or "international financial reporting standards" in ft_lower:
            evidence = _make_evidence(doc_id, doc_name, "accounting_standard", "IFRS")
            return "IFRS", "IFRS", evidence

        if "us gaap" in ft_lower or "u.s. gaap" in ft_lower:
            evidence = _make_evidence(doc_id, doc_name, "accounting_standard", "US GAAP")
            return "US GAAP", "US GAAP", evidence

        return "Unknown", None, None

    @classmethod
    def _detect_audit_status(
        cls,
        blocks: List[ExtractedTextBlock],
        tables: List[ExtractedTable],
        doc_id: str,
        doc_name: str,
    ) -> Tuple[AuditStatus, Optional[EvidenceReference]]:
        """Identify assurance level: Audited vs Limited Review vs Unaudited from table headers and statement titles."""
        # Check table headers for primary column assurance
        table_header_text = ""
        for t in tables[:3]:
            table_header_text += " " + " ".join(t.headers)
            if t.title:
                table_header_text += " " + t.title

        th_lower = table_header_text.lower()
        if "(unaudited)" in th_lower or "unaudited" in th_lower:
            full_b_text = " ".join([b.text for b in blocks[:25]]).lower()
            if "limited review" in full_b_text or "review report" in full_b_text:
                evidence = _make_evidence(doc_id, doc_name, "audit_status", "Limited Review (Unaudited with Review Report)")
                return AuditStatus.LIMITED_REVIEW, evidence
            evidence = _make_evidence(doc_id, doc_name, "audit_status", "Unaudited")
            return AuditStatus.UNAUDITED, evidence

        if "(audited)" in th_lower or "statement of audited" in th_lower:
            evidence = _make_evidence(doc_id, doc_name, "audit_status", "Audited")
            return AuditStatus.AUDITED, evidence

        # Fallback to early blocks
        full_text = " ".join([b.text for b in blocks[:30]]).lower()
        if "limited review" in full_text or "review report" in full_text:
            evidence = _make_evidence(doc_id, doc_name, "audit_status", "Limited Review")
            return AuditStatus.LIMITED_REVIEW, evidence

        if "unaudited" in full_text or "un-audited" in full_text:
            evidence = _make_evidence(doc_id, doc_name, "audit_status", "Unaudited")
            return AuditStatus.UNAUDITED, evidence

        if "audited" in full_text or "independent auditor" in full_text:
            evidence = _make_evidence(doc_id, doc_name, "audit_status", "Audited")
            return AuditStatus.AUDITED, evidence

        if "provisional" in full_text:
            evidence = _make_evidence(doc_id, doc_name, "audit_status", "Provisional")
            return AuditStatus.PROVISIONAL, evidence

        return AuditStatus.UNKNOWN, None

    @classmethod
    def _detect_reporting_scope(
        cls,
        blocks: List[ExtractedTextBlock],
        tables: List[ExtractedTable],
        doc_id: str,
        doc_name: str,
    ) -> Tuple[ReportingScope, List[str], Optional[EvidenceReference]]:
        """Identify Consolidated vs Standalone, prioritizing statement/table titles over narrative mentions."""
        cons_in_titles = False
        stand_in_titles = False

        # 1. Primary Check: Table titles and Table Headers
        for t in tables[:5]:
            t_str = ((t.title or "") + " " + " ".join(t.headers or [])).lower()
            if "consolidated" in t_str:
                cons_in_titles = True
            if "standalone" in t_str:
                stand_in_titles = True

        # 2. Check early primary statement title blocks (first 5 blocks only)
        for b in blocks[:5]:
            b_low = b.text.lower()
            if "statement of" in b_low or "results for" in b_low or b.heading_level or len(b.text.split("\n")) <= 3:
                if re.search(r"\bstatement\s+of\s+standalone\b", b_low) or re.search(r"\bstandalone\s+(?:financial\s+)?results\b", b_low):
                    stand_in_titles = True
                elif re.search(r"\bstatement\s+of\s+consolidated\b", b_low) or re.search(r"\bconsolidated\s+(?:financial\s+)?results\b", b_low):
                    cons_in_titles = True
                else:
                    if "consolidated" in b_low and "standalone" not in b_low:
                        cons_in_titles = True
                    elif "standalone" in b_low and "consolidated" not in b_low:
                        stand_in_titles = True

        if cons_in_titles and stand_in_titles:
            evidence = _make_evidence(doc_id, doc_name, "reporting_scope", "Both Consolidated and Standalone statements present")
            return ReportingScope.BOTH, ["CONSOLIDATED", "STANDALONE"], evidence

        if cons_in_titles:
            evidence = _make_evidence(doc_id, doc_name, "reporting_scope", "Consolidated Financial Results")
            return ReportingScope.CONSOLIDATED, [], evidence

        if stand_in_titles:
            evidence = _make_evidence(doc_id, doc_name, "reporting_scope", "Standalone Financial Results")
            return ReportingScope.STANDALONE, [], evidence

        # Fallback to early text corpus (first 10 blocks, requiring clear single scope)
        for b in blocks[:10]:
            b_low = b.text.lower()
            if "standalone" in b_low and "consolidated" not in b_low:
                evidence = _make_evidence(doc_id, doc_name, "reporting_scope", "Standalone")
                return ReportingScope.STANDALONE, [], evidence
            if "consolidated" in b_low and "standalone" not in b_low:
                evidence = _make_evidence(doc_id, doc_name, "reporting_scope", "Consolidated")
                return ReportingScope.CONSOLIDATED, [], evidence

        return ReportingScope.UNKNOWN, [], None

    @classmethod
    def _detect_industry(
        cls,
        blocks: List[ExtractedTextBlock],
        tables: List[ExtractedTable],
        doc_id: str,
        doc_name: str,
    ) -> Tuple[str, Optional[EvidenceReference]]:
        """Identify industry or sector only if explicitly disclosed in text; never assume without evidence."""
        for b in blocks[:30]:
            m = _INDUSTRY_PATTERN.search(b.text)
            if m:
                raw_ind = m.group(1).strip()
                clean_ind = re.sub(r"[\.,;:].*$", "", raw_ind).strip()
                if clean_ind.lower() in _GENERIC_INDUSTRY_TERMS:
                    continue
                words = set(clean_ind.lower().split())
                if words & _INVALID_INDUSTRY_WORDS:
                    continue
                if clean_ind and len(clean_ind) >= 3:
                    evidence = _make_evidence(
                        doc_id,
                        doc_name,
                        "industry",
                        clean_ind,
                        page_number=b.page_number,
                        structural_ref=b.structural_ref,
                    )
                    return clean_ind, evidence

        return "UNKNOWN", None
