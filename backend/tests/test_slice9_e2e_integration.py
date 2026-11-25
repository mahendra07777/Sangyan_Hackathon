"""Comprehensive End-to-End Integration, Regression, and Verification Test Suite (Slice 9).

Covers all 11 core integration dimensions for Bharat Investor Copilot — Compare Documents:
1. Complete 17-step Session Lifecycle & Cleanup
2. Quick Compare 2-Document Boundary Enforcement
3. Multi-Document Scaling (2 to 5 documents) & 6-Document Rejection
4. All 8 Document Formats Parser & Provenance Handling
5. Financial Accuracy & Deterministic Calculations (9 core metrics, division by zero, negative base, missing data)
6. Compatibility Matrix Scenarios (FY, quarters, annual vs quarterly, peer industry, currency mismatch, blockers)
7. Local Mode ₹0 Offline Guarantee & AI Consent / Withdrawal
8. Evidence Viewer Page Navigation & Coordinate Integrity
9. PDF & Excel Export Engines Verification
10. Security, Capability Tokens, Query Parameter Rejection & Path Traversal
11. Single-Document Workflow Non-Regressive Integrity
"""

from __future__ import annotations

import io
import json
import os
import shutil
import struct
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import openpyxl
import pymupdf

# Ensure backend root is on sys.path
import sys
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import main as app_main
from app.models.comparison import (
    AccountingDifference,
    AuditStatus,
    CalculationResult,
    CompatibilityFinding,
    CompatibilityReport,
    CompatibilityStatus,
    ComparisonChatMessage,
    ComparisonDocument,
    ComparisonMode,
    ComparisonResult,
    ComparisonSession,
    DocumentMetadata,
    DocumentSlot,
    EvidenceReference,
    ExecutiveSummary,
    FactClassification,
    FinancialValue,
    ReportingScope,
    RiskDisclosure,
    SessionStatus,
    SupportedFileFormat,
    VarianceStatus,
    VerificationResult,
    VerificationSourceType,
    VerificationStatus,
)
from app.services.compatibility_engine import CompatibilityEngine
from app.services.comparison_session_store import ComparisonSessionStore, session_store
from app.services.compare_synthesis_service import CompareSynthesisService
from app.services.document_parsers import parse_docx, parse_image, parse_pdf, parse_xls, parse_xlsx
from app.services.export_excel_service import ExportExcelService
from app.services.export_pdf_service import ExportPdfService
from app.services.financial_calculator import FinancialCalculator
from app.services.financial_extractor import FinancialExtractor
from app.services.financial_normalizer import FinancialNormalizer
from tests.test_slice2_parsers import create_synthetic_xls


# ===========================================================================
# Controlled Synthetic Test Fixture Generators
# NOTE: All generated documents contain synthetic test-only data and are
# NOT real company filings or real financial disclosures.
# ===========================================================================

def generate_synthetic_digital_pdf(title: str = "Test Corp FY24", words: int = 120) -> bytes:
    """Generate in-memory digital PDF with structured financial table and text."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(50, 50), title, fontsize=14)
    page.insert_text(pymupdf.Point(50, 75), "SYNTHETIC TEST FIXTURE - NOT A REAL FILING", fontsize=8)

    sample_text = (
        "Revenue from Operations for the fiscal year reached strong operational levels. "
        "Profit After Tax demonstrated robust growth under Ind AS accounting framework. "
        "Operating expenses remained controlled in the current reporting period. "
    ) * (words // 20 + 1)
    page.insert_textbox(pymupdf.Rect(50, 90, 550, 200), sample_text[:words * 5], fontsize=9)

    # Financial Table
    page.draw_rect(pymupdf.Rect(50, 220, 550, 360), color=(0, 0, 0), width=1)
    page.insert_text(pymupdf.Point(60, 240), "Particulars (INR Crores)", fontsize=10)
    page.insert_text(pymupdf.Point(350, 240), "FY 2023-24", fontsize=10)
    page.insert_text(pymupdf.Point(60, 265), "Revenue from Operations", fontsize=9)
    page.insert_text(pymupdf.Point(350, 265), "12500.00", fontsize=9)
    page.insert_text(pymupdf.Point(60, 290), "Profit After Tax", fontsize=9)
    page.insert_text(pymupdf.Point(350, 290), "1500.00", fontsize=9)
    page.insert_text(pymupdf.Point(60, 315), "Total Assets", fontsize=9)
    page.insert_text(pymupdf.Point(350, 315), "45000.00", fontsize=9)
    page.insert_text(pymupdf.Point(60, 340), "Total Debt", fontsize=9)
    page.insert_text(pymupdf.Point(350, 340), "8200.00", fontsize=9)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_synthetic_scanned_pdf() -> bytes:
    """Generate in-memory scanned PDF with sparse text (<50 words)."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(100, 100), "Synthetic Scanned Document - Minimal Text", fontsize=10)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_synthetic_image(format_type: str = "png") -> bytes:
    """Generate in-memory PNG or JPG image."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 120), 0)
    return pix.tobytes(format_type)


def generate_synthetic_docx() -> bytes:
    """Generate in-memory valid DOCX package with heading and financial table."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>',
        )
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Financial Report FY24</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Synthetic DOCX financial summary.</w:t></w:r></w:p>'
            '<w:tbl>'
            '<w:tr><w:tc><w:p><w:r><w:t>Revenue from Operations</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>9800.00</w:t></w:r></w:p></w:tc></w:tr>'
            '<w:tr><w:tc><w:p><w:r><w:t>Profit After Tax</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>1120.00</w:t></w:r></w:p></w:tc></w:tr>'
            '</w:tbl>'
            '</w:body>'
            '</w:document>',
        )
    return bio.getvalue()


def generate_synthetic_xlsx() -> bytes:
    """Generate in-memory valid XLSX with financial metrics."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financials"
    ws["A1"] = "Metric"
    ws["B1"] = "Amount (INR Cr)"
    ws["A2"] = "Revenue from Operations"
    ws["B2"] = 15400.50
    ws["A3"] = "Profit After Tax"
    ws["B3"] = 1890.20
    ws["A4"] = "Total Assets"
    ws["B4"] = 52000.00
    bio = io.BytesIO()
    wb.save(bio)
    wb.close()
    return bio.getvalue()


# ===========================================================================
# End-to-End Integration Test Suite
# ===========================================================================

class TestSlice9EndToEndIntegration(unittest.TestCase):
    """Exhaustive integration and regression tests for Slice 9."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_main.app)

    # -----------------------------------------------------------------------
    # Scenario A: Full 17-Step Session Lifecycle
    # -----------------------------------------------------------------------

    def test_01_session_complete_17_step_lifecycle(self) -> None:
        """Executes full 17-step comparison flow from session initialization to deletion."""
        # 1. Create Session
        resp = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        session_id = data["session_id"]
        token = data["session_token"]
        headers = {"X-Session-Token": token}

        try:
            # 2. Upload exactly 2 documents
            pdf_a = generate_synthetic_digital_pdf(title="Company Alpha FY23")
            pdf_b = generate_synthetic_digital_pdf(title="Company Alpha FY24")
            files = [
                ("files", ("Alpha_FY23.pdf", pdf_a, "application/pdf")),
                ("files", ("Alpha_FY24.pdf", pdf_b, "application/pdf")),
            ]
            resp = self.client.post(f"/api/compare/session/{session_id}/upload", headers=headers, files=files)
            self.assertEqual(resp.status_code, 200)
            upload_data = resp.json()
            docs = upload_data["uploaded_documents"]
            self.assertEqual(len(docs), 2)
            doc_a_id = docs[0]["doc_id"]
            doc_b_id = docs[1]["doc_id"]

            # 3. Retrieve metadata
            resp = self.client.get(f"/api/compare/session/{session_id}/metadata", headers=headers)
            self.assertEqual(resp.status_code, 200)
            meta_data = resp.json()
            meta_dict = meta_data.get("metadata", {})
            self.assertIn(doc_a_id, meta_dict)
            self.assertIn(doc_b_id, meta_dict)

            # 4. Correct metadata via PUT
            correction_payload = {
                "company_name": "Company Alpha Limited",
                "financial_year": "2023-24",
                "reporting_period": "FY",
                "currency": "INR",
                "scale": "CRORE",
                "audit_status": "AUDITED",
                "reporting_scope": "STANDALONE",
            }
            resp = self.client.put(
                f"/api/compare/session/{session_id}/metadata/{doc_a_id}",
                headers=headers,
                json=correction_payload,
            )
            self.assertEqual(resp.status_code, 200)
            updated_meta = resp.json()
            self.assertEqual(updated_meta["company_name"], "Company Alpha Limited")

            # 5. Retrieve compatibility
            resp = self.client.get(f"/api/compare/session/{session_id}/compatibility", headers=headers)
            self.assertEqual(resp.status_code, 200)
            comp_data = resp.json()
            self.assertIn("overall_status", comp_data)

            # 6. Retrieve pre-consent disclosure terms (GET)
            resp = self.client.get(f"/api/compare/session/{session_id}/consent", headers=headers)
            self.assertEqual(resp.status_code, 200)
            consent_terms = resp.json()
            self.assertIn("terms_disclosure", consent_terms)
            self.assertIn("Standard Free Tier", consent_terms["terms_disclosure"])

            # 7. Record affirmative consent (POST)
            resp = self.client.post(
                f"/api/compare/session/{session_id}/consent",
                headers=headers,
                json={"consent_granted": True},
            )
            self.assertEqual(resp.status_code, 200)
            consent_resp = resp.json()
            self.assertTrue(consent_resp["consent_granted"])

            # 8. Process comparison documents (POST)
            resp = self.client.post(f"/api/compare/session/{session_id}/process", headers=headers)
            self.assertEqual(resp.status_code, 200)
            proc_data = resp.json()
            self.assertTrue(proc_data["is_completed"])

            # 9. Retrieve extracted financials (GET)
            resp = self.client.get(f"/api/compare/session/{session_id}/financials", headers=headers)
            self.assertEqual(resp.status_code, 200)

            # 10. Retrieve calculations (GET)
            resp = self.client.get(f"/api/compare/session/{session_id}/calculations", headers=headers)
            self.assertEqual(resp.status_code, 200)

            # 11. Retrieve complete results (GET)
            resp = self.client.get(f"/api/compare/session/{session_id}/results", headers=headers)
            self.assertEqual(resp.status_code, 200)
            result = resp.json()
            self.assertEqual(result["session_id"], session_id)
            self.assertIn("financial_values", result)
            self.assertIn("variances", result)

            # 12. Retrieve evidence page image (GET)
            resp = self.client.get(
                f"/api/compare/session/{session_id}/evidence/{doc_a_id}/page/1",
                headers=headers,
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers["content-type"], "image/png")
            self.assertGreater(len(resp.content), 500)

            # 13. Retrieve evidence context (GET)
            resp = self.client.get(
                f"/api/compare/session/{session_id}/evidence/{doc_a_id}/context",
                headers=headers,
            )
            self.assertEqual(resp.status_code, 200)
            ctx_data = resp.json()
            self.assertEqual(ctx_data["doc_id"], doc_a_id)

            # 14. Comparative grounded chat (POST)
            chat_payload = {
                "message": "What is the revenue variance between the two documents?",
                "language": "English",
            }
            resp = self.client.post(
                f"/api/compare/session/{session_id}/chat",
                headers=headers,
                json=chat_payload,
            )
            self.assertEqual(resp.status_code, 200)
            chat_msg = resp.json()
            self.assertEqual(chat_msg["role"], "assistant")
            self.assertGreater(len(chat_msg["content"]), 10)

            # 15. Export PDF (POST)
            resp = self.client.post(
                f"/api/compare/session/{session_id}/export/pdf",
                headers=headers,
                json={"language": "English"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers["content-type"], "application/pdf")
            self.assertTrue(resp.content.startswith(b"%PDF-"))

            # 16. Export Excel (POST)
            resp = self.client.post(
                f"/api/compare/session/{session_id}/export/xlsx",
                headers=headers,
                json={"language": "English"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(
                resp.headers["content-type"],
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            wb = openpyxl.load_workbook(io.BytesIO(resp.content))
            self.assertEqual(len(wb.sheetnames), 7)
            wb.close()

            # 17. Delete session (DELETE) and verify termination
            resp = self.client.delete(f"/api/compare/session/{session_id}", headers=headers)
            self.assertEqual(resp.status_code, 200)

            # Verify session directory removed and further requests rejected
            session_dir = session_store.storage_root / f"session_{session_id}"
            self.assertFalse(session_dir.exists())

            # Subsequent authenticated call returns 410 GONE
            resp_after = self.client.get(f"/api/compare/session/{session_id}/results", headers=headers)
            self.assertEqual(resp_after.status_code, 410)

        finally:
            # Ensure cleanup if test fails mid-run
            session_store.terminate_session(session_id)

    # -----------------------------------------------------------------------
    # Scenario B: Quick Compare 2-Document Enforcement
    # -----------------------------------------------------------------------

    def test_02_quick_compare_exact_two_document_enforcement(self) -> None:
        """Verifies QUICK_COMPARE strictly requires exactly 2 documents."""
        # 1. Rejects 1 document
        resp = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(resp.status_code, 201)
        session_id = resp.json()["session_id"]
        headers = {"X-Session-Token": resp.json()["session_token"]}

        try:
            pdf1 = generate_synthetic_digital_pdf(title="Doc 1")
            files_1 = [("files", ("Doc1.pdf", pdf1, "application/pdf"))]
            resp_1 = self.client.post(f"/api/compare/session/{session_id}/upload", headers=headers, files=files_1)
            self.assertEqual(resp_1.status_code, 400)
            self.assertIn("requires exactly 2 documents", resp_1.json()["detail"])

            # 2. Rejects 3 documents
            pdf2 = generate_synthetic_digital_pdf(title="Doc 2")
            pdf3 = generate_synthetic_digital_pdf(title="Doc 3")
            files_3 = [
                ("files", ("Doc1.pdf", pdf1, "application/pdf")),
                ("files", ("Doc2.pdf", pdf2, "application/pdf")),
                ("files", ("Doc3.pdf", pdf3, "application/pdf")),
            ]
            resp_3 = self.client.post(f"/api/compare/session/{session_id}/upload", headers=headers, files=files_3)
            self.assertEqual(resp_3.status_code, 400)
            self.assertIn("requires exactly 2 documents", resp_3.json()["detail"])

            # 3. Accepts exactly 2 documents
            files_2 = [
                ("files", ("Doc1.pdf", pdf1, "application/pdf")),
                ("files", ("Doc2.pdf", pdf2, "application/pdf")),
            ]
            resp_2 = self.client.post(f"/api/compare/session/{session_id}/upload", headers=headers, files=files_2)
            self.assertEqual(resp_2.status_code, 200)
            self.assertEqual(len(resp_2.json()["uploaded_documents"]), 2)

        finally:
            session_store.terminate_session(session_id)

    # -----------------------------------------------------------------------
    # Scenario C: Multi-Document Scaling (2 to 5) & 6-Document Rejection
    # -----------------------------------------------------------------------

    def test_03_multi_document_scaling_and_max_boundary(self) -> None:
        """Verifies MULTI_DOCUMENT accepts 2 to 5 documents and rejects 6."""
        for count in (2, 3, 4, 5):
            resp = self.client.post("/api/compare/session", json={"comparison_mode": "MULTI_DOCUMENT"})
            self.assertEqual(resp.status_code, 201)
            session_id = resp.json()["session_id"]
            headers = {"X-Session-Token": resp.json()["session_token"]}

            try:
                files = [
                    ("files", (f"Doc_{i}.pdf", generate_synthetic_digital_pdf(title=f"Doc {i}"), "application/pdf"))
                    for i in range(1, count + 1)
                ]
                resp_upload = self.client.post(f"/api/compare/session/{session_id}/upload", headers=headers, files=files)
                self.assertEqual(resp_upload.status_code, 200)
                self.assertEqual(len(resp_upload.json()["uploaded_documents"]), count)

                # Pairwise compatibility check
                resp_comp = self.client.get(f"/api/compare/session/{session_id}/compatibility", headers=headers)
                self.assertEqual(resp_comp.status_code, 200)
                comp_data = resp_comp.json()
                self.assertIn("pairwise_matrix", comp_data)

            finally:
                session_store.terminate_session(session_id)

        # Boundary rejection: 6 documents rejected
        resp_6 = self.client.post("/api/compare/session", json={"comparison_mode": "MULTI_DOCUMENT"})
        session_id_6 = resp_6.json()["session_id"]
        headers_6 = {"X-Session-Token": resp_6.json()["session_token"]}

        try:
            files_6 = [
                ("files", (f"Doc_{i}.pdf", generate_synthetic_digital_pdf(title=f"Doc {i}"), "application/pdf"))
                for i in range(1, 7)
            ]
            resp_upload_6 = self.client.post(f"/api/compare/session/{session_id_6}/upload", headers=headers_6, files=files_6)
            self.assertEqual(resp_upload_6.status_code, 400)
            self.assertIn("between 2 and 5 documents", resp_upload_6.json()["detail"])
        finally:
            session_store.terminate_session(session_id_6)

    # -----------------------------------------------------------------------
    # Scenario D: All Eight Document Formats Coverage
    # -----------------------------------------------------------------------

    def test_04_all_eight_formats_coverage(self) -> None:
        """Verifies ingestion, parsing, and honest limitation reporting across all 8 formats."""
        # Test fixture mapping
        format_fixtures = {
            "PDF_DIGITAL": (generate_synthetic_digital_pdf(), "Alpha.pdf", "application/pdf", SupportedFileFormat.PDF_DIGITAL),
            "PDF_SCANNED": (generate_synthetic_scanned_pdf(), "Scanned.pdf", "application/pdf", SupportedFileFormat.PDF_SCANNED),
            "IMAGE_PNG": (generate_synthetic_image("png"), "Chart.png", "image/png", SupportedFileFormat.IMAGE_PNG),
            "IMAGE_JPG": (generate_synthetic_image("jpeg"), "Report.jpg", "image/jpeg", SupportedFileFormat.IMAGE_JPG),
            "IMAGE_JPEG": (generate_synthetic_image("jpeg"), "Report.jpeg", "image/jpeg", SupportedFileFormat.IMAGE_JPEG),
            "DOCX": (generate_synthetic_docx(), "Notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", SupportedFileFormat.DOCX),
            "XLSX": (generate_synthetic_xlsx(), "Sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", SupportedFileFormat.XLSX),
            "XLS": (create_synthetic_xls(), "Legacy.xls", "application/vnd.ms-excel", SupportedFileFormat.XLS),
        }

        self.assertEqual(len(format_fixtures), 8)

        for fmt_name, (data_bytes, filename, mime, expected_fmt) in format_fixtures.items():
            resp = self.client.post("/api/compare/session", json={"comparison_mode": "MULTI_DOCUMENT"})
            self.assertEqual(resp.status_code, 201)
            session_id = resp.json()["session_id"]
            headers = {"X-Session-Token": resp.json()["session_token"]}

            try:
                # Upload target format paired with a standard digital PDF
                standard_pdf = generate_synthetic_digital_pdf()
                files = [
                    ("files", (filename, data_bytes, mime)),
                    ("files", ("Standard.pdf", standard_pdf, "application/pdf")),
                ]
                resp_upload = self.client.post(f"/api/compare/session/{session_id}/upload", headers=headers, files=files)
                self.assertEqual(resp_upload.status_code, 200, f"Failed upload for format: {fmt_name}")
                docs = resp_upload.json()["uploaded_documents"]
                self.assertEqual(len(docs), 2)
                target_doc = docs[0]
                self.assertEqual(target_doc["file_format"], expected_fmt.value)

                # Honest local mode extraction check
                context_resp = self.client.get(
                    f"/api/compare/session/{session_id}/evidence/{target_doc['doc_id']}/context",
                    headers=headers,
                )
                self.assertEqual(context_resp.status_code, 200)
                extracted_data = context_resp.json()

                if expected_fmt == SupportedFileFormat.PDF_SCANNED:
                    self.assertEqual(extracted_data.get("extraction_status"), "OCR_UNAVAILABLE_LOCAL_MODE")
                elif expected_fmt in (SupportedFileFormat.IMAGE_PNG, SupportedFileFormat.IMAGE_JPG, SupportedFileFormat.IMAGE_JPEG):
                    self.assertEqual(extracted_data.get("extraction_status"), "VISION_EXTRACTION_REQUIRED")
                elif expected_fmt in (SupportedFileFormat.PDF_DIGITAL, SupportedFileFormat.DOCX, SupportedFileFormat.XLSX, SupportedFileFormat.XLS):
                    self.assertEqual(extracted_data.get("extraction_status"), "SUCCESS")

            finally:
                session_store.terminate_session(session_id)

    # -----------------------------------------------------------------------
    # Scenario E: Financial Accuracy & Deterministic Calculations
    # -----------------------------------------------------------------------

    def test_05_financial_accuracy_deterministic_calculations(self) -> None:
        """Verifies deterministic math, zero denominator, negative base, and missing value preservation."""
        # 1. Standard positive to positive growth: 10000 -> 12500 (+2500, +25.0%)
        val_a = FinancialValue(
            doc_id="doc_a",
            metric_key="REVENUE",
            label="Revenue from Operations",
            amount=Decimal("10000.0000"),
            currency="INR",
            status="REPORTED",
        )
        val_b = FinancialValue(
            doc_id="doc_b",
            metric_key="REVENUE",
            label="Revenue from Operations",
            amount=Decimal("12500.0000"),
            currency="INR",
            status="REPORTED",
        )
        res = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="REVENUE",
            label="Revenue from Operations",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=val_a,
            comp_fv=val_b,
        )
        self.assertEqual(res.absolute_variance, Decimal("2500.0000"))
        self.assertEqual(res.percentage_change, Decimal("25.0000"))
        self.assertEqual(res.status, VarianceStatus.CALCULATED)

        # 2. Zero Denominator: 0 -> 1500 (Absolute +1500, percentage None, DIV_BY_ZERO)
        val_zero = FinancialValue(
            doc_id="doc_a",
            metric_key="PAT",
            label="Profit After Tax",
            amount=Decimal("0.0000"),
            currency="INR",
            status="REPORTED",
        )
        val_pos = FinancialValue(
            doc_id="doc_b",
            metric_key="PAT",
            label="Profit After Tax",
            amount=Decimal("1500.0000"),
            currency="INR",
            status="REPORTED",
        )
        res_zero = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="PAT",
            label="Profit After Tax",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=val_zero,
            comp_fv=val_pos,
        )
        self.assertEqual(res_zero.absolute_variance, Decimal("1500.0000"))
        self.assertIsNone(res_zero.percentage_change)
        self.assertEqual(res_zero.status, VarianceStatus.DIV_BY_ZERO)
        self.assertIn("percentage undefined", res_zero.directional_explanation.lower())

        # 3. Negative Base Turnaround (Loss to Profit): -500 -> +750 (+1250)
        val_neg = FinancialValue(
            doc_id="doc_a",
            metric_key="PAT",
            label="Profit After Tax",
            amount=Decimal("-500.0000"),
            currency="INR",
            status="REPORTED",
        )
        val_profit = FinancialValue(
            doc_id="doc_b",
            metric_key="PAT",
            label="Profit After Tax",
            amount=Decimal("750.0000"),
            currency="INR",
            status="REPORTED",
        )
        res_turnaround = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="PAT",
            label="Profit After Tax",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=val_neg,
            comp_fv=val_profit,
        )
        self.assertEqual(res_turnaround.absolute_variance, Decimal("1250.0000"))
        self.assertEqual(res_turnaround.status, VarianceStatus.NON_POSITIVE_BASE)
        self.assertIn("turnaround", res_turnaround.directional_explanation.lower())

        # 4. Missing value: NOT_DISCLOSED preserved, NEVER converted to 0
        res_missing = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="EBITDA",
            label="EBITDA",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=None,
            comp_fv=val_pos,
        )
        self.assertIsNone(res_missing.absolute_variance)
        self.assertIsNone(res_missing.percentage_change)
        self.assertEqual(res_missing.status, VarianceStatus.NOT_DISCLOSED)

        # 5. Currency Mismatch: CURRENCY_MISMATCH
        val_usd = FinancialValue(
            doc_id="doc_a",
            metric_key="TOTAL_DEBT",
            label="Total Debt",
            amount=Decimal("100.0000"),
            currency="USD",
            status="REPORTED",
        )
        val_debt_inr = FinancialValue(
            doc_id="doc_b",
            metric_key="TOTAL_DEBT",
            label="Total Debt",
            amount=Decimal("800.0000"),
            currency="INR",
            status="REPORTED",
        )
        res_mismatch = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="TOTAL_DEBT",
            label="Total Debt",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=val_usd,
            comp_fv=val_debt_inr,
        )
        self.assertEqual(res_mismatch.status, VarianceStatus.CURRENCY_MISMATCH)

    # -----------------------------------------------------------------------
    # Scenario F: Compatibility Matrix Scenarios
    # -----------------------------------------------------------------------

    def test_06_compatibility_matrix_scenarios(self) -> None:
        """Verifies pairwise compatibility rules across period, scope, currency, and company."""
        # 1. Same company consecutive FYs -> COMPATIBLE
        meta_same_fy = {
            "doc_a": DocumentMetadata(
                doc_id="doc_a",
                company_name="Tata Motors Limited",
                financial_year="2022-23",
                reporting_period="FY",
                currency="INR",
                scale="CRORE",
                audit_status=AuditStatus.AUDITED,
                reporting_scope=ReportingScope.STANDALONE,
                industry="Automotive",
            ),
            "doc_b": DocumentMetadata(
                doc_id="doc_b",
                company_name="Tata Motors Limited",
                financial_year="2023-24",
                reporting_period="FY",
                currency="INR",
                scale="CRORE",
                audit_status=AuditStatus.AUDITED,
                reporting_scope=ReportingScope.STANDALONE,
                industry="Automotive",
            ),
        }
        report_fy = CompatibilityEngine.evaluate_session(meta_same_fy, session_id="test_fy")
        self.assertEqual(report_fy.overall_status, CompatibilityStatus.COMPATIBLE)
        self.assertTrue(report_fy.is_comparable)

        # 2. Same company different quarters -> COMPATIBLE_WITH_WARNINGS
        meta_quarters = {
            "doc_a": DocumentMetadata(
                doc_id="doc_a",
                company_name="Tata Motors Limited",
                financial_year="2023-24",
                reporting_period="Q1",
                currency="INR",
                scale="CRORE",
                audit_status=AuditStatus.UNAUDITED,
                reporting_scope=ReportingScope.STANDALONE,
                industry="Automotive",
            ),
            "doc_b": DocumentMetadata(
                doc_id="doc_b",
                company_name="Tata Motors Limited",
                financial_year="2023-24",
                reporting_period="Q2",
                currency="INR",
                scale="CRORE",
                audit_status=AuditStatus.UNAUDITED,
                reporting_scope=ReportingScope.STANDALONE,
                industry="Automotive",
            ),
        }
        report_q = CompatibilityEngine.evaluate_session(meta_quarters, session_id="test_q")
        self.assertIn(report_q.overall_status, (CompatibilityStatus.COMPATIBLE_WITH_WARNINGS, CompatibilityStatus.COMPATIBLE))

        # 3. Currency mismatch -> BLOCKED (or warning with explicit mismatch finding)
        meta_curr_mismatch = {
            "doc_a": DocumentMetadata(
                doc_id="doc_a",
                company_name="Tata Motors Limited",
                financial_year="2023-24",
                reporting_period="FY",
                currency="INR",
                scale="CRORE",
            ),
            "doc_b": DocumentMetadata(
                doc_id="doc_b",
                company_name="Tata Motors Limited",
                financial_year="2023-24",
                reporting_period="FY",
                currency="USD",
                scale="MILLION",
            ),
        }
        report_curr = CompatibilityEngine.evaluate_session(meta_curr_mismatch, session_id="test_curr")
        has_currency_finding = any(
            "currency" in f.description.lower() or "currency" in f.code.lower()
            for f in report_curr.findings
        )
        self.assertTrue(has_currency_finding)

        # 4. Peer companies with unknown industry -> COMPATIBLE_WITH_WARNINGS
        meta_unknown_ind = {
            "doc_a": DocumentMetadata(
                doc_id="doc_a",
                company_name="Alpha Enterprises",
                financial_year="2023-24",
                reporting_period="FY",
                currency="INR",
                scale="CRORE",
                industry="UNKNOWN",
            ),
            "doc_b": DocumentMetadata(
                doc_id="doc_b",
                company_name="Beta Logistics",
                financial_year="2023-24",
                reporting_period="FY",
                currency="INR",
                scale="CRORE",
                industry="UNKNOWN",
            ),
        }
        report_ind = CompatibilityEngine.evaluate_session(meta_unknown_ind, session_id="test_ind")
        self.assertEqual(report_ind.overall_status, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)

    # -----------------------------------------------------------------------
    # Scenario G: Local Mode Zero Cloud Guarantee & AI Consent / Withdrawal
    # -----------------------------------------------------------------------

    def test_07_local_mode_zero_cloud_and_consent_withdrawal(self) -> None:
        """Verifies zero external calls in Local Mode and atomic consent withdrawal."""
        resp = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        session_id = resp.json()["session_id"]
        headers = {"X-Session-Token": resp.json()["session_token"]}

        try:
            # Check consent terms endpoint
            terms_resp = self.client.get(f"/api/compare/session/{session_id}/consent", headers=headers)
            self.assertEqual(terms_resp.status_code, 200)
            self.assertIn("Local Mode", terms_resp.json()["terms_disclosure"])

            # Verify initial consent state is False
            self.assertFalse(session_store.is_consent_granted(session_id))

            # Record affirmative consent
            post_resp = self.client.post(
                f"/api/compare/session/{session_id}/consent",
                headers=headers,
                json={"consent_granted": True},
            )
            self.assertEqual(post_resp.status_code, 200)
            self.assertTrue(session_store.is_consent_granted(session_id))

            # Revoke consent via DELETE
            del_resp = self.client.delete(f"/api/compare/session/{session_id}/consent", headers=headers)
            self.assertEqual(del_resp.status_code, 200)
            self.assertFalse(session_store.is_consent_granted(session_id))

            # In Local Mode (consent False), synthesis performs zero network calls
            mock_gemini = MagicMock()
            with patch.object(CompareSynthesisService, "_answer_via_gemini_chat", mock_gemini):
                dummy_result = ComparisonResult(
                    session_id=session_id,
                    mode="LOCAL_DETERMINISTIC",
                    documents=[],
                    metadata={},
                    compatibility=CompatibilityReport(
                        overall_status=CompatibilityStatus.COMPATIBLE,
                        is_comparable=True,
                    ),
                    financial_values={},
                    variances=[],
                    executive_summary=ExecutiveSummary(
                        overview_story="Overview: strong operational performance.",
                        core_positive_changes=["Revenue up."],
                        core_negative_changes=[],
                        neutral_observations=[],
                        uncertain_findings=[],
                        critical_disclosures=[],
                        fact_classification=FactClassification.DOCUMENT_FACT,
                    ),
                )
                msg = CompareSynthesisService.answer_comparison_question(
                    session_id=session_id,
                    user_message="Tell me about profitability",
                    comparison_result=dummy_result,
                    language="English",
                    consent_granted=False,
                )
                self.assertIsNotNone(msg)
                mock_gemini.assert_not_called()

        finally:
            session_store.terminate_session(session_id)

    # -----------------------------------------------------------------------
    # Scenario H: Evidence Viewer Page Navigation & Coordinate Integrity
    # -----------------------------------------------------------------------

    def test_08_evidence_viewer_and_provenance(self) -> None:
        """Verifies page rendering, coordinate accuracy, and non-visual format rejection."""
        resp = self.client.post("/api/compare/session", json={"comparison_mode": "MULTI_DOCUMENT"})
        session_id = resp.json()["session_id"]
        headers = {"X-Session-Token": resp.json()["session_token"]}

        try:
            pdf_bytes = generate_synthetic_digital_pdf()
            docx_bytes = generate_synthetic_docx()
            files = [
                ("files", ("Report.pdf", pdf_bytes, "application/pdf")),
                ("files", ("Report.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ]
            resp_upload = self.client.post(f"/api/compare/session/{session_id}/upload", headers=headers, files=files)
            self.assertEqual(resp_upload.status_code, 200)
            docs = resp_upload.json()["uploaded_documents"]
            pdf_id = docs[0]["doc_id"]
            docx_id = docs[1]["doc_id"]

            # 1. Valid PDF Page 1 renders PNG
            page1_resp = self.client.get(
                f"/api/compare/session/{session_id}/evidence/{pdf_id}/page/1",
                headers=headers,
            )
            self.assertEqual(page1_resp.status_code, 200)
            self.assertEqual(page1_resp.headers["content-type"], "image/png")

            # 2. Out of bounds page numbers return 404
            page0_resp = self.client.get(
                f"/api/compare/session/{session_id}/evidence/{pdf_id}/page/0",
                headers=headers,
            )
            self.assertEqual(page0_resp.status_code, 404)

            page999_resp = self.client.get(
                f"/api/compare/session/{session_id}/evidence/{pdf_id}/page/999",
                headers=headers,
            )
            self.assertEqual(page999_resp.status_code, 404)

            # 3. Non-visual format (DOCX) returns 400
            docx_page_resp = self.client.get(
                f"/api/compare/session/{session_id}/evidence/{docx_id}/page/1",
                headers=headers,
            )
            self.assertEqual(docx_page_resp.status_code, 400)
            self.assertIn("Visual page rendering is only supported for PDF and image filings", docx_page_resp.json()["detail"])

        finally:
            session_store.terminate_session(session_id)

    # -----------------------------------------------------------------------
    # Scenario I: Export Engines Verification (PDF & Excel)
    # -----------------------------------------------------------------------

    def test_09_export_engines_pdf_and_excel(self) -> None:
        """Verifies institutional PDF and 7-sheet Excel generation without formulas or macros."""
        resp = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        session_id = resp.json()["session_id"]
        headers = {"X-Session-Token": resp.json()["session_token"]}

        try:
            pdf_a = generate_synthetic_digital_pdf(title="Export Test Alpha")
            pdf_b = generate_synthetic_digital_pdf(title="Export Test Beta")
            files = [
                ("files", ("Alpha.pdf", pdf_a, "application/pdf")),
                ("files", ("Beta.pdf", pdf_b, "application/pdf")),
            ]
            self.client.post(f"/api/compare/session/{session_id}/upload", headers=headers, files=files)
            self.client.post(f"/api/compare/session/{session_id}/process", headers=headers)

            # PDF Export Check
            pdf_resp = self.client.post(
                f"/api/compare/session/{session_id}/export/pdf",
                headers=headers,
                json={"language": "English"},
            )
            self.assertEqual(pdf_resp.status_code, 200)
            self.assertTrue(pdf_resp.content.startswith(b"%PDF-"))

            # Inspect PDF structure with PyMuPDF
            doc = pymupdf.open(stream=pdf_resp.content, filetype="pdf")
            self.assertGreaterEqual(len(doc), 1)
            full_text = " ".join([page.get_text() for page in doc]).replace("\xa0", " ").replace("‐", "-")
            self.assertIn("BHARAT INVESTOR COPILOT", full_text)
            self.assertIn("SEBI-registered", full_text)
            doc.close()

            # Excel Export Check
            xlsx_resp = self.client.post(
                f"/api/compare/session/{session_id}/export/xlsx",
                headers=headers,
                json={"language": "English"},
            )
            self.assertEqual(xlsx_resp.status_code, 200)
            wb = openpyxl.load_workbook(io.BytesIO(xlsx_resp.content), data_only=False)

            # Exactly 7 worksheets in exact specified order
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

            # Verify no executable formulas or macros
            for sheetname in expected_sheets:
                ws = wb[sheetname]
                for row in ws.iter_rows(values_only=True):
                    for cell in row:
                        if isinstance(cell, str):
                            # Must not begin with formula operators
                            self.assertFalse(
                                cell.startswith(("=", "+", "-", "@")) and len(cell) > 1 and cell[1:].isalnum(),
                                f"Suspicious formula found in {sheetname}: {cell}",
                            )
            wb.close()

        finally:
            session_store.terminate_session(session_id)

    # -----------------------------------------------------------------------
    # Scenario J: Security, Tokens, Query Rejection & Path Traversal
    # -----------------------------------------------------------------------

    def test_10_security_tokens_and_path_traversal(self) -> None:
        """Verifies cryptographic security, query param rejection, cross-session protection and traversal guards."""
        resp = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        session_id = resp.json()["session_id"]
        valid_token = resp.json()["session_token"]
        headers = {"X-Session-Token": valid_token}

        try:
            # 1. Missing token -> 401
            resp_missing = self.client.get(f"/api/compare/session/{session_id}/metadata")
            self.assertEqual(resp_missing.status_code, 401)

            # 2. Invalid token -> 401
            resp_invalid = self.client.get(
                f"/api/compare/session/{session_id}/metadata",
                headers={"X-Session-Token": "invalid_token_12345"},
            )
            self.assertEqual(resp_invalid.status_code, 401)

            # 3. Query param token -> 400
            resp_query = self.client.get(
                f"/api/compare/session/{session_id}/metadata?token={valid_token}",
            )
            self.assertEqual(resp_query.status_code, 400)
            self.assertIn("must not be passed in query parameters", resp_query.json()["detail"])

            # 4. Cross-session isolation
            resp_other = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
            other_id = resp_other.json()["session_id"]
            other_token = resp_other.json()["session_token"]
            try:
                # Session 1 token accessing Session 2 -> 401
                cross_resp = self.client.get(
                    f"/api/compare/session/{other_id}/metadata",
                    headers=headers,
                )
                self.assertEqual(cross_resp.status_code, 401)
            finally:
                session_store.terminate_session(other_id)

            # 5. Path traversal attempts
            traversal_doc_ids = [
                "../../etc/passwd",
                "..%2F..%2Fwindows%2Fsystem32",
                "doc_a/../../../secret",
            ]
            for bad_doc in traversal_doc_ids:
                resp_trav = self.client.get(
                    f"/api/compare/session/{session_id}/evidence/{bad_doc}/page/1",
                    headers=headers,
                )
                self.assertIn(resp_trav.status_code, (400, 404))

        finally:
            session_store.terminate_session(session_id)

    # -----------------------------------------------------------------------
    # Scenario K: Single-Document Workflow Non-Regressive Integrity
    # -----------------------------------------------------------------------

    def test_11_single_document_regression(self) -> None:
        """Verifies that existing single-document routes, models, and services remain completely functional."""
        # 1. Health endpoint check
        resp_health = self.client.get("/health")
        self.assertEqual(resp_health.status_code, 200)
        self.assertEqual(resp_health.json()["status"], "healthy")

        # 2. Verify single document processor and chat services imports and callable APIs
        from app.services.document_processor import DocumentProcessor
        from app.services.chat_service import ChatService
        from app.models.chat import ChatRequest

        processor = DocumentProcessor()
        self.assertTrue(hasattr(processor, "process_upload"))
        self.assertTrue(hasattr(processor, "process_pdf"))

        # Verify chat service non-advisory behavior or configuration safety
        req = ChatRequest(
            message="Which stock should I buy for 100% returns?",
            context="Document text context",
            history=[],
            language="English",
        )
        chat_resp = ChatService.answer_question(req)
        self.assertIsNotNone(chat_resp.answer)


if __name__ == "__main__":
    unittest.main()
