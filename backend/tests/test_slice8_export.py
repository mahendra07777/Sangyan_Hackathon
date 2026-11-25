"""Comprehensive automated test suite for Compare Documents Slice 8:
PDF Report Generation & 7-Tab Excel Workbook Export.
"""

from __future__ import annotations

import io
import os
import unittest
from decimal import Decimal
from typing import Dict, List

from fastapi.testclient import TestClient
import openpyxl
import pymupdf

from app.models.comparison import (
    AccountingDifference,
    AuditStatus,
    CalculationResult,
    CompatibilityFinding,
    CompatibilityReport,
    CompatibilityStatus,
    ComparisonDocument,
    ComparisonResult,
    DocumentMetadata,
    EvidenceReference,
    ExecutiveSummary,
    FactClassification,
    FinancialValue,
    ReportingScope,
    RiskDisclosure,
    SupportedFileFormat,
    VarianceStatus,
    VerificationResult,
    VerificationSourceType,
    VerificationStatus,
)
from app.services.comparison_session_store import session_store
from app.services.export_excel_service import ExportExcelService
from app.services.export_pdf_service import ExportPdfService
import main as app_main


def build_test_comparison_result(session_id: str) -> ComparisonResult:
    """Constructs a fully populated, verified ComparisonResult fixture for export testing."""
    doc_a = ComparisonDocument(
        doc_id="doc_a",
        slot="doc_a",
        original_filename="TataMotors_FY24.pdf",
        file_format=SupportedFileFormat.PDF_DIGITAL,
        file_size_bytes=1024,
        storage_rel_path="documents/doc_a.pdf",
    )
    doc_b = ComparisonDocument(
        doc_id="doc_b",
        slot="doc_b",
        original_filename="MarutiSuzuki_FY24.pdf",
        file_format=SupportedFileFormat.PDF_DIGITAL,
        file_size_bytes=1024,
        storage_rel_path="documents/doc_b.pdf",
    )

    ev_a = EvidenceReference(
        evidence_id="ev_a1",
        doc_id="doc_a",
        document_name="TataMotors_FY24.pdf",
        page_number=5,
        verbatim_snippet="Revenue from operations: ₹ 1,10,577.00 Cr",
    )
    ev_b = EvidenceReference(
        evidence_id="ev_b1",
        doc_id="doc_b",
        document_name="MarutiSuzuki_FY24.pdf",
        page_number=4,
        verbatim_snippet="Revenue from operations: ₹ 33,309.00 Cr",
    )
    ev_pat_a = EvidenceReference(
        evidence_id="ev_a2",
        doc_id="doc_a",
        document_name="TataMotors_FY24.pdf",
        page_number=6,
        verbatim_snippet="Profit for the period (PAT): ₹ 31,807.00 Cr",
    )
    ev_pat_b = EvidenceReference(
        evidence_id="ev_b2",
        doc_id="doc_b",
        document_name="MarutiSuzuki_FY24.pdf",
        page_number=4,
        verbatim_snippet="Net profit for the year: ₹ 13,241.00 Cr",
    )

    meta_a = DocumentMetadata(
        doc_id="doc_a",
        company_name="Tata Motors Limited",
        company_identifier="L28920MH1945PLC004520",
        financial_year="FY 2023-24",
        currency="INR",
        reporting_scale="CRORE",
        reporting_scope=ReportingScope.CONSOLIDATED,
        audit_status=AuditStatus.AUDITED,
    )
    meta_b = DocumentMetadata(
        doc_id="doc_b",
        company_name="Maruti Suzuki India Limited",
        company_identifier="L34103DL1981PLC011375",
        financial_year="FY 2023-24",
        currency="INR",
        reporting_scale="CRORE",
        reporting_scope=ReportingScope.CONSOLIDATED,
        audit_status=AuditStatus.AUDITED,
    )

    compat = CompatibilityReport(
        session_id=session_id,
        is_comparable=True,
        overall_status=CompatibilityStatus.COMPATIBLE,
        blocker_count=0,
        warning_count=0,
        findings=[],
    )

    # Financial values: Revenue, PAT, and an intentionally NOT_DISCLOSED metric (EBITDA)
    financial_values: Dict[str, Dict[str, FinancialValue]] = {
        "REVENUE": {
            "doc_a": FinancialValue(
                doc_id="doc_a",
                metric_key="REVENUE",
                label="Revenue from Operations",
                amount=Decimal("110577.0000"),
                reported_amount=Decimal("110577.0000"),
                display_amount="₹1,10,577.00 Cr",
                unit="INR_CRORE",
                currency="INR",
                status="REPORTED",
                evidence=ev_a,
            ),
            "doc_b": FinancialValue(
                doc_id="doc_b",
                metric_key="REVENUE",
                label="Revenue from Operations",
                amount=Decimal("33309.0000"),
                reported_amount=Decimal("33309.0000"),
                display_amount="₹33,309.00 Cr",
                unit="INR_CRORE",
                currency="INR",
                status="REPORTED",
                evidence=ev_b,
            ),
        },
        "PAT": {
            "doc_a": FinancialValue(
                doc_id="doc_a",
                metric_key="PAT",
                label="Profit After Tax (PAT)",
                amount=Decimal("31807.0000"),
                reported_amount=Decimal("31807.0000"),
                display_amount="₹31,807.00 Cr",
                unit="INR_CRORE",
                currency="INR",
                status="REPORTED",
                evidence=ev_pat_a,
            ),
            "doc_b": FinancialValue(
                doc_id="doc_b",
                metric_key="PAT",
                label="Profit After Tax (PAT)",
                amount=Decimal("13241.0000"),
                reported_amount=Decimal("13241.0000"),
                display_amount="₹13,241.00 Cr",
                unit="INR_CRORE",
                currency="INR",
                status="REPORTED",
                evidence=ev_pat_b,
            ),
        },
        "EBITDA": {
            "doc_a": FinancialValue(
                doc_id="doc_a",
                metric_key="EBITDA",
                label="EBITDA",
                amount=None,
                reported_amount=None,
                display_amount=None,
                unit="INR_CRORE",
                currency="INR",
                status="NOT_DISCLOSED",
                evidence=None,
            ),
            "doc_b": FinancialValue(
                doc_id="doc_b",
                metric_key="EBITDA",
                label="EBITDA",
                amount=None,
                reported_amount=None,
                display_amount=None,
                unit="INR_CRORE",
                currency="INR",
                status="NOT_DISCLOSED",
                evidence=None,
            ),
        },
    }

    variances: List[CalculationResult] = [
        CalculationResult(
            metric_key="REVENUE",
            label="Revenue from Operations",
            base_doc_id="doc_b",
            comparison_doc_id="doc_a",
            base_value=Decimal("33309.0000"),
            comparison_value=Decimal("110577.0000"),
            formula="(comparison - base)",
            absolute_variance=Decimal("77268.0000"),
            percentage_change=Decimal("231.97"),
            display_absolute_variance="+₹77,268.00 Cr",
            display_percentage_change="+231.97%",
            unit="INR_CRORE",
            status=VarianceStatus.CALCULATED,
        ),
        CalculationResult(
            metric_key="PAT",
            label="Profit After Tax (PAT)",
            base_doc_id="doc_b",
            comparison_doc_id="doc_a",
            base_value=Decimal("13241.0000"),
            comparison_value=Decimal("31807.0000"),
            formula="(comparison - base)",
            absolute_variance=Decimal("18566.0000"),
            percentage_change=Decimal("140.22"),
            display_absolute_variance="+₹18,566.00 Cr",
            display_percentage_change="+140.22%",
            unit="INR_CRORE",
            status=VarianceStatus.CALCULATED,
        ),
    ]

    exec_summary = ExecutiveSummary(
        overview_story="Tata Motors reported FY24 revenue of ₹1,10,577 Cr compared to Maruti Suzuki's ₹33,309 Cr.",
        core_positive_changes=["Tata Motors revenue expanded with strong CV and JLR performance."],
        core_negative_changes=["Raw material pressures noted in domestic passenger vehicle segment."],
        neutral_observations=["Both entities report consolidated figures under Ind AS standards."],
        uncertain_findings=[],
        critical_disclosures=["Statutory disclosure on capital expenditure commitments."],
        mode="LOCAL_MODE",
    )

    ev_risk = EvidenceReference(
        evidence_id="ev_risk1",
        doc_id="doc_a",
        document_name="TataMotors_FY24.pdf",
        page_number=18,
        verbatim_snippet="Commodity price volatility poses margin risks.",
    )
    risks = [
        RiskDisclosure(
            risk_id="risk_1",
            title="Raw Material & Commodity Volatility",
            category="Operational",
            doc_id="doc_a",
            severity="MEDIUM",
            disclosure_text="Commodity price fluctuations could impact gross margins.",
            evidence=ev_risk,
            fact_classification=FactClassification.DOCUMENT_FACT,
            audit_status="AUDITED",
        )
    ]

    ev_acct_a = EvidenceReference(
        evidence_id="ev_acct1",
        doc_id="doc_a",
        document_name="TataMotors_FY24.pdf",
        page_number=45,
        verbatim_snippet="Depreciation calculated on straight line method.",
    )
    ev_acct_b = EvidenceReference(
        evidence_id="ev_acct2",
        doc_id="doc_b",
        document_name="MarutiSuzuki_FY24.pdf",
        page_number=52,
        verbatim_snippet="Depreciation on straight line basis over estimated useful lives.",
    )
    accounting_differences = [
        AccountingDifference(
            difference_id="diff_1",
            topic="Depreciation Policy",
            doc_a_policy="Straight-line method over 10-30 years for plant and machinery",
            doc_b_policy="Straight-line method over 8-20 years for tooling and equipment",
            impact_summary="Useful life assumptions differ modestly for plant assets.",
            evidence_a=ev_acct_a,
            evidence_b=ev_acct_b,
            fact_classification=FactClassification.DOCUMENT_FACT,
            audit_status_a="AUDITED",
            audit_status_b="AUDITED",
        )
    ]

    verifications = [
        VerificationResult(
            source_type=VerificationSourceType.SEBI_FILING,
            source_url="Local Offline Mode",
            status=VerificationStatus.SIMULATED,
            verified_item="CIN & Corporate Identity",
            details="Registry lookups are simulated in offline test environment.",
        )
    ]

    return ComparisonResult(
        session_id=session_id,
        mode="LOCAL_MODE",
        documents=[doc_a, doc_b],
        metadata={"doc_a": meta_a, "doc_b": meta_b},
        compatibility=compat,
        financial_values=financial_values,
        variances=variances,
        executive_summary=exec_summary,
        risks=risks,
        accounting_differences=accounting_differences,
        verifications=verifications,
        language="English",
    )


class TestSlice8Exports(unittest.TestCase):
    """Test suite covering PDF & Excel exports, 7-sheet workbook integrity, and security lifecycle."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_main.app)

    def setUp(self) -> None:
        resp = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.session_id = data["session_id"]
        self.token = data["session_token"]
        self.auth_headers = {"X-Session-Token": self.token}
        self.session_dir = session_store.resolve_session_path(self.session_id)

    def tearDown(self) -> None:
        session_store.terminate_session(self.session_id)

    # ---------------------------------------------------------------------------
    # 1. Security & Authentication Checks
    # ---------------------------------------------------------------------------

    def test_export_pdf_missing_or_invalid_token_401(self) -> None:
        """Endpoint 15 requires valid X-Session-Token in header."""
        resp_missing = self.client.post(f"/api/compare/session/{self.session_id}/export/pdf")
        self.assertEqual(resp_missing.status_code, 401)
        self.assertIn("Authentication required", resp_missing.json()["detail"])

        resp_invalid = self.client.post(
            f"/api/compare/session/{self.session_id}/export/pdf",
            headers={"X-Session-Token": "invalid_fake_token"},
        )
        self.assertEqual(resp_invalid.status_code, 401)

    def test_export_pdf_query_param_token_rejected_400(self) -> None:
        """Tokens in query parameters are strictly rejected with 400."""
        resp = self.client.post(
            f"/api/compare/session/{self.session_id}/export/pdf?token={self.token}"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Tokens must not be passed in query parameters", resp.json()["detail"])

    def test_export_xlsx_missing_or_invalid_token_401(self) -> None:
        """Endpoint 16 requires valid X-Session-Token in header."""
        resp_missing = self.client.post(f"/api/compare/session/{self.session_id}/export/xlsx")
        self.assertEqual(resp_missing.status_code, 401)

        resp_invalid = self.client.post(
            f"/api/compare/session/{self.session_id}/export/xlsx",
            headers={"X-Session-Token": "invalid_fake_token"},
        )
        self.assertEqual(resp_invalid.status_code, 401)

    def test_export_xlsx_query_param_token_rejected_400(self) -> None:
        """Tokens in query parameters are strictly rejected with 400."""
        resp = self.client.post(
            f"/api/compare/session/{self.session_id}/export/xlsx?token={self.token}"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Tokens must not be passed in query parameters", resp.json()["detail"])

    def test_export_unprocessed_session_400(self) -> None:
        """Export before processing filings returns 400 Bad Request."""
        resp_pdf = self.client.post(
            f"/api/compare/session/{self.session_id}/export/pdf",
            headers=self.auth_headers,
        )
        self.assertEqual(resp_pdf.status_code, 400)
        self.assertIn("Please process comparison filings", resp_pdf.json()["detail"])

        resp_xlsx = self.client.post(
            f"/api/compare/session/{self.session_id}/export/xlsx",
            headers=self.auth_headers,
        )
        self.assertEqual(resp_xlsx.status_code, 400)
        self.assertIn("Please process comparison filings", resp_xlsx.json()["detail"])

    def test_export_cross_session_isolation_401(self) -> None:
        """Session B token cannot trigger exports for Session A."""
        resp_b = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(resp_b.status_code, 201)
        data_b = resp_b.json()
        session_id_b = data_b["session_id"]
        token_b = data_b["session_token"]

        # Populate session A with comparison result
        comp_res = build_test_comparison_result(self.session_id)
        session_store.save_session_comparison_result(self.session_id, comp_res)

        # Attacker with token B attempts to export session A
        resp_leak_pdf = self.client.post(
            f"/api/compare/session/{self.session_id}/export/pdf",
            headers={"X-Session-Token": token_b},
        )
        self.assertEqual(resp_leak_pdf.status_code, 401)

        resp_leak_xlsx = self.client.post(
            f"/api/compare/session/{self.session_id}/export/xlsx",
            headers={"X-Session-Token": token_b},
        )
        self.assertEqual(resp_leak_xlsx.status_code, 401)

        session_store.terminate_session(session_id_b)

    # ---------------------------------------------------------------------------
    # 2. Excel Export (7 Worksheets, Formatting & Financial Preservation)
    # ---------------------------------------------------------------------------

    def test_export_xlsx_seven_sheets_and_order(self) -> None:
        """Endpoint 16 produces valid Excel workbook with exactly seven approved sheets in order."""
        comp_res = build_test_comparison_result(self.session_id)
        session_store.save_session_comparison_result(self.session_id, comp_res)

        resp = self.client.post(
            f"/api/compare/session/{self.session_id}/export/xlsx",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment; filename=", resp.headers.get("content-disposition", ""))

        # Load workbook via openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        expected_sheets = [
            "Executive Summary",
            "Financial Metrics",
            "Calculations",
            "Risks & Disclosures",
            "Accounting Differences",
            "Source Evidence",
            "Verification Results",
        ]
        self.assertEqual(wb.sheetnames, expected_sheets)
        self.assertEqual(len(wb.sheetnames), 7)

    def test_export_xlsx_financial_accuracy_and_missing_values(self) -> None:
        """Verifies original values preserved, missing values not converted to zero, and zero macros."""
        comp_res = build_test_comparison_result(self.session_id)
        session_store.save_session_comparison_result(self.session_id, comp_res)

        resp = self.client.post(
            f"/api/compare/session/{self.session_id}/export/xlsx",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)

        wb = openpyxl.load_workbook(io.BytesIO(resp.content))

        # Check Sheet 2: Financial Metrics
        ws_metrics = wb["Financial Metrics"]
        rows = list(ws_metrics.iter_rows(values_only=True))
        headers = rows[0]
        self.assertIn("Original Reported Value", headers)
        self.assertIn("Normalized Amount (INR Cr)", headers)

        # Check EBITDA missing row
        ebitda_rows = [r for r in rows if r[0] == "EBITDA"]
        self.assertGreaterEqual(len(ebitda_rows), 2)
        for r in ebitda_rows:
            # Col 6 is Original Reported Value, Col 9 is Normalized Amount
            # Must be 'NOT_DISCLOSED', never zero!
            self.assertNotEqual(r[6], 0)
            self.assertNotEqual(r[6], 0.0)
            self.assertIn("NOT_DISCLOSED", str(r[6]))
            self.assertNotEqual(r[9], 0)
            self.assertNotEqual(r[9], 0.0)

        # Check Sheet 3: Calculations
        ws_calc = wb["Calculations"]
        calc_rows = list(ws_calc.iter_rows(values_only=True))
        self.assertGreaterEqual(len(calc_rows), 2)  # Header + calculations

        # Ensure no formula injection: formula text must start with quote or safe string
        for r in calc_rows[1:]:
            formula_val = str(r[9] or "")
            self.assertTrue(formula_val.startswith("'") or not formula_val.startswith("="))

        # Ensure workbook has no macros or VBA archives
        self.assertIsNone(wb.vba_archive)

    def test_export_xlsx_evidence_and_verifications(self) -> None:
        """Verifies Sheet 6 (Source Evidence) and Sheet 7 (Verification Results) contain verified records."""
        comp_res = build_test_comparison_result(self.session_id)
        session_store.save_session_comparison_result(self.session_id, comp_res)

        resp = self.client.post(
            f"/api/compare/session/{self.session_id}/export/xlsx",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)

        wb = openpyxl.load_workbook(io.BytesIO(resp.content))

        # Check Sheet 6: Source Evidence
        ws_ev = wb["Source Evidence"]
        ev_rows = list(ws_ev.iter_rows(values_only=True))
        self.assertGreaterEqual(len(ev_rows), 3)  # Headers + evidence items
        ev_ids = [r[0] for r in ev_rows[1:]]
        self.assertIn("ev_a1", ev_ids)
        self.assertIn("ev_b1", ev_ids)

        # Check Sheet 7: Verification Results
        ws_ver = wb["Verification Results"]
        ver_rows = list(ws_ver.iter_rows(values_only=True))
        self.assertGreaterEqual(len(ver_rows), 2)
        status_vals = [r[1] for r in ver_rows[1:]]
        self.assertTrue(any("SIMULATED" in s or "SKIPPED_LOCAL_MODE" in s for s in status_vals))

    # ---------------------------------------------------------------------------
    # 3. PDF Export (PyMuPDF Generation, Sections & Hindi Font Support)
    # ---------------------------------------------------------------------------

    def test_export_pdf_valid_structure_and_disclaimer(self) -> None:
        """Endpoint 15 produces valid multi-page PDF with mandatory SEBI disclaimer."""
        comp_res = build_test_comparison_result(self.session_id)
        session_store.save_session_comparison_result(self.session_id, comp_res)

        resp = self.client.post(
            f"/api/compare/session/{self.session_id}/export/pdf",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF-"))

        # Open and inspect PDF structure with PyMuPDF
        pdf_doc = pymupdf.open(stream=resp.content, filetype="pdf")
        self.assertGreaterEqual(len(pdf_doc), 1)

        # Extract all text from all pages
        full_text = "".join(p.get_text() for p in pdf_doc).replace("\xa0", " ").replace("‐", "-")
        pdf_doc.close()

        # Mandatory content checks
        self.assertIn("BHARAT INVESTOR COPILOT", full_text)
        self.assertIn("Tata Motors", full_text)
        self.assertIn("Maruti Suzuki", full_text)
        self.assertIn("IMPORTANT STATUTORY & NON-ADVISORY REGULATORY NOTICE", full_text)
        self.assertIn("NOT constitute SEBI-registered", full_text)
        self.assertIn("investment advice", full_text)

    def test_export_pdf_devanagari_hindi_text(self) -> None:
        """Verifies ExportPdfService handles Devanagari Hindi text cleanly."""
        comp_res = build_test_comparison_result(self.session_id)
        # Add Hindi text into executive summary narrative
        comp_res.executive_summary.overview_story = (
            "टाटा मोटर्स ने FY24 में ₹1,10,577 करोड़ का राजस्व दर्ज किया। मारुति सुजुकी का राजस्व ₹33,309 करोड़ रहा।"
        )
        comp_res.language = "Hindi"

        pdf_bytes = ExportPdfService.generate_comparison_pdf(comp_res)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

        pdf_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        self.assertGreaterEqual(len(pdf_doc), 1)
        pdf_doc.close()

    # ---------------------------------------------------------------------------
    # 4. Temporary Export Storage & Lifecycle Cleanup
    # ---------------------------------------------------------------------------

    def test_export_temporary_storage_lifecycle_and_cleanup(self) -> None:
        """Export files are created in session temporary directory and purged on session termination."""
        comp_res = build_test_comparison_result(self.session_id)
        session_store.save_session_comparison_result(self.session_id, comp_res)

        # Request PDF and Excel exports
        resp_pdf = self.client.post(
            f"/api/compare/session/{self.session_id}/export/pdf",
            headers=self.auth_headers,
        )
        self.assertEqual(resp_pdf.status_code, 200)

        resp_xlsx = self.client.post(
            f"/api/compare/session/{self.session_id}/export/xlsx",
            headers=self.auth_headers,
        )
        self.assertEqual(resp_xlsx.status_code, 200)

        # Verify export files exist in session directory
        exports_dir = self.session_dir / "exports"
        self.assertTrue(exports_dir.exists())
        cached_files = list(exports_dir.glob("comparison_*"))
        self.assertGreaterEqual(len(cached_files), 2)

        # Terminate session
        del_resp = self.client.delete(
            f"/api/compare/session/{self.session_id}",
            headers=self.auth_headers,
        )
        self.assertEqual(del_resp.status_code, 200)

        # Storage directory and exports must be completely eradicated
        self.assertFalse(self.session_dir.exists())
        self.assertFalse(exports_dir.exists())


if __name__ == "__main__":
    unittest.main()
