"""Comprehensive automated test suite for Compare Documents Slice 3:
Document Identification and Compatibility Matrix Engine.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
import openpyxl
import pymupdf

from app.models.comparison import (
    AuditStatus,
    CompatibilityReport,
    CompatibilityStatus,
    ComparisonDocument,
    DocumentExtractionResult,
    DocumentMetadata,
    DocumentSlot,
    DocumentType,
    ExtractedTable,
    ExtractedTextBlock,
    IssueSeverity,
    ReportingPeriodType,
    ReportingScope,
    SupportedFileFormat,
)
from app.services.comparison_session_store import session_store
from app.services.compatibility_engine import CompatibilityEngine
from app.services.financial_normalizer import FinancialNormalizer
from app.services.metadata_extractor import MetadataExtractor
from main import app

client = TestClient(app)


def create_sample_extraction(
    doc_id: str = "doc_a",
    slot: DocumentSlot = DocumentSlot.DOC_A,
    texts: list[str] = None,
    headers: list[str] = None,
    is_scanned: bool = False,
    status_tag: str = "SUCCESS",
) -> DocumentExtractionResult:
    """Helper to generate DocumentExtractionResult for testing metadata extraction."""
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

    tables = []
    if headers:
        tables.append(
            ExtractedTable(
                table_id=f"{doc_id}_tbl_1",
                page_number=1,
                num_rows=2,
                num_cols=len(headers),
                headers=headers,
                rows=[headers, ["1000", "200"]],
            )
        )

    return DocumentExtractionResult(
        doc_id=doc_id,
        slot=slot,
        file_format=SupportedFileFormat.PDF_DIGITAL if not is_scanned else SupportedFileFormat.PDF_SCANNED,
        page_count=2,
        is_scanned=is_scanned,
        extraction_status=status_tag,
        tables=tables,
        text_blocks=text_blocks,
        raw_word_count=sum(len(t.split()) for t in (texts or [])),
    )


def create_synthetic_pdf(text_header: str, table_headers: list[str] = None) -> bytes:
    """Create a minimal PyMuPDF PDF with custom metadata headers."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(50, 50), text_header, fontsize=12)
    if table_headers:
        page.insert_text(pymupdf.Point(50, 150), " | ".join(table_headers), fontsize=10)
    # Add sufficient filler text so it is recognized as digital PDF (>50 words)
    filler = "Financial statements statement of profit and loss balance sheet assets liabilities " * 10
    page.insert_text(pymupdf.Point(50, 200), filler, fontsize=8)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestSlice3MetadataCompatibility(unittest.TestCase):
    """Slice 3 Unit and Integration Tests."""

    # -----------------------------------------------------------------------
    # 1. Metadata Extraction Category Tests
    # -----------------------------------------------------------------------

    def test_company_identification_with_cin(self) -> None:
        """Verify company name and explicit CIN identification."""
        extraction = create_sample_extraction(
            texts=[
                "Tata Motors Limited",
                "CIN: L28920MH1945PLC004520",
                "Registered Office: Bombay House, 24 Homi Mody Street, Mumbai",
            ]
        )
        comp_doc = session_store.create_session()[0] # dummy session
        from app.models.comparison import ComparisonDocument
        cdoc = ComparisonDocument(
            doc_id="doc_a",
            slot=DocumentSlot.DOC_A,
            original_filename="TataMotors_Q3.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024,
            storage_rel_path="documents/doc_a.pdf",
        )

        meta = MetadataExtractor.extract_metadata(cdoc, extraction)
        self.assertEqual(meta.company_name, "Tata Motors Limited")
        self.assertEqual(meta.company_identifier, "L28920MH1945PLC004520")
        self.assertIn("TML", meta.alternative_names)
        self.assertIn("company_name", meta.evidence_sources)
        self.assertEqual(meta.confidence_category, "HIGH")

    def test_document_type_distinctions_drhp_rhp_prospectus(self) -> None:
        """Verify strict distinction between DRHP, RHP, and Final Prospectus."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A,
            original_filename="Filing.pdf", file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        # DRHP
        ext_drhp = create_sample_extraction(texts=["Draft Red Herring Prospectus dated October 12, 2023"])
        meta_drhp = MetadataExtractor.extract_metadata(cdoc, ext_drhp)
        self.assertEqual(meta_drhp.document_type, DocumentType.DRAFT_RED_HERRING_PROSPECTUS.value)

        # RHP
        ext_rhp = create_sample_extraction(texts=["Red Herring Prospectus with Book Building Issue"])
        meta_rhp = MetadataExtractor.extract_metadata(cdoc, ext_rhp)
        self.assertEqual(meta_rhp.document_type, DocumentType.RED_HERRING_PROSPECTUS.value)

        # Final Prospectus
        ext_prosp = create_sample_extraction(texts=["Initial Public Offer Prospectus filed with RoC"])
        meta_prosp = MetadataExtractor.extract_metadata(cdoc, ext_prosp)
        self.assertEqual(meta_prosp.document_type, DocumentType.IPO_PROSPECTUS.value)

    def test_financial_year_explicit_vs_inferred(self) -> None:
        """Verify canonical FY2023-24 extraction and inferred single year tracking."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A, original_filename="Report.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL, file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        # Explicit FY 2023-24
        ext_explicit = create_sample_extraction(texts=["Financial Results for the year FY 2023-24"])
        meta_exp = MetadataExtractor.extract_metadata(cdoc, ext_explicit)
        self.assertEqual(meta_exp.financial_year, "FY 2023-24")
        self.assertEqual(meta_exp.fy_start, "2023-04-01")
        self.assertEqual(meta_exp.fy_end, "2024-03-31")
        self.assertFalse(meta_exp.is_inferred_year)

        # Inferred FY24
        ext_inferred = create_sample_extraction(texts=["Highlights for FY24 Performance"])
        meta_inf = MetadataExtractor.extract_metadata(cdoc, ext_inferred)
        self.assertEqual(meta_inf.financial_year, "FY 2023-24")
        self.assertTrue(meta_inf.is_inferred_year)

    def test_reporting_period_and_quarter_identification(self) -> None:
        """Verify quarter (Q1-Q4) and period date detection."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A, original_filename="Report.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL, file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        ext_q3 = create_sample_extraction(texts=["Financial Results for the quarter ended December 31, 2023"])
        meta_q3 = MetadataExtractor.extract_metadata(cdoc, ext_q3)
        self.assertEqual(meta_q3.reporting_period, ReportingPeriodType.QUARTERLY.value)
        self.assertEqual(meta_q3.quarter, "Q3")
        self.assertEqual(meta_q3.period_end_date, "2023-12-31")

        ext_annual = create_sample_extraction(texts=["Annual Report 2023-24"])
        meta_ann = MetadataExtractor.extract_metadata(cdoc, ext_annual)
        self.assertEqual(meta_ann.reporting_period, ReportingPeriodType.ANNUAL.value)
        self.assertIsNone(meta_ann.quarter)

    def test_currency_and_scale_identification(self) -> None:
        """Verify currency (INR/USD) and scale (Crore/Lakh/Units) detection."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A, original_filename="Report.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL, file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        # INR in Crores
        ext_inr = create_sample_extraction(
            texts=["Statement of Profit and Loss (Rs. in Crores)"],
            headers=["Particulars", "Quarter ended Dec 31, 2023 (Rs. in Cr)"],
        )
        meta_inr = MetadataExtractor.extract_metadata(cdoc, ext_inr)
        self.assertEqual(meta_inr.currency, "INR")
        self.assertEqual(meta_inr.reporting_scale, "CRORE")

        # USD in Millions
        ext_usd = create_sample_extraction(
            texts=["Consolidated Financial Results (in USD Millions)"],
            headers=["Line Item", "Amount ($ in Millions)"],
        )
        meta_usd = MetadataExtractor.extract_metadata(cdoc, ext_usd)
        self.assertEqual(meta_usd.currency, "USD")
        self.assertEqual(meta_usd.reporting_scale, "MILLION")

    def test_accounting_standard_identification(self) -> None:
        """Verify Ind AS vs Indian GAAP vs IFRS identification."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A, original_filename="Report.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL, file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        ext_ind_as = create_sample_extraction(texts=["Prepared in accordance with Indian Accounting Standards (Ind AS) Rules, 2015"])
        meta_ind_as = MetadataExtractor.extract_metadata(cdoc, ext_ind_as)
        self.assertEqual(meta_ind_as.accounting_standard, "Ind AS")

        ext_us_gaap = create_sample_extraction(texts=["Statements prepared in conformity with US GAAP"])
        meta_us_gaap = MetadataExtractor.extract_metadata(cdoc, ext_us_gaap)
        self.assertEqual(meta_us_gaap.accounting_standard, "US GAAP")

    def test_audit_status_limited_review_vs_audit(self) -> None:
        """Verify Limited Review is not confused with a full audit."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A, original_filename="Report.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL, file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        ext_lr = create_sample_extraction(texts=["Independent Auditor's Limited Review Report on Quarterly Financial Results"])
        meta_lr = MetadataExtractor.extract_metadata(cdoc, ext_lr)
        self.assertEqual(meta_lr.audit_status, AuditStatus.LIMITED_REVIEW)

        ext_aud = create_sample_extraction(texts=["Independent Auditor's Report on Annual Financial Statements"])
        meta_aud = MetadataExtractor.extract_metadata(cdoc, ext_aud)
        self.assertEqual(meta_aud.audit_status, AuditStatus.AUDITED)

    def test_reporting_scope_consolidated_vs_standalone(self) -> None:
        """Verify Consolidated vs Standalone and detection of both."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A, original_filename="Report.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL, file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        ext_cons = create_sample_extraction(texts=["Statement of Consolidated Unaudited Financial Results"])
        meta_cons = MetadataExtractor.extract_metadata(cdoc, ext_cons)
        self.assertEqual(meta_cons.reporting_scope, ReportingScope.CONSOLIDATED)

        ext_both = create_sample_extraction(texts=[
            "Part I: Consolidated Financial Results",
            "Part II: Standalone Financial Results",
        ])
        meta_both = MetadataExtractor.extract_metadata(cdoc, ext_both)
        self.assertEqual(meta_both.reporting_scope, ReportingScope.BOTH)
        self.assertIn("reporting_scope", meta_both.conflicting_candidates)

    def test_scanned_pdf_and_image_metadata_marked_unknown(self) -> None:
        """Verify unextractable formats (scanned PDF / images in local mode) yield UNKNOWN metadata."""
        cdoc_scanned = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A, original_filename="Scan.pdf",
            file_format=SupportedFileFormat.PDF_SCANNED, file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )
        ext_scanned = create_sample_extraction(is_scanned=True, status_tag="OCR_UNAVAILABLE_LOCAL_MODE")
        meta_scan = MetadataExtractor.extract_metadata(cdoc_scanned, ext_scanned)
        self.assertEqual(meta_scan.company_name, "Unknown")
        self.assertEqual(meta_scan.confidence_category, "UNKNOWN")
        self.assertTrue(any("OCR" in n for n in meta_scan.extraction_notes))

    # -----------------------------------------------------------------------
    # 2. Compatibility Engine Scenario Tests
    # -----------------------------------------------------------------------

    def test_scenario_a_same_company_consecutive_fy(self) -> None:
        """Scenario A: Same company, consecutive financial years -> COMPATIBLE."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="Tata Motors Limited", document_type="Annual Report",
            financial_year="FY 2023-24", reporting_period="Annual", currency="INR",
            reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="Tata Motors Limited", document_type="Annual Report",
            financial_year="FY 2024-25", reporting_period="Annual", currency="INR",
            reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertTrue(report.is_comparable)
        self.assertEqual(report.overall_status, CompatibilityStatus.COMPATIBLE)
        self.assertEqual(report.blocker_count, 0)
        self.assertEqual(report.warning_count, 0)

    def test_scenario_b_same_company_different_quarters(self) -> None:
        """Scenario B: Same company, sequential quarters -> COMPATIBLE."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="Tata Motors Limited", document_type="Quarterly Financial Results",
            financial_year="FY 2023-24", reporting_period="Quarterly", quarter="Q1", currency="INR",
            reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.LIMITED_REVIEW,
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="Tata Motors Limited", document_type="Quarterly Financial Results",
            financial_year="FY 2023-24", reporting_period="Quarterly", quarter="Q2", currency="INR",
            reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.LIMITED_REVIEW,
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertTrue(report.is_comparable)
        self.assertEqual(report.overall_status, CompatibilityStatus.COMPATIBLE)
        self.assertEqual(report.blocker_count, 0)

    def test_scenario_c_peer_company_comparison(self) -> None:
        """Scenario C: Different companies in same verified industry -> SAME_INDUSTRY_PEER_COMPARISON info."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="Tata Motors Limited", document_type="Quarterly Financial Results",
            financial_year="FY 2023-24", reporting_period="Quarterly", quarter="Q3", currency="INR",
            industry="Automobiles", reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="Maruti Suzuki India Limited", document_type="Quarterly Financial Results",
            financial_year="FY 2023-24", reporting_period="Quarterly", quarter="Q3", currency="INR",
            industry="Automobiles", reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertTrue(report.is_comparable)
        self.assertTrue(any(f.code == "SAME_INDUSTRY_PEER_COMPARISON" and f.severity == IssueSeverity.INFORMATION for f in report.findings))

    def test_cross_company_unknown_industry_limitations(self) -> None:
        """Unknown or disparate industry -> CROSS_COMPANY_COMPARISON warning with explicit limitations."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="Tata Motors Limited", document_type="Quarterly Financial Results",
            financial_year="FY 2023-24", reporting_period="Quarterly", quarter="Q3", currency="INR",
            industry="UNKNOWN", reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="Infosys Limited", document_type="Quarterly Financial Results",
            financial_year="FY 2023-24", reporting_period="Quarterly", quarter="Q3", currency="INR",
            industry="UNKNOWN", reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertTrue(report.is_comparable)
        self.assertEqual(report.overall_status, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)
        cross_findings = [f for f in report.findings if f.code == "CROSS_COMPANY_COMPARISON"]
        self.assertEqual(len(cross_findings), 1)
        finding = cross_findings[0]
        self.assertEqual(finding.severity, IssueSeverity.WARNING)
        self.assertIn("severe limitations", finding.description.lower())
        self.assertIn("UNKNOWN", finding.observed_values["doc_a"])
        self.assertIn("UNKNOWN", finding.observed_values["doc_b"])

    def test_lifecycle_state_machine_transitions_including_files_uploaded(self) -> None:
        """Verify explicit lifecycle transitions: INITIALIZED -> FILES_UPLOADED -> METADATA_EXTRACTED."""
        from app.models.comparison import SessionStatus
        session, token = session_store.create_session()
        try:
            self.assertEqual(session.status, SessionStatus.INITIALIZED)

            # Legal transition 1: INITIALIZED -> FILES_UPLOADED
            self.assertTrue(session.can_transition_to(SessionStatus.FILES_UPLOADED))
            session.transition_to(SessionStatus.FILES_UPLOADED)
            self.assertEqual(session.status, SessionStatus.FILES_UPLOADED)

            # Legal transition 2: FILES_UPLOADED -> METADATA_EXTRACTED
            self.assertTrue(session.can_transition_to(SessionStatus.METADATA_EXTRACTED))
            session.transition_to(SessionStatus.METADATA_EXTRACTED)
            self.assertEqual(session.status, SessionStatus.METADATA_EXTRACTED)

            # Legal transition 3: Retry scenario: METADATA_EXTRACTED -> FILES_UPLOADED -> METADATA_EXTRACTED
            self.assertTrue(session.can_transition_to(SessionStatus.FILES_UPLOADED))
            session.transition_to(SessionStatus.FILES_UPLOADED)
            self.assertEqual(session.status, SessionStatus.FILES_UPLOADED)
            self.assertTrue(session.can_transition_to(SessionStatus.METADATA_EXTRACTED))
            session.transition_to(SessionStatus.METADATA_EXTRACTED)
            self.assertEqual(session.status, SessionStatus.METADATA_EXTRACTED)

            # Illegal transition: INITIALIZED or METADATA_EXTRACTED -> COMPLETED directly without PROCESSING
            self.assertFalse(session.can_transition_to(SessionStatus.COMPLETED))
            with self.assertRaises(ValueError):
                session.transition_to(SessionStatus.COMPLETED)

            # Transition to TERMINATED (terminal)
            self.assertTrue(session.can_transition_to(SessionStatus.TERMINATED))
            session.transition_to(SessionStatus.TERMINATED)
            self.assertEqual(session.status, SessionStatus.TERMINATED)

            # Terminal state cannot transition to any active state
            self.assertFalse(session.can_transition_to(SessionStatus.INITIALIZED))
            self.assertFalse(session.can_transition_to(SessionStatus.FILES_UPLOADED))
            self.assertFalse(session.can_transition_to(SessionStatus.METADATA_EXTRACTED))
            with self.assertRaises(ValueError):
                session.transition_to(SessionStatus.FILES_UPLOADED)
        finally:
            session_store.terminate_session(session.session_id)

    def test_scenario_d_ipo_prospectus_stages(self) -> None:
        """Scenario D: DRHP vs Final Prospectus -> PROSPECTUS_VERSION_DIFFERENCE warning."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="Ola Electric Limited", document_type="Draft Red Herring Prospectus (DRHP)",
            financial_year="FY 2023-24", reporting_period="Annual", currency="INR",
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="Ola Electric Limited", document_type="IPO Prospectus",
            financial_year="FY 2023-24", reporting_period="Annual", currency="INR",
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertTrue(report.is_comparable)
        self.assertTrue(any(f.code == "PROSPECTUS_VERSION_DIFFERENCE" for f in report.findings))

    def test_scenario_e_annual_vs_quarterly_duration_mismatch(self) -> None:
        """Scenario E: Annual vs Quarterly -> PERIOD_DURATION_MISMATCH warning."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="Tata Motors Limited", document_type="Annual Report",
            financial_year="FY 2023-24", reporting_period="Annual", currency="INR",
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="Tata Motors Limited", document_type="Quarterly Financial Results",
            financial_year="FY 2023-24", reporting_period="Quarterly", quarter="Q3", currency="INR",
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertTrue(report.is_comparable)
        self.assertEqual(report.overall_status, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)
        self.assertTrue(any(f.code == "PERIOD_DURATION_MISMATCH" for f in report.findings))

    def test_currency_mismatch_blocks_comparison(self) -> None:
        """Currency mismatch (INR vs USD) -> BLOCKER."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="Tata Motors Limited", document_type="Annual Report",
            financial_year="FY 2023-24", reporting_period="Annual", currency="INR",
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="Tesla Inc", document_type="Annual Report",
            financial_year="FY 2023-24", reporting_period="Annual", currency="USD",
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertFalse(report.is_comparable)
        self.assertEqual(report.overall_status, CompatibilityStatus.BLOCKED)
        self.assertEqual(report.blocker_count, 1)
        self.assertTrue(any(f.code == "CURRENCY_MISMATCH" and f.severity == IssueSeverity.BLOCKER for f in report.findings))

    def test_scope_mismatch_consolidated_vs_standalone(self) -> None:
        """Consolidated vs Standalone -> SCOPE_MISMATCH warning."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="Reliance Industries", document_type="Annual Report",
            financial_year="FY 2023-24", reporting_period="Annual", currency="INR", reporting_scope=ReportingScope.CONSOLIDATED,
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="Reliance Industries", document_type="Annual Report",
            financial_year="FY 2023-24", reporting_period="Annual", currency="INR", reporting_scope=ReportingScope.STANDALONE,
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertTrue(report.is_comparable)
        self.assertTrue(any(f.code == "SCOPE_MISMATCH" for f in report.findings))

    def test_multi_document_pairwise_and_partial_subsets(self) -> None:
        """Verify 4-document comparison calculates all 6 pairs and finds compatible subsets."""
        meta_a = DocumentMetadata(doc_id="doc_a", company_name="Tata Motors", currency="INR", financial_year="FY 2023-24")
        meta_b = DocumentMetadata(doc_id="doc_b", company_name="Tata Motors", currency="INR", financial_year="FY 2024-25")
        meta_c = DocumentMetadata(doc_id="doc_c", company_name="Maruti Suzuki", currency="INR", financial_year="FY 2024-25")
        meta_d = DocumentMetadata(doc_id="doc_d", company_name="Ford Motor Co", currency="USD", financial_year="FY 2024-25")

        report = CompatibilityEngine.evaluate_session({
            "doc_a": meta_a, "doc_b": meta_b, "doc_c": meta_c, "doc_d": meta_d,
        })

        # 4 documents -> 6 pairwise combinations
        self.assertEqual(len(report.pairwise_matrix), 6)
        self.assertFalse(report.is_comparable)
        self.assertEqual(report.overall_status, CompatibilityStatus.PARTIALLY_COMPATIBLE)

        # doc_a, doc_b, doc_c share INR and should form a compatible subset
        self.assertTrue(any(set(["doc_a", "doc_b", "doc_c"]).issubset(set(s)) for s in report.compatible_subsets))
        # Any pair with doc_d (USD) must be blocked
        pairs_with_d = [p for p in report.pairwise_matrix if p.doc_a_id == "doc_d" or p.doc_b_id == "doc_d"]
        self.assertTrue(all(not p.is_comparable for p in pairs_with_d))

    # -----------------------------------------------------------------------
    # 3. API Endpoints (GET /metadata, PUT /metadata/{doc_id}, GET /compatibility)
    # -----------------------------------------------------------------------

    def test_api_metadata_retrieval_and_user_correction(self) -> None:
        """Verify GET /metadata, PUT /metadata/{doc_id}, and GET /compatibility lifecycle."""
        # 1. Create session and upload 2 synthetic files
        create_res = client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(create_res.status_code, 201)
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]

        pdf_a = create_synthetic_pdf("Tata Motors Limited - Q3 Results (in INR Crores)")
        pdf_b = create_synthetic_pdf("Maruti Suzuki India Limited - Q3 Results (in INR Crores)")

        upload_res = client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=[
                ("files", ("DocA.pdf", pdf_a, "application/pdf")),
                ("files", ("DocB.pdf", pdf_b, "application/pdf")),
            ],
        )
        self.assertEqual(upload_res.status_code, 200)

        # Verify session state reached METADATA_EXTRACTED via FILES_UPLOADED
        sess_post_upload = session_store.get_session(session_id)
        self.assertEqual(sess_post_upload.status, "METADATA_EXTRACTED")

        # 2. GET /metadata
        meta_res = client.get(
            f"/api/compare/session/{session_id}/metadata",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(meta_res.status_code, 200)
        meta_data = meta_res.json()["metadata"]
        self.assertIn("doc_a", meta_data)
        self.assertIn("doc_b", meta_data)
        self.assertFalse(meta_data["doc_a"]["is_user_overridden"])

        # 3. PUT /metadata/{doc_id} to correct company name, reporting scope, and industry
        put_res = client.put(
            f"/api/compare/session/{session_id}/metadata/doc_a",
            headers={"X-Session-Token": token},
            json={
                "company_name": "Tata Motors Group",
                "reporting_scope": "CONSOLIDATED",
                "industry": "Automobiles",
            },
        )
        self.assertEqual(put_res.status_code, 200)
        updated_a = put_res.json()
        self.assertEqual(updated_a["company_name"], "Tata Motors Group")
        self.assertEqual(updated_a["industry"], "Automobiles")
        self.assertTrue(updated_a["is_user_overridden"])
        self.assertIn("company_name", updated_a["user_overrides"])
        self.assertIn("industry", updated_a["user_overrides"])

        # Verify sibling doc_b was not altered
        get_again = client.get(
            f"/api/compare/session/{session_id}/metadata",
            headers={"X-Session-Token": token},
        )
        self.assertFalse(get_again.json()["metadata"]["doc_b"]["is_user_overridden"])

        # 4. GET /compatibility
        comp_res = client.get(
            f"/api/compare/session/{session_id}/compatibility",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(comp_res.status_code, 200)
        comp_data = comp_res.json()
        self.assertTrue(comp_data["is_comparable"])
        self.assertGreaterEqual(len(comp_data["pairwise_matrix"]), 1)

        # 5. Security & Isolation checks
        # Invalid slot PUT -> 404
        bad_slot = client.put(
            f"/api/compare/session/{session_id}/metadata/doc_z",
            headers={"X-Session-Token": token},
            json={"company_name": "New Name"},
        )
        self.assertEqual(bad_slot.status_code, 404)

        # Missing token -> 401
        no_token = client.get(f"/api/compare/session/{session_id}/metadata")
        self.assertEqual(no_token.status_code, 401)

        # Token in query string -> 400
        query_token = client.get(f"/api/compare/session/{session_id}/metadata?token={token}")
        self.assertEqual(query_token.status_code, 400)

        # Cleanup
        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    # -----------------------------------------------------------------------
    # Phase 3 Targeted Metadata & Compatibility Improvement Tests
    # -----------------------------------------------------------------------

    def test_indian_corporate_suffixes_and_cin_proximity(self) -> None:
        """Verify expanded corporate suffixes (Bank, LLP, Securities) and CIN proximity matching."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A,
            original_filename="Bank_Results.pdf", file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )
        # Block 0 has company name with scope suffix, Block 1 has CIN
        extraction = create_sample_extraction(
            texts=[
                "HDFC Bank Limited - Standalone",
                "CIN: L65920MH1994PLC080618",
                "Registered Office: Senapati Bapat Marg, Lower Parel, Mumbai",
            ]
        )
        meta = MetadataExtractor.extract_metadata(cdoc, extraction)
        # Company name should be cleaned of scope noise
        self.assertEqual(meta.company_name, "HDFC Bank Limited")
        self.assertEqual(meta.company_identifier, "L65920MH1994PLC080618")

        # Test LLP suffix
        ext_llp = create_sample_extraction(
            texts=["Reliance Advisory Services LLP", "CIN: U74140MH2018LLP001234"]
        )
        meta_llp = MetadataExtractor.extract_metadata(cdoc, ext_llp)
        self.assertEqual(meta_llp.company_name, "Reliance Advisory Services LLP")

        # Test Securities suffix
        ext_sec = create_sample_extraction(
            texts=["ICICI Securities Limited", "CIN: L67120MH1995PLC086241"]
        )
        meta_sec = MetadataExtractor.extract_metadata(cdoc, ext_sec)
        self.assertEqual(meta_sec.company_name, "ICICI Securities Limited")

    def test_indian_financial_year_date_mapping_and_ambiguity(self) -> None:
        """Verify Indian April–March FY mapping from end-dates and unevidenced date fallback."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A,
            original_filename="Results.pdf", file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        # December 31, 2023 -> Month 12 belongs to FY 2023-24
        ext_dec = create_sample_extraction(texts=["Financial Results for the quarter ended 31-12-2023"])
        meta_dec = MetadataExtractor.extract_metadata(cdoc, ext_dec)
        self.assertEqual(meta_dec.financial_year, "FY 2023-24")
        self.assertEqual(meta_dec.quarter, "Q3")

        # September 30, 2024 -> Month 9 belongs to FY 2024-25
        ext_sep = create_sample_extraction(texts=["Statement of results for the period ended 30th September, 2024"])
        meta_sep = MetadataExtractor.extract_metadata(cdoc, ext_sep)
        self.assertEqual(meta_sep.financial_year, "FY 2024-25")
        self.assertEqual(meta_sep.quarter, "Q2")

        # March 31, 2025 -> Month 3 belongs to FY 2024-25
        ext_mar = create_sample_extraction(texts=["Financial Results for the quarter ended March 31, 2025"])
        meta_mar = MetadataExtractor.extract_metadata(cdoc, ext_mar)
        self.assertEqual(meta_mar.financial_year, "FY 2024-25")
        self.assertEqual(meta_mar.quarter, "Q4")

        # June 30, 2024 -> Month 6 belongs to FY 2024-25
        ext_jun = create_sample_extraction(texts=["Results for the three months ended 30.06.2024"])
        meta_jun = MetadataExtractor.extract_metadata(cdoc, ext_jun)
        self.assertEqual(meta_jun.financial_year, "FY 2024-25")
        self.assertEqual(meta_jun.quarter, "Q1")

        # Ambiguous date with no period-ended anchor -> preserves Unknown
        ext_amb = create_sample_extraction(texts=["General notice published on 15/08/2023 regarding AGM"])
        meta_amb = MetadataExtractor.extract_metadata(cdoc, ext_amb)
        self.assertEqual(meta_amb.financial_year, "Unknown")

    def test_annual_vs_q4_period_distinction(self) -> None:
        """Verify strict distinction between Annual (Full Year) and Q4 quarterly results."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A,
            original_filename="Report.pdf", file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        # Annual Report with period ended March 31 -> Annual / Full Year, quarter is None
        ext_annual = create_sample_extraction(
            texts=["Tata Motors Limited - Annual Report 2023-24", "Year ended March 31, 2024"]
        )
        meta_annual = MetadataExtractor.extract_metadata(cdoc, ext_annual)
        self.assertEqual(meta_annual.document_type, DocumentType.ANNUAL_REPORT.value)
        self.assertEqual(meta_annual.reporting_period, ReportingPeriodType.ANNUAL.value)
        self.assertIsNone(meta_annual.quarter)

        # Quarterly results for period ended March 31 -> Q4
        ext_q4 = create_sample_extraction(
            texts=[
                "Statement of Unaudited Financial Results",
                "Quarter ended March 31, 2024",
            ]
        )
        meta_q4 = MetadataExtractor.extract_metadata(cdoc, ext_q4)
        self.assertEqual(meta_q4.document_type, DocumentType.QUARTERLY_RESULTS.value)
        self.assertEqual(meta_q4.reporting_period, ReportingPeriodType.QUARTERLY.value)
        self.assertEqual(meta_q4.quarter, "Q4")

    def test_evidence_grounded_industry_detection_and_unknown_fallback(self) -> None:
        """Verify industry extraction only when explicitly evidenced in text, never inferred from company name."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A,
            original_filename="Doc.pdf", file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )

        # Evidenced segment disclosure
        ext_ind = create_sample_extraction(
            texts=[
                "Infosys Limited",
                "Primary business segment: Information Technology Services",
            ]
        )
        meta_ind = MetadataExtractor.extract_metadata(cdoc, ext_ind)
        self.assertEqual(meta_ind.industry, "Information Technology Services")
        self.assertIn("industry", meta_ind.evidence_sources)

        # Generic non-industry phrase filtered -> remains UNKNOWN
        ext_generic = create_sample_extraction(
            texts=[
                "Tata Steel Limited",
                "Operating segment: Single Segment (Not Applicable)",
            ]
        )
        meta_generic = MetadataExtractor.extract_metadata(cdoc, ext_generic)
        self.assertEqual(meta_generic.industry, "UNKNOWN")

        # Company name alone without industry text -> remains UNKNOWN (no hallucination)
        ext_none = create_sample_extraction(
            texts=["Tata Motors Limited", "CIN: L28920MH1945PLC004520"]
        )
        meta_none = MetadataExtractor.extract_metadata(cdoc, ext_none)
        self.assertEqual(meta_none.industry, "UNKNOWN")

    def test_document_type_precedence_hierarchy(self) -> None:
        """Verify Annual Report is not downgraded to Quarterly Results when comparison tables are present."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A,
            original_filename="AnnualReport2024.pdf", file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )
        # Annual Report containing quarterly comparative breakdown tables
        ext = create_sample_extraction(
            texts=[
                "Tata Motors Limited - Integrated Annual Report 2023-24",
                "Operating and Financial Review",
                "Comparative performance for the three months ended December 31, 2023",
            ]
        )
        meta = MetadataExtractor.extract_metadata(cdoc, ext)
        self.assertEqual(meta.document_type, DocumentType.ANNUAL_REPORT.value)

    def test_column_specific_audit_status_detection(self) -> None:
        """Verify audit status is derived from primary statement/table headers rather than stray narrative text."""
        cdoc = ComparisonDocument(
            doc_id="doc_a", slot=DocumentSlot.DOC_A,
            original_filename="Results.pdf", file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024, storage_rel_path="documents/doc_a.pdf",
        )
        # Table with Unaudited header and Limited Review report reference
        ext_lr = create_sample_extraction(
            texts=[
                "Statement of Unaudited Financial Results",
                "Subject to Limited Review by the Statutory Auditors",
            ],
            headers=["Particulars", "Quarter ended 31-12-2023 (Unaudited)", "Quarter ended 31-12-2022 (Unaudited)"],
        )
        meta_lr = MetadataExtractor.extract_metadata(cdoc, ext_lr)
        self.assertEqual(meta_lr.audit_status, AuditStatus.LIMITED_REVIEW)

        # Table with Audited header
        ext_aud = create_sample_extraction(
            texts=["Statement of Audited Financial Results for the Year ended March 31, 2024"],
            headers=["Line Item", "Year ended 31-03-2024 (Audited)"],
        )
        meta_aud = MetadataExtractor.extract_metadata(cdoc, ext_aud)
        self.assertEqual(meta_aud.audit_status, AuditStatus.AUDITED)

    def test_scale_difference_and_quarter_mismatch_compatibility(self) -> None:
        """Verify SCALE_DIFFERENCE and QUARTER_MISMATCH findings are surfaced without blocking comparison."""
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="ABC Ltd", financial_year="FY 2024-25",
            reporting_period="Quarterly", quarter="Q1", currency="INR", reporting_scale="LAKH",
            reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="ABC Ltd", financial_year="FY 2024-25",
            reporting_period="Quarterly", quarter="Q3", currency="INR", reporting_scale="CRORE",
            reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        # Must be comparable (non-blocking)
        self.assertTrue(report.is_comparable)
        self.assertEqual(report.blocker_count, 0)
        self.assertEqual(report.overall_status, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)

        codes = [f.code for f in report.findings]
        self.assertIn("SCALE_DIFFERENCE", codes)
        self.assertIn("QUARTER_MISMATCH", codes)

    def test_year_gap_warning_and_dual_scope_compatibility(self) -> None:
        """Verify YEAR_GAP_WARNING for multi-year distance and DUAL_SCOPE_ALIGNMENT for BOTH scope."""
        # 3-year gap between FY 2024-25 and FY 2021-22
        meta_a = DocumentMetadata(
            doc_id="doc_a", company_name="XYZ Ltd", financial_year="FY 2024-25",
            reporting_period="Annual", currency="INR", reporting_scale="CRORE",
            reporting_scope=ReportingScope.BOTH, audit_status=AuditStatus.AUDITED,
        )
        meta_b = DocumentMetadata(
            doc_id="doc_b", company_name="XYZ Ltd", financial_year="FY 2021-22",
            reporting_period="Annual", currency="INR", reporting_scale="CRORE",
            reporting_scope=ReportingScope.CONSOLIDATED, audit_status=AuditStatus.AUDITED,
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_a, "doc_b": meta_b})
        self.assertTrue(report.is_comparable)
        self.assertEqual(report.blocker_count, 0)

        codes = [f.code for f in report.findings]
        self.assertIn("YEAR_GAP_WARNING", codes)
        self.assertIn("DUAL_SCOPE_ALIGNMENT", codes)

        # Verify dual scope alignment is INFORMATION severity (does not cause blocker)
        dual_finding = next(f for f in report.findings if f.code == "DUAL_SCOPE_ALIGNMENT")
        self.assertEqual(dual_finding.severity, IssueSeverity.INFORMATION)

    def test_scale_conversion_exact_arithmetic(self) -> None:
        """Verify exact deterministic scale multipliers (100 Lakhs = 1 Cr, 10 Mn = 1 Cr, 1 Bn = 100 Cr)."""
        # 100 Lakhs -> 1.0000 Crore
        val_lakh, unit_lakh = FinancialNormalizer.normalize_to_crore(Decimal("100"), "LAKH")
        self.assertEqual(val_lakh, Decimal("1.0000"))
        self.assertEqual(unit_lakh, "INR_CRORE")

        # 10 Million -> 1.0000 Crore
        val_mn, unit_mn = FinancialNormalizer.normalize_to_crore(Decimal("10"), "MILLION")
        self.assertEqual(val_mn, Decimal("1.0000"))
        self.assertEqual(unit_mn, "INR_CRORE")

        # 1 Billion -> 100.0000 Crores
        val_bn, unit_bn = FinancialNormalizer.normalize_to_crore(Decimal("1"), "BILLION")
        self.assertEqual(val_bn, Decimal("100.0000"))
        self.assertEqual(unit_bn, "INR_CRORE")

        # 10,000 Thousands -> 1.0000 Crore
        val_th, unit_th = FinancialNormalizer.normalize_to_crore(Decimal("10000"), "THOUSAND")
        self.assertEqual(val_th, Decimal("1.0000"))
        self.assertEqual(unit_th, "INR_CRORE")

    def test_strict_blocker_boundary(self) -> None:
        """Verify strict blocker behavior only for genuine material non-comparability (CURRENCY_MISMATCH)."""
        meta_inr = DocumentMetadata(
            doc_id="doc_a", company_name="Company A", currency="INR", reporting_scale="CRORE",
            financial_year="FY 2023-24", reporting_period="Annual",
        )
        meta_usd = DocumentMetadata(
            doc_id="doc_b", company_name="Company B", currency="USD", reporting_scale="MILLION",
            financial_year="FY 2023-24", reporting_period="Annual",
        )

        report = CompatibilityEngine.evaluate_session({"doc_a": meta_inr, "doc_b": meta_usd})
        self.assertFalse(report.is_comparable)
        self.assertEqual(report.overall_status, CompatibilityStatus.BLOCKED)
        self.assertGreaterEqual(report.blocker_count, 1)
        self.assertTrue(any(f.code == "CURRENCY_MISMATCH" for f in report.findings))


if __name__ == "__main__":
    unittest.main()
