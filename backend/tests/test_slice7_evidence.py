"""Comprehensive automated test suite for Compare Documents Slice 7:
Evidence Viewer, Source Traceability & Document Navigation.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Dict

from fastapi.testclient import TestClient
import pymupdf

from app.models.comparison import (
    ComparisonDocument,
    DocumentExtractionResult,
    ExtractedTable,
    ExtractedTableCell,
    ExtractedTextBlock,
    SupportedFileFormat,
)
from app.services.comparison_session_store import session_store
import main as app_main


class TestSlice7EvidenceViewer(unittest.TestCase):
    """Test suite covering Endpoint 13 (Page Rendering) & Endpoint 13.1 (Context) for Slice 7."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_main.app)

    def setUp(self) -> None:
        # Create a fresh session for each test
        resp = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.session_id = data["session_id"]
        self.token = data["session_token"]
        self.auth_headers = {"X-Session-Token": self.token}
        self.session_dir = session_store.resolve_session_path(self.session_id)

    def tearDown(self) -> None:
        session_store.terminate_session(self.session_id)

    def _create_sample_pdf(self, filename: str, num_pages: int = 2) -> Path:
        """Helper to create a valid multi-page PDF using PyMuPDF."""
        doc_dir = self.session_dir / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = doc_dir / filename

        doc = pymupdf.open()
        for i in range(num_pages):
            page = doc.new_page(width=595, height=842)
            page.insert_text((50, 72), f"Sangyan Bharat Investor Copilot - Page {i + 1}")
            page.insert_text((50, 100), f"Sample Revenue FY24: Rs. {1000 * (i + 1)} Crores")
        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    def _create_sample_image(self, filename: str, format_type: str = "png") -> Path:
        """Helper to create a valid image file using PyMuPDF pixmap."""
        doc_dir = self.session_dir / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        img_path = doc_dir / filename

        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
        pix.clear_with(240)  # Light gray
        if format_type.lower() == "png":
            img_bytes = pix.tobytes("png")
        else:
            # Save as jpeg
            img_bytes = pix.tobytes("jpeg")
        img_path.write_bytes(img_bytes)
        return img_path

    def _register_document(self, doc: ComparisonDocument, session_id: Optional[str] = None) -> None:
        sid = session_id or self.session_id
        docs = session_store.get_session_documents(sid)
        docs.append(doc)
        session_store.save_session_documents(sid, docs)

    # ---------------------------------------------------------------------------
    # 1. Security & Authentication Checks
    # ---------------------------------------------------------------------------

    def test_evidence_page_missing_or_invalid_token(self) -> None:
        """Endpoint 13 requires a valid X-Session-Token header."""
        # Missing token
        resp = self.client.get(f"/api/compare/session/{self.session_id}/evidence/doc_a/page/1")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Authentication required", resp.json()["detail"])

        # Invalid token
        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/page/1",
            headers={"X-Session-Token": "invalid_fake_token_value_here"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid", resp.json()["detail"])

    def test_evidence_page_query_param_token_rejected(self) -> None:
        """Tokens passed via query parameter are strictly rejected with 400 Bad Request."""
        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/page/1?token={self.token}",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Tokens must not be passed in query parameters", resp.json()["detail"])

    def test_evidence_context_missing_or_invalid_token(self) -> None:
        """Endpoint 13.1 requires valid X-Session-Token in header."""
        resp = self.client.get(f"/api/compare/session/{self.session_id}/evidence/doc_a/context")
        self.assertEqual(resp.status_code, 401)

        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/context?token={self.token}"
        )
        self.assertEqual(resp.status_code, 400)

    # ---------------------------------------------------------------------------
    # 2. PDF Page Rendering (Endpoint 13)
    # ---------------------------------------------------------------------------

    def test_evidence_pdf_page_render_success(self) -> None:
        """Endpoint 13 renders digital PDF pages to 150 DPI PNG byte stream."""
        pdf_path = self._create_sample_pdf("doc_a.pdf", num_pages=2)
        doc = ComparisonDocument(
            doc_id="doc_a",
            slot="doc_a",
            original_filename="doc_a.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=pdf_path.stat().st_size,
            storage_rel_path="documents/doc_a.pdf",
        )
        self._register_document(doc)

        # Page 1
        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/page/1",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "image/png")
        self.assertTrue(resp.content.startswith(b"\x89PNG\r\n\x1a\n"))

        # Page 2
        resp2 = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/page/2",
            headers=self.auth_headers,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.headers["content-type"], "image/png")
        self.assertTrue(resp2.content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_evidence_pdf_page_out_of_bounds_404(self) -> None:
        """Endpoint 13 returns 404 when requested page is out of bounds."""
        pdf_path = self._create_sample_pdf("doc_a.pdf", num_pages=2)
        doc = ComparisonDocument(
            doc_id="doc_a",
            slot="doc_a",
            original_filename="doc_a.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=pdf_path.stat().st_size,
            storage_rel_path="documents/doc_a.pdf",
        )
        self._register_document(doc)

        # Page 0 (out of bounds)
        resp_0 = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/page/0",
            headers=self.auth_headers,
        )
        self.assertEqual(resp_0.status_code, 404)
        self.assertIn("out of bounds", resp_0.json()["detail"])

        # Page 3 (exceeds total 2 pages)
        resp_3 = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/page/3",
            headers=self.auth_headers,
        )
        self.assertEqual(resp_3.status_code, 404)
        self.assertIn("out of bounds", resp_3.json()["detail"])

    def test_evidence_scanned_pdf_render(self) -> None:
        """Endpoint 13 correctly renders page for scanned PDF format."""
        pdf_path = self._create_sample_pdf("scanned_doc.pdf", num_pages=1)
        doc = ComparisonDocument(
            doc_id="doc_scanned",
            slot="doc_a",
            original_filename="scanned_doc.pdf",
            file_format=SupportedFileFormat.PDF_SCANNED,
            file_size_bytes=pdf_path.stat().st_size,
            storage_rel_path="documents/scanned_doc.pdf",
        )
        self._register_document(doc)

        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_scanned/page/1",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "image/png")
        self.assertTrue(resp.content.startswith(b"\x89PNG\r\n\x1a\n"))

    # ---------------------------------------------------------------------------
    # 3. Image Page Rendering (Endpoint 13)
    # ---------------------------------------------------------------------------

    def test_evidence_image_png_render_success(self) -> None:
        """Endpoint 13 returns page 1 for PNG images and 404 for page > 1."""
        img_path = self._create_sample_image("statement.png", "png")
        doc = ComparisonDocument(
            doc_id="doc_png",
            slot="doc_b",
            original_filename="statement.png",
            file_format=SupportedFileFormat.IMAGE_PNG,
            file_size_bytes=img_path.stat().st_size,
            storage_rel_path="documents/statement.png",
        )
        self._register_document(doc)

        # Page 1
        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_png/page/1",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "image/png")

        # Page 2 -> 404
        resp2 = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_png/page/2",
            headers=self.auth_headers,
        )
        self.assertEqual(resp2.status_code, 404)
        self.assertIn("only contain page 1", resp2.json()["detail"])

    def test_evidence_image_jpeg_render_success(self) -> None:
        """Endpoint 13 returns page 1 for JPEG images with image/jpeg content type."""
        img_path = self._create_sample_image("report.jpg", "jpeg")
        doc = ComparisonDocument(
            doc_id="doc_jpg",
            slot="doc_b",
            original_filename="report.jpg",
            file_format=SupportedFileFormat.IMAGE_JPG,
            file_size_bytes=img_path.stat().st_size,
            storage_rel_path="documents/report.jpg",
        )
        self._register_document(doc)

        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_jpg/page/1",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "image/jpeg")

    # ---------------------------------------------------------------------------
    # 4. Non-Visual Formats & Error Handling
    # ---------------------------------------------------------------------------

    def test_evidence_non_visual_formats_rejected(self) -> None:
        """Endpoint 13 returns 400 Bad Request for DOCX and XLSX files."""
        # DOCX
        doc_dir = self.session_dir / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        docx_path = doc_dir / "filing.docx"
        docx_path.write_bytes(b"PK\x03\x04dummy_docx")

        doc_docx = ComparisonDocument(
            doc_id="doc_docx",
            slot="doc_a",
            original_filename="filing.docx",
            file_format=SupportedFileFormat.DOCX,
            file_size_bytes=docx_path.stat().st_size,
            storage_rel_path="documents/filing.docx",
        )
        self._register_document(doc_docx)

        resp_docx = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_docx/page/1",
            headers=self.auth_headers,
        )
        self.assertEqual(resp_docx.status_code, 400)
        self.assertIn("Visual page rendering is only supported for PDF and image filings", resp_docx.json()["detail"])

        # XLSX
        xlsx_path = doc_dir / "filing.xlsx"
        xlsx_path.write_bytes(b"PK\x03\x04dummy_xlsx")

        doc_xlsx = ComparisonDocument(
            doc_id="doc_xlsx",
            slot="doc_b",
            original_filename="filing.xlsx",
            file_format=SupportedFileFormat.XLSX,
            file_size_bytes=xlsx_path.stat().st_size,
            storage_rel_path="documents/filing.xlsx",
        )
        self._register_document(doc_xlsx)

        resp_xlsx = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_xlsx/page/1",
            headers=self.auth_headers,
        )
        self.assertEqual(resp_xlsx.status_code, 400)
        self.assertIn("Visual page rendering is only supported for PDF and image filings", resp_xlsx.json()["detail"])

    def test_evidence_nonexistent_document_404(self) -> None:
        """Endpoint 13 returns 404 when doc_id is not in active session."""
        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_unknown/page/1",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found in active session", resp.json()["detail"])

    def test_evidence_missing_underlying_filing_404(self) -> None:
        """Endpoint 13 returns 404 if document is registered but file is deleted/missing."""
        doc = ComparisonDocument(
            doc_id="doc_missing_file",
            slot="doc_a",
            original_filename="ghost.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024,
            storage_rel_path="documents/ghost.pdf",
        )
        self._register_document(doc)

        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_missing_file/page/1",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Underlying document filing not found in session storage", resp.json()["detail"])

    # ---------------------------------------------------------------------------
    # 5. Extraction Context Endpoint (Endpoint 13.1)
    # ---------------------------------------------------------------------------

    def test_evidence_context_endpoint_success(self) -> None:
        """Endpoint 13.1 delivers parsed structured extraction context for DOCX/spreadsheets."""
        # Create and save a structured DocumentExtractionResult
        table = ExtractedTable(
            table_id="tbl_1",
            page_number=None,
            sheet_name="Profit & Loss",
            headers=["Particulars", "FY24", "FY23"],
            rows=[
                ["Revenue from Operations", "1,10,577", "95,000"],
                ["Total Expenses", "98,000", "85,000"],
                ["Net Profit", "12,577", "10,000"],
            ],
            cells=[
                ExtractedTableCell(
                    row_index=0,
                    col_index=1,
                    value="1,10,577",
                    cell_range="B1",
                    is_header=False,
                )
            ],
        )
        text_block = ExtractedTextBlock(
            block_id="blk_1",
            page_number=None,
            structural_ref="Heading 1: Financial Performance",
            text="The company recorded strong revenue growth across all segments.",
        )
        extraction = DocumentExtractionResult(
            doc_id="doc_xlsx",
            slot="doc_b",
            file_format=SupportedFileFormat.XLSX,
            tables=[table],
            text_blocks=[text_block],
            extraction_status="SUCCESS",
        )
        session_store.save_document_extraction(self.session_id, "doc_xlsx", extraction)

        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_xlsx/context",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["doc_id"], "doc_xlsx")
        self.assertEqual(data["file_format"], "XLSX")
        self.assertEqual(len(data["tables"]), 1)
        self.assertEqual(data["tables"][0]["sheet_name"], "Profit & Loss")
        self.assertEqual(len(data["tables"][0]["rows"]), 3)
        self.assertEqual(len(data["text_blocks"]), 1)
        self.assertEqual(data["text_blocks"][0]["structural_ref"], "Heading 1: Financial Performance")

    def test_evidence_context_endpoint_not_found_404(self) -> None:
        """Endpoint 13.1 returns 404 when extraction context does not exist."""
        resp = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_nonexistent/context",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"])

    # ---------------------------------------------------------------------------
    # 6. Cross-Session Isolation & Path Traversal
    # ---------------------------------------------------------------------------

    def test_evidence_cross_session_isolation(self) -> None:
        """Session A cannot access Session B's evidence even with a valid token from Session A."""
        # Create second session
        resp_b = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(resp_b.status_code, 201)
        data_b = resp_b.json()
        session_id_b = data_b["session_id"]
        token_b = data_b["session_token"]

        # Put PDF in Session A
        pdf_path = self._create_sample_pdf("doc_a.pdf", num_pages=1)
        doc = ComparisonDocument(
            doc_id="doc_a",
            slot="doc_a",
            original_filename="doc_a.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=pdf_path.stat().st_size,
            storage_rel_path="documents/doc_a.pdf",
        )
        self._register_document(doc)

        # Attempt to access Session A's doc_a using Session B's token -> 401 Unauthorized
        resp_leak = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/page/1",
            headers={"X-Session-Token": token_b},
        )
        self.assertEqual(resp_leak.status_code, 401)

        # Attempt to access Session A's context using Session B's token -> 401 Unauthorized
        resp_leak_context = self.client.get(
            f"/api/compare/session/{self.session_id}/evidence/doc_a/context",
            headers={"X-Session-Token": token_b},
        )
        self.assertEqual(resp_leak_context.status_code, 401)

        # Cleanup session B
        session_store.terminate_session(session_id_b)


if __name__ == "__main__":
    unittest.main()
