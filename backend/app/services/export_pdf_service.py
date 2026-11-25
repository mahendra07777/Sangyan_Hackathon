"""Institutional PDF report generation engine for Compare Documents (Slice 8).
Assembles multi-page, publication-quality comparative reports using PyMuPDF.
Strictly adheres to SEBI-educational non-advisory principles.
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pymupdf

from app.models.comparison import (
    AccountingDifference,
    CalculationResult,
    ComparisonDocument,
    ComparisonResult,
    DocumentMetadata,
    EvidenceReference,
    FinancialValue,
    RiskDisclosure,
    VerificationResult,
)


class ExportPdfService:
    """Generates authoritative, multi-page comparative PDF reports via PyMuPDF.

    Features:
    - Complete multi-page layout with headers, footers, and dynamic page numbering.
    - TrueType font integration (Nirmala.ttc on Windows for full Devanagari Hindi support).
    - Preserves exact financial values, units, and missing-data status (never converts missing to zero).
    - Unbreakable source evidence traceability index.
    - Mandatory prominent SEBI educational non-advisory disclaimer.
    """

    PAGE_WIDTH = 595.0   # A4 portrait width
    PAGE_HEIGHT = 842.0  # A4 portrait height
    MARGIN_LEFT = 40.0
    MARGIN_RIGHT = 555.0
    CONTENT_WIDTH = 515.0
    TOP_MARGIN = 45.0
    BOTTOM_MARGIN = 790.0

    # Professional Palette
    COLOR_PRIMARY = (0.06, 0.09, 0.16)     # Deep Slate
    COLOR_ACCENT = (0.09, 0.35, 0.65)      # Royal Blue
    COLOR_BORDER = (0.80, 0.84, 0.88)      # Light Slate Border
    COLOR_ROW_ALT = (0.97, 0.98, 0.99)     # Soft Slate Zebra
    COLOR_HEADER_BG = (0.12, 0.16, 0.23)   # Dark Slate Header
    COLOR_RED = (0.75, 0.12, 0.12)         # Red Warning / Disclaimer
    COLOR_AMBER = (0.85, 0.55, 0.08)       # Amber Warning
    COLOR_GREEN = (0.10, 0.55, 0.25)       # Green Success

    # Windows standard Devanagari font path
    DEFAULT_INDIC_FONT = "C:/Windows/Fonts/Nirmala.ttc"

    @classmethod
    def _resolve_font(cls) -> Tuple[Optional[str], Optional[str]]:
        """Resolves Unicode font for Hindi rendering or returns fallback."""
        if os.path.exists(cls.DEFAULT_INDIC_FONT):
            return "nirmala", cls.DEFAULT_INDIC_FONT
        # Check linux/other common paths if applicable
        linux_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        ]
        for p in linux_paths:
            if os.path.exists(p):
                return "unicode_fallback", p
        return "helv", None

    @classmethod
    def generate_comparison_pdf(cls, result: ComparisonResult) -> bytes:
        """Assembles authoritative multi-page comparative PDF report."""
        doc = pymupdf.open()
        font_name, font_file = cls._resolve_font()

        # State tracking for multi-page flow
        page = doc.new_page(width=cls.PAGE_WIDTH, height=cls.PAGE_HEIGHT)
        y_cursor = cls.TOP_MARGIN + 10.0

        def ensure_space(needed_height: float) -> pymupdf.Page:
            nonlocal y_cursor
            if y_cursor + needed_height > cls.BOTTOM_MARGIN:
                doc.new_page(width=cls.PAGE_WIDTH, height=cls.PAGE_HEIGHT)
                y_cursor = cls.TOP_MARGIN + 20.0
            return doc[-1]

        # =======================================================================
        # 1. Cover Title & Overview Header
        # =======================================================================
        # Header banner box
        banner_rect = pymupdf.Rect(cls.MARGIN_LEFT, y_cursor, cls.MARGIN_RIGHT, y_cursor + 62)
        page.draw_rect(banner_rect, color=cls.COLOR_PRIMARY, fill=cls.COLOR_PRIMARY)

        page.insert_text(
            (cls.MARGIN_LEFT + 15, y_cursor + 24),
            "BHARAT INVESTOR COPILOT",
            fontsize=15,
            fontname=font_name,
            fontfile=font_file,
            color=(1, 1, 1),
        )
        page.insert_text(
            (cls.MARGIN_LEFT + 15, y_cursor + 42),
            "Comparative Financial Document Understanding Report",
            fontsize=10,
            fontname=font_name,
            fontfile=font_file,
            color=(0.9, 0.9, 0.9),
        )
        page.insert_text(
            (cls.MARGIN_LEFT + 15, y_cursor + 54),
            "FOUNDATIONAL PRINCIPLE: UNDERSTANDING BEFORE ACTION • NON-ADVISORY",
            fontsize=7,
            fontname=font_name,
            fontfile=font_file,
            color=(0.8, 0.85, 0.95),
        )
        y_cursor += 72

        # Metadata Bar (Session, Date, Mode)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        meta_rect = pymupdf.Rect(cls.MARGIN_LEFT, y_cursor, cls.MARGIN_RIGHT, y_cursor + 22)
        page.draw_rect(meta_rect, color=cls.COLOR_BORDER, fill=cls.COLOR_ROW_ALT)

        meta_text = f"Session: {result.session_id[:16]}... | Generated: {now_str} | Mode: {result.mode} | Language: {result.language}"
        page.insert_text((cls.MARGIN_LEFT + 8, y_cursor + 14), meta_text, fontsize=8, color=(0.2, 0.25, 0.3))
        y_cursor += 30

        # =======================================================================
        # 2. Participating Documents Overview
        # =======================================================================
        y_cursor = cls._render_section_heading(page, y_cursor, "1. Participating Financial Documents")
        
        doc_headers = ["Slot", "Document Filename", "Company Name", "Period", "Scope", "Accounting", "Audit"]
        col_widths = [45, 140, 110, 60, 60, 50, 50]
        y_cursor = cls._render_table_header(page, y_cursor, doc_headers, col_widths)

        for doc_item in result.documents:
            page = ensure_space(20)
            meta = result.metadata.get(doc_item.doc_id)
            row_data = [
                doc_item.slot.upper().replace("DOC_", "Doc "),
                doc_item.original_filename,
                meta.company_name if meta else "Unidentified",
                meta.financial_year if meta else "FY",
                meta.reporting_scope if meta else "CONSOLIDATED",
                meta.accounting_standard if meta else "IND_AS",
                meta.audit_status if meta else "UNAUDITED",
            ]
            y_cursor = cls._render_table_row(page, y_cursor, row_data, col_widths, font_name, font_file)
        y_cursor += 15

        # =======================================================================
        # 3. Document Compatibility Evaluation
        # =======================================================================
        page = ensure_space(70)
        y_cursor = cls._render_section_heading(page, y_cursor, "2. Document Compatibility & Limitations")

        compat = result.compatibility
        badge_color = cls.COLOR_GREEN if compat.overall_status in ("COMPATIBLE", "COMPATIBLE_WITH_WARNINGS") else cls.COLOR_AMBER
        if compat.overall_status == "BLOCKED":
            badge_color = cls.COLOR_RED

        # Compatibility Status Pill
        page.draw_rect(pymupdf.Rect(cls.MARGIN_LEFT, y_cursor, cls.MARGIN_LEFT + 180, y_cursor + 18), color=badge_color, fill=badge_color)
        page.insert_text(
            (cls.MARGIN_LEFT + 8, y_cursor + 13),
            f"STATUS: {compat.overall_status}",
            fontsize=8,
            fontname=font_name,
            fontfile=font_file,
            color=(1, 1, 1),
        )
        y_cursor += 24

        # Summary narrative
        narrative_text = (
            f"Compatibility Status: {compat.overall_status}. Comparable: {compat.is_comparable}. "
            f"Blockers: {compat.blocker_count}, Warnings: {compat.warning_count}. "
            "Evaluated across currency, reporting period duration, accounting standard, and audit status."
        )
        narrative_rect = pymupdf.Rect(cls.MARGIN_LEFT, y_cursor, cls.MARGIN_RIGHT, y_cursor + 35)
        page.insert_textbox(narrative_rect, narrative_text, fontsize=8.5, fontname=font_name, fontfile=font_file, color=(0.15, 0.15, 0.15))
        y_cursor += 42

        # Warnings list
        if compat.findings:
            warnings_count = len(compat.findings)
            page = ensure_space(20 + warnings_count * 15)
            page.insert_text((cls.MARGIN_LEFT, y_cursor), "Specific Findings & Comparison Nuances:", fontsize=8.5, fontname=font_name, fontfile=font_file, color=cls.COLOR_PRIMARY)
            y_cursor += 12
            for f in compat.findings:
                page = ensure_space(15)
                sev_bullet = "• [WARNING]" if getattr(f, "severity", "") == "WARNING" else "• [INFO]"
                finding_title = getattr(f, "title", None) or getattr(f, "rule_name", None) or getattr(f, "code", "Finding")
                finding_desc = getattr(f, "description", None) or getattr(f, "message", "")
                msg = f"{sev_bullet} {finding_title}: {finding_desc}"
                tb_rect = pymupdf.Rect(cls.MARGIN_LEFT + 10, y_cursor, cls.MARGIN_RIGHT, y_cursor + 20)
                page.insert_textbox(tb_rect, msg, fontsize=7.5, fontname=font_name, fontfile=font_file, color=(0.25, 0.25, 0.25))
                y_cursor += 14
        y_cursor += 10

        # =======================================================================
        # 4. Executive Summary Narrative
        # =======================================================================
        if result.executive_summary:
            es = result.executive_summary
            page = ensure_space(80)
            y_cursor = cls._render_section_heading(page, y_cursor, "3. Executive Summary Narrative")

            ov_rect = pymupdf.Rect(cls.MARGIN_LEFT, y_cursor, cls.MARGIN_RIGHT, y_cursor + 45)
            page.insert_textbox(ov_rect, es.overview_story, fontsize=8.5, fontname=font_name, fontfile=font_file, color=(0.1, 0.1, 0.1))
            y_cursor += 50

            categories = [
                ("Key Disclosed Positive Observations", es.core_positive_changes, cls.COLOR_GREEN),
                ("Key Disclosed Pressures / Risks", es.core_negative_changes, cls.COLOR_RED),
                ("Neutral Structural Disclosures", es.neutral_observations, cls.COLOR_PRIMARY),
                ("Uncertain Findings / Inconsistencies", es.uncertain_findings, cls.COLOR_AMBER),
            ]
            for title, items, color_accent in categories:
                if items:
                    page = ensure_space(20 + len(items) * 16)
                    page.insert_text((cls.MARGIN_LEFT, y_cursor), title, fontsize=9, fontname=font_name, fontfile=font_file, color=color_accent)
                    y_cursor += 13
                    for itm in items:
                        page = ensure_space(16)
                        bullet_rect = pymupdf.Rect(cls.MARGIN_LEFT + 8, y_cursor, cls.MARGIN_RIGHT, y_cursor + 20)
                        page.insert_textbox(bullet_rect, f"• {itm}", fontsize=8, fontname=font_name, fontfile=font_file, color=(0.2, 0.2, 0.2))
                        y_cursor += 14
                    y_cursor += 6
            y_cursor += 10

        # =======================================================================
        # 5. Financial Comparison Matrix & Deterministic Calculations
        # =======================================================================
        page = ensure_space(90)
        y_cursor = cls._render_section_heading(page, y_cursor, "4. Financial Comparison Matrix & Deterministic Variances")

        matrix_headers = ["Metric", "Filing A (Base)", "Filing B (Comp)", "Abs Variance", "% Change", "Status"]
        matrix_cols = [125, 80, 80, 75, 75, 80]
        y_cursor = cls._render_table_header(page, y_cursor, matrix_headers, matrix_cols)

        doc_a_id = result.documents[0].doc_id if len(result.documents) > 0 else ""
        doc_b_id = result.documents[1].doc_id if len(result.documents) > 1 else ""

        for metric_key, doc_vals in result.financial_values.items():
            page = ensure_space(22)
            f_a = doc_vals.get(doc_a_id)
            f_b = doc_vals.get(doc_b_id)

            label = f_a.label if f_a else (f_b.label if f_b else metric_key)

            # Format A
            val_a_str = "Not Disclosed"
            if f_a and f_a.status == "REPORTED" and f_a.amount is not None:
                unit_label = " / sh" if getattr(f_a, "unit", "") == "INR" or metric_key in ("EPS", "basic_eps") else " Cr"
                val_a_str = f"₹{f_a.amount:,.2f}{unit_label}"
                if getattr(f_a, "is_user_corrected", False):
                    val_a_str += " *"

            # Format B
            val_b_str = "Not Disclosed"
            if f_b and f_b.status == "REPORTED" and f_b.amount is not None:
                unit_label = " / sh" if getattr(f_b, "unit", "") == "INR" or metric_key in ("EPS", "basic_eps") else " Cr"
                val_b_str = f"₹{f_b.amount:,.2f}{unit_label}"
                if getattr(f_b, "is_user_corrected", False):
                    val_b_str += " *"

            # Find matching variance
            var_item = next(
                (v for v in result.variances if v.metric_key == metric_key),
                None,
            )
            abs_str = "N/A"
            pct_str = "N/A"
            stat_str = "Not Compared"

            if var_item:
                stat_str = var_item.status
                if var_item.display_absolute_variance:
                    abs_str = var_item.display_absolute_variance
                elif var_item.absolute_variance is not None:
                    abs_str = f"{var_item.absolute_variance:+,.2f} Cr"

                if var_item.display_percentage_change:
                    pct_str = var_item.display_percentage_change
                elif var_item.percentage_change is not None:
                    pct_str = f"{var_item.percentage_change:+,.2f}%"

            row_data = [label, val_a_str, val_b_str, abs_str, pct_str, stat_str]
            y_cursor = cls._render_table_row(page, y_cursor, row_data, matrix_cols, font_name, font_file)
        y_cursor += 15

        has_corrections = any(
            getattr(fv, "is_user_corrected", False)
            for doc_vals in result.financial_values.values()
            for fv in doc_vals.values()
        )
        if has_corrections:
            page = ensure_space(32)
            corr_note = "* Note: Metrics marked with an asterisk (*) reflect user-entered manual adjustments and were not independently extracted or verified from filings. Dependent variances have been recalculated accordingly."
            page.insert_textbox(
                pymupdf.Rect(cls.MARGIN_LEFT, y_cursor, cls.MARGIN_RIGHT, y_cursor + 32),
                corr_note,
                fontsize=7.5,
                fontname=font_name,
                fontfile=font_file,
                color=cls.COLOR_AMBER,
            )
            y_cursor += 36

        # =======================================================================
        # 6. Disclosed Institutional Risks & Warning Signals
        # =======================================================================
        if result.risks:
            page = ensure_space(80)
            y_cursor = cls._render_section_heading(page, y_cursor, "5. Disclosed Institutional Risks & Warning Signals")

            risk_headers = ["Category", "Severity", "Filing", "Risk Title & Summary", "Evidence Citation"]
            risk_cols = [75, 55, 65, 230, 90]
            y_cursor = cls._render_table_header(page, y_cursor, risk_headers, risk_cols)

            for r in result.risks:
                page = ensure_space(28)
                doc_name = r.doc_id
                target_doc = next((d for d in result.documents if d.doc_id == r.doc_id), None)
                if target_doc:
                    doc_name = target_doc.slot.upper().replace("DOC_", "Doc ")

                ev_str = f"Ev: {r.evidence.evidence_id}" if r.evidence else "N/A"
                if r.evidence and r.evidence.page_number:
                    ev_str += f" (p.{r.evidence.page_number})"

                row_data = [r.category, r.severity, doc_name, f"{r.title}: {r.disclosure_text[:60]}...", ev_str]
                y_cursor = cls._render_table_row(page, y_cursor, row_data, risk_cols, font_name, font_file)
            y_cursor += 15

        # =======================================================================
        # 7. Disclosed Accounting Policy Differences
        # =======================================================================
        if result.accounting_differences:
            page = ensure_space(80)
            y_cursor = cls._render_section_heading(page, y_cursor, "6. Disclosed Accounting Policy Differences")

            acct_headers = ["Topic", "Filing A Policy", "Filing B Policy", "Variance Summary"]
            acct_cols = [100, 130, 130, 155]
            y_cursor = cls._render_table_header(page, y_cursor, acct_headers, acct_cols)

            for ad in result.accounting_differences:
                page = ensure_space(26)
                row_data = [ad.topic, ad.doc_a_policy, ad.doc_b_policy, ad.impact_summary]
                y_cursor = cls._render_table_row(page, y_cursor, row_data, acct_cols, font_name, font_file)
            y_cursor += 15

        # =======================================================================
        # 8. Source Evidence & Traceability Chain of Custody
        # =======================================================================
        page = ensure_space(90)
        y_cursor = cls._render_section_heading(page, y_cursor, "7. Source Evidence & Chain of Custody")

        ev_headers = ["Evidence ID", "Document", "Location", "Verbatim Source Excerpt", "Provenance"]
        ev_cols = [70, 75, 75, 215, 80]
        y_cursor = cls._render_table_header(page, y_cursor, ev_headers, ev_cols)

        # Collect unique evidence
        collected_evidence: Dict[str, EvidenceReference] = {}
        for metric_key, doc_map in result.financial_values.items():
            for doc_id, fval in doc_map.items():
                if fval.evidence and fval.evidence.evidence_id not in collected_evidence:
                    collected_evidence[fval.evidence.evidence_id] = fval.evidence
        for r in result.risks:
            if r.evidence and r.evidence.evidence_id not in collected_evidence:
                collected_evidence[r.evidence.evidence_id] = r.evidence
        for ad in result.accounting_differences:
            if ad.evidence_a and ad.evidence_a.evidence_id not in collected_evidence:
                collected_evidence[ad.evidence_a.evidence_id] = ad.evidence_a
            if ad.evidence_b and ad.evidence_b.evidence_id not in collected_evidence:
                collected_evidence[ad.evidence_b.evidence_id] = ad.evidence_b

        for ev_id, ev in sorted(collected_evidence.items()):
            page = ensure_space(24)
            loc = "N/A"
            if ev.page_number:
                loc = f"Page {ev.page_number}"
            elif ev.cell_range:
                loc = f"{ev.sheet_name or 'Sheet'}:{ev.cell_range}"
            elif ev.structural_ref:
                loc = ev.structural_ref[:18]

            snip = ev.verbatim_snippet.replace("\n", " ").strip()
            if len(snip) > 65:
                snip = snip[:65] + "..."

            row_data = [ev.evidence_id, ev.doc_id, loc, snip, "DOCUMENT_FACT"]
            y_cursor = cls._render_table_row(page, y_cursor, row_data, ev_cols, font_name, font_file)
        y_cursor += 15

        # =======================================================================
        # 9. Regulatory & Registry Verification Checks
        # =======================================================================
        page = ensure_space(70)
        y_cursor = cls._render_section_heading(page, y_cursor, "8. Regulatory Verification Status")

        ver_headers = ["Registry / Source", "Status", "Verified Item", "Finding / Local Mode Limitation"]
        ver_cols = [110, 85, 110, 210]
        y_cursor = cls._render_table_header(page, y_cursor, ver_headers, ver_cols)

        if result.verifications:
            for v in result.verifications:
                page = ensure_space(22)
                row_data = [str(v.source_type), str(v.status), v.verified_item, v.details]
                y_cursor = cls._render_table_row(page, y_cursor, row_data, ver_cols, font_name, font_file)
        else:
            page = ensure_space(22)
            row_data = ["SEBI / MCA / Exchanges", "SKIPPED_LOCAL_MODE", "All Entities", "External registry checks omitted in offline Local Mode."]
            y_cursor = cls._render_table_row(page, y_cursor, row_data, ver_cols, font_name, font_file)
        y_cursor += 20

        # =======================================================================
        # 10. Mandatory SEBI Educational & Non-Advisory Disclaimer
        # =======================================================================
        page = ensure_space(85)
        disclaimer_box = pymupdf.Rect(cls.MARGIN_LEFT, y_cursor, cls.MARGIN_RIGHT, y_cursor + 80)
        page.draw_rect(disclaimer_box, color=cls.COLOR_RED, fill=(0.99, 0.95, 0.95))

        page.insert_text(
            (cls.MARGIN_LEFT + 10, y_cursor + 16),
            "IMPORTANT STATUTORY & NON-ADVISORY REGULATORY NOTICE",
            fontsize=8.5,
            fontname=font_name,
            fontfile=font_file,
            color=cls.COLOR_RED,
        )
        notice_text = (
            "This report is generated strictly for educational financial-document understanding and comparative study. "
            "It does NOT constitute SEBI-registered investment advice, stock recommendations, buy/sell ratings, price targets, "
            "or financial suitability evaluations. Positive and negative classifications describe reported directional movements "
            "in primary document disclosures, not investment ratings. Always consult a SEBI-registered investment advisor."
        )
        page.insert_textbox(
            pymupdf.Rect(cls.MARGIN_LEFT + 10, y_cursor + 20, cls.MARGIN_RIGHT - 10, y_cursor + 75),
            notice_text,
            fontsize=7.5,
            fontname=font_name,
            fontfile=font_file,
            color=(0.3, 0.1, 0.1),
        )

        # =======================================================================
        # Apply Running Headers, Footers & Total Page Numbers
        # =======================================================================
        total_pages = len(doc)
        for idx in range(total_pages):
            p = doc[idx]
            # Top running header
            p.draw_line(
                (cls.MARGIN_LEFT, cls.TOP_MARGIN - 8),
                (cls.MARGIN_RIGHT, cls.TOP_MARGIN - 8),
                color=cls.COLOR_BORDER,
                width=0.5,
            )
            p.insert_text(
                (cls.MARGIN_LEFT, cls.TOP_MARGIN - 13),
                "Bharat Investor Copilot — Document Comparison Report",
                fontsize=7.5,
                color=(0.5, 0.55, 0.6),
            )

            # Bottom running footer
            p.draw_line(
                (cls.MARGIN_LEFT, cls.BOTTOM_MARGIN + 12),
                (cls.MARGIN_RIGHT, cls.BOTTOM_MARGIN + 12),
                color=cls.COLOR_BORDER,
                width=0.5,
            )
            footer_text = f"Confidential • For Educational Understanding Only • Page {idx + 1} of {total_pages}"
            p.insert_text(
                (cls.MARGIN_LEFT + 130, cls.BOTTOM_MARGIN + 24),
                footer_text,
                fontsize=7.5,
                color=(0.5, 0.55, 0.6),
            )

        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ---------------------------------------------------------------------------
    # Rendering Helpers
    # ---------------------------------------------------------------------------

    @classmethod
    def _render_section_heading(cls, page: pymupdf.Page, y: float, title: str) -> float:
        """Renders section header with underlying accent line."""
        page.insert_text((cls.MARGIN_LEFT, y + 12), title, fontsize=10.5, color=cls.COLOR_PRIMARY)
        page.draw_line((cls.MARGIN_LEFT, y + 16), (cls.MARGIN_RIGHT, y + 16), color=cls.COLOR_ACCENT, width=1.0)
        return y + 24

    @classmethod
    def _render_table_header(cls, page: pymupdf.Page, y: float, headers: List[str], col_widths: List[float]) -> float:
        """Renders dark header row for tables."""
        row_rect = pymupdf.Rect(cls.MARGIN_LEFT, y, cls.MARGIN_RIGHT, y + 16)
        page.draw_rect(row_rect, color=cls.COLOR_HEADER_BG, fill=cls.COLOR_HEADER_BG)

        curr_x = cls.MARGIN_LEFT + 4
        for h, w in zip(headers, col_widths):
            page.insert_text((curr_x, y + 11), h, fontsize=7.5, color=(1, 1, 1))
            curr_x += w
        return y + 18

    @classmethod
    def _render_table_row(
        cls,
        page: pymupdf.Page,
        y: float,
        row_data: List[str],
        col_widths: List[float],
        font_name: Optional[str] = None,
        font_file: Optional[str] = None,
    ) -> float:
        """Renders a single row with light border and text truncation."""
        row_rect = pymupdf.Rect(cls.MARGIN_LEFT, y, cls.MARGIN_RIGHT, y + 14)
        page.draw_rect(row_rect, color=cls.COLOR_BORDER, fill=None)

        curr_x = cls.MARGIN_LEFT + 4
        for val, w in zip(row_data, col_widths):
            val_str = str(val or "—")
            # Truncate if too long to prevent spillover
            max_chars = int(w / 4.8)
            if len(val_str) > max_chars:
                val_str = val_str[:max_chars - 2] + ".."

            try:
                page.insert_text(
                    (curr_x, y + 10),
                    val_str,
                    fontsize=7,
                    fontname=font_name,
                    fontfile=font_file,
                    color=(0.15, 0.15, 0.15),
                )
            except Exception:
                # Fallback to standard text if font encoding issue occurs on rare symbols
                page.insert_text((curr_x, y + 10), val_str.encode("ascii", "replace").decode("ascii"), fontsize=7, color=(0.15, 0.15, 0.15))

            curr_x += w
        return y + 15
