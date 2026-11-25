"""Comprehensive Unit and Regression Tests for Repair Group 3: Metadata Correction.

Covers all 10 audit scenarios:
1. Uppercase company names (TATA MOTORS LIMITED, INFOSYS LIMITED, etc.)
2. CIN proximity uppercase company detection
3. Company suffixes with parentheses and variations (Siemens (India) Limited, Pvt Ltd, LLP)
4. Rejection of compound adjectives as industry (industry-leading profitability, etc.)
5. Valid industry and sector extraction
6. Missing metadata representation
7. Reporting scope: Standalone with incidental consolidated mentions in notes
8. Reporting scope from table headers
9. Document type: Quarterly results referencing previous Annual Report in footnotes
10. Explain Document (LocalExplanationEngine): uppercase company and accurate scope without hardcoded fallbacks
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
    DocumentType,
    ExtractedTable,
    ExtractedTextBlock,
    ReportingPeriodType,
    ReportingScope,
    SupportedFileFormat,
)
from app.services.document_processor import LocalExplanationEngine
from app.services.metadata_extractor import MetadataExtractor


def make_comp_doc(doc_id: str = "doc_test", filename: str = "filing.pdf") -> ComparisonDocument:
    return ComparisonDocument(
        doc_id=doc_id,
        slot=DocumentSlot.DOC_A,
        original_filename=filename,
        file_format=SupportedFileFormat.PDF_DIGITAL,
        file_size_bytes=1024,
        storage_rel_path=f"documents/{filename}",
    )


def make_extraction(
    texts: list[str] = None,
    tables: list[ExtractedTable] = None,
    doc_id: str = "doc_test",
) -> DocumentExtractionResult:
    text_blocks = []
    if texts:
        for idx, t in enumerate(texts):
            text_blocks.append(
                ExtractedTextBlock(
                    block_id=f"{doc_id}_b{idx}",
                    page_number=1,
                    text=t,
                    structural_ref=f"Paragraph {idx + 1}",
                )
            )

    return DocumentExtractionResult(
        doc_id=doc_id,
        slot=DocumentSlot.DOC_A,
        file_format=SupportedFileFormat.PDF_DIGITAL,
        page_count=2,
        is_scanned=False,
        extraction_status="SUCCESS",
        tables=tables or [],
        text_blocks=text_blocks,
        raw_word_count=sum(len(t.split()) for t in (texts or [])),
    )


class TestSlice13MetadataCorrection(unittest.TestCase):
    """Regression test suite for Repair Group 3 metadata fixes."""

    # -----------------------------------------------------------------------
    # 1. Uppercase Company Names
    # -----------------------------------------------------------------------

    def test_01_uppercase_company_names(self):
        """Uppercase company names in corporate filings must be accurately extracted."""
        test_cases = [
            ("TATA MOTORS LIMITED\nFinancial Results", "TATA MOTORS LIMITED"),
            ("INFOSYS LIMITED\nBengaluru, India", "INFOSYS LIMITED"),
            ("HDFC BANK LIMITED\nRegistered Office", "HDFC BANK LIMITED"),
            ("RELIANCE INDUSTRIES LIMITED\nMaker Chambers IV", "RELIANCE INDUSTRIES LIMITED"),
        ]
        for text, expected in test_cases:
            cdoc = make_comp_doc(filename="filing.pdf")
            ext = make_extraction(texts=[text])
            meta = MetadataExtractor.extract_metadata(cdoc, ext)
            self.assertEqual(meta.company_name, expected, f"Failed for {text}")

    # -----------------------------------------------------------------------
    # 2. CIN Proximity Detection
    # -----------------------------------------------------------------------

    def test_02_cin_proximity_uppercase_detection(self):
        """Company name placed directly above or near CIN in uppercase must be identified."""
        cdoc = make_comp_doc(filename="results.pdf")
        ext = make_extraction(
            texts=[
                "BHARTI AIRTEL LIMITED\nCIN: L74899HR1995PLC095967\nRegistered Office: Airtel Center, Gurugram",
            ]
        )
        meta = MetadataExtractor.extract_metadata(cdoc, ext)
        self.assertEqual(meta.company_name, "BHARTI AIRTEL LIMITED")
        self.assertEqual(meta.company_identifier, "L74899HR1995PLC095967")

    # -----------------------------------------------------------------------
    # 3. Company Suffix Variations & Parentheses
    # -----------------------------------------------------------------------

    def test_03_company_suffixes_with_parentheses_and_variations(self):
        """Handles (India) Limited, Pvt Ltd, LLP, and parentheses in company titles."""
        test_cases = [
            ("Siemens (India) Limited", "Siemens (India) Limited"),
            ("NESTLE INDIA LIMITED", "NESTLE INDIA LIMITED"),
            ("Maruti Suzuki India Limited", "Maruti Suzuki India Limited"),
            ("ABC HEALTHCARE PRIVATE LIMITED", "ABC HEALTHCARE PRIVATE LIMITED"),
            ("XYZ ADVISORY SERVICES LLP", "XYZ ADVISORY SERVICES LLP"),
            ("TATA CONSULTANCY SERVICES LTD.", "TATA CONSULTANCY SERVICES LTD"),
        ]
        for text, expected_prefix in test_cases:
            cdoc = make_comp_doc(filename="filing.pdf")
            ext = make_extraction(texts=[text])
            meta = MetadataExtractor.extract_metadata(cdoc, ext)
            self.assertTrue(
                meta.company_name.upper().startswith(expected_prefix.upper()) or expected_prefix.upper() in meta.company_name.upper(),
                f"Expected '{expected_prefix}' in '{meta.company_name}'",
            )

    # -----------------------------------------------------------------------
    # 4. Industry: Rejection of False Compound Adjectives
    # -----------------------------------------------------------------------

    def test_04_industry_rejects_compound_adjectives(self):
        """Compound adjectives like 'industry-leading profitability' must not be captured as industry."""
        corpus = [
            "Chairman's Statement",
            "The company delivered industry-leading profitability and strong cash conversion across all product lines.",
            "Our industry-standard margins reflect robust operational efficiencies.",
            "We navigated a sector-wide slowdown with resilience.",
        ]
        cdoc = make_comp_doc(filename="annual_review.pdf")
        ext = make_extraction(texts=corpus)
        meta = MetadataExtractor.extract_metadata(cdoc, ext)
        self.assertNotIn("leading profitability", (meta.industry or "").lower())
        self.assertNotIn("standard margins", (meta.industry or "").lower())
        self.assertNotIn("wide slowdown", (meta.industry or "").lower())
        self.assertEqual(meta.industry, "UNKNOWN")

    # -----------------------------------------------------------------------
    # 5. Industry: Genuine Disclosures Captured
    # -----------------------------------------------------------------------

    def test_05_industry_valid_extraction(self):
        """Explicit industry disclosures are captured with provenance."""
        test_cases = [
            ("Industry: Automobiles & Auto Components", "Automobiles & Auto Components"),
            ("Sector: Information Technology", "Information Technology"),
            ("Primary Business Segment: Commercial Vehicles", "Commercial Vehicles"),
            ("Operating Segment: Banking & Financial Services", "Banking & Financial Services"),
        ]
        for text, expected in test_cases:
            cdoc = make_comp_doc(filename="filing.pdf")
            ext = make_extraction(texts=["Overview", text])
            meta = MetadataExtractor.extract_metadata(cdoc, ext)
            self.assertEqual(meta.industry, expected)
            self.assertIn("industry", meta.evidence_sources)

    # -----------------------------------------------------------------------
    # 6. Missing Metadata Representation
    # -----------------------------------------------------------------------

    def test_06_missing_metadata_defaults(self):
        """When metadata is missing, internal defaults represent unknown without crashes."""
        cdoc = make_comp_doc(filename="unknown_filing.pdf")
        ext = make_extraction(texts=["Just some general text without corporate markers."])
        meta = MetadataExtractor.extract_metadata(cdoc, ext)
        self.assertEqual(meta.company_name, "Unknown")
        self.assertEqual(meta.industry, "UNKNOWN")
        self.assertIsNone(meta.company_identifier)

    # -----------------------------------------------------------------------
    # 7. Reporting Scope: Standalone with Incidental Consolidated Mention
    # -----------------------------------------------------------------------

    def test_07_reporting_scope_standalone_with_consolidated_notes(self):
        """Standalone document with incidental footnote mention of 'consolidated' must be STANDALONE, not BOTH."""
        table = ExtractedTable(
            table_id="t1",
            title="Statement of Standalone Audited Financial Results",
            headers=["Particulars", "30-Sep-2024"],
            rows=[["Revenue from operations", "5,000"]],
            num_rows=1,
            num_cols=2,
        )
        texts = [
            "Statement of Standalone Audited Financial Results for the Quarter Ended September 30, 2024",
            "Note 1: The Company has prepared standalone results. Consolidated figures are published separately.",
            "Auditor's report on standalone financial results.",
        ]
        cdoc = make_comp_doc(filename="standalone_q2.pdf")
        ext = make_extraction(texts=texts, tables=[table])
        meta = MetadataExtractor.extract_metadata(cdoc, ext)
        self.assertEqual(meta.reporting_scope, ReportingScope.STANDALONE)

    # -----------------------------------------------------------------------
    # 8. Reporting Scope from Table Headers
    # -----------------------------------------------------------------------

    def test_08_reporting_scope_from_table_headers(self):
        """When scope is present in table headers, it is correctly identified even if table.title is None."""
        table = ExtractedTable(
            table_id="t1",
            title=None,
            headers=["Particulars", "Standalone | 30-Sep-2024", "Standalone | 30-Jun-2024"],
            rows=[["Revenue", "1,000", "900"]],
            num_rows=1,
            num_cols=3,
        )
        texts = ["Financial Results for the Quarter Ended September 30, 2024"]
        cdoc = make_comp_doc(filename="q2.pdf")
        ext = make_extraction(texts=texts, tables=[table])
        meta = MetadataExtractor.extract_metadata(cdoc, ext)
        self.assertEqual(meta.reporting_scope, ReportingScope.STANDALONE)

    # -----------------------------------------------------------------------
    # 9. Document Type: Quarterly not Overridden by Annual Report Reference
    # -----------------------------------------------------------------------

    def test_09_document_type_quarterly_not_overridden(self):
        """A quarterly filing referencing prior Annual Report in footnotes remains QUARTERLY_RESULTS."""
        texts = [
            "UNAUDITED FINANCIAL RESULTS FOR THE QUARTER ENDED 30TH SEPTEMBER 2024",
            "Limited Review Report on Quarterly Financial Results",
            "Note 3: Accounting policies are consistent with those in the latest Annual Report for FY2023-24.",
        ]
        cdoc = make_comp_doc(filename="Q2_Results.pdf")
        ext = make_extraction(texts=texts)
        meta = MetadataExtractor.extract_metadata(cdoc, ext)
        self.assertEqual(meta.document_type, DocumentType.QUARTERLY_RESULTS.value)

    # -----------------------------------------------------------------------
    # 10. Explain Document (LocalExplanationEngine) Company & Scope
    # -----------------------------------------------------------------------

    def test_10_explain_document_local_engine(self):
        """LocalExplanationEngine detects uppercase company names without 'Corporate Entity' and handles scope."""
        text = (
            "TATA MOTORS LIMITED\n"
            "CIN: L28920MH1945PLC004520\n"
            "Statement of Standalone Audited Financial Results for the Quarter ended 30-Sep-2024\n"
            "Revenue from operations: 10,500.50 Crores\n"
            "Net Profit: 1,200.00 Crores\n"
        )
        detected_company = LocalExplanationEngine._detect_company(text)
        self.assertEqual(detected_company, "TATA MOTORS LIMITED")
        self.assertNotEqual(detected_company, "Corporate Entity")

        detected_scope = LocalExplanationEngine._detect_scope(text)
        self.assertEqual(detected_scope, "Standalone")


if __name__ == "__main__":
    unittest.main()
