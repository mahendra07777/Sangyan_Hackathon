"""File validation, signature sniffing, decompression bomb guards, and sanitization for Compare Documents."""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import List, Optional, Set, Tuple

from fastapi import HTTPException, UploadFile, status
import pymupdf

from ..models.comparison import SupportedFileFormat

logger = logging.getLogger(__name__)

# Resource and security limits
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024        # 20 MiB per document
MAX_SESSION_TOTAL_BYTES = 100 * 1024 * 1024   # 100 MiB aggregate session limit
MAX_ZIP_UNCOMPRESSED_BYTES = 50 * 1024 * 1024 # 50 MiB max uncompressed ZIP hard ceiling
MAX_ZIP_EXPANSION_RATIO = 25.0                # 25:1 ratio safeguard (accommodates legitimate OpenXML repetitive XML tables up to ~20:1 while blocking malicious bombs with >100:1 ratios)
MAX_IMAGE_DIMENSION = 10000                   # 10000x10000 max image dimension
MAX_IMAGE_PIXELS = 100_000_000                # 100 Megapixels max

# Magic byte signatures
MAGIC_PDF = b"%PDF-"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_ZIP = b"PK\x03\x04"
MAGIC_ZIP_EMPTY = b"PK\x05\x06"
MAGIC_ZIP_SPANNED = b"PK\x07\x08"
MAGIC_XLS = b"\xd0\xcf\x11\xe0"

_SAFE_FILENAME_CHARS = re.compile(r"[^a-zA-Z0-9_\-\. ]")
_MULTI_DOTS_OR_SPACES = re.compile(r"[\s_]+")


def sanitize_filename(filename: str) -> str:
    """Sanitize original filename to prevent path traversal, shell injection, or illegal characters.
    
    Ensures safe basename, enforces [a-zA-Z0-9_\\-\\.] characters, and bounds length to 255.
    """
    if not filename or not filename.strip():
        return "document"

    # Take strictly the basename to strip any directory traversal segments
    clean_name = os.path.basename(filename.strip().replace("\\", "/"))
    # Also strip URL-encoded traversal if any
    clean_name = clean_name.replace("%2e", ".").replace("%2f", "").replace("%5c", "")
    clean_name = os.path.basename(clean_name)

    # Strip illegal characters
    clean_name = _SAFE_FILENAME_CHARS.sub("_", clean_name)
    clean_name = _MULTI_DOTS_OR_SPACES.sub("_", clean_name).strip("._ ")

    if not clean_name:
        clean_name = "document"

    # Limit to 255 characters while preserving extension
    if len(clean_name) > 255:
        stem, ext = os.path.splitext(clean_name)
        allowed_stem_len = max(1, 255 - len(ext))
        clean_name = stem[:allowed_stem_len] + ext

    return clean_name


def validate_image_dimensions(image_bytes: bytes) -> Tuple[int, int]:
    """Validate image dimensions and protect against decompression bombs."""
    try:
        pix = pymupdf.Pixmap(image_bytes)
        width, height = pix.width, pix.height
        total_pixels = width * height

        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image dimensions ({width}x{height}) exceed maximum allowed {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}.",
            )
        if total_pixels > MAX_IMAGE_PIXELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image pixel count ({total_pixels}) exceeds maximum safety limit of {MAX_IMAGE_PIXELS}.",
            )
        return width, height
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupt or invalid image file: {exc}",
        )


def validate_zip_safety(zip_bytes: bytes) -> zipfile.ZipFile:
    """Check ZIP archives (DOCX, XLSX) for decompression bombs and traversal attacks."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupted or invalid ZIP archive: {exc}",
        )

    total_uncompressed = 0
    total_compressed = len(zip_bytes)

    for info in zf.infolist():
        # Prevent zip directory traversal attacks
        if info.filename.startswith("/") or ".." in info.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Archive contains illegal path traversal member: {info.filename}",
            )
        total_uncompressed += info.file_size

        if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Archive uncompressed size exceeds maximum safety limit of {MAX_ZIP_UNCOMPRESSED_BYTES // (1024 * 1024)} MiB.",
            )

    if total_compressed > 0:
        ratio = total_uncompressed / total_compressed
        if ratio > MAX_ZIP_EXPANSION_RATIO and total_uncompressed > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Decompression bomb detected: expansion ratio {ratio:.1f} exceeds {MAX_ZIP_EXPANSION_RATIO}:1.",
            )

    return zf


def detect_file_format(header_bytes: bytes, full_content: bytes, filename: str) -> SupportedFileFormat:
    """Detect file format using magic byte inspection and archive structure validation.
    
    Never relies solely on client-provided Content-Type or file extension.
    """
    ext = os.path.splitext(filename.lower())[1]

    # 1. PDF
    if header_bytes.startswith(MAGIC_PDF):
        return SupportedFileFormat.PDF_DIGITAL

    # 2. PNG
    if header_bytes.startswith(MAGIC_PNG):
        validate_image_dimensions(full_content)
        return SupportedFileFormat.IMAGE_PNG

    # 3. JPEG / JPG
    if header_bytes.startswith(MAGIC_JPEG):
        validate_image_dimensions(full_content)
        if ext == ".jpg":
            return SupportedFileFormat.IMAGE_JPG
        return SupportedFileFormat.IMAGE_JPEG

    # 4. ZIP-based: DOCX or XLSX
    if header_bytes.startswith(MAGIC_ZIP) or header_bytes.startswith(MAGIC_ZIP_EMPTY) or header_bytes.startswith(MAGIC_ZIP_SPANNED):
        zf = validate_zip_safety(full_content)
        namelist = set(zf.namelist())

        if "word/document.xml" in namelist:
            return SupportedFileFormat.DOCX

        if "xl/workbook.xml" in namelist:
            return SupportedFileFormat.XLSX

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported ZIP archive. File must be a valid Microsoft Word (.docx) or Excel (.xlsx) document.",
        )

    # 5. XLS (Legacy BIFF8 OLE2 Compound Document)
    if header_bytes.startswith(MAGIC_XLS):
        return SupportedFileFormat.XLS

    # Fallback error for unrecognized signatures
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Unsupported or unrecognized file format for '{filename}'. "
            "Approved formats are: PDF, Scanned PDF, PNG, JPG, JPEG, DOCX, XLSX, XLS."
        ),
    )


async def read_and_validate_upload(
    file: UploadFile,
    current_total_bytes: int = 0,
) -> Tuple[bytes, SupportedFileFormat, str]:
    """Stream and validate an uploaded file against size and signature constraints.
    
    Returns (content_bytes, detected_format, safe_filename).
    """
    safe_name = sanitize_filename(file.filename or "uploaded_file")
    chunk_size = 64 * 1024  # 64 KiB chunks
    file_bytes_accum = io.BytesIO()
    total_read = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_read += len(chunk)

        if total_read > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File '{safe_name}' exceeds maximum permitted size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MiB.",
            )

        if current_total_bytes + total_read > MAX_SESSION_TOTAL_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Total upload exceeds aggregate session limit of {MAX_SESSION_TOTAL_BYTES // (1024 * 1024)} MiB.",
            )

        file_bytes_accum.write(chunk)

    content = file_bytes_accum.getvalue()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{safe_name}' is empty (0 bytes).",
        )

    header = content[:512]
    detected_format = detect_file_format(header, content, safe_name)

    return content, detected_format, safe_name
