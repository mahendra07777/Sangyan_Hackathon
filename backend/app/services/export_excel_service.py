"""Institutional Excel workbook export service for Compare Documents (Slice 8).
Generates formatted, static 7-tab Excel workbooks using openpyxl.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

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


class ExportExcelService:
    """Produces institutional 7-tab comparative financial workbooks.

    Adheres strictly to SEBI-educational non-advisory principles.
    Static values only; zero macros; zero executable formulas.
    """

    # Color Palette (Tailwind Slate theme)
    COLOR_HEADER_BG = "1E293B"       # Dark Slate 800
    COLOR_HEADER_FG = "FFFFFF"       # White
    COLOR_SECTION_BG = "F1F5F9"      # Slate 100
    COLOR_SECTION_FG = "0F172A"      # Slate 900
    COLOR_BORDER = "CBD5E1"          # Slate 300
    COLOR_HIGHLIGHT_BG = "FEF3C7"    # Amber 100 (uncertain / warning)
    COLOR_ZEBRA_BG = "F8FAFC"        # Slate 50

    @classmethod
    def generate_comparison_workbook(cls, result: ComparisonResult) -> bytes:
        """Generates formatted 7-sheet Excel workbook from authoritative ComparisonResult."""
        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)

        # 1. Executive Summary
        ws1 = wb.create_sheet(title="Executive Summary")
        cls._populate_executive_summary(ws1, result)

        # 2. Financial Metrics
        ws2 = wb.create_sheet(title="Financial Metrics")
        cls._populate_financial_metrics(ws2, result)

        # 3. Calculations
        ws3 = wb.create_sheet(title="Calculations")
        cls._populate_calculations(ws3, result)

        # 4. Risks & Disclosures
        ws4 = wb.create_sheet(title="Risks & Disclosures")
        cls._populate_risks_disclosures(ws4, result)

        # 5. Accounting Differences
        ws5 = wb.create_sheet(title="Accounting Differences")
        cls._populate_accounting_differences(ws5, result)

        # 6. Source Evidence
        ws6 = wb.create_sheet(title="Source Evidence")
        cls._populate_source_evidence(ws6, result)

        # 7. Verification Results
        ws7 = wb.create_sheet(title="Verification Results")
        cls._populate_verification_results(ws7, result)

        # Apply Auto-column widths and auto-filters across all sheets
        for ws in wb.worksheets:
            cls._apply_sheet_dimensions(ws)

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    # ---------------------------------------------------------------------------
    # Styling Helpers
    # ---------------------------------------------------------------------------

    @classmethod
    def _get_header_font(cls, size: int = 11, bold: bool = True) -> Font:
        return Font(name="Calibri", size=size, bold=bold, color=cls.COLOR_HEADER_FG)

    @classmethod
    def _get_body_font(cls, size: int = 11, bold: bool = False, italic: bool = False, color: str = "000000") -> Font:
        return Font(name="Calibri", size=size, bold=bold, italic=italic, color=color)

    @classmethod
    def _get_header_fill(cls) -> PatternFill:
        return PatternFill(start_color=cls.COLOR_HEADER_BG, end_color=cls.COLOR_HEADER_BG, fill_type="solid")

    @classmethod
    def _get_section_fill(cls) -> PatternFill:
        return PatternFill(start_color=cls.COLOR_SECTION_BG, end_color=cls.COLOR_SECTION_BG, fill_type="solid")

    @classmethod
    def _get_thin_border(cls) -> Border:
        thin_side = Side(style="thin", color=cls.COLOR_BORDER)
        return Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    @classmethod
    def _style_header_row(cls, ws, row_idx: int, cols_count: int) -> None:
        """Applies dark slate header styling to given row."""
        header_fill = cls._get_header_fill()
        header_font = cls._get_header_font()
        border = cls._get_thin_border()
        for col in range(1, cols_count + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[row_idx].height = 28

    @classmethod
    def _apply_sheet_dimensions(cls, ws) -> None:
        """Calculates dynamic column widths clamped safely between 12 and 55."""
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if cell.number_format and "@" not in cell.number_format:
                    pass
                if len(val) > max_len and not cell.coordinate.startswith("A1"):
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(14, min(max_len + 4, 55))

    # ---------------------------------------------------------------------------
    # Sheet 1: Executive Summary
    # ---------------------------------------------------------------------------

    @classmethod
    def _populate_executive_summary(cls, ws, result: ComparisonResult) -> None:
        ws.views.sheetView[0].showGridLines = True

        # Title Block
        ws.cell(row=1, column=1, value="BHARAT INVESTOR COPILOT — COMPARATIVE DOCUMENT REPORT").font = Font(
            name="Calibri", size=15, bold=True, color="0F172A"
        )
        ws.cell(row=2, column=1, value="FOUNDATIONAL PRINCIPLE: UNDERSTANDING BEFORE ACTION").font = Font(
            name="Calibri", size=10, bold=True, color="475569"
        )
        ws.cell(row=3, column=1, value=f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Session: {result.session_id} | Mode: {result.mode}").font = Font(
            name="Calibri", size=10, italic=True, color="64748B"
        )

        # Meta details
        ws.cell(row=5, column=1, value="COMPARISON OVERVIEW & PARTICIPATING FILINGS").font = cls._get_body_font(size=12, bold=True, color="1E293B")
        ws.row_dimensions[5].height = 22

        headers = ["Slot", "Document Filename", "Company Name", "Financial Period", "Report Scope", "Accounting Standard", "Audit Status"]
        for col_idx, h in enumerate(headers, start=1):
            ws.cell(row=6, column=col_idx, value=h)
        cls._style_header_row(ws, row_idx=6, cols_count=len(headers))

        curr_row = 7
        for doc in result.documents:
            meta = result.metadata.get(doc.doc_id)
            ws.cell(row=curr_row, column=1, value=doc.slot.upper().replace("DOC_", "Doc "))
            ws.cell(row=curr_row, column=2, value=doc.original_filename)
            ws.cell(row=curr_row, column=3, value=meta.company_name if meta else "Not Identified")
            ws.cell(row=curr_row, column=4, value=meta.financial_year if meta else "Not Identified")
            ws.cell(row=curr_row, column=5, value=meta.reporting_scope if meta else "CONSOLIDATED")
            ws.cell(row=curr_row, column=6, value=meta.accounting_standard if meta else "IND_AS")
            ws.cell(row=curr_row, column=7, value=meta.audit_status if meta else "UNAUDITED")
            for c in range(1, len(headers) + 1):
                cell = ws.cell(row=curr_row, column=c)
                cell.font = cls._get_body_font(size=10)
                cell.border = cls._get_thin_border()
            curr_row += 1

        curr_row += 1
        # Compatibility Summary
        ws.cell(row=curr_row, column=1, value="DOCUMENT COMPATIBILITY EVALUATION").font = cls._get_body_font(size=12, bold=True, color="1E293B")
        curr_row += 1
        ws.cell(row=curr_row, column=1, value=f"Overall Status: {result.compatibility.overall_status}").font = cls._get_body_font(size=11, bold=True)
        curr_row += 1
        compat_desc = (
            f"Compatibility: {result.compatibility.overall_status}. Comparable: {result.compatibility.is_comparable}. "
            f"Blockers: {result.compatibility.blocker_count}, Warnings: {result.compatibility.warning_count}."
        )
        ws.cell(row=curr_row, column=1, value=compat_desc).font = cls._get_body_font(size=10)
        curr_row += 2

        # Executive Summary Observations
        ws.cell(row=curr_row, column=1, value="SYNTHESIS OBSERVATIONS & FINDINGS").font = cls._get_body_font(size=12, bold=True, color="1E293B")
        curr_row += 1

        if result.executive_summary:
            es = result.executive_summary
            ws.cell(row=curr_row, column=1, value="Overview:").font = cls._get_body_font(bold=True)
            ws.cell(row=curr_row, column=2, value=es.overview_story).font = cls._get_body_font(size=10)
            curr_row += 2

            obs_categories = [
                ("Positive Disclosed Changes", es.core_positive_changes),
                ("Negative / Pressure Disclosures", es.core_negative_changes),
                ("Neutral Structural Observations", es.neutral_observations),
                ("Uncertain Findings / Discrepancies", es.uncertain_findings),
                ("Critical Disclosed Matters", es.critical_disclosures),
            ]
            for cat_title, items in obs_categories:
                if items:
                    ws.cell(row=curr_row, column=1, value=f"{cat_title}:").font = cls._get_body_font(bold=True)
                    for item in items:
                        ws.cell(row=curr_row, column=2, value=f"• {item}").font = cls._get_body_font(size=10)
                        curr_row += 1
                    curr_row += 1
        else:
            ws.cell(row=curr_row, column=1, value="Executive summary narrative not generated.").font = cls._get_body_font(size=10, italic=True)
            curr_row += 2

        # Prominent Mandatory Disclaimer
        curr_row += 1
        disclaimer_cell = ws.cell(row=curr_row, column=1, value=f"IMPORTANT REGULATORY NOTICE: {result.safety_disclaimer}")
        disclaimer_cell.font = cls._get_body_font(size=9, bold=True, italic=True, color="991B1B")
        ws.row_dimensions[curr_row].height = 40

    # ---------------------------------------------------------------------------
    # Sheet 2: Financial Metrics
    # ---------------------------------------------------------------------------

    @classmethod
    def _populate_financial_metrics(cls, ws, result: ComparisonResult) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        headers = [
            "Metric Key",
            "Metric Label",
            "Document Slot",
            "Document Name",
            "Company Name",
            "Reporting Period",
            "Original Reported Value",
            "Original Currency",
            "Original Scale / Unit",
            "Normalized Amount (INR Cr)",
            "Metric Status",
            "Selected Candidate ID",
            "Evidence ID",
            "Source Location",
        ]
        for col_idx, h in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=h)
        cls._style_header_row(ws, row_idx=1, cols_count=len(headers))

        row_idx = 2
        for metric_key, doc_map in result.financial_values.items():
            for doc_id, fval in doc_map.items():
                target_doc = next((d for d in result.documents if d.doc_id == doc_id), None)
                meta = result.metadata.get(doc_id)

                loc_str = "Unavailable"
                ev_id = "None"
                if fval.evidence:
                    ev_id = fval.evidence.evidence_id
                    if fval.evidence.page_number:
                        loc_str = f"Page {fval.evidence.page_number}"
                    elif fval.evidence.cell_range:
                        loc_str = f"{fval.evidence.sheet_name or 'Sheet'}:{fval.evidence.cell_range}"
                    elif fval.evidence.structural_ref:
                        loc_str = fval.evidence.structural_ref

                # Original reported amount preserved
                orig_reported = str(fval.reported_amount) if fval.reported_amount is not None else (fval.display_amount or "NOT_DISCLOSED")
                norm_val = float(fval.amount) if fval.amount is not None else None

                ws.cell(row=row_idx, column=1, value=metric_key)
                ws.cell(row=row_idx, column=2, value=fval.label)
                ws.cell(row=row_idx, column=3, value=target_doc.slot.upper().replace("DOC_", "Doc ") if target_doc else doc_id)
                ws.cell(row=row_idx, column=4, value=target_doc.original_filename if target_doc else doc_id)
                ws.cell(row=row_idx, column=5, value=meta.company_name if meta else "Not Identified")
                ws.cell(row=row_idx, column=6, value=meta.financial_year if meta else "FY")
                ws.cell(row=row_idx, column=7, value=orig_reported)
                ws.cell(row=row_idx, column=8, value=fval.reported_currency or fval.currency)
                ws.cell(row=row_idx, column=9, value=fval.reported_scale or fval.unit)
                
                # Normalized amount (number cell if available)
                cell_norm = ws.cell(row=row_idx, column=10, value=norm_val if norm_val is not None else "NOT_DISCLOSED")
                if norm_val is not None:
                    cell_norm.number_format = "#,##0.00"

                status_val = "USER_ENTERED" if getattr(fval, "is_user_corrected", False) else fval.status
                ws.cell(row=row_idx, column=11, value=status_val)
                ws.cell(row=row_idx, column=12, value=fval.selected_candidate_id or "Direct")
                ws.cell(row=row_idx, column=13, value=ev_id)
                ws.cell(row=row_idx, column=14, value=loc_str)

                border = cls._get_thin_border()
                for c in range(1, len(headers) + 1):
                    ws.cell(row=row_idx, column=c).border = border
                    ws.cell(row=row_idx, column=c).font = cls._get_body_font(size=10)

                row_idx += 1

        ws.auto_filter.ref = f"A1:N{max(2, row_idx - 1)}"

    # ---------------------------------------------------------------------------
    # Sheet 3: Calculations
    # ---------------------------------------------------------------------------

    @classmethod
    def _populate_calculations(cls, ws, result: ComparisonResult) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        headers = [
            "Metric Key",
            "Metric Label",
            "Base Filing",
            "Base Value",
            "Comparison Filing",
            "Comparison Value",
            "Absolute Variance",
            "Percentage Change (%)",
            "Calculation Status",
            "Formula Description",
            "Directional / Incompatibility Explanation",
        ]
        for col_idx, h in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=h)
        cls._style_header_row(ws, row_idx=1, cols_count=len(headers))

        row_idx = 2
        for v in result.variances:
            base_meta = result.metadata.get(v.base_doc_id)
            comp_meta = result.metadata.get(v.comparison_doc_id)

            base_lbl = f"{base_meta.company_name} ({base_meta.financial_year})" if base_meta else v.base_doc_id
            comp_lbl = f"{comp_meta.company_name} ({comp_meta.financial_year})" if comp_meta else v.comparison_doc_id

            abs_val = float(v.absolute_variance) if v.absolute_variance is not None else None
            pct_val = float(v.percentage_change) if v.percentage_change is not None else None

            ws.cell(row=row_idx, column=1, value=v.metric_key)
            ws.cell(row=row_idx, column=2, value=v.label)
            ws.cell(row=row_idx, column=3, value=base_lbl)
            ws.cell(row=row_idx, column=4, value=float(v.base_value) if v.base_value is not None else "NOT_DISCLOSED")
            ws.cell(row=row_idx, column=5, value=comp_lbl)
            ws.cell(row=row_idx, column=6, value=float(v.comparison_value) if v.comparison_value is not None else "NOT_DISCLOSED")
            
            # Numeric absolute variance
            cell_abs = ws.cell(row=row_idx, column=7, value=abs_val if abs_val is not None else "N/A")
            if abs_val is not None:
                cell_abs.number_format = "#,##0.00"

            # Numeric or text percentage change
            cell_pct = ws.cell(row=row_idx, column=8, value=pct_val if pct_val is not None else (v.display_percentage_change or "N/A"))
            if pct_val is not None:
                cell_pct.number_format = "0.00%"

            ws.cell(row=row_idx, column=9, value=v.status)
            ws.cell(row=row_idx, column=10, value=f"'{v.formula}")  # Prevent executable formula
            ws.cell(row=row_idx, column=11, value=v.directional_explanation or "Standard mathematical comparison")

            border = cls._get_thin_border()
            for c in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=c).border = border
                ws.cell(row=row_idx, column=c).font = cls._get_body_font(size=10)

            row_idx += 1

        ws.auto_filter.ref = f"A1:K{max(2, row_idx - 1)}"

    # ---------------------------------------------------------------------------
    # Sheet 4: Risks & Disclosures
    # ---------------------------------------------------------------------------

    @classmethod
    def _populate_risks_disclosures(cls, ws, result: ComparisonResult) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        headers = [
            "Risk ID",
            "Risk Title",
            "Category",
            "Severity Flag",
            "Filing Source",
            "Disclosure Text",
            "Fact Classification",
            "Audit Status",
            "Evidence ID",
            "Location Context",
        ]
        for col_idx, h in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=h)
        cls._style_header_row(ws, row_idx=1, cols_count=len(headers))

        row_idx = 2
        for r in result.risks:
            doc = next((d for d in result.documents if d.doc_id == r.doc_id), None)
            loc = "Unavailable"
            ev_id = "None"
            if r.evidence:
                ev_id = r.evidence.evidence_id
                loc = f"Page {r.evidence.page_number}" if r.evidence.page_number else (r.evidence.structural_ref or "Excerpt")

            ws.cell(row=row_idx, column=1, value=r.risk_id)
            ws.cell(row=row_idx, column=2, value=r.title)
            ws.cell(row=row_idx, column=3, value=r.category)
            ws.cell(row=row_idx, column=4, value=r.severity)
            ws.cell(row=row_idx, column=5, value=doc.original_filename if doc else r.doc_id)
            ws.cell(row=row_idx, column=6, value=r.disclosure_text)
            ws.cell(row=row_idx, column=7, value=str(r.fact_classification))
            ws.cell(row=row_idx, column=8, value=r.audit_status or "DISCLOSED")
            ws.cell(row=row_idx, column=9, value=ev_id)
            ws.cell(row=row_idx, column=10, value=loc)

            border = cls._get_thin_border()
            for c in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=c).border = border
                ws.cell(row=row_idx, column=c).font = cls._get_body_font(size=10)

            row_idx += 1

        ws.auto_filter.ref = f"A1:J{max(2, row_idx - 1)}"

    # ---------------------------------------------------------------------------
    # Sheet 5: Accounting Differences
    # ---------------------------------------------------------------------------

    @classmethod
    def _populate_accounting_differences(cls, ws, result: ComparisonResult) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        headers = [
            "Difference ID",
            "Accounting Policy Topic",
            "Filing A Disclosed Policy",
            "Filing B Disclosed Policy",
            "Variance / Divergence Summary",
            "Fact Classification",
            "Filing A Audit Status",
            "Filing B Audit Status",
            "Evidence Citations",
        ]
        for col_idx, h in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=h)
        cls._style_header_row(ws, row_idx=1, cols_count=len(headers))

        row_idx = 2
        for ad in result.accounting_differences:
            ev_str = f"EvA: {ad.evidence_a.evidence_id if ad.evidence_a else 'N/A'} | EvB: {ad.evidence_b.evidence_id if ad.evidence_b else 'N/A'}"

            ws.cell(row=row_idx, column=1, value=ad.difference_id)
            ws.cell(row=row_idx, column=2, value=ad.topic)
            ws.cell(row=row_idx, column=3, value=ad.doc_a_policy)
            ws.cell(row=row_idx, column=4, value=ad.doc_b_policy)
            ws.cell(row=row_idx, column=5, value=ad.impact_summary)
            ws.cell(row=row_idx, column=6, value=str(ad.fact_classification))
            ws.cell(row=row_idx, column=7, value=ad.audit_status_a or "UNAUDITED")
            ws.cell(row=row_idx, column=8, value=ad.audit_status_b or "UNAUDITED")
            ws.cell(row=row_idx, column=9, value=ev_str)

            border = cls._get_thin_border()
            for c in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=c).border = border
                ws.cell(row=row_idx, column=c).font = cls._get_body_font(size=10)

            row_idx += 1

        ws.auto_filter.ref = f"A1:I{max(2, row_idx - 1)}"

    # ---------------------------------------------------------------------------
    # Sheet 6: Source Evidence
    # ---------------------------------------------------------------------------

    @classmethod
    def _populate_source_evidence(cls, ws, result: ComparisonResult) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        headers = [
            "Evidence ID",
            "Document ID",
            "Document Filename",
            "Page Number",
            "Section / Heading Reference",
            "Spreadsheet Sheet",
            "Cell Reference",
            "Verbatim Text Excerpt",
            "Table Context",
            "Provenance Classification",
        ]
        for col_idx, h in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=h)
        cls._style_header_row(ws, row_idx=1, cols_count=len(headers))

        # Collect and deduplicate all evidence references
        collected_evidence: Dict[str, EvidenceReference] = {}

        # 1. From financial values
        for metric_key, doc_map in result.financial_values.items():
            for doc_id, fval in doc_map.items():
                if fval.evidence and fval.evidence.evidence_id not in collected_evidence:
                    collected_evidence[fval.evidence.evidence_id] = fval.evidence

        # 2. From risks
        for r in result.risks:
            if r.evidence and r.evidence.evidence_id not in collected_evidence:
                collected_evidence[r.evidence.evidence_id] = r.evidence

        # 3. From accounting differences
        for ad in result.accounting_differences:
            if ad.evidence_a and ad.evidence_a.evidence_id not in collected_evidence:
                collected_evidence[ad.evidence_a.evidence_id] = ad.evidence_a
            if ad.evidence_b and ad.evidence_b.evidence_id not in collected_evidence:
                collected_evidence[ad.evidence_b.evidence_id] = ad.evidence_b

        row_idx = 2
        for ev_id, ev in sorted(collected_evidence.items()):
            ws.cell(row=row_idx, column=1, value=ev.evidence_id)
            ws.cell(row=row_idx, column=2, value=ev.doc_id)
            ws.cell(row=row_idx, column=3, value=ev.document_name)
            ws.cell(row=row_idx, column=4, value=ev.page_number if ev.page_number is not None else "N/A")
            ws.cell(row=row_idx, column=5, value=ev.structural_ref or "N/A")
            ws.cell(row=row_idx, column=6, value=ev.sheet_name or "N/A")
            ws.cell(row=row_idx, column=7, value=ev.cell_range or "N/A")
            ws.cell(row=row_idx, column=8, value=ev.verbatim_snippet)
            ws.cell(row=row_idx, column=9, value=ev.table_context or "N/A")
            ws.cell(row=row_idx, column=10, value="DOCUMENT_FACT")

            border = cls._get_thin_border()
            for c in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=c).border = border
                ws.cell(row=row_idx, column=c).font = cls._get_body_font(size=10)

            row_idx += 1

        ws.auto_filter.ref = f"A1:J{max(2, row_idx - 1)}"

    # ---------------------------------------------------------------------------
    # Sheet 7: Verification Results
    # ---------------------------------------------------------------------------

    @classmethod
    def _populate_verification_results(cls, ws, result: ComparisonResult) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        headers = [
            "Source Registry / Authority",
            "Verification Status",
            "Verified Item",
            "Verification Outcome / Details",
            "Source URL / Reference",
            "Verification Timestamp",
            "Data Provenance Notice",
        ]
        for col_idx, h in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=h)
        cls._style_header_row(ws, row_idx=1, cols_count=len(headers))

        row_idx = 2
        for v in result.verifications:
            time_str = v.retrieved_at.strftime("%Y-%m-%d %H:%M:%S") if v.retrieved_at else "Offline"
            prov_notice = "Simulated / Local Mode only; not checked against external live registry" if v.status == "SIMULATED" or v.status == "SKIPPED_LOCAL_MODE" else "Live registry check"

            ws.cell(row=row_idx, column=1, value=str(v.source_type))
            ws.cell(row=row_idx, column=2, value=str(v.status))
            ws.cell(row=row_idx, column=3, value=v.verified_item)
            ws.cell(row=row_idx, column=4, value=v.details)
            ws.cell(row=row_idx, column=5, value=v.source_url or "Local Offline Environment")
            ws.cell(row=row_idx, column=6, value=time_str)
            ws.cell(row=row_idx, column=7, value=prov_notice)

            border = cls._get_thin_border()
            for c in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=c).border = border
                ws.cell(row=row_idx, column=c).font = cls._get_body_font(size=10)

            row_idx += 1

        # Fallback note if no verification records
        if not result.verifications:
            ws.cell(row=row_idx, column=1, value="LOCAL_OFFLINE")
            ws.cell(row=row_idx, column=2, value="SKIPPED_LOCAL_MODE")
            ws.cell(row=row_idx, column=3, value="All Entities")
            ws.cell(row=row_idx, column=4, value="External registry lookups skipped in offline Local Mode.")
            ws.cell(row=row_idx, column=5, value="N/A")
            ws.cell(row=row_idx, column=6, value=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            ws.cell(row=row_idx, column=7, value="Offline privacy preservation guarantee")
            row_idx += 1

        ws.auto_filter.ref = f"A1:G{max(2, row_idx - 1)}"
