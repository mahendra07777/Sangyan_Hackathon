"""Comprehensive automated test suite for Compare Documents Slice 2:
Multi-Document Ingestion, File Validation, 8-Format Parsers, Slot Retries,
and Targeted Boundary / Safeguard Verifications.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import struct
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
import openpyxl
import pymupdf
import xlrd

from app.api.compare_routes import compare_router
from app.models.comparison import (
    ComparisonMode,
    DocumentSlot,
    SessionStatus,
    SupportedFileFormat,
)
from app.services.comparison_session_store import ComparisonSessionStore, session_store
from app.services.document_parsers import (
    MAX_PDF_PAGES,
    parse_docx,
    parse_image,
    parse_pdf,
    parse_xls,
    parse_xlsx,
)
from app.services.file_validator import (
    MAX_FILE_SIZE_BYTES,
    detect_file_format,
    read_and_validate_upload,
    sanitize_filename,
    validate_image_dimensions,
    validate_zip_safety,
)
from main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Synthetic Document Generators
# ---------------------------------------------------------------------------

def create_synthetic_digital_pdf(words_per_page: int = 120) -> bytes:
    """Generate a valid in-memory digital PDF with PyMuPDF containing high text density."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    financial_words = [
        "Revenue", "Operating", "Profit", "EBITDA", "Balance", "Sheet",
        "Assets", "Liabilities", "Equity", "Growth", "Performance", "Audit",
        "Quarterly", "Annual", "Report", "Consolidated", "Standalone", "Crore",
    ] * (words_per_page // 18 + 1)
    text_content = " ".join(financial_words[:words_per_page])

    page.insert_text(pymupdf.Point(50, 72), "Tata Motors Limited - Q3 Results", fontsize=14)
    page.insert_textbox(pymupdf.Rect(50, 100, 550, 500), text_content, fontsize=10)

    # Draw table borders and text
    page.draw_rect(pymupdf.Rect(50, 520, 550, 650), color=(0, 0, 0), width=1)
    page.draw_line(pymupdf.Point(50, 550), pymupdf.Point(550, 550), color=(0, 0, 0))
    page.draw_line(pymupdf.Point(250, 520), pymupdf.Point(250, 650), color=(0, 0, 0))
    page.insert_text(pymupdf.Point(60, 540), "Metric", fontsize=11)
    page.insert_text(pymupdf.Point(260, 540), "Amount (INR Cr)", fontsize=11)
    page.insert_text(pymupdf.Point(60, 580), "Total Revenue", fontsize=10)
    page.insert_text(pymupdf.Point(260, 580), "10500.00", fontsize=10)
    page.insert_text(pymupdf.Point(60, 620), "Net Profit", fontsize=10)
    page.insert_text(pymupdf.Point(260, 620), "1250.50", fontsize=10)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_synthetic_scanned_pdf() -> bytes:
    """Generate a valid in-memory scanned PDF with PyMuPDF with <50 words."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(100, 100), "Scanned document with minimal text content", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_synthetic_image(format_type: str = "png") -> bytes:
    """Generate a valid PNG or JPEG image via PyMuPDF Pixmap."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
    img_bytes = pix.tobytes(format_type)
    return img_bytes


def create_synthetic_docx() -> bytes:
    """Generate a valid in-memory DOCX with paragraphs, heading, and table."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        ct = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        )
        zf.writestr("[Content_Types].xml", ct)

        w_doc = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Financial Highlights FY 2023-24</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>The company demonstrated strong operational growth across key segments.</w:t></w:r></w:p>'
            '<w:tbl>'
            '<w:tr>'
            '<w:tc><w:p><w:r><w:t>Particulars</w:t></w:r></w:p></w:tc>'
            '<w:tc><w:p><w:r><w:t>FY24</w:t></w:r></w:p></w:tc>'
            '</w:tr>'
            '<w:tr>'
            '<w:tc><w:p><w:r><w:t>Total Income</w:t></w:r></w:p></w:tc>'
            '<w:tc><w:p><w:r><w:t>50000</w:t></w:r></w:p></w:tc>'
            '</w:tr>'
            '</w:tbl>'
            '</w:body>'
            '</w:document>'
        )
        zf.writestr("word/document.xml", w_doc)

    return bio.getvalue()


def create_synthetic_xlsx() -> bytes:
    """Generate a valid in-memory XLSX workbook with multiple sheets and merged cells."""
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Financial_Results"

    # Merged header
    ws1.merge_cells("A1:B1")
    ws1["A1"] = "Summary Results"

    ws1["A2"] = "Metric"
    ws1["B2"] = "Value (INR Cr)"
    ws1["A3"] = "Revenue from Operations"
    ws1["B3"] = 43210.75
    ws1["A4"] = "Profit After Tax"
    ws1["B4"] = 3890.20

    ws2 = wb.create_sheet(title="Balance_Sheet")
    ws2["A1"] = "Total Assets"
    ws2["B1"] = 120500.00

    bio = io.BytesIO()
    wb.save(bio)
    wb.close()
    return bio.getvalue()


def create_synthetic_xls() -> bytes:
    """Generate a valid in-memory BIFF8 OLE2 Excel .xls file for xlrd parsing."""
    bof_wb = struct.pack('<HH HHHH II', 0x0809, 16, 0x0600, 0x0005, 0x0dbb, 0x07cd, 0, 0)
    r_1904 = struct.pack('<HHH', 0x0022, 2, 0)
    sheet_name = 'Results'
    name_bytes = sheet_name.encode('latin1')
    bs_data_tmp = struct.pack('<IBBBB', 0, 0, 0, len(sheet_name), 0) + name_bytes
    boundsheet = struct.pack('<HH', 0x0085, len(bs_data_tmp)) + bs_data_tmp
    eof = struct.pack('<HH', 0x000A, 0)

    bof_ws = struct.pack('<HH HHHH II', 0x0809, 16, 0x0600, 0x0010, 0x0dbb, 0x07cd, 0, 0)
    dimension = struct.pack('<HH IIHHH', 0x0200, 14, 0, 2, 0, 2, 0)
    num_cell = struct.pack('<HH HHH d', 0x0203, 14, 0, 0, 0, 7890.5)
    eof_ws = struct.pack('<HH', 0x000A, 0)

    ws_offset = len(bof_wb) + len(r_1904) + len(boundsheet) + len(eof)
    bs_data = struct.pack('<IBBBB', ws_offset, 0, 0, len(sheet_name), 0) + name_bytes
    boundsheet = struct.pack('<HH', 0x0085, len(bs_data)) + bs_data

    wb_stream = bof_wb + r_1904 + boundsheet + eof + bof_ws + dimension + num_cell + eof_ws
    wb_data = wb_stream + b'\x00' * (4096 - len(wb_stream))

    hdr = bytearray(512)
    hdr[0:8] = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
    struct.pack_into('<H', hdr, 28, 0xFFFE)
    struct.pack_into('<H', hdr, 30, 9)
    struct.pack_into('<H', hdr, 32, 6)
    struct.pack_into('<I', hdr, 44, 1)
    struct.pack_into('<I', hdr, 48, 1)
    struct.pack_into('<I', hdr, 56, 4096)
    struct.pack_into('<I', hdr, 60, 0xFFFFFFFE)
    struct.pack_into('<I', hdr, 68, 0xFFFFFFFE)
    struct.pack_into('<I', hdr, 76, 0)
    for i in range(1, 109):
        struct.pack_into('<I', hdr, 76 + i * 4, 0xFFFFFFFF)

    sat = bytearray(512)
    struct.pack_into('<I', sat, 0, 0xFFFFFFFD)
    struct.pack_into('<I', sat, 4, 0xFFFFFFFE)
    for s in range(2, 9):
        struct.pack_into('<I', sat, s * 4, s + 1)
    struct.pack_into('<I', sat, 9 * 4, 0xFFFFFFFE)
    for s in range(10, 128):
        struct.pack_into('<I', sat, s * 4, 0xFFFFFFFF)

    dir_sec = bytearray(512)
    root_name = 'Root Entry\x00'.encode('utf-16le')
    dir_sec[0:len(root_name)] = root_name
    struct.pack_into('<H', dir_sec, 64, len(root_name))
    dir_sec[66] = 5
    dir_sec[67] = 1
    struct.pack_into('<I', dir_sec, 68, 0xFFFFFFFF)
    struct.pack_into('<I', dir_sec, 72, 0xFFFFFFFF)
    struct.pack_into('<I', dir_sec, 76, 1)
    struct.pack_into('<I', dir_sec, 116, 0xFFFFFFFE)
    struct.pack_into('<I', dir_sec, 120, 0)

    wb_name = 'Workbook\x00'.encode('utf-16le')
    dir_sec[128:128 + len(wb_name)] = wb_name
    struct.pack_into('<H', dir_sec, 128 + 64, len(wb_name))
    dir_sec[128 + 66] = 2
    dir_sec[128 + 67] = 1
    struct.pack_into('<I', dir_sec, 128 + 68, 0xFFFFFFFF)
    struct.pack_into('<I', dir_sec, 128 + 72, 0xFFFFFFFF)
    struct.pack_into('<I', dir_sec, 128 + 76, 0xFFFFFFFF)
    struct.pack_into('<I', dir_sec, 128 + 116, 2)
    struct.pack_into('<I', dir_sec, 128 + 120, 4096)

    return bytes(hdr) + bytes(sat) + bytes(dir_sec) + wb_data


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestSlice2Parsers(unittest.TestCase):
    """Slice 2 Unit and Integration Tests."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_slice2_")
        self.temp_path = Path(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # 1. File Validator & Security Tests
    # -----------------------------------------------------------------------

    def test_sanitize_filename_traversal_protection(self) -> None:
        """Verify filename sanitization removes directory traversals and dangerous characters."""
        self.assertEqual(sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(sanitize_filename("..\\..\\windows\\system32\\cmd.exe"), "cmd.exe")
        self.assertEqual(sanitize_filename("Tata_Motors*Q3?Results!.pdf"), "Tata_Motors_Q3_Results_.pdf")
        self.assertEqual(sanitize_filename(""), "document")
        self.assertEqual(sanitize_filename("   "), "document")

    def test_detect_file_format_all_signatures(self) -> None:
        """Verify detect_file_format detects PDF, PNG, JPG, JPEG, DOCX, XLSX, and XLS."""
        pdf_bytes = create_synthetic_digital_pdf()
        self.assertEqual(detect_file_format(pdf_bytes[:512], pdf_bytes, "doc.pdf"), SupportedFileFormat.PDF_DIGITAL)

        png_bytes = create_synthetic_image("png")
        self.assertEqual(detect_file_format(png_bytes[:512], png_bytes, "img.png"), SupportedFileFormat.IMAGE_PNG)

        jpg_bytes = create_synthetic_image("jpeg")
        self.assertEqual(detect_file_format(jpg_bytes[:512], jpg_bytes, "img.jpg"), SupportedFileFormat.IMAGE_JPG)
        self.assertEqual(detect_file_format(jpg_bytes[:512], jpg_bytes, "img.jpeg"), SupportedFileFormat.IMAGE_JPEG)

        docx_bytes = create_synthetic_docx()
        self.assertEqual(detect_file_format(docx_bytes[:512], docx_bytes, "doc.docx"), SupportedFileFormat.DOCX)

        xlsx_bytes = create_synthetic_xlsx()
        self.assertEqual(detect_file_format(xlsx_bytes[:512], xlsx_bytes, "doc.xlsx"), SupportedFileFormat.XLSX)

        xls_bytes = create_synthetic_xls()
        self.assertEqual(detect_file_format(xls_bytes[:512], xls_bytes, "doc.xls"), SupportedFileFormat.XLS)

    def test_detect_file_format_corrupt_or_unsupported(self) -> None:
        """Verify corrupted or unrecognized files are rejected with HTTP 400."""
        random_bytes = b"This is plain text and not an approved document format."
        with self.assertRaises(HTTPException) as ctx:
            detect_file_format(random_bytes[:512], random_bytes, "random.txt")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_zip_safety_traversal_detection(self) -> None:
        """Verify zip files with traversal paths are rejected."""
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as zf:
            zf.writestr("../../bad_path.xml", "<data/>")
        zip_bytes = bio.getvalue()

        with self.assertRaises(HTTPException) as ctx:
            validate_zip_safety(zip_bytes)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("traversal", ctx.exception.detail.lower())

    # -----------------------------------------------------------------------
    # 2. Individual Format Parser Tests (All 8 Approved Formats)
    # -----------------------------------------------------------------------

    def test_format_01_pdf_digital_parser(self) -> None:
        """FMT-01: Verify digital PDF extracts text blocks and coordinates."""
        pdf_bytes = create_synthetic_digital_pdf(words_per_page=120)
        pdf_path = self.temp_path / "digital.pdf"
        pdf_path.write_bytes(pdf_bytes)

        result = parse_pdf(pdf_path, "doc_a", DocumentSlot.DOC_A)
        self.assertEqual(result.file_format, SupportedFileFormat.PDF_DIGITAL)
        self.assertFalse(result.is_scanned)
        self.assertEqual(result.extraction_status, "SUCCESS")
        self.assertGreater(len(result.text_blocks), 0)
        self.assertGreater(result.raw_word_count, 50)
        self.assertIsNotNone(result.text_blocks[0].bounding_box)

    def test_format_02_pdf_scanned_parser(self) -> None:
        """FMT-02: Verify low text density PDF is flagged as scanned with OCR_UNAVAILABLE_LOCAL_MODE."""
        pdf_bytes = create_synthetic_scanned_pdf()
        pdf_path = self.temp_path / "scanned.pdf"
        pdf_path.write_bytes(pdf_bytes)

        result = parse_pdf(pdf_path, "doc_a", DocumentSlot.DOC_A)
        self.assertEqual(result.file_format, SupportedFileFormat.PDF_SCANNED)
        self.assertTrue(result.is_scanned)
        self.assertEqual(result.extraction_status, "OCR_UNAVAILABLE_LOCAL_MODE")
        self.assertTrue(any("scanned" in note.lower() for note in result.notes))

    def test_pdf_200_page_limit_enforced(self) -> None:
        """Verify PDF exceeding 200 pages raises ValueError."""
        doc = pymupdf.open()
        for _ in range(201):
            doc.new_page(width=100, height=100)
        pdf_bytes = doc.tobytes()
        doc.close()

        pdf_path = self.temp_path / "oversized.pdf"
        pdf_path.write_bytes(pdf_bytes)

        with self.assertRaises(ValueError) as ctx:
            parse_pdf(pdf_path, "doc_a", DocumentSlot.DOC_A)
        self.assertIn("200 pages", str(ctx.exception))

    def test_format_03_png_image_parser(self) -> None:
        """FMT-03: Verify PNG image parsing sets VISION_EXTRACTION_REQUIRED in local mode."""
        png_bytes = create_synthetic_image("png")
        png_path = self.temp_path / "test.png"
        png_path.write_bytes(png_bytes)

        result = parse_image(png_path, "doc_a", DocumentSlot.DOC_A, SupportedFileFormat.IMAGE_PNG)
        self.assertEqual(result.file_format, SupportedFileFormat.IMAGE_PNG)
        self.assertEqual(result.extraction_status, "VISION_EXTRACTION_REQUIRED")
        self.assertEqual(result.page_count, 1)

    def test_format_04_05_jpg_jpeg_image_parser(self) -> None:
        """FMT-04/05: Verify JPG and JPEG parsing sets VISION_EXTRACTION_REQUIRED."""
        jpg_bytes = create_synthetic_image("jpeg")
        jpg_path = self.temp_path / "test.jpg"
        jpg_path.write_bytes(jpg_bytes)

        result = parse_image(jpg_path, "doc_b", DocumentSlot.DOC_B, SupportedFileFormat.IMAGE_JPEG)
        self.assertEqual(result.file_format, SupportedFileFormat.IMAGE_JPEG)
        self.assertEqual(result.extraction_status, "VISION_EXTRACTION_REQUIRED")

    def test_format_06_docx_parser(self) -> None:
        """FMT-06: Verify standard OpenXML DOCX parser extracts headings, paragraphs, and tables."""
        docx_bytes = create_synthetic_docx()
        docx_path = self.temp_path / "test.docx"
        docx_path.write_bytes(docx_bytes)

        result = parse_docx(docx_path, "doc_a", DocumentSlot.DOC_A)
        self.assertEqual(result.file_format, SupportedFileFormat.DOCX)
        self.assertEqual(result.extraction_status, "SUCCESS")
        self.assertGreater(len(result.text_blocks), 0)
        self.assertGreater(len(result.tables), 0)

        # Check heading extraction
        heading_block = next((b for b in result.text_blocks if b.heading_level == 1), None)
        self.assertIsNotNone(heading_block)
        self.assertIn("Financial Highlights", heading_block.text)

        # Check table extraction
        table = result.tables[0]
        self.assertEqual(table.headers, ["Particulars", "FY24"])
        self.assertEqual(len(table.rows), 2)

    def test_format_07_xlsx_parser(self) -> None:
        """FMT-07: Verify openpyxl XLSX parser extracts sheets, headers, and merged cell values."""
        xlsx_bytes = create_synthetic_xlsx()
        xlsx_path = self.temp_path / "test.xlsx"
        xlsx_path.write_bytes(xlsx_bytes)

        result = parse_xlsx(xlsx_path, "doc_a", DocumentSlot.DOC_A)
        self.assertEqual(result.file_format, SupportedFileFormat.XLSX)
        self.assertEqual(result.extraction_status, "SUCCESS")
        self.assertEqual(len(result.sheet_names), 2)
        self.assertIn("Financial_Results", result.sheet_names)
        self.assertIn("Balance_Sheet", result.sheet_names)

        # Check table and cell extraction
        table = next(t for t in result.tables if t.sheet_name == "Financial_Results")
        self.assertGreater(table.num_rows, 0)
        cell_a1 = next(c for c in table.cells if c.row_index == 0 and c.col_index == 0)
        self.assertEqual(cell_a1.value, "Summary Results")

    def test_format_08_xls_parser(self) -> None:
        """FMT-08: Verify legacy BIFF8 XLS parser via xlrd extracts sheet and numeric cell values."""
        xls_bytes = create_synthetic_xls()
        xls_path = self.temp_path / "test.xls"
        xls_path.write_bytes(xls_bytes)

        result = parse_xls(xls_path, "doc_a", DocumentSlot.DOC_A)
        self.assertEqual(result.file_format, SupportedFileFormat.XLS)
        self.assertEqual(result.extraction_status, "SUCCESS")
        self.assertIn("Results", result.sheet_names)
        self.assertEqual(len(result.tables), 1)

        table = result.tables[0]
        cell_0_0 = next(c for c in table.cells if c.row_index == 0 and c.col_index == 0)
        self.assertIn("7890", str(cell_0_0.value))

    # -----------------------------------------------------------------------
    # 3. API Upload Endpoint Tests
    # -----------------------------------------------------------------------

    def test_upload_quick_compare_success(self) -> None:
        """MOD-01 / POST /upload: Verify exactly 2 files uploaded in QUICK_COMPARE mode."""
        create_res = client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(create_res.status_code, 201)
        data = create_res.json()
        session_id = data["session_id"]
        token = data["session_token"]

        pdf_bytes = create_synthetic_digital_pdf()
        xlsx_bytes = create_synthetic_xlsx()

        upload_res = client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=[
                ("files", ("Filing_A.pdf", pdf_bytes, "application/pdf")),
                ("files", ("Filing_B.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
            ],
            data={"gemini_consent_acknowledged": "false"},
        )
        self.assertEqual(upload_res.status_code, 200)
        res_data = upload_res.json()
        self.assertEqual(res_data["session_id"], session_id)
        self.assertFalse(res_data["consent_granted"])
        self.assertEqual(len(res_data["uploaded_documents"]), 2)

        doc_a = res_data["uploaded_documents"][0]
        doc_b = res_data["uploaded_documents"][1]
        self.assertEqual(doc_a["doc_id"], "doc_a")
        self.assertEqual(doc_a["slot"], "doc_a")
        self.assertEqual(doc_a["file_format"], SupportedFileFormat.PDF_DIGITAL.value)
        self.assertEqual(doc_b["doc_id"], "doc_b")
        self.assertEqual(doc_b["slot"], "doc_b")
        self.assertEqual(doc_b["file_format"], SupportedFileFormat.XLSX.value)

        # Verify filesystem persistence using approved documents/ directory
        session_dir = session_store.resolve_session_path(session_id)
        self.assertTrue((session_dir / "documents" / "doc_a_Filing_A.pdf").exists())
        self.assertTrue((session_dir / "documents" / "doc_b_Filing_B.xlsx").exists())
        self.assertTrue((session_dir / "extracted" / "doc_a_extraction.json").exists())
        self.assertTrue((session_dir / "extracted" / "doc_b_extraction.json").exists())
        self.assertTrue((session_dir / "documents.json").exists())

        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    def test_upload_quick_compare_invalid_counts(self) -> None:
        """Verify QUICK_COMPARE mode rejects 1 file or 3 files with HTTP 400."""
        create_res = client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]
        pdf_bytes = create_synthetic_digital_pdf()

        # Test with 1 file
        res_1 = client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=[("files", ("Doc1.pdf", pdf_bytes, "application/pdf"))],
        )
        self.assertEqual(res_1.status_code, 400)
        self.assertIn("requires exactly 2 documents", res_1.json()["detail"])

        # Test with 3 files
        res_3 = client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=[
                ("files", ("Doc1.pdf", pdf_bytes, "application/pdf")),
                ("files", ("Doc2.pdf", pdf_bytes, "application/pdf")),
                ("files", ("Doc3.pdf", pdf_bytes, "application/pdf")),
            ],
        )
        self.assertEqual(res_3.status_code, 400)
        self.assertIn("requires exactly 2 documents", res_3.json()["detail"])

        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    def test_upload_multi_document_success(self) -> None:
        """MOD-02 / POST /upload: Verify 3 files in MULTI_DOCUMENT mode."""
        create_res = client.post("/api/compare/session", json={"comparison_mode": "MULTI_DOCUMENT"})
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]

        pdf_bytes = create_synthetic_digital_pdf()
        docx_bytes = create_synthetic_docx()
        xlsx_bytes = create_synthetic_xlsx()

        upload_res = client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=[
                ("files", ("DocA.pdf", pdf_bytes, "application/pdf")),
                ("files", ("DocB.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
                ("files", ("DocC.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
            ],
            data={"gemini_consent_acknowledged": "true"},
        )
        self.assertEqual(upload_res.status_code, 200)
        res_data = upload_res.json()
        self.assertTrue(res_data["consent_granted"])
        self.assertEqual(len(res_data["uploaded_documents"]), 3)
        self.assertEqual(res_data["uploaded_documents"][0]["doc_id"], "doc_a")
        self.assertEqual(res_data["uploaded_documents"][1]["doc_id"], "doc_b")
        self.assertEqual(res_data["uploaded_documents"][2]["doc_id"], "doc_c")

        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    # -----------------------------------------------------------------------
    # 4. Single-Slot Retry Endpoint Tests
    # -----------------------------------------------------------------------

    def test_retry_single_slot_isolation(self) -> None:
        """Verify POST /session/{id}/retry/{doc_id} replaces single slot without affecting sibling."""
        create_res = client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]

        pdf_bytes = create_synthetic_digital_pdf()
        xlsx_bytes = create_synthetic_xlsx()

        client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=[
                ("files", ("OriginalA.pdf", pdf_bytes, "application/pdf")),
                ("files", ("OriginalB.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
            ],
        )

        session_dir = session_store.resolve_session_path(session_id)
        doc_b_file = session_dir / "documents" / "doc_b_OriginalB.xlsx"
        doc_b_extraction = session_dir / "extracted" / "doc_b_extraction.json"
        self.assertTrue(doc_b_file.exists())
        self.assertTrue(doc_b_extraction.exists())
        doc_b_mtime = doc_b_file.stat().st_mtime

        # Retry slot doc_a with DOCX
        docx_bytes = create_synthetic_docx()
        retry_res = client.post(
            f"/api/compare/session/{session_id}/retry/doc_a",
            headers={"X-Session-Token": token},
            files=[("file", ("ReplacementA.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
        )
        self.assertEqual(retry_res.status_code, 200)
        retried_doc = retry_res.json()
        self.assertEqual(retried_doc["doc_id"], "doc_a")
        self.assertEqual(retried_doc["file_format"], SupportedFileFormat.DOCX.value)

        # Sibling document doc_b must remain completely intact
        self.assertTrue(doc_b_file.exists())
        self.assertTrue(doc_b_extraction.exists())
        self.assertEqual(doc_b_file.stat().st_mtime, doc_b_mtime)

        docs = session_store.get_session_documents(session_id)
        self.assertEqual(len(docs), 2)
        doc_a_rec = next(d for d in docs if d.doc_id == "doc_a")
        self.assertEqual(doc_a_rec.file_format, SupportedFileFormat.DOCX.value)

        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    def test_retry_invalid_slot_returns_400(self) -> None:
        """Verify retrying an invalid slot identifier returns HTTP 400."""
        create_res = client.post("/api/compare/session")
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]
        docx_bytes = create_synthetic_docx()

        res = client.post(
            f"/api/compare/session/{session_id}/retry/doc_z",
            headers={"X-Session-Token": token},
            files=[("file", ("test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid document slot", res.json()["detail"])

        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    # -----------------------------------------------------------------------
    # 5. Targeted Boundary & Safeguard Tests (Verification Round)
    # -----------------------------------------------------------------------

    def test_zip_safeguard_legitimate_vs_malicious_bomb(self) -> None:
        """Verify legitimate repetitive XLSX documents are accepted while zip bombs are rejected."""
        # 1. Legitimate repetitive XLSX (ratio ~14.5:1)
        wb = openpyxl.Workbook()
        ws = wb.active
        for r in range(1, 3000):
            ws.append(["Tata Motors Limited", 1000.0, 500.0, "Audited Statement"])
        bio = io.BytesIO()
        wb.save(bio)
        legit_xlsx_bytes = bio.getvalue()
        zf = validate_zip_safety(legit_xlsx_bytes)
        self.assertIsNotNone(zf)

        # 2. Malicious ZIP bomb fixture (>100:1 ratio with >5 MiB uncompressed)
        bomb_bio = io.BytesIO()
        with zipfile.ZipFile(bomb_bio, "w", zipfile.ZIP_DEFLATED) as zf_bomb:
            # 10 MB of zeros compresses to ~10 KB (ratio ~1000:1)
            zf_bomb.writestr("xl/workbook.xml", b"\x00" * (10 * 1024 * 1024))
        bomb_bytes = bomb_bio.getvalue()
        with self.assertRaises(HTTPException) as ctx:
            validate_zip_safety(bomb_bytes)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Decompression bomb detected", ctx.exception.detail)

        # 3. Archive exceeding 50 MiB uncompressed hard ceiling
        oversized_bio = io.BytesIO()
        with zipfile.ZipFile(oversized_bio, "w", zipfile.ZIP_STORED) as zf_over:
            zf_over.writestr("xl/workbook.xml", b"A" * (52 * 1024 * 1024))
        oversized_bytes = oversized_bio.getvalue()
        with self.assertRaises(HTTPException) as ctx:
            validate_zip_safety(oversized_bytes)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("exceeds maximum safety limit of 50 MiB", ctx.exception.detail)

    def test_boundary_20mb_single_file_limit(self) -> None:
        """Verify upload exceeding 20 MiB per single file is rejected with HTTP 413."""
        create_res = client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]

        # Synthetic PDF exceeding 20 MiB by 1024 bytes
        oversized_bytes = b"%PDF-1.4\n" + b"0" * (20 * 1024 * 1024 + 1024)
        valid_pdf_bytes = create_synthetic_digital_pdf()

        res = client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=[
                ("files", ("Oversized.pdf", oversized_bytes, "application/pdf")),
                ("files", ("Valid.pdf", valid_pdf_bytes, "application/pdf")),
            ],
        )
        self.assertEqual(res.status_code, 413)
        self.assertIn("exceeds maximum permitted size of 20 MiB", res.json()["detail"])

        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    def test_boundary_100mb_session_aggregate_limit(self) -> None:
        """Verify session total exceeding 100 MiB aggregate is rejected with HTTP 413."""
        # Simulate read_and_validate_upload when prior files consumed 95 MiB and new file is 8 MiB
        chunk_8mb = b"%PDF-1.4\n" + b"A" * (8 * 1024 * 1024)
        upload_mock = UploadFile(filename="Doc.pdf", file=io.BytesIO(chunk_8mb))

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(read_and_validate_upload(upload_mock, current_total_bytes=95 * 1024 * 1024))
        self.assertEqual(ctx.exception.status_code, 413)
        self.assertIn("aggregate session limit of 100 MiB", ctx.exception.detail)

    def test_boundary_max_five_documents(self) -> None:
        """Verify upload of 6 files in MULTI_DOCUMENT mode is rejected with HTTP 400."""
        create_res = client.post("/api/compare/session", json={"comparison_mode": "MULTI_DOCUMENT"})
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]

        pdf_bytes = create_synthetic_digital_pdf()
        files = [("files", (f"Doc_{i}.pdf", pdf_bytes, "application/pdf")) for i in range(6)]

        res = client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=files,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("requires between 2 and 5 documents, received 6", res.json()["detail"])

        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    def test_partial_upload_failure_cleanup(self) -> None:
        """Verify transactional cleanup: if file 2 of a batch fails, file 1 is purged from disk."""
        create_res = client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]

        valid_pdf = create_synthetic_digital_pdf()
        corrupted_file = b"Corrupted content that is not any valid format"

        res = client.post(
            f"/api/compare/session/{session_id}/upload",
            headers={"X-Session-Token": token},
            files=[
                ("files", ("Valid.pdf", valid_pdf, "application/pdf")),
                ("files", ("Corrupt.txt", corrupted_file, "text/plain")),
            ],
        )
        self.assertEqual(res.status_code, 400)

        # Inspect disk: documents/ directory must NOT contain orphaned Valid.pdf
        session_dir = session_store.resolve_session_path(session_id)
        docs_dir = session_dir / "documents"
        stored_files = list(docs_dir.glob("*")) if docs_dir.exists() else []
        self.assertEqual(len(stored_files), 0, f"Expected 0 orphaned files, found: {stored_files}")

        client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    def test_xlsx_formula_and_missing_cached_values(self) -> None:
        """Verify XLSX parser extracts formula provenance and handles missing cached values."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Formulas"
        ws["A1"] = 500
        ws["A2"] = 700
        ws["A3"] = "=SUM(A1:A2)"

        xlsx_path = self.temp_path / "formula_test.xlsx"
        wb.save(str(xlsx_path))
        wb.close()

        result = parse_xlsx(xlsx_path, "doc_a", DocumentSlot.DOC_A)
        self.assertEqual(result.file_format, SupportedFileFormat.XLSX)
        self.assertEqual(result.extraction_status, "SUCCESS")

        table = result.tables[0]
        cell_a3 = next(c for c in table.cells if c.row_index == 2 and c.col_index == 0)
        self.assertEqual(cell_a3.formula, "=SUM(A1:A2)")
        # Since Excel didn't evaluate it, cached value is None and data_type is formula_uncached
        self.assertEqual(cell_a3.data_type, "formula_uncached")
        self.assertIsNone(cell_a3.value)

    def test_borderless_table_reconstruction_and_bounding_boxes(self) -> None:
        """Phase 2: Verify coordinate-based reconstruction of borderless digital PDF tables."""
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)

        # Header
        page.insert_text(pymupdf.Point(50, 50), "Bharat Alpha Engineering Limited - Financial Highlights", fontsize=12)
        # Table column headers
        page.insert_text(pymupdf.Point(50, 100), "Particulars", fontsize=10)
        page.insert_text(pymupdf.Point(320, 100), "FY 2024-25", fontsize=10)
        page.insert_text(pymupdf.Point(450, 100), "FY 2023-24", fontsize=10)

        # Row 1
        page.insert_text(pymupdf.Point(50, 120), "Revenue from operations", fontsize=10)
        page.insert_text(pymupdf.Point(350, 120), "12,500.00", fontsize=10)
        page.insert_text(pymupdf.Point(470, 120), "10,200.00", fontsize=10)

        # Row 2
        page.insert_text(pymupdf.Point(50, 140), "Total expenses", fontsize=10)
        page.insert_text(pymupdf.Point(355, 140), "9,800.50", fontsize=10)
        page.insert_text(pymupdf.Point(475, 140), "8,100.25", fontsize=10)

        # Row 3 with bracketed negative
        page.insert_text(pymupdf.Point(50, 160), "Finance costs", fontsize=10)
        page.insert_text(pymupdf.Point(360, 160), "(150.00)", fontsize=10)
        page.insert_text(pymupdf.Point(480, 160), "(120.00)", fontsize=10)

        # Narrative context ensuring text density > 50 words
        narrative = "The accompanying notes are an integral part of these financial statements and should be read in conjunction with significant accounting policies and regulatory filings under Indian Accounting Standards. " * 3
        page.insert_textbox(pymupdf.Rect(50, 200, 550, 350), narrative, fontsize=9)

        pdf_path = self.temp_path / "borderless_test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        result = parse_pdf(pdf_path, "doc_bl", DocumentSlot.DOC_A)
        self.assertEqual(result.extraction_status, "SUCCESS")
        self.assertGreaterEqual(len(result.tables), 1, "Expected at least 1 reconstructed borderless table")

        bl_table = result.tables[0]
        self.assertIsNotNone(bl_table.bounding_box, "Table must have normalized bounding box")
        self.assertEqual(len(bl_table.bounding_box), 4)
        for coord in bl_table.bounding_box:
            self.assertGreaterEqual(coord, 0.0)
            self.assertLessEqual(coord, 1.0)

        # Verify cells have normalized bounding boxes
        self.assertGreater(len(bl_table.cells), 0)
        cells_with_bbox = [c for c in bl_table.cells if c.bounding_box is not None]
        self.assertGreater(len(cells_with_bbox), 0, "At least some cells must have bounding boxes")
        for c in cells_with_bbox:
            self.assertEqual(len(c.bounding_box), 4)

    def test_spatial_exclusion_mask_bordered_and_borderless_coexistence(self) -> None:
        """Phase 2: Verify spatial masking prevents duplicate extraction when bordered & borderless tables coexist."""
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)

        # 1. Native bordered table at top of page (y: 100 to 200)
        page.draw_rect(pymupdf.Rect(50, 100, 550, 200), color=(0, 0, 0), width=1)
        page.draw_line(pymupdf.Point(50, 130), pymupdf.Point(550, 130), color=(0, 0, 0))
        page.draw_line(pymupdf.Point(300, 100), pymupdf.Point(300, 200), color=(0, 0, 0))
        page.insert_text(pymupdf.Point(60, 120), "Primary Line Item", fontsize=10)
        page.insert_text(pymupdf.Point(320, 120), "Current (INR Cr)", fontsize=10)
        page.insert_text(pymupdf.Point(60, 160), "Gross Turnover", fontsize=10)
        page.insert_text(pymupdf.Point(320, 160), "15000.00", fontsize=10)

        # 2. Borderless schedule at bottom of page (y: 300 to 400)
        page.insert_text(pymupdf.Point(50, 300), "Note 24: Other Income Breakdown", fontsize=11)
        page.insert_text(pymupdf.Point(50, 330), "Interest Income", fontsize=10)
        page.insert_text(pymupdf.Point(350, 330), "450.00", fontsize=10)
        page.insert_text(pymupdf.Point(50, 350), "Dividend Income", fontsize=10)
        page.insert_text(pymupdf.Point(350, 350), "75.00", fontsize=10)

        # Narrative context ensuring text density > 50 words
        narrative = "The accompanying notes are an integral part of these financial statements and should be read in conjunction with significant accounting policies and regulatory filings under Indian Accounting Standards. " * 3
        page.insert_textbox(pymupdf.Rect(50, 450, 550, 600), narrative, fontsize=9)

        pdf_path = self.temp_path / "coexistence_test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        result = parse_pdf(pdf_path, "doc_coex", DocumentSlot.DOC_A)
        self.assertEqual(result.extraction_status, "SUCCESS")
        # Native table detected + borderless table detected
        self.assertGreaterEqual(len(result.tables), 2, "Expected both bordered and borderless tables to be extracted")

        # Verify Gross Turnover is only in Table 1 (not duplicated in borderless table)
        tbl_1_text = " ".join(str(c.value) for c in result.tables[0].cells)
        self.assertTrue("Gross Turnover" in tbl_1_text or "GrossTurnover" in tbl_1_text)

        tbl_2_text = " ".join(str(c.value) for c in result.tables[1].cells)
        self.assertNotIn("Gross Turnover", tbl_2_text, "Bordered item must not be duplicated into borderless table")
        self.assertNotIn("GrossTurnover", tbl_2_text, "Bordered item must not be duplicated into borderless table")
        self.assertTrue("Interest Income" in tbl_2_text or "InterestIncome" in tbl_2_text)


if __name__ == "__main__":
    unittest.main()
