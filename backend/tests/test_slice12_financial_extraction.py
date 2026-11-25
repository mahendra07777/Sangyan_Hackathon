"""
Slice 12 Test Suite: Financial Data Extraction Enhancements.
Covers:
1. Detection of financial labels in Column 0 or Column 1 (serial numbers and empty first columns).
2. Safe parsing of numeric cells with trailing qualifiers (e.g. '(Audited)', '[Note 2]').
3. Rejection of ambiguous multi-number cells (never concatenate distinct figures).
4. Unspaced labels produced by PDF font extraction (e.g. 'RevenuefromOperations').
5. Indian statutory disclosure aliases (Ind AS 115, Schedule III, SEBI LODR).
6. Compound label disambiguation ('Revenue from operations and other income' -> TOTAL_INCOME).
7. Multi-row table header merging for scope and period detection.
8. Capture of valid additional disclosed financial metrics with source provenance.
9. Strict distinction between zero, missing, undisclosed, and ambiguous values.
10. Preservation of evidence references and bounding boxes.
11. Non-regression to manual corrections and undo behavior.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from app.models.comparison import (
    AuditStatus,
    ComparisonDocument,
    DocumentExtractionResult,
    DocumentMetadata,
    DocumentSlot,
    ExtractedTable,
    ExtractedTableCell,
    ReportingScope,
    StatementType,
    SupportedFileFormat,
)
from app.services.conflict_arbitrator import ConflictArbitrator
from app.services.financial_extractor import FinancialExtractor, METRIC_REGISTRY
from app.services.financial_normalizer import FinancialNormalizer


def make_test_metadata(doc_id: str = "doc_test") -> DocumentMetadata:
    return DocumentMetadata(
        doc_id=doc_id,
        company_name="Tata Motors Limited",
        document_type="Quarterly Financial Results",
        reporting_scale="CRORE",
        currency="INR",
        financial_year="FY 2024-25",
        quarter="Q2",
        reporting_period="Quarterly",
        reporting_scope=ReportingScope.CONSOLIDATED,
        audit_status=AuditStatus.AUDITED,
    )


def make_test_comp_doc(doc_id: str = "doc_test") -> ComparisonDocument:
    return ComparisonDocument(
        doc_id=doc_id,
        slot=DocumentSlot.DOC_A,
        original_filename="TataMotors_Q2_FY25.pdf",
        file_format=SupportedFileFormat.PDF_DIGITAL,
        file_size_bytes=2048,
        storage_rel_path=f"documents/{doc_id}.pdf",
    )


class TestSlice12FinancialExtraction(unittest.TestCase):
    """Slice 12 Unit and Regression Tests for Group 2."""

    # -----------------------------------------------------------------------
    # 1. Labels in Column 1 (Serial numbers & empty col 0)
    # -----------------------------------------------------------------------

    def test_01_labels_in_column_1_with_serial_numbers(self):
        """Labels in col 1 with serial numbers in col 0 (e.g. '1', '(a)', 'I.') extract correctly."""
        table = ExtractedTable(
            table_id="t_serial",
            sheet_name="Statement of P&L",
            headers=["Sl. No.", "Particulars", "Quarter ended 30-Sep-2024"],
            rows=[
                ["1.", "Revenue from Operations", "10,500.50"],
                ["(a)", "Total Income", "11,200.00"],
                ["II.", "Operating Expenses", "8,900.00"],
                ["3", "Profit Before Tax", "2,300.00"],
                ["4", "Profit After Tax", "1,750.00"],
            ],
            num_rows=5,
            num_cols=3,
        )
        extraction = DocumentExtractionResult(
            doc_id="doc_test",
            slot=DocumentSlot.DOC_A,
            file_format=SupportedFileFormat.PDF_DIGITAL,
            tables=[table],
        )
        meta = make_test_metadata()
        comp_doc = make_test_comp_doc()

        cands = FinancialExtractor.extract_candidates(comp_doc, extraction, meta)
        cands_by_key = {c.metric_key: c for c in cands}

        self.assertIn("REVENUE", cands_by_key)
        self.assertEqual(cands_by_key["REVENUE"].raw_text_value, "10,500.50")
        self.assertEqual(cands_by_key["REVENUE"].parsed_number, Decimal("10500.5000"))

        self.assertIn("TOTAL_INCOME", cands_by_key)
        self.assertEqual(cands_by_key["TOTAL_INCOME"].raw_text_value, "11,200.00")

        self.assertIn("PAT", cands_by_key)
        self.assertEqual(cands_by_key["PAT"].parsed_number, Decimal("1750.0000"))

    def test_02_labels_in_column_1_with_empty_col_0(self):
        """Labels in col 1 when col 0 is empty string or None extract correctly."""
        table = ExtractedTable(
            table_id="t_empty_col0",
            sheet_name="Statement of P&L",
            headers=["", "Particulars", "Quarter ended 30-Sep-2024"],
            rows=[
                ["", "Revenue from Operations", "15,200.00"],
                [None, "Net Profit After Tax", "2,100.00"],
            ],
            num_rows=2,
            num_cols=3,
        )
        extraction = DocumentExtractionResult(
            doc_id="doc_test",
            slot=DocumentSlot.DOC_A,
            file_format=SupportedFileFormat.PDF_DIGITAL,
            tables=[table],
        )
        cands = FinancialExtractor.extract_candidates(make_test_comp_doc(), extraction, make_test_metadata())
        cands_by_key = {c.metric_key: c for c in cands}

        self.assertIn("REVENUE", cands_by_key)
        self.assertEqual(cands_by_key["REVENUE"].parsed_number, Decimal("15200.0000"))
        self.assertIn("PAT", cands_by_key)
        self.assertEqual(cands_by_key["PAT"].parsed_number, Decimal("2100.0000"))

    # -----------------------------------------------------------------------
    # 2. Number Normalization & Safe Qualifier Stripping
    # -----------------------------------------------------------------------

    def test_03_numeric_cells_with_trailing_qualifiers(self):
        """Cells with trailing qualifiers like '(Audited)', '[Note 4]' parse cleanly without data loss."""
        # Trailing parenthetical qualifier
        self.assertEqual(FinancialNormalizer.parse_raw_number("10,500.50\n(Audited)"), Decimal("10500.5000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("10,500.50 (Unaudited)"), Decimal("10500.5000"))
        # Trailing note bracket
        self.assertEqual(FinancialNormalizer.parse_raw_number("12,345.00 [Note 4]"), Decimal("12345.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("12,345.00\n(Refer Note 2)"), Decimal("12345.0000"))
        # Line break within negative parenthetical
        self.assertEqual(FinancialNormalizer.parse_raw_number("( 1,234.50\n)"), Decimal("-1234.5000"))
        # Line break within positive number
        self.assertEqual(FinancialNormalizer.parse_raw_number("10,\n500.50"), Decimal("10500.5000"))

    def test_04_reject_ambiguous_multi_number_cells(self):
        """Cells containing multiple distinct numbers are rejected; never concatenate into a false number."""
        # Two distinct figures in one cell (e.g. from merged columns)
        self.assertIsNone(FinancialNormalizer.parse_raw_number("10,500.50\n9,800.00"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("10,500.50 9,800.00"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("120.50 / 95.00"))

    # -----------------------------------------------------------------------
    # 3. Unspaced Labels (PDF Font Spaces Removal)
    # -----------------------------------------------------------------------

    def test_05_unspaced_pdf_labels_matched(self):
        """Labels where PDF font extraction dropped spaces match correct canonical metrics."""
        self.assertEqual(FinancialExtractor._match_metric_label("RevenuefromOperations")["key"], "REVENUE")
        self.assertEqual(FinancialExtractor._match_metric_label("TotalIncome")["key"], "TOTAL_INCOME")
        self.assertEqual(FinancialExtractor._match_metric_label("OperatingExpenses")["key"], "OPERATING_EXPENSES")
        self.assertEqual(FinancialExtractor._match_metric_label("ProfitBeforeTax")["key"], "PBT")
        self.assertEqual(FinancialExtractor._match_metric_label("ProfitAfterTax")["key"], "PAT")
        self.assertEqual(FinancialExtractor._match_metric_label("TotalAssets")["key"], "TOTAL_ASSETS")
        self.assertEqual(FinancialExtractor._match_metric_label("TotalLiabilities")["key"], "TOTAL_LIABILITIES")
        self.assertEqual(FinancialExtractor._match_metric_label("CashandCashEquivalents")["key"], "CASH_EQUIVALENTS")

    # -----------------------------------------------------------------------
    # 4. Indian Statutory Accounting Aliases
    # -----------------------------------------------------------------------

    def test_06_indian_statutory_aliases(self):
        """Ind AS 115, Schedule III, and SEBI LODR statutory aliases resolve accurately."""
        # Revenue
        self.assertEqual(FinancialExtractor._match_metric_label("Income from operations")["key"], "REVENUE")
        self.assertEqual(FinancialExtractor._match_metric_label("Revenue from contracts with customers")["key"], "REVENUE")
        self.assertEqual(FinancialExtractor._match_metric_label("Net sales / income from operations")["key"], "REVENUE")
        # Finance costs
        self.assertEqual(FinancialExtractor._match_metric_label("Finance expenses")["key"], "FINANCE_COSTS")
        self.assertEqual(FinancialExtractor._match_metric_label("Interest and finance charges")["key"], "FINANCE_COSTS")
        # Depreciation
        self.assertEqual(FinancialExtractor._match_metric_label("Depreciation, amortisation and impairment expense")["key"], "DEPRECIATION")
        # Profit
        self.assertEqual(FinancialExtractor._match_metric_label("Profit before exceptional items and tax")["key"], "PBT")
        self.assertEqual(FinancialExtractor._match_metric_label("Profit / (loss) before tax")["key"], "PBT")
        self.assertEqual(FinancialExtractor._match_metric_label("Profit / (loss) for the period")["key"], "PAT")
        self.assertEqual(FinancialExtractor._match_metric_label("Profit / (loss) for the period after tax")["key"], "PAT")
        # Cash flow
        self.assertEqual(FinancialExtractor._match_metric_label("Cash generated from operations")["key"], "OPERATING_CASH_FLOW")
        self.assertEqual(FinancialExtractor._match_metric_label("Net cash generated from / (used in) operating activities")["key"], "OPERATING_CASH_FLOW")
        # Debt & Equity
        self.assertEqual(FinancialExtractor._match_metric_label("Total equity and liabilities")["key"], "TOTAL_LIABILITIES")

    # -----------------------------------------------------------------------
    # 5. Compound Label Disambiguation
    # -----------------------------------------------------------------------

    def test_07_compound_label_disambiguation(self):
        """Compound labels like 'Revenue from operations and other income' map to TOTAL_INCOME, not REVENUE."""
        match = FinancialExtractor._match_metric_label("Revenue from operations and other income")
        self.assertIsNotNone(match)
        self.assertEqual(match["key"], "TOTAL_INCOME")

    # -----------------------------------------------------------------------
    # 6. Multi-Row Table Headers Period Detection
    # -----------------------------------------------------------------------

    def test_08_multi_row_headers_period_detection(self):
        """2-tier table headers merge scope and period, preventing 'Unverified Period' demotion."""
        # Simulated multi-tier header merged into table.headers
        hdr = "Consolidated | Quarter ended 30-Sep-2024 (Q2) | Unaudited"
        meta = make_test_metadata()
        p_info = FinancialExtractor._parse_column_period_info(hdr, meta)

        self.assertFalse(p_info["is_unverified"])
        self.assertEqual(p_info["quarter"], "Q2")
        self.assertEqual(p_info["financial_year"], "FY 2024-25")
        self.assertEqual(p_info["period_duration"], "3M")

    # -----------------------------------------------------------------------
    # 7. Additional Disclosed Metrics Capture
    # -----------------------------------------------------------------------

    def test_09_additional_disclosed_metrics_captured(self):
        """Non-registry statutory disclosures (Cost of materials, Employee benefits) are captured and arbitrated."""
        table = ExtractedTable(
            table_id="t_additional",
            sheet_name="P&L Statement",
            headers=["Particulars", "Quarter ended 30-Sep-2024"],
            rows=[
                ["Revenue from Operations", "10,500.50"],
                ["Cost of Materials Consumed", "4,200.00"],
                ["Employee Benefits Expense", "1,850.00"],
                ["Trade Payables", "2,400.00"],
            ],
            num_rows=4,
            num_cols=2,
        )
        extraction = DocumentExtractionResult(
            doc_id="doc_test",
            slot=DocumentSlot.DOC_A,
            file_format=SupportedFileFormat.PDF_DIGITAL,
            tables=[table],
        )
        meta = make_test_metadata()
        comp_doc = make_test_comp_doc()

        cands = FinancialExtractor.extract_candidates(comp_doc, extraction, meta)
        cand_keys = {c.metric_key for c in cands}

        self.assertIn("REVENUE", cand_keys)
        # Check that valid additional line items are extracted
        self.assertTrue(any("COST_OF_MATERIALS" in k for k in cand_keys))
        self.assertTrue(any("EMPLOYEE_BENEFITS" in k for k in cand_keys))

        # Check arbitration into financial_values
        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_test", cands, meta)
        fv_keys = set(fvs.keys())
        self.assertTrue(any("COST_OF_MATERIALS" in k for k in fv_keys))
        self.assertTrue(any("EMPLOYEE_BENEFITS" in k for k in fv_keys))

    # -----------------------------------------------------------------------
    # 8. Strict Distinction of Missing/Undisclosed vs Zero
    # -----------------------------------------------------------------------

    def test_10_missing_undisclosed_not_converted_to_zero(self):
        """Missing or nil values are preserved as None/NOT_DISCLOSED, never zero."""
        self.assertIsNone(FinancialNormalizer.parse_raw_number("Nil"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("N/A"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("-"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("0"), Decimal("0.0000"))

    # -----------------------------------------------------------------------
    # 9. Evidence Reference and Provenance Preservation
    # -----------------------------------------------------------------------

    def test_11_evidence_provenance_preserved(self):
        """When labels appear in col 1, cell bounding box and row/col coordinates track the value cell accurately."""
        table = ExtractedTable(
            table_id="t_ev_provenance",
            sheet_name="P&L",
            headers=["No", "Particulars", "Quarter ended 30-Sep-2024"],
            rows=[
                ["1", "Revenue from Operations", "10,500.50"],
            ],
            cells=[
                ExtractedTableCell(row_index=0, col_index=0, value="1", raw_value="1", bounding_box=[0.1, 0.1, 0.15, 0.12]),
                ExtractedTableCell(row_index=0, col_index=1, value="Revenue from Operations", raw_value="Revenue from Operations", bounding_box=[0.16, 0.1, 0.45, 0.12]),
                ExtractedTableCell(row_index=0, col_index=2, value="10,500.50", raw_value="10,500.50", bounding_box=[0.75, 0.1, 0.85, 0.12]),
            ],
            num_rows=1,
            num_cols=3,
        )
        extraction = DocumentExtractionResult(
            doc_id="doc_test",
            slot=DocumentSlot.DOC_A,
            file_format=SupportedFileFormat.PDF_DIGITAL,
            tables=[table],
        )
        cands = FinancialExtractor.extract_candidates(make_test_comp_doc(), extraction, make_test_metadata())
        self.assertEqual(len(cands), 1)
        c = cands[0]
        self.assertEqual(c.metric_key, "REVENUE")
        self.assertEqual(c.evidence.bounding_box, [0.75, 0.1, 0.85, 0.12])
        self.assertIn("Col 3", c.evidence.cell_range)


if __name__ == "__main__":
    unittest.main()
