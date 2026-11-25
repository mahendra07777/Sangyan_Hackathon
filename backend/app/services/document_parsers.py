"""Document parsing, structural extraction, coordinate preservation, and JSON persistence for Compare Documents."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
import pymupdf
import xlrd
from fastapi import HTTPException, status

from ..models.comparison import (
    ComparisonDocument,
    DocumentExtractionResult,
    DocumentSlot,
    ExtractedTable,
    ExtractedTableCell,
    ExtractedTextBlock,
    SupportedFileFormat,
)
from .file_validator import validate_zip_safety

logger = logging.getLogger(__name__)

# Concurrency boundary: max 2 concurrent document extractions
_parser_semaphores: Dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}

def get_parser_semaphore() -> asyncio.Semaphore:
    """Return an asyncio.Semaphore(2) safely bound to the current running event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.Semaphore(2)
    sem = _parser_semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(2)
        _parser_semaphores[loop] = sem
    return sem

# Retain module-level symbol for backwards-compatibility
PARSER_SEMAPHORE = None

# Typography-grounded coordinate clustering tolerances
LINE_BASELINE_TOLERANCE_PT = 3.5
COLUMN_ALIGNMENT_TOLERANCE_PT = 4.0


def _is_numeric_token(text: str) -> bool:
    """Check if token represents a financial number, percentage, or dash."""
    t = text.strip()
    if not t:
        return False
    if t in ("-", "—", "–", "N/A", "n/a", "Nil", "nil", "None"):
        return True
    clean = t.replace("₹", "").replace(",", "").replace("$", "").strip()
    if clean.startswith("(") and clean.endswith(")"):
        clean = clean[1:-1].strip()
    if clean.endswith("%"):
        clean = clean[:-1].strip()
    try:
        float(clean)
        return True
    except ValueError:
        return False


def _extract_borderless_tables_from_page(
    page: pymupdf.Page,
    page_w: float,
    page_h: float,
    doc_id: str,
    page_num: int,
    bordered_tables: List[ExtractedTable],
    start_table_idx: int = 1,
) -> List[ExtractedTable]:
    """Reconstruct borderless tables using coordinate clustering on PyMuPDF word streams.

    Implements:
    - Right-edge (x1) numeric column alignment
    - 3.5pt vertical baseline line tolerance
    - 4.0pt horizontal column alignment tolerance
    - Conservative spatial exclusion mask around bordered tables
    - Split currency (₹) and parenthesized negative token reconciliation
    - Multi-line financial line item label handling
    """
    borderless_tables: List[ExtractedTable] = []

    # 1. Build Inset Exclusion Mask for Bordered Tables
    bordered_masks: List[Tuple[float, float, float, float]] = []
    for bt in bordered_tables:
        if bt.bounding_box and len(bt.bounding_box) == 4:
            bx0 = bt.bounding_box[0] * page_w
            by0 = bt.bounding_box[1] * page_h
            bx1 = bt.bounding_box[2] * page_w
            by1 = bt.bounding_box[3] * page_h
            bordered_masks.append((bx0 + 1.0, by0 + 1.0, bx1 - 1.0, by1 - 1.0))

    try:
        raw_words = page.get_text("words")
    except Exception as e:
        logger.debug(f"Could not extract words from page {page_num}: {e}")
        return borderless_tables

    if not raw_words:
        return borderless_tables

    # 2. Filter words inside bordered table masks
    filtered_words: List[Tuple[float, float, float, float, str]] = []
    for w in raw_words:
        wx0, wy0, wx1, wy1, wtext = float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4]).strip()
        if not wtext:
            continue
        w_area = max((wx1 - wx0) * (wy1 - wy0), 0.001)
        w_xc = (wx0 + wx1) / 2.0
        w_yc = (wy0 + wy1) / 2.0

        is_masked = False
        for mx0, my0, mx1, my1 in bordered_masks:
            if mx0 <= w_xc <= mx1 and my0 <= w_yc <= my1:
                is_masked = True
                break
            ix0, iy0 = max(wx0, mx0), max(wy0, my0)
            ix1, iy1 = min(wx1, mx1), min(wy1, my1)
            if ix1 > ix0 and iy1 > iy0:
                inter_area = (ix1 - ix0) * (iy1 - iy0)
                if (inter_area / w_area) >= 0.50:
                    is_masked = True
                    break
        if not is_masked:
            filtered_words.append((wx0, wy0, wx1, wy1, wtext))

    if not filtered_words:
        return borderless_tables

    # 3. Line Clustering (Vertical Baseline Tolerance: 3.5pt)
    filtered_words.sort(key=lambda item: (item[1], item[0]))
    lines: List[List[Tuple[float, float, float, float, str]]] = []
    current_line: List[Tuple[float, float, float, float, str]] = []
    current_y_baseline: Optional[float] = None

    for w in filtered_words:
        if not current_line:
            current_line.append(w)
            current_y_baseline = w[1]
        else:
            if current_y_baseline is not None and abs(w[1] - current_y_baseline) <= LINE_BASELINE_TOLERANCE_PT:
                current_line.append(w)
                current_y_baseline = sum(item[1] for item in current_line) / len(current_line)
            else:
                current_line.sort(key=lambda item: item[0])
                lines.append(current_line)
                current_line = [w]
                current_y_baseline = w[1]
    if current_line:
        current_line.sort(key=lambda item: item[0])
        lines.append(current_line)

    # 4. Reconcile Split Tokens (e.g. ₹ or ( ) )
    reconciled_lines: List[List[Tuple[float, float, float, float, str]]] = []
    for line in lines:
        new_line: List[Tuple[float, float, float, float, str]] = []
        i = 0
        while i < len(line):
            w = line[i]
            # ₹ or Rs. prefix
            if w[4] in ("₹", "Rs.", "Rs", "$") and i + 1 < len(line) and (line[i + 1][0] - w[2]) < 4.0:
                nxt = line[i + 1]
                w = (w[0], min(w[1], nxt[1]), nxt[2], max(w[3], nxt[3]), w[4] + nxt[4])
                i += 1
            # Parenthesized negative ( 1,234.56 )
            if w[4] == "(" and i + 2 < len(line):
                mid = line[i + 1]
                end = line[i + 2]
                if end[4] == ")" and (mid[0] - w[2]) < 4.0 and (end[0] - mid[2]) < 4.0:
                    w = (w[0], min(w[1], mid[1], end[1]), end[2], max(w[3], mid[3], end[3]), f"({mid[4]})")
                    i += 2
            new_line.append(w)
            i += 1
        reconciled_lines.append(new_line)

    # 5. Identify Borderless Table Blocks via Right-Edge Alignment
    line_meta = []
    for line_idx, line in enumerate(reconciled_lines):
        num_tokens = [tok for tok in line if _is_numeric_token(tok[4])]
        line_meta.append({
            "line_idx": line_idx,
            "line": line,
            "has_numeric": len(num_tokens) > 0,
            "num_tokens": num_tokens,
            "num_x1s": [round(tok[2], 1) for tok in num_tokens],
        })

    # Find contiguous or near-contiguous blocks of numeric lines
    table_blocks: List[List[int]] = []
    current_block: List[int] = []

    for idx, lm in enumerate(line_meta):
        if lm["has_numeric"]:
            current_block.append(idx)
        else:
            if current_block and idx + 1 < len(line_meta) and line_meta[idx + 1]["has_numeric"]:
                current_block.append(idx)
            else:
                if len([i for i in current_block if line_meta[i]["has_numeric"]]) >= 2:
                    table_blocks.append(current_block)
                current_block = []
    if len([i for i in current_block if line_meta[i]["has_numeric"]]) >= 2:
        table_blocks.append(current_block)

    # 6. Reconstruct Each Table Block
    for b_idx, block_line_indices in enumerate(table_blocks):
        block_lines = [line_meta[i] for i in block_line_indices]
        numeric_lines = [bl for bl in block_lines if bl["has_numeric"]]
        if len(numeric_lines) < 2:
            continue

        # Cluster column right edges (x1) across all numeric tokens in the block
        all_x1s = []
        for nl in numeric_lines:
            all_x1s.extend(nl["num_x1s"])
        if not all_x1s:
            continue

        all_x1s.sort()
        col_clusters: List[float] = []
        for x1 in all_x1s:
            if not col_clusters:
                col_clusters.append(x1)
            else:
                matched_c = False
                for c_idx, c_val in enumerate(col_clusters):
                    if abs(x1 - c_val) <= COLUMN_ALIGNMENT_TOLERANCE_PT:
                        col_clusters[c_idx] = (c_val + x1) / 2.0
                        matched_c = True
                        break
                if not matched_c:
                    col_clusters.append(x1)
        col_clusters.sort()
        if not col_clusters:
            continue

        first_num_x0 = min(tok[0] for nl in numeric_lines for tok in nl["num_tokens"])
        label_cutoff_x = first_num_x0 - 5.0

        # Check for potential header line right before or at top of block
        header_candidate_line = None
        data_start_idx = 0
        first_line_meta = block_lines[0]
        if not first_line_meta["has_numeric"]:
            header_candidate_line = first_line_meta["line"]
            data_start_idx = 1
        elif block_line_indices[0] > 0:
            prev_line = reconciled_lines[block_line_indices[0] - 1]
            if prev_line and abs(block_lines[0]["line"][0][1] - prev_line[0][1]) < 25.0:
                header_candidate_line = prev_line

        # Build Headers
        headers: List[str] = ["Particulars"]
        for c_idx, c_x1 in enumerate(col_clusters):
            matched_hdr_text = ""
            if header_candidate_line:
                hdr_words = [
                    w[4] for w in header_candidate_line
                    if abs(w[2] - c_x1) <= 30.0 or (w[0] >= label_cutoff_x and abs((w[0] + w[2]) / 2.0 - c_x1) <= 30.0)
                ]
                if hdr_words:
                    matched_hdr_text = " ".join(hdr_words).strip()
            headers.append(matched_hdr_text or f"Col {c_idx + 1}")

        # Build Rows and Cells
        rows: List[List[Optional[str]]] = []
        cells: List[ExtractedTableCell] = []
        pending_label_parts: List[str] = []
        pending_label_boxes: List[Tuple[float, float, float, float]] = []

        all_table_x0, all_table_y0 = float("inf"), float("inf")
        all_table_x1, all_table_y1 = float("-inf"), float("-inf")
        current_row_idx = 0

        for bl in block_lines[data_start_idx:]:
            line_words = bl["line"]
            for w in line_words:
                all_table_x0 = min(all_table_x0, w[0])
                all_table_y0 = min(all_table_y0, w[1])
                all_table_x1 = max(all_table_x1, w[2])
                all_table_y1 = max(all_table_y1, w[3])

            if not bl["has_numeric"]:
                left_words = [w for w in line_words if w[2] <= label_cutoff_x]
                if left_words:
                    pending_label_parts.append(" ".join(w[4] for w in left_words))
                    pending_label_boxes.extend([(w[0], w[1], w[2], w[3]) for w in left_words])
                continue

            label_words = [w for w in line_words if w[2] <= label_cutoff_x]
            curr_label = " ".join(w[4] for w in label_words).strip()
            if pending_label_parts:
                curr_label = (" ".join(pending_label_parts) + " " + curr_label).strip()
                label_boxes = pending_label_boxes + [(w[0], w[1], w[2], w[3]) for w in label_words]
                pending_label_parts = []
                pending_label_boxes = []
            else:
                label_boxes = [(w[0], w[1], w[2], w[3]) for w in label_words]

            if not curr_label:
                continue

            row_vals: List[Optional[str]] = [curr_label]

            if label_boxes:
                lx0 = min(b[0] for b in label_boxes)
                ly0 = min(b[1] for b in label_boxes)
                lx1 = max(b[2] for b in label_boxes)
                ly1 = max(b[3] for b in label_boxes)
                label_norm_bbox = [
                    round(lx0 / page_w, 4),
                    round(ly0 / page_h, 4),
                    round(lx1 / page_w, 4),
                    round(ly1 / page_h, 4),
                ]
            else:
                label_norm_bbox = None

            cells.append(
                ExtractedTableCell(
                    row_index=current_row_idx,
                    col_index=0,
                    value=curr_label,
                    raw_value=curr_label,
                    data_type="string",
                    is_header=False,
                    bounding_box=label_norm_bbox,
                )
            )

            for col_i, col_x1 in enumerate(col_clusters):
                matched_tok = None
                for tok in bl["num_tokens"]:
                    if abs(tok[2] - col_x1) <= COLUMN_ALIGNMENT_TOLERANCE_PT:
                        matched_tok = tok
                        break
                if matched_tok:
                    val_str = matched_tok[4]
                    cell_norm_box = [
                        round(matched_tok[0] / page_w, 4),
                        round(matched_tok[1] / page_h, 4),
                        round(matched_tok[2] / page_w, 4),
                        round(matched_tok[3] / page_h, 4),
                    ]
                else:
                    val_str = None
                    cell_norm_box = None

                row_vals.append(val_str)
                cells.append(
                    ExtractedTableCell(
                        row_index=current_row_idx,
                        col_index=col_i + 1,
                        value=val_str,
                        raw_value=val_str,
                        data_type="number" if val_str and _is_numeric_token(val_str) else "string",
                        is_header=False,
                        bounding_box=cell_norm_box,
                    )
                )

            rows.append(row_vals)
            current_row_idx += 1

        if rows:
            if all_table_x0 < all_table_x1 and all_table_y0 < all_table_y1:
                table_norm_bbox = [
                    round(all_table_x0 / page_w, 4),
                    round(all_table_y0 / page_h, 4),
                    round(all_table_x1 / page_w, 4),
                    round(all_table_y1 / page_h, 4),
                ]
            else:
                table_norm_bbox = None

            table_num = start_table_idx + len(borderless_tables)
            borderless_tables.append(
                ExtractedTable(
                    table_id=f"{doc_id}_p{page_num}_bl_t{table_num}",
                    page_number=page_num,
                    structural_ref=f"Page {page_num}, Borderless Table {table_num}",
                    num_rows=len(rows),
                    num_cols=len(headers),
                    headers=headers,
                    rows=rows,
                    cells=cells,
                    bounding_box=table_norm_bbox,
                )
            )

    return borderless_tables

MAX_PDF_PAGES = 200
SCANNED_DENSITY_THRESHOLD_WORDS_PER_PAGE = 50


# ---------------------------------------------------------------------------
# PDF Parser (Digital & Scanned Detection)
# ---------------------------------------------------------------------------

def parse_pdf(
    file_path: Path,
    doc_id: str,
    slot: DocumentSlot,
) -> DocumentExtractionResult:
    """Extract text blocks, bounding boxes, and native tables from PDF using PyMuPDF.
    
    Identifies scanned PDFs via page text density (<50 words/page).
    Enforces maximum limit of 200 pages.
    """
    doc = pymupdf.open(str(file_path))
    try:
        page_count = len(doc)
        if page_count > MAX_PDF_PAGES:
            raise ValueError(
                f"PDF exceeds maximum allowed limit of {MAX_PDF_PAGES} pages ({page_count} pages found)."
            )

        text_blocks: List[ExtractedTextBlock] = []
        tables: List[ExtractedTable] = []
        total_words = 0
        notes: List[str] = []

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc[page_idx]
            page_w = page.rect.width or 1.0
            page_h = page.rect.height or 1.0

            # 1. Text blocks with normalized bounding boxes
            blocks = page.get_text("blocks")
            for b_idx, block in enumerate(blocks):
                # block tuple: (x0, y0, x1, y1, text, block_no, block_type)
                if len(block) >= 7 and block[6] == 0:  # Text block
                    x0, y0, x1, y1, text, block_no = block[:6]
                    cleaned_text = text.strip()
                    if cleaned_text:
                        word_count = len(cleaned_text.split())
                        total_words += word_count
                        norm_bbox = [
                            round(x0 / page_w, 4),
                            round(y0 / page_h, 4),
                            round(x1 / page_w, 4),
                            round(y1 / page_h, 4),
                        ]
                        text_blocks.append(
                            ExtractedTextBlock(
                                block_id=f"{doc_id}_p{page_num}_b{block_no}_{b_idx}",
                                page_number=page_num,
                                structural_ref=f"Page {page_num}, Block {block_no}",
                                text=cleaned_text,
                                bounding_box=norm_bbox,
                                block_type="paragraph",
                            )
                        )

            # 2. Native Table Extraction via PyMuPDF
            page_bordered_tables: List[ExtractedTable] = []
            try:
                found_tables = page.find_tables()
                if found_tables and found_tables.tables:
                    for t_idx, tab in enumerate(found_tables.tables):
                        tab_data = tab.extract()
                        if not tab_data:
                            continue

                        headers = [str(c or "").strip() for c in tab_data[0]] if tab_data else []

                        # Multi-Row Table Header Merging (e.g. Row 0: Scope/Standalone, Row 1: Reporting Dates/Quarters)
                        if len(tab_data) >= 2:
                            r0 = [str(c or "").strip() for c in tab_data[0]]
                            r1 = [str(c or "").strip() for c in tab_data[1]]
                            date_period_pattern = re.compile(
                                r"(?:quarter|ended|month|year|as\s+at|audited|unaudited|particulars|\d{1,2}[\.\-\/]\d{1,2}[\.\-\/]\d{2,4}|[A-Za-z]+\s+\d{4})",
                                re.IGNORECASE,
                            )
                            r1_indicators = sum(1 for c in r1 if c and date_period_pattern.search(c))
                            r0_indicators = sum(1 for c in r0 if c and date_period_pattern.search(c))
                            has_scope_in_r0 = any("standalone" in c.lower() or "consolidated" in c.lower() for c in r0)

                            if r1_indicators >= 1 and (r1_indicators > r0_indicators or has_scope_in_r0):
                                merged_headers = []
                                last_group = ""
                                for col_i in range(len(r0)):
                                    c0 = r0[col_i] if col_i < len(r0) else ""
                                    c1 = r1[col_i] if col_i < len(r1) else ""
                                    if c0 and any(g in c0.lower() for g in ["standalone", "consolidated", "segment", "results", "audited", "unaudited"]):
                                        last_group = c0
                                    group_prefix = (c0 or last_group).strip()
                                    if group_prefix and c1 and group_prefix.lower() != c1.lower():
                                        merged_headers.append(f"{group_prefix} | {c1}".strip())
                                    else:
                                        merged_headers.append((c1 or group_prefix or f"Col {col_i + 1}").strip())
                                headers = merged_headers
                        rows: List[List[Optional[str]]] = []
                        cells: List[ExtractedTableCell] = []

                        norm_tab_bbox = None
                        if hasattr(tab, "bbox") and tab.bbox:
                            norm_tab_bbox = [
                                round(tab.bbox[0] / page_w, 4),
                                round(tab.bbox[1] / page_h, 4),
                                round(tab.bbox[2] / page_w, 4),
                                round(tab.bbox[3] / page_h, 4),
                            ]

                        for r_idx, row in enumerate(tab_data):
                            row_vals = [str(c).strip() if c is not None else None for c in row]
                            rows.append(row_vals)
                            for c_idx, val in enumerate(row_vals):
                                c_bbox = None
                                if hasattr(tab, "rows") and r_idx < len(tab.rows):
                                    row_obj = tab.rows[r_idx]
                                    if hasattr(row_obj, "cells") and c_idx < len(row_obj.cells):
                                        raw_cb = row_obj.cells[c_idx]
                                        if raw_cb and len(raw_cb) == 4:
                                            c_bbox = [
                                                round(raw_cb[0] / page_w, 4),
                                                round(raw_cb[1] / page_h, 4),
                                                round(raw_cb[2] / page_w, 4),
                                                round(raw_cb[3] / page_h, 4),
                                            ]
                                cells.append(
                                    ExtractedTableCell(
                                        row_index=r_idx,
                                        col_index=c_idx,
                                        value=val,
                                        raw_value=val,
                                        data_type="number" if (val and val.replace(".", "", 1).replace("-", "", 1).isdigit()) else "string",
                                        is_header=(r_idx == 0),
                                        bounding_box=c_bbox or norm_tab_bbox,
                                    )
                                )

                        t_obj = ExtractedTable(
                            table_id=f"{doc_id}_p{page_num}_t{t_idx + 1}",
                            page_number=page_num,
                            structural_ref=f"Page {page_num}, Table {t_idx + 1}",
                            num_rows=len(rows),
                            num_cols=len(headers),
                            headers=headers,
                            rows=rows,
                            cells=cells,
                            bounding_box=norm_tab_bbox,
                        )
                        page_bordered_tables.append(t_obj)
                        tables.append(t_obj)
            except Exception as tab_err:
                logger.debug(f"PyMuPDF table extraction note on page {page_num}: {tab_err}")

            # 3. Borderless Table Extraction (Reconstruction from word stream)
            try:
                borderless_tabs = _extract_borderless_tables_from_page(
                    page=page,
                    page_w=page_w,
                    page_h=page_h,
                    doc_id=doc_id,
                    page_num=page_num,
                    bordered_tables=page_bordered_tables,
                    start_table_idx=len(page_bordered_tables) + 1,
                )
                if borderless_tabs:
                    tables.extend(borderless_tabs)
            except Exception as bl_err:
                logger.debug(f"Borderless table extraction note on page {page_num}: {bl_err}")

        # Text density calculation for scanned PDF detection
        avg_words_per_page = total_words / max(page_count, 1)
        is_scanned = avg_words_per_page < SCANNED_DENSITY_THRESHOLD_WORDS_PER_PAGE

        if is_scanned:
            detected_format = SupportedFileFormat.PDF_SCANNED
            status_tag = "OCR_UNAVAILABLE_LOCAL_MODE"
            notes.append(
                f"Low text density ({avg_words_per_page:.1f} words/page < {SCANNED_DENSITY_THRESHOLD_WORDS_PER_PAGE}). "
                "Document identified as Scanned PDF. OCR extraction is unavailable in offline Local Mode."
            )
        else:
            detected_format = SupportedFileFormat.PDF_DIGITAL
            status_tag = "SUCCESS"

        return DocumentExtractionResult(
            doc_id=doc_id,
            slot=slot,
            file_format=detected_format,
            page_count=page_count,
            is_scanned=is_scanned,
            extraction_status=status_tag,
            tables=tables,
            text_blocks=text_blocks,
            raw_word_count=total_words,
            notes=notes,
        )
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Image Parser (PNG, JPG, JPEG)
# ---------------------------------------------------------------------------

def parse_image(
    file_path: Path,
    doc_id: str,
    slot: DocumentSlot,
    file_format: SupportedFileFormat,
) -> DocumentExtractionResult:
    """Parse image filing metadata. Preserves dimensions and sets VISION_EXTRACTION_REQUIRED."""
    pix = pymupdf.Pixmap(str(file_path))
    try:
        width, height = pix.width, pix.height
        notes = [
            f"Image dimensions verified ({width}x{height} px). "
            "Local extraction mode does not call cloud vision without user consent (Slice 5)."
        ]
        return DocumentExtractionResult(
            doc_id=doc_id,
            slot=slot,
            file_format=file_format,
            page_count=1,
            is_scanned=True,
            extraction_status="VISION_EXTRACTION_REQUIRED",
            tables=[],
            text_blocks=[],
            raw_word_count=0,
            notes=notes,
        )
    finally:
        # PyMuPDF Pixmap cleanup
        del pix


# ---------------------------------------------------------------------------
# DOCX Parser (Pure Standard Library OpenXML)
# ---------------------------------------------------------------------------

def parse_docx(
    file_path: Path,
    doc_id: str,
    slot: DocumentSlot,
) -> DocumentExtractionResult:
    """Extract paragraphs, headings, and tables from DOCX using standard zipfile and xml.etree."""
    with open(file_path, "rb") as f:
        content = f.read()

    validate_zip_safety(content)

    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    text_blocks: List[ExtractedTextBlock] = []
    tables: List[ExtractedTable] = []
    total_words = 0

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        if "word/document.xml" not in zf.namelist():
            raise ValueError("Invalid DOCX filing: word/document.xml not found.")

        doc_xml = zf.read("word/document.xml")
        root = ET.fromstring(doc_xml)
        body = root.find(f"{w_ns}body")

        if body is None:
            return DocumentExtractionResult(
                doc_id=doc_id,
                slot=slot,
                file_format=SupportedFileFormat.DOCX,
                extraction_status="SUCCESS",
                tables=[],
                text_blocks=[],
            )

        p_idx = 0
        t_idx = 0

        for child in body:
            # Paragraph
            if child.tag == f"{w_ns}p":
                p_idx += 1
                texts = [elem.text for elem in child.iter(f"{w_ns}t") if elem.text]
                full_text = "".join(texts).strip()
                if not full_text:
                    continue

                total_words += len(full_text.split())

                # Check heading style
                heading_level = None
                p_style = child.find(f"{w_ns}pPr/{w_ns}pStyle")
                if p_style is not None:
                    style_val = p_style.attrib.get(f"{w_ns}val", "").lower()
                    if "heading" in style_val:
                        for num in range(1, 10):
                            if str(num) in style_val:
                                heading_level = num
                                break

                structural_ref = (
                    f"Heading {heading_level}: {full_text[:40]}"
                    if heading_level
                    else f"Paragraph {p_idx}"
                )

                text_blocks.append(
                    ExtractedTextBlock(
                        block_id=f"{doc_id}_docx_p{p_idx}",
                        structural_ref=structural_ref,
                        text=full_text,
                        heading_level=heading_level,
                        block_type="heading" if heading_level else "paragraph",
                    )
                )

            # Table
            elif child.tag == f"{w_ns}tbl":
                t_idx += 1
                rows_data: List[List[Optional[str]]] = []
                cells_data: List[ExtractedTableCell] = []

                tr_elements = child.findall(f"{w_ns}tr")
                for r_i, tr in enumerate(tr_elements):
                    row_vals: List[Optional[str]] = []
                    tc_elements = tr.findall(f"{w_ns}tc")
                    for c_i, tc in enumerate(tc_elements):
                        cell_texts = [node.text for node in tc.iter(f"{w_ns}t") if node.text]
                        c_val = "".join(cell_texts).strip() or None
                        row_vals.append(c_val)
                        if c_val:
                            total_words += len(c_val.split())
                        cells_data.append(
                            ExtractedTableCell(
                                row_index=r_i,
                                col_index=c_i,
                                value=c_val,
                                raw_value=c_val,
                                is_header=(r_i == 0),
                            )
                        )
                    rows_data.append(row_vals)

                headers = [str(c or "") for c in rows_data[0]] if rows_data else []
                tables.append(
                    ExtractedTable(
                        table_id=f"{doc_id}_docx_tbl{t_idx}",
                        structural_ref=f"Table {t_idx}",
                        num_rows=len(rows_data),
                        num_cols=len(headers),
                        headers=headers,
                        rows=rows_data,
                        cells=cells_data,
                    )
                )

    return DocumentExtractionResult(
        doc_id=doc_id,
        slot=slot,
        file_format=SupportedFileFormat.DOCX,
        page_count=None,
        is_scanned=False,
        extraction_status="SUCCESS",
        tables=tables,
        text_blocks=text_blocks,
        raw_word_count=total_words,
    )


# ---------------------------------------------------------------------------
# XLSX Parser (openpyxl cached value & formula provenance)
# ---------------------------------------------------------------------------

def parse_xlsx(
    file_path: Path,
    doc_id: str,
    slot: DocumentSlot,
) -> DocumentExtractionResult:
    """Extract sheets, tabular grids, cached formula values, and merged cells from XLSX.
    
    Technical Note on Macros:
    openpyxl is purely a file reading and writing engine and never executes VBA macros
    (which reside as inert binary streams in .xlsm files). The `data_only=True` parameter
    controls formula evaluation reading:
    - When True: openpyxl reads the pre-calculated, cached formula result stored by
      Microsoft Excel when the workbook was last saved.
    - When False: openpyxl reads the raw formula string (e.g. "=SUM(A1:B1)").
    
    If a workbook was generated programmatically without calculating formulas, cached
    results will be None; this parser identifies both cached results and formula strings,
    tagging uncached formulas as 'formula_uncached' without crashing or guessing numbers.
    """
    wb = openpyxl.load_workbook(str(file_path), data_only=True, read_only=False)
    # Also load raw formula workbook to preserve formula provenance
    try:
        wb_raw = openpyxl.load_workbook(str(file_path), data_only=False, read_only=True)
    except Exception:
        wb_raw = None

    try:
        sheet_names = list(wb.sheetnames)
        tables: List[ExtractedTable] = []
        total_words = 0

        for s_idx, s_name in enumerate(sheet_names):
            ws = wb[s_name]
            ws_raw = wb_raw[s_name] if (wb_raw and s_name in wb_raw.sheetnames) else None

            # Build merged cells lookup map: (row, col) -> (range_str, anchor_val)
            merged_map: Dict[Tuple[int, int], Tuple[str, Any]] = {}
            for m_range in list(ws.merged_cells.ranges):
                anchor_val = ws.cell(row=m_range.min_row, column=m_range.min_col).value
                for r in range(m_range.min_row, m_range.max_row + 1):
                    for c in range(m_range.min_col, m_range.max_col + 1):
                        merged_map[(r, c)] = (str(m_range), anchor_val)

            rows: List[List[Optional[str]]] = []
            cells: List[ExtractedTableCell] = []
            max_r = min(ws.max_row or 0, 5000)
            max_c = min(ws.max_column or 0, 100)

            for r_idx in range(1, max_r + 1):
                row_vals: List[Optional[str]] = []
                for c_idx in range(1, max_c + 1):
                    cell = ws.cell(row=r_idx, column=c_idx)
                    raw_val = cell.value
                    cell_range = None

                    # Inspect formula string from raw workbook if present
                    formula_str = None
                    if ws_raw is not None:
                        try:
                            raw_cell = ws_raw.cell(row=r_idx, column=c_idx)
                            if raw_cell.value and str(raw_cell.value).startswith("="):
                                formula_str = str(raw_cell.value)
                        except Exception:
                            pass

                    if (r_idx, c_idx) in merged_map:
                        rng_str, anchor_v = merged_map[(r_idx, c_idx)]
                        cell_range = rng_str
                        if raw_val is None:
                            raw_val = anchor_v

                    str_val = None
                    data_type = "string"
                    if raw_val is not None:
                        if isinstance(raw_val, (int, float)):
                            data_type = "number"
                            str_val = str(raw_val)
                        elif isinstance(raw_val, datetime):
                            data_type = "date"
                            str_val = raw_val.strftime("%Y-%m-%d")
                        elif isinstance(raw_val, bool):
                            data_type = "boolean"
                            str_val = str(raw_val)
                        else:
                            str_val = str(raw_val).strip()

                        total_words += len(str_val.split())
                    elif formula_str:
                        # Formula present but cached value is missing
                        data_type = "formula_uncached"

                    row_vals.append(str_val)
                    cell_col_letter = openpyxl.utils.get_column_letter(c_idx)
                    cells.append(
                        ExtractedTableCell(
                            row_index=r_idx - 1,
                            col_index=c_idx - 1,
                            value=str_val,
                            raw_value=raw_val if not isinstance(raw_val, datetime) else str_val,
                            data_type=data_type,
                            is_header=(r_idx == 1),
                            cell_range=f"{s_name}!{cell_col_letter}{r_idx}" if not cell_range else cell_range,
                            formula=formula_str,
                        )
                    )

                # Skip completely blank trailing rows
                if any(v is not None for v in row_vals):
                    rows.append(row_vals)

            headers = [str(c or "") for c in rows[0]] if rows else []
            tables.append(
                ExtractedTable(
                    table_id=f"{doc_id}_xlsx_s{s_idx + 1}",
                    sheet_name=s_name,
                    structural_ref=f"Sheet: {s_name}",
                    num_rows=len(rows),
                    num_cols=len(headers),
                    headers=headers,
                    rows=rows,
                    cells=cells,
                )
            )

        return DocumentExtractionResult(
            doc_id=doc_id,
            slot=slot,
            file_format=SupportedFileFormat.XLSX,
            sheet_names=sheet_names,
            is_scanned=False,
            extraction_status="SUCCESS",
            tables=tables,
            text_blocks=[],
            raw_word_count=total_words,
        )
    finally:
        wb.close()
        if wb_raw:
            wb_raw.close()


# ---------------------------------------------------------------------------
# XLS Parser (xlrd BIFF8)
# ---------------------------------------------------------------------------

def parse_xls(
    file_path: Path,
    doc_id: str,
    slot: DocumentSlot,
) -> DocumentExtractionResult:
    """Extract legacy Excel BIFF8 spreadsheets via xlrd, handling 1900/1904 dates and merged cells."""
    wb = xlrd.open_workbook(str(file_path), formatting_info=False)
    try:
        sheet_names = wb.sheet_names()
        tables: List[ExtractedTable] = []
        total_words = 0

        for s_idx in range(wb.nsheets):
            sh = wb.sheet_by_index(s_idx)
            s_name = sh.name

            # Merged cells map: (r, c) -> (range_str, anchor_val)
            merged_map: Dict[Tuple[int, int], Tuple[str, Any]] = {}
            for rlo, rhi, clo, chi in sh.merged_cells:
                anchor_v = sh.cell_value(rlo, clo) if rlo < sh.nrows and clo < sh.ncols else None
                range_str = f"{s_name}!R{rlo + 1}C{clo + 1}:R{rhi}C{chi}"
                for r in range(rlo, rhi):
                    for c in range(clo, chi):
                        merged_map[(r, c)] = (range_str, anchor_v)

            rows: List[List[Optional[str]]] = []
            cells: List[ExtractedTableCell] = []

            for r in range(sh.nrows):
                row_vals: List[Optional[str]] = []
                for c in range(sh.ncols):
                    cell_type = sh.cell_type(r, c)
                    raw_val = sh.cell_value(r, c)
                    cell_range = None

                    if (r, c) in merged_map:
                        rng_str, anchor_v = merged_map[(r, c)]
                        cell_range = rng_str
                        if raw_val is None or raw_val == "":
                            raw_val = anchor_v

                    str_val = None
                    data_type = "string"

                    if cell_type == xlrd.XL_CELL_NUMBER:
                        data_type = "number"
                        # Handle integer values cleanly
                        str_val = str(int(raw_val)) if raw_val == int(raw_val) else str(raw_val)
                    elif cell_type == xlrd.XL_CELL_DATE:
                        data_type = "date"
                        try:
                            dt_tuple = xlrd.xldate_as_tuple(raw_val, wb.datemode)
                            str_val = f"{dt_tuple[0]:04d}-{dt_tuple[1]:02d}-{dt_tuple[2]:02d}"
                        except Exception:
                            str_val = str(raw_val)
                    elif cell_type == xlrd.XL_CELL_BOOLEAN:
                        data_type = "boolean"
                        str_val = "True" if raw_val else "False"
                    elif cell_type == xlrd.XL_CELL_TEXT:
                        str_val = str(raw_val).strip()
                    elif cell_type in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        str_val = None
                    elif cell_type == xlrd.XL_CELL_ERROR:
                        str_val = f"ERROR_{raw_val}"

                    if str_val:
                        total_words += len(str_val.split())

                    row_vals.append(str_val)
                    cells.append(
                        ExtractedTableCell(
                            row_index=r,
                            col_index=c,
                            value=str_val,
                            raw_value=raw_val,
                            data_type=data_type,
                            is_header=(r == 0),
                            cell_range=cell_range or f"{s_name}!R{r + 1}C{c + 1}",
                        )
                    )

                if any(v is not None for v in row_vals):
                    rows.append(row_vals)

            headers = [str(c or "") for c in rows[0]] if rows else []
            tables.append(
                ExtractedTable(
                    table_id=f"{doc_id}_xls_s{s_idx + 1}",
                    sheet_name=s_name,
                    structural_ref=f"Sheet: {s_name}",
                    num_rows=len(rows),
                    num_cols=len(headers),
                    headers=headers,
                    rows=rows,
                    cells=cells,
                )
            )

        return DocumentExtractionResult(
            doc_id=doc_id,
            slot=slot,
            file_format=SupportedFileFormat.XLS,
            sheet_names=sheet_names,
            is_scanned=False,
            extraction_status="SUCCESS",
            tables=tables,
            text_blocks=[],
            raw_word_count=total_words,
        )
    finally:
        wb.release_resources()


# ---------------------------------------------------------------------------
# High-Level Bounded Dispatcher
# ---------------------------------------------------------------------------

async def parse_document_file(
    file_path: Path,
    doc_id: str,
    slot: DocumentSlot,
    file_format: SupportedFileFormat,
    original_filename: str,
    session_dir: Path,
) -> Tuple[ComparisonDocument, DocumentExtractionResult]:
    """Execute parser under bounded concurrency semaphore, persist structured JSON, and return models."""
    async with get_parser_semaphore():
        file_size = file_path.stat().st_size
        logger.info(f"Parsing document {doc_id} ({file_format.value}): {original_filename} [{file_size} bytes]")

        try:
            if file_format in (SupportedFileFormat.PDF_DIGITAL, SupportedFileFormat.PDF_SCANNED):
                extraction = await asyncio.to_thread(parse_pdf, file_path, doc_id, slot)
            elif file_format in (SupportedFileFormat.IMAGE_PNG, SupportedFileFormat.IMAGE_JPG, SupportedFileFormat.IMAGE_JPEG):
                extraction = await asyncio.to_thread(parse_image, file_path, doc_id, slot, file_format)
            elif file_format == SupportedFileFormat.DOCX:
                extraction = await asyncio.to_thread(parse_docx, file_path, doc_id, slot)
            elif file_format == SupportedFileFormat.XLSX:
                extraction = await asyncio.to_thread(parse_xlsx, file_path, doc_id, slot)
            elif file_format == SupportedFileFormat.XLS:
                extraction = await asyncio.to_thread(parse_xls, file_path, doc_id, slot)
            else:
                raise ValueError(f"No parser available for format: {file_format}")

        except Exception as exc:
            logger.error(f"Error parsing {doc_id} ({original_filename}): {exc}", exc_info=True)
            extraction = DocumentExtractionResult(
                doc_id=doc_id,
                slot=slot,
                file_format=file_format,
                extraction_status="FAILED",
                extraction_error=str(exc),
                notes=[f"Extraction failed: {exc}"],
            )

        # Persist structured extraction JSON to session extracted directory
        extracted_dir = session_dir / "extracted"
        extracted_dir.mkdir(parents=True, exist_ok=True)
        json_path = extracted_dir / f"{doc_id}_extraction.json"
        tmp_json = extracted_dir / f"{doc_id}_extraction.json.tmp"

        with open(tmp_json, "w", encoding="utf-8") as f:
            f.write(extraction.model_dump_json(indent=2))
        tmp_json.replace(json_path)

        # Storage relative path for document
        doc_rel = f"documents/{file_path.name}"

        comp_doc = ComparisonDocument(
            doc_id=doc_id,
            slot=slot,
            original_filename=original_filename,
            file_format=extraction.file_format,
            file_size_bytes=file_size,
            page_count=extraction.page_count,
            sheet_names=extraction.sheet_names,
            is_scanned=extraction.is_scanned,
            storage_rel_path=doc_rel,
            extraction_status=extraction.extraction_status,
            extraction_error=extraction.extraction_error,
        )

        return comp_doc, extraction
