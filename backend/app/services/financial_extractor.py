"""Financial metric extraction engine for Compare Documents.

Extracts core and additional financial metric candidates across all 8 supported document formats
(tables and text blocks) without cloud AI dependencies.
Preserves every candidate with an unbreakable chain of custody (EvidenceReference).
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from ..models.comparison import (
    AuditStatus,
    ComparisonDocument,
    DocumentExtractionResult,
    DocumentMetadata,
    EvidenceReference,
    ExtractedTable,
    ExtractedTextBlock,
    ReportingScope,
    StatementType,
    ValueCandidate,
)
from .financial_normalizer import FinancialNormalizer


# ---------------------------------------------------------------------------
# Metric Definitions & Priority Regex Mappings
# ---------------------------------------------------------------------------

# Ordered metric definitions with canonical key, user-facing label, statement type hint, and regex patterns
METRIC_REGISTRY = [
    # Core Metrics
    {
        "key": "TOTAL_INCOME",
        "label": "Total Income",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?(?:total\s+income|total\s+revenue(?:\s+and\s+other\s+income)?|revenue\s+from\s+operations\s+and\s+other\s+income)\b", re.IGNORECASE),
            re.compile(r"\b(?:total\s+income|revenue\s+from\s+operations\s+and\s+other\s+income)\b", re.IGNORECASE),
        ],
    },
    {
        "key": "REVENUE",
        "label": "Revenue from Operations",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?(?:revenue\s+from\s+operations|gross\s+revenue|net\s+sales(?:\s*\/\s*income\s+from\s+operations)?|income\s+from\s+operations|revenue\s+from\s+contracts\s+with\s+customers|operating\s+revenue|turnover|net\s+turnover)\b", re.IGNORECASE),
            re.compile(r"\b(?:revenue\s+from\s+operations|income\s+from\s+operations|revenue\s+from\s+contracts\s+with\s+customers)\b", re.IGNORECASE),
        ],
    },
    {
        "key": "OPERATING_EXPENSES",
        "label": "Operating Expenses",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?(?:total\s+expenses|operating\s+expenses)\b", re.IGNORECASE),
        ],
    },
    {
        "key": "EBITDA",
        "label": "EBITDA",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"\b(?:operating\s+)?ebitda\b", re.IGNORECASE),
            re.compile(r"operating\s+profit\s+before\s+(?:interest|working|depreciation)", re.IGNORECASE),
        ],
    },
    {
        "key": "FINANCE_COSTS",
        "label": "Finance Costs",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?(?:finance\s+costs|finance\s+expenses|interest\s+expense|interest\s+and\s+finance\s+charges|borrowing\s+costs)\b", re.IGNORECASE),
        ],
    },
    {
        "key": "DEPRECIATION",
        "label": "Depreciation and Amortisation",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?depreciation(?:\s*,\s*|\s+and\s+|&)\s*amortis?ation(?:\s+and\s+impairment)?(?:\s+expense)?\b", re.IGNORECASE),
        ],
    },
    {
        "key": "EXCEPTIONAL_ITEMS",
        "label": "Exceptional Items",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?exceptional\s+items(?:\s*\/\s*non-recurring\s+items)?\b", re.IGNORECASE),
        ],
    },
    {
        "key": "PBT",
        "label": "Profit Before Tax",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?profit(?:\s*\/\s*\(?loss\)?)?\s+(?:before\s+exceptional\s+items\s+and\s+tax|before\s+tax\s+and\s+exceptional\s+items|before\s+tax)\b", re.IGNORECASE),
            re.compile(r"\bprofit(?:\s*\/\s*\(?loss\)?)?\s+before\s+tax\b", re.IGNORECASE),
        ],
    },
    {
        "key": "PAT",
        "label": "Profit After Tax",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?(?:profit|loss|profit\s*\/\s*\(?loss\)?)\s+(?:for\s+the\s+period|for\s+the\s+year|after\s+tax)(?:\s+after\s+tax)?\b", re.IGNORECASE),
            re.compile(r"\bnet\s+profit(?:\s+after\s+tax)?\b", re.IGNORECASE),
            re.compile(r"\bprofit\s+after\s+tax\b", re.IGNORECASE),
            re.compile(r"\btotal\s+comprehensive\s+income\s+for\s+the\s+period(?:\s+attributable\s+to\s+owners)?\b", re.IGNORECASE),
        ],
    },
    {
        "key": "EPS",
        "label": "Earnings Per Share (Basic)",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:basic\s+)?earnings\s+per\s+share\b|^\s*basic\s+eps\b|^\s*earnings\s+per\s+equity\s+share\b", re.IGNORECASE),
            re.compile(r"\b(?:basic\s+)?eps\s*\([^)]*\)", re.IGNORECASE),
            re.compile(r"\bearnings\s+per\s+equity\s+share\s*\([^)]*\)", re.IGNORECASE),
        ],
    },
    {
        "key": "GROSS_PROFIT",
        "label": "Gross Profit",
        "statement_hint": StatementType.PROFIT_AND_LOSS,
        "patterns": [
            re.compile(r"^\s*(?:[I|V|X\d]+[\.\)]?\s*)?gross\s+profit\b", re.IGNORECASE),
        ],
    },
    # Balance Sheet Metrics
    {
        "key": "CURRENT_ASSETS",
        "label": "Current Assets",
        "statement_hint": StatementType.BALANCE_SHEET,
        "patterns": [
            re.compile(r"^\s*(?:total\s+)?current\s+assets\b", re.IGNORECASE),
        ],
    },
    {
        "key": "TOTAL_ASSETS",
        "label": "Total Assets",
        "statement_hint": StatementType.BALANCE_SHEET,
        "patterns": [
            re.compile(r"^\s*total\s+assets\b", re.IGNORECASE),
        ],
    },
    {
        "key": "CURRENT_LIABILITIES",
        "label": "Current Liabilities",
        "statement_hint": StatementType.BALANCE_SHEET,
        "patterns": [
            re.compile(r"^\s*(?:total\s+)?current\s+liabilities\b", re.IGNORECASE),
        ],
    },
    {
        "key": "TOTAL_LIABILITIES",
        "label": "Total Liabilities",
        "statement_hint": StatementType.BALANCE_SHEET,
        "patterns": [
            re.compile(r"^\s*total\s+(?:equity\s+and\s+)?liabilities\b", re.IGNORECASE),
        ],
    },
    {
        "key": "TOTAL_DEBT",
        "label": "Total Debt / Borrowings",
        "statement_hint": StatementType.BALANCE_SHEET,
        "patterns": [
            re.compile(r"^\s*(?:total\s+)?(?:borrowings|debt)\b", re.IGNORECASE),
            re.compile(r"\btotal\s+borrowings\b", re.IGNORECASE),
            re.compile(r"\bborrowings\s*\(\s*current\s+and\s+non-current\s*\)\b", re.IGNORECASE),
        ],
    },
    {
        "key": "NET_WORTH",
        "label": "Net Worth / Total Equity",
        "statement_hint": StatementType.BALANCE_SHEET,
        "patterns": [
            re.compile(r"^\s*total\s+equity\b|^\s*net\s+worth\b|^\s*shareholders['\s]+funds\b", re.IGNORECASE),
        ],
    },
    {
        "key": "CASH_EQUIVALENTS",
        "label": "Cash and Cash Equivalents",
        "statement_hint": StatementType.BALANCE_SHEET,
        "patterns": [
            re.compile(r"cash\s+(?:and|&)\s+cash\s+equivalents\b", re.IGNORECASE),
            re.compile(r"\bcash\s+(?:and|&)\s+bank\s+balances\b", re.IGNORECASE),
        ],
    },
    # Cash Flow Metrics
    {
        "key": "OPERATING_CASH_FLOW",
        "label": "Operating Cash Flow",
        "statement_hint": StatementType.CASH_FLOW,
        "patterns": [
            re.compile(r"(?:net\s+)?cash\s+.*operating\s+activities", re.IGNORECASE),
            re.compile(r"(?:net\s+)?cash\s+(?:flow\s+from|generated\s+from(?:\s*\/\s*\(?used\s+in\)?)?|\(?used\s+in\)?)\s+operating\s+activities", re.IGNORECASE),
            re.compile(r"\bcash\s+generated\s+from\s+operations\b", re.IGNORECASE),
        ],
    },
    {
        "key": "INVESTING_CASH_FLOW",
        "label": "Investing Cash Flow",
        "statement_hint": StatementType.CASH_FLOW,
        "patterns": [
            re.compile(r"(?:net\s+)?cash\s+(?:flow\s+from|generated\s+from|\(?used\s+in\)?)\s+investing\s+activities", re.IGNORECASE),
        ],
    },
    {
        "key": "FINANCING_CASH_FLOW",
        "label": "Financing Cash Flow",
        "statement_hint": StatementType.CASH_FLOW,
        "patterns": [
            re.compile(r"(?:net\s+)?cash\s+(?:flow\s+from|generated\s+from|\(?used\s+in\)?)\s+financing\s+activities", re.IGNORECASE),
        ],
    },
]


class FinancialExtractor:
    """Extracts candidate financial metrics from structured document tables and text blocks."""

    @classmethod
    def extract_candidates(
        cls,
        comp_doc: ComparisonDocument,
        extraction: DocumentExtractionResult,
        metadata: DocumentMetadata,
    ) -> List[ValueCandidate]:
        """Extract all identifiable financial metric candidates for a document."""
        candidates: List[ValueCandidate] = []

        # Local mode OCR unavailability guard
        if extraction.extraction_status in ("OCR_UNAVAILABLE_LOCAL_MODE", "VISION_EXTRACTION_REQUIRED"):
            # Return empty candidate list; do not fabricate data
            return candidates

        doc_id = comp_doc.doc_id
        doc_name = comp_doc.original_filename
        scale = metadata.reporting_scale if (metadata.reporting_scale and metadata.reporting_scale.upper() not in ("UNKNOWN", "NONE")) else "UNKNOWN"
        currency = metadata.currency if (metadata.currency and metadata.currency.upper() not in ("UNKNOWN", "NONE")) else "UNKNOWN"
        scope = metadata.reporting_scope
        audit = metadata.audit_status
        standard = metadata.accounting_standard

        # 1. Extract from Tabular Structures (primary authoritative source)
        for table in extraction.tables:
            cls._extract_from_table(
                table=table,
                doc_id=doc_id,
                doc_name=doc_name,
                default_scale=scale,
                currency=currency,
                default_scope=scope,
                audit=audit,
                standard=standard,
                metadata=metadata,
                candidates=candidates,
            )

        # 2. Extract from Text Blocks (MD&A and narrative disclosures)
        for block in extraction.text_blocks:
            cls._extract_from_text_block(
                block=block,
                doc_id=doc_id,
                doc_name=doc_name,
                default_scale=scale,
                currency=currency,
                default_scope=scope,
                audit=audit,
                standard=standard,
                metadata=metadata,
                candidates=candidates,
            )

        return candidates

    @classmethod
    def _detect_dash_zero_convention(cls, table: ExtractedTable, metadata: DocumentMetadata) -> bool:
        """Detect whether table or document has explicitly disclosed that a dash denotes nil or zero."""
        texts_to_check: List[str] = []
        if table.headers:
            texts_to_check.extend(table.headers)
        if metadata.extraction_notes:
            texts_to_check.extend(metadata.extraction_notes)
        if getattr(table, "notes", None):
            texts_to_check.extend(table.notes)  # type: ignore[attr-defined]
        full_text = " ".join(texts_to_check).lower()
        patterns = [
            r"[-–—]\s*(?:denotes|represents|means|indicates|stands\s+for)\s*(?:nil|zero|negligible)",
            r"(?:nil|zero)\s*(?:is\s*)?represented\s*by\s*[-–—]",
            r"dash\s*\(?[-–—]\)?\s*(?:denotes|represents|means|indicates)\s*(?:nil|zero)",
        ]
        return any(re.search(p, full_text) for p in patterns)

    @classmethod
    def _parse_column_period_info(cls, col_header: str, metadata: DocumentMetadata) -> Dict[str, Any]:
        """Chronologically parse column header for financial year, quarter, duration, and restatement.

        Adheres strictly to the Indian financial calendar (April 1 to March 31).
        Does NOT blindly default to metadata periods if the header provides no evidence.
        """
        hdr = col_header.strip()
        hdr_lower = hdr.lower()

        # 1. Note Column Detection (Explicit note references only)
        is_note_column = bool(re.search(r"^(?:notes?|ref)(?:\s*(?:no\.?|reference))?$", hdr_lower))

        # 2. Restatement Detection (Explicit restatement indicator only)
        is_restated = "restated" in hdr_lower or "revised" in hdr_lower

        # 3. Prior/Comparative Period Indicator
        is_comparative = (
            "previous" in hdr_lower
            or "preceding" in hdr_lower
            or "corresponding" in hdr_lower
            or "comparative" in hdr_lower
        )

        detected_fy = None
        detected_quarter = None
        detected_duration = None

        # Check explicit quarter tokens: Q1, Q2, Q3, Q4
        q_match = re.search(r"\b(Q[1-4])\b", hdr, re.IGNORECASE)
        if q_match:
            detected_quarter = q_match.group(1).upper()
            detected_duration = "3M"

        # Check explicit FY tokens: FY 2024-25, FY 24-25, 2024-25
        fy_match = re.search(r"(?:FY\s*)?(\d{4})[-\/](\d{2,4})", hdr, re.IGNORECASE)
        if fy_match:
            start_y = int(fy_match.group(1))
            end_raw = fy_match.group(2)
            end_y = int(end_raw) if len(end_raw) == 4 else (start_y // 100 * 100 + int(end_raw))
            detected_fy = f"FY {start_y}-{str(end_y)[-2:]}"
        else:
            fy_single = re.search(r"\bFY\s*(\d{2,4})\b", hdr, re.IGNORECASE)
            if fy_single:
                val = int(fy_single.group(1))
                end_y = (2000 + val) if val < 100 else val
                start_y = end_y - 1
                detected_fy = f"FY {start_y}-{str(end_y)[-2:]}"

        # Check Date tokens: e.g. 31-03-2025, 31/12/2024, 30-Sep-2024, March 31, 2025
        date_match = re.search(r"(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})", hdr)
        dmy_name_match = re.search(
            r"(\d{1,2})[-\/\s\.]+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)[-\/\s\.]+(\d{2,4})",
            hdr_lower,
        )
        month_name_match = re.search(
            r"(?:ended\s+)?(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*(\d{1,2})?,?\s*(\d{2,4})",
            hdr_lower,
        )

        _m_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        day, month_num, year = None, None, None
        if date_match:
            d_raw, m_raw, y_raw = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            if m_raw <= 12 and d_raw <= 31:
                day, month_num, year = d_raw, m_raw, y_raw
        elif dmy_name_match:
            day = int(dmy_name_match.group(1))
            m_name = dmy_name_match.group(2)[:3]
            month_num = _m_map.get(m_name)
            y_val = int(dmy_name_match.group(3))
            year = (2000 + y_val) if y_val < 100 else y_val
        elif month_name_match:
            m_name = month_name_match.group(1)[:3]
            month_num = _m_map.get(m_name)
            d_val = month_name_match.group(2)
            day = int(d_val) if d_val else 31
            y_val = int(month_name_match.group(3))
            year = (2000 + y_val) if y_val < 100 else y_val

        if month_num is not None and year is not None:
            if month_num >= 4:
                start_y = year
                end_y = year + 1
            else:
                start_y = year - 1
                end_y = year
            calc_fy = f"FY {start_y}-{str(end_y)[-2:]}"
            if not detected_fy:
                detected_fy = calc_fy

            if "three" in hdr_lower or "quarter" in hdr_lower or "3 month" in hdr_lower:
                detected_duration = "3M"
                _q_map = {6: "Q1", 9: "Q2", 12: "Q3", 3: "Q4"}
                if not detected_quarter:
                    detected_quarter = _q_map.get(month_num)
            elif "six" in hdr_lower or "half" in hdr_lower or "6 month" in hdr_lower:
                detected_duration = "6M"
            elif "nine" in hdr_lower or "9 month" in hdr_lower:
                detected_duration = "9M"
            elif "year ended" in hdr_lower or "annual" in hdr_lower or "12 month" in hdr_lower:
                detected_duration = "ANNUAL"
            elif month_num == 3 and (day == 31 or day is None):
                if not detected_quarter and not detected_duration:
                    detected_duration = "ANNUAL"

        if "year ended" in hdr_lower or "annual" in hdr_lower or "full year" in hdr_lower:
            detected_duration = "ANNUAL"
            detected_quarter = None

        return {
            "is_note_column": is_note_column,
            "is_restated": is_restated,
            "is_comparative": is_comparative,
            "financial_year": detected_fy,
            "quarter": detected_quarter,
            "period_duration": detected_duration,
            "is_unverified": (detected_fy is None and detected_quarter is None and detected_duration is None),
        }

    @classmethod
    def _extract_from_table(
        cls,
        table: ExtractedTable,
        doc_id: str,
        doc_name: str,
        default_scale: str,
        currency: str,
        default_scope: ReportingScope,
        audit: AuditStatus,
        standard: str,
        metadata: DocumentMetadata,
        candidates: List[ValueCandidate],
    ) -> None:
        """Parse rows and columns of an extracted table for financial line items."""
        if not table.rows:
            return

        stmt_type = cls._infer_statement_type(table)
        has_dash_zero_convention = cls._detect_dash_zero_convention(table, metadata)

        # Inspect headers for scale or period clues
        header_text = " ".join(table.headers).lower() if table.headers else ""
        table_scale = default_scale
        if "in crore" in header_text or "in cr" in header_text or "₹ in crore" in header_text:
            table_scale = "CRORE"
        elif "in lakh" in header_text or "in lac" in header_text:
            table_scale = "LAKH"
        elif "in thousand" in header_text:
            table_scale = "THOUSAND"
        elif "in million" in header_text or "in mn" in header_text:
            table_scale = "MILLION"
        elif "in billion" in header_text or "in bn" in header_text:
            table_scale = "BILLION"

        for row_idx, row in enumerate(table.rows):
            if not row or len(row) < 2:
                continue

            # Detect whether label is in col 0 or col 1 (handles serial numbers "1", "(a)", "I." and empty col 0)
            col0 = str(row[0]).strip() if row[0] is not None else ""
            col1 = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""

            label_col_idx = 0
            raw_label = col0

            is_col0_serial = bool(re.match(r"^\s*(?:\d{1,2}|[I|V|X]+|\([a-z\d]+\))[\.\)]?\s*$", col0, re.IGNORECASE))
            if (not col0 or len(col0) < 3 or is_col0_serial) and len(col1) >= 3:
                clean_col1 = col1.replace(",", "").replace(".", "").strip()
                if not clean_col1.isdigit():
                    label_col_idx = 1
                    raw_label = col1

            if not raw_label or len(raw_label) < 3:
                continue

            # Match label against canonical metric definitions
            matched_metric = cls._match_metric_label(raw_label)

            # Check if this is a valid additional disclosed financial metric
            if not matched_metric:
                is_structural = any(raw_label.lower().startswith(p) for p in [
                    "particulars", "description", "item", "notes", "as at", "quarter ended", "year ended", "col "
                ]) or raw_label.lower() in ("total", "sub-total", "sub total", "grand total")
                if not is_structural and len(raw_label) >= 3 and len(raw_label) <= 100 and any(c.isalpha() for c in raw_label):
                    # Verify row has at least one valid numeric data cell
                    has_numeric_cell = any(
                        FinancialNormalizer.parse_raw_number(str(row[c_idx]).strip()) is not None
                        for c_idx in range(label_col_idx + 1, len(row))
                        if row[c_idx] is not None
                    )
                    if has_numeric_cell:
                        slug = re.sub(r"[^A-Z0-9]+", "_", raw_label.upper()).strip("_")
                        if slug:
                            metric_key = f"ADDITIONAL_{slug[:50]}"
                            matched_metric = {
                                "key": metric_key,
                                "label": raw_label,
                                "statement_hint": stmt_type,
                            }

            if not matched_metric:
                continue

            metric_key = matched_metric["key"]
            val_start_col = label_col_idx + 1

            # Value columns (evaluate each column individually with chronological parsing)
            for col_idx in range(val_start_col, len(row)):
                cell_raw = str(row[col_idx]).strip()
                if not cell_raw:
                    continue

                col_header = table.headers[col_idx] if table.headers and col_idx < len(table.headers) else f"Col {col_idx}"
                p_info = cls._parse_column_period_info(col_header, metadata)

                # Conservative Note-Column Handling: Skip explicit note reference columns only
                if p_info["is_note_column"]:
                    continue

                parsed_num = FinancialNormalizer.parse_raw_number(
                    cell_raw,
                    allow_dash_as_zero=has_dash_zero_convention,
                )

                val_lower = cell_raw.lower()
                is_dash = cell_raw in ("-", "—", "–")
                is_nil_na = val_lower in ("nil", "none", "null", "n.a.", "na", "n/a", "not disclosed")

                # If not a valid number and not an explicit dash/nil/na token, skip
                if parsed_num is None and not (is_dash or is_nil_na):
                    continue

                # Determine candidate period identity
                cand_fy = p_info["financial_year"]
                cand_quarter = p_info["quarter"]
                cand_duration = p_info["period_duration"]
                is_prior_period = p_info["is_comparative"]
                is_explicit_restated = p_info["is_restated"]

                extraction_conf = "HIGH"
                warnings = []

                if p_info["is_unverified"]:
                    extraction_conf = "LOW"
                    warnings.append("Unidentified column period: header lacks explicit date or period metadata.")
                else:
                    if is_prior_period:
                        warnings.append("Prior period comparative column.")
                    if is_explicit_restated:
                        warnings.append("Explicitly restated column disclosure.")

                # Calculate normalized amount preserving currency and scale
                norm_amt, norm_curr, norm_scale, norm_unit = FinancialNormalizer.normalize_value(
                    raw_number=parsed_num,
                    currency=currency,
                    scale=table_scale,
                    metric_key=metric_key,
                )

                if is_dash:
                    if has_dash_zero_convention:
                        warnings.append("Dash converted to zero based on document disclosed convention.")
                    else:
                        warnings.append("Dash retained as missing/uncertain because no zero convention was disclosed.")
                elif is_nil_na:
                    warnings.append(f"Disclosed as '{cell_raw}'; retained as missing/unavailable, not zero.")

                # Propagate exact cell-level bounding box if present, otherwise table bounding box
                matching_cell = next((c for c in table.cells if c.row_index == row_idx and c.col_index == col_idx), None)
                cell_bbox = (matching_cell.bounding_box if matching_cell else None) or table.bounding_box

                candidate_id = f"cand_{doc_id}_{metric_key}_{table.table_id}_{row_idx}_{col_idx}_{uuid.uuid4().hex[:6]}"
                evidence = EvidenceReference(
                    evidence_id=f"ev_{candidate_id}",
                    doc_id=doc_id,
                    document_name=doc_name,
                    page_number=table.page_number,
                    bounding_box=cell_bbox,
                    sheet_name=table.sheet_name,
                    cell_range=f"Row {row_idx + 1}, Col {col_idx + 1}",
                    structural_ref=table.structural_ref or f"Table {table.table_id}",
                    verbatim_snippet=f"{raw_label}: {cell_raw} ({col_header})",
                    table_context=f"Table: {table.sheet_name or table.table_id} | Header: {col_header}",
                )

                candidates.append(
                    ValueCandidate(
                        candidate_id=candidate_id,
                        doc_id=doc_id,
                        metric_key=metric_key,
                        raw_label=raw_label,
                        raw_text_value=cell_raw,
                        parsed_number=parsed_num,
                        normalized_amount=norm_amt,
                        original_currency=currency,
                        normalized_currency=norm_curr,
                        original_scale=table_scale,
                        normalized_unit=norm_unit,
                        statement_type=stmt_type,
                        reporting_scope=default_scope,
                        audit_status=audit,
                        accounting_standard=standard,
                        period_start_date=metadata.period_start_date,
                        period_end_date=metadata.period_end_date,
                        financial_year=cand_fy,
                        quarter=cand_quarter,
                        period_duration=cand_duration,
                        is_restated=is_explicit_restated,
                        is_derived=False,
                        dash_convention_applied=has_dash_zero_convention and is_dash,
                        evidence=evidence,
                        extraction_method="TABLE_CELL",
                        extraction_confidence=extraction_conf,
                        warnings=warnings,
                    )
                )

    @classmethod
    def _extract_from_text_block(
        cls,
        block: ExtractedTextBlock,
        doc_id: str,
        doc_name: str,
        default_scale: str,
        currency: str,
        default_scope: ReportingScope,
        audit: AuditStatus,
        standard: str,
        metadata: DocumentMetadata,
        candidates: List[ValueCandidate],
    ) -> None:
        """Extract narrative disclosures of financial figures from text paragraphs."""
        text = block.text
        if not text or len(text) < 15:
            return

        for metric in METRIC_REGISTRY:
            metric_key = metric["key"]
            for pat in metric["patterns"]:
                match = pat.search(text)
                if match:
                    # Look for numerical values immediately after the match
                    after_text = text[match.end() : min(len(text), match.end() + 70)]
                    num_match = re.search(r"[:\s\-–=]+(?:stood\s+at|of|was|is|reached)?\s*(?:₹|rs\.?|inr)?\s*([0-9.,]+)\s*(?:cr(?:ore)?|lakh|lac|k|mn|bn)?", after_text, re.IGNORECASE)

                    if not num_match:
                        # Fallback: check immediately before the match (e.g. "₹ 10,500 crore of revenue")
                        before_text = text[max(0, match.start() - 50) : match.start()]
                        num_match = re.search(r"(?:₹|rs\.?|inr)?\s*([0-9.,]+)\s*(?:cr(?:ore)?|lakh|lac|k|mn|bn)?\s*(?:of)?$", before_text, re.IGNORECASE)

                    if num_match:
                        raw_num_str = num_match.group(1).rstrip(".")
                        parsed_num = FinancialNormalizer.parse_raw_number(raw_num_str)
                        if parsed_num is not None:
                            # Scale detection in nearby text
                            context_snippet = text[max(0, match.start() - 25) : min(len(text), match.end() + 75)]
                            snip_lower = context_snippet.lower()
                            item_scale = default_scale
                            if "crore" in snip_lower or " cr" in snip_lower:
                                item_scale = "CRORE"
                            elif "lakh" in snip_lower or "lac" in snip_lower:
                                item_scale = "LAKH"

                            norm_amt, norm_curr, norm_scale, norm_unit = FinancialNormalizer.normalize_value(
                                raw_number=parsed_num,
                                currency=currency,
                                scale=item_scale,
                                metric_key=metric_key,
                            )

                            candidate_id = f"cand_{doc_id}_{metric_key}_{block.block_id}_{uuid.uuid4().hex[:6]}"
                            evidence = EvidenceReference(
                                evidence_id=f"ev_{candidate_id}",
                                doc_id=doc_id,
                                document_name=doc_name,
                                page_number=block.page_number,
                                bounding_box=block.bounding_box,
                                structural_ref=block.structural_ref or f"Block {block.block_id}",
                                verbatim_snippet=context_snippet.strip(),
                                table_context="MD&A / Narrative Disclosure",
                            )

                            candidates.append(
                                ValueCandidate(
                                    candidate_id=candidate_id,
                                    doc_id=doc_id,
                                    metric_key=metric_key,
                                    raw_label=match.group(0),
                                    raw_text_value=raw_num_str,
                                    parsed_number=parsed_num,
                                    normalized_amount=norm_amt,
                                    original_currency=currency,
                                    normalized_currency=norm_curr,
                                    original_scale=item_scale,
                                    normalized_unit=norm_unit,
                                    statement_type=StatementType.MDA_NARRATIVE,
                                    reporting_scope=default_scope,
                                    audit_status=audit,
                                    accounting_standard=standard,
                                    period_start_date=metadata.period_start_date,
                                    period_end_date=metadata.period_end_date,
                                    financial_year=metadata.financial_year,
                                    quarter=metadata.quarter,
                                    is_restated=False,
                                    is_derived=False,
                                    evidence=evidence,
                                    extraction_method="TEXT_PATTERN",
                                    extraction_confidence="MEDIUM",
                                    warnings=["Extracted from narrative text"],
                                )
                            )
                    break

    @classmethod
    def _match_metric_label(cls, raw_label: str) -> Optional[Dict]:
        """Find the matching metric definition for a table row label, including unspaced PDF text."""
        cleaned = re.sub(r"^\s*(?:[I|V|X\d]+[\.\)]?|\([a-z\d]+\))\s*", "", raw_label).strip()

        # 1. Standard pattern matching
        for metric in METRIC_REGISTRY:
            for pat in metric["patterns"]:
                if pat.search(cleaned) or pat.search(raw_label):
                    return metric

        # 2. Unspaced label normalization (when PDF font extraction omits whitespace)
        # e.g. "RevenuefromOperations" -> matches "REVENUE"
        compact = re.sub(r"[^a-zA-Z0-9]", "", raw_label).lower()
        unspaced_metric_map = [
            ("totalincome", "TOTAL_INCOME"),
            ("totalrevenueandotherincome", "TOTAL_INCOME"),
            ("revenuefromoperationsandotherincome", "TOTAL_INCOME"),
            ("revenuefromoperations", "REVENUE"),
            ("grossrevenue", "REVENUE"),
            ("operatingrevenue", "REVENUE"),
            ("netsales", "REVENUE"),
            ("operatingexpenses", "OPERATING_EXPENSES"),
            ("totalexpenses", "OPERATING_EXPENSES"),
            ("operatingebitda", "EBITDA"),
            ("ebitda", "EBITDA"),
            ("financecosts", "FINANCE_COSTS"),
            ("financeexpenses", "FINANCE_COSTS"),
            ("borrowingcosts", "FINANCE_COSTS"),
            ("depreciationandamortisation", "DEPRECIATION"),
            ("depreciationandamortization", "DEPRECIATION"),
            ("exceptionalitems", "EXCEPTIONAL_ITEMS"),
            ("profitbeforetax", "PBT"),
            ("profitlossbeforetax", "PBT"),
            ("profitaftertax", "PAT"),
            ("netprofit", "PAT"),
            ("netprofitaftertax", "PAT"),
            ("profitfortheperiod", "PAT"),
            ("basicearningspershare", "EPS"),
            ("earningspershare", "EPS"),
            ("basiceps", "EPS"),
            ("totalassets", "TOTAL_ASSETS"),
            ("currentassets", "CURRENT_ASSETS"),
            ("totalliabilities", "TOTAL_LIABILITIES"),
            ("totalequityandliabilities", "TOTAL_LIABILITIES"),
            ("currentliabilities", "CURRENT_LIABILITIES"),
            ("totaldebt", "TOTAL_DEBT"),
            ("totalborrowings", "TOTAL_DEBT"),
            ("cashandcashequivalents", "CASH_EQUIVALENTS"),
            ("cashflowfromoperatingactivities", "OPERATING_CASH_FLOW"),
            ("operatingcashflow", "OPERATING_CASH_FLOW"),
            ("cashgeneratedfromoperations", "OPERATING_CASH_FLOW"),
        ]
        for token, m_key in unspaced_metric_map:
            if token in compact:
                for m in METRIC_REGISTRY:
                    if m["key"] == m_key:
                        return m

        return None

    @classmethod
    def _infer_statement_type(cls, table: ExtractedTable) -> StatementType:
        """Infer StatementType from table metadata, sheet name, or headers."""
        context = f"{table.sheet_name or ''} {table.structural_ref or ''} {' '.join(table.headers or [])}".lower()
        if "balance sheet" in context or "statement of financial position" in context:
            return StatementType.BALANCE_SHEET
        if "profit and loss" in context or "statement of operations" in context or "p&l" in context or "income statement" in context:
            return StatementType.PROFIT_AND_LOSS
        if "cash flow" in context:
            return StatementType.CASH_FLOW
        if "notes" in context or "schedule" in context:
            return StatementType.NOTES_TO_ACCOUNTS
        return StatementType.OTHER
