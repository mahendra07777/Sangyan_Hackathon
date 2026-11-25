"""Comparison session, authentication, ingestion, and lifecycle endpoints (Slice 1 & 2)."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

logger = logging.getLogger(__name__)

from pydantic import BaseModel

from ..models.comparison import (
    CalculationResult,
    CompatibilityReport,
    ComparisonChatMessage,
    ComparisonDocument,
    ComparisonMode,
    ComparisonResult,
    ComparisonSession,
    ConflictResolution,
    ConsentRequest,
    ConsentResponse,
    DocumentExtractionResult,
    DocumentMetadata,
    DocumentSlot,
    ErrorDetail,
    ErrorResponse,
    FinancialCorrectionRecord,
    FinancialCorrectionRequest,
    FinancialCorrectionResponse,
    FinancialUndoResponse,
    FinancialValue,
    MetadataUpdateRequest,
    ProcessingStage,
    ProcessingStatusResponse,
    ProcessPayload,
    SessionCalculationsResponse,
    SessionCorrectionsResponse,
    SessionCreateRequest,
    SessionCreatedResponse,
    SessionDeleteResponse,
    SessionFinancialsResponse,
    SessionMetadataResponse,
    SessionStatus,
    SupportedFileFormat,
    TransmissionPreview,
    TransmissionSectionPreview,
    UploadSuccessResponse,
    ValueCandidate,
)
from ..services.compare_synthesis_service import CompareSynthesisService
from ..services.comparison_session_store import (
    DEFAULT_ABSOLUTE_LIFETIME_HOURS,
    DEFAULT_IDLE_TIMEOUT_MINUTES,
    DEFAULT_MAX_DOCUMENTS,
    session_store,
)
from ..services.compatibility_engine import CompatibilityEngine
from ..services.conflict_arbitrator import ConflictArbitrator
from ..services.document_parsers import parse_document_file
from ..services.export_excel_service import ExportExcelService
from ..services.export_pdf_service import ExportPdfService
from ..services.file_validator import read_and_validate_upload
from ..services.financial_calculator import FinancialCalculator
from ..services.financial_extractor import FinancialExtractor
from ..services.metadata_extractor import MetadataExtractor

compare_router = APIRouter(prefix="/api/compare", tags=["compare-session"])

_SLOT_SEQUENCE = [
    DocumentSlot.DOC_A,
    DocumentSlot.DOC_B,
    DocumentSlot.DOC_C,
    DocumentSlot.DOC_D,
    DocumentSlot.DOC_E,
]

_UUID_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def order_documents_chronologically(
    doc_ids: List[str],
    metadata_map: Dict[str, DocumentMetadata],
) -> List[str]:
    """Sort document IDs chronologically (earlier period first as baseline).

    Uses verified financial year and period-end metadata.
    Never relies on upload order or filenames as chronological evidence.
    Preserves original relative order if metadata cannot be differentiated.
    """
    if not doc_ids or len(doc_ids) <= 1:
        return list(doc_ids)

    def _get_sort_key(doc_id: str, index: int):
        meta = metadata_map.get(doc_id)
        if not meta:
            return (9, "9999-99-99", 0, index)

        # 1. Period end date (YYYY-MM-DD or parseable ISO date)
        period_end = getattr(meta, "period_end_date", None)
        end_date_str = ""
        if period_end:
            end_date_str = str(period_end).strip()[:10]

        # 2. Financial Year (e.g. "FY 2023-24", "FY 2024-25", "2024", "FY24")
        fy_year = None
        fy_raw = getattr(meta, "financial_year", None)
        if fy_raw and fy_raw != "Unknown":
            m_range = re.search(r"(?:19|20)?(\d{2})\s*[-/]\s*(\d{2,4})", fy_raw)
            if m_range:
                part1 = int(m_range.group(1))
                if part1 < 100:
                    part1 += 2000
                fy_year = part1
            else:
                m_single = re.search(r"\b(19\d{2}|20\d{2})\b", fy_raw)
                if m_single:
                    fy_year = int(m_single.group(1))

        # 3. Quarter (Q1, Q2, Q3, Q4)
        quarter_num = 0
        q_raw = getattr(meta, "quarter", None)
        if q_raw:
            m_q = re.search(r"Q([1-4])", str(q_raw), re.IGNORECASE)
            if m_q:
                quarter_num = int(m_q.group(1))

        # Primary sort priority:
        if end_date_str and re.match(r"^\d{4}-\d{2}-\d{2}", end_date_str):
            return (0, end_date_str, quarter_num, index)
        if fy_year is not None:
            return (1, f"{fy_year:04d}", quarter_num, index)
        if end_date_str:
            return (2, end_date_str, quarter_num, index)
        return (3, "9999", 0, index)

    return sorted(doc_ids, key=lambda d_id: _get_sort_key(d_id, doc_ids.index(d_id)))


def _check_query_params_for_token(request: Request) -> None:
    """Reject requests that attempt to supply capability tokens via URL query parameters."""
    query_keys = {k.lower() for k in request.query_params.keys()}
    if "token" in query_keys or "session_token" in query_keys or "x-session-token" in query_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tokens must not be passed in query parameters. Use X-Session-Token header.",
        )


async def get_authenticated_session(
    request: Request,
    session_id: str,
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
) -> ComparisonSession:
    """FastAPI dependency: Authenticates comparison session requests using constant-time token verification."""
    _check_query_params_for_token(request)

    if not x_session_token or not x_session_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. X-Session-Token header missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not session_id or not _UUID_REGEX.match(session_id.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session identifier format.",
        )

    session, error = session_store.verify_and_get_session(
        session_id=session_id.strip(),
        supplied_token=x_session_token.strip(),
        touch=True,
    )

    if error in ("SESSION_NOT_FOUND", "INVALID_TOKEN"):
        # Uniform 401 response: never disclose whether another session ID exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired comparison session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if error == "SESSION_EXPIRED":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Comparison session has expired due to inactivity or maximum lifetime.",
        )

    if error == "SESSION_TERMINATED":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Comparison session has been terminated.",
        )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

    return session


@compare_router.post(
    "/session",
    response_model=SessionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
async def create_comparison_session(
    request: Request,
    payload: Optional[SessionCreateRequest] = None,
) -> SessionCreatedResponse:
    """Create a new ephemeral comparison session, allocate isolated disk storage, return capability token."""
    _check_query_params_for_token(request)

    mode = payload.comparison_mode if payload else SessionCreateRequest().comparison_mode
    session, raw_token = session_store.create_session(comparison_mode=mode)

    return SessionCreatedResponse(
        session_id=session.session_id,
        session_token=raw_token,
        comparison_mode=session.comparison_mode,
        idle_timeout_seconds=DEFAULT_IDLE_TIMEOUT_MINUTES * 60,
        absolute_timeout_seconds=DEFAULT_ABSOLUTE_LIFETIME_HOURS * 3600,
        max_documents=DEFAULT_MAX_DOCUMENTS,
    )


@compare_router.delete(
    "/session/{session_id}",
    response_model=SessionDeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired or Terminated"},
    },
)
async def delete_comparison_session(
    session_id: str,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> SessionDeleteResponse:
    """Explicitly terminate comparison session and purge temporary storage."""
    session_store.terminate_session(session.session_id)
    return SessionDeleteResponse(
        status="DELETED",
        message="Session storage wiped cleanly and terminated.",
        session_id=session.session_id,
    )


@compare_router.post(
    "/session/{session_id}/upload",
    response_model=UploadSuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error / Bad file / Mode mismatch"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
        413: {"model": ErrorResponse, "description": "Payload Too Large (>20 MiB per file or >100 MiB total)"},
    },
)
async def upload_documents(
    session_id: str,
    request: Request,
    files: List[UploadFile] = File(...),
    gemini_consent_acknowledged: Optional[str] = Form("false"),
    session: ComparisonSession = Depends(get_authenticated_session),
) -> UploadSuccessResponse:
    """Ingest 2 to 5 financial filings, validate signatures, parse locally, and persist extraction JSON."""
    _check_query_params_for_token(request)

    # Validate document count against mode requirements
    if session.comparison_mode == ComparisonMode.QUICK_COMPARE:
        if len(files) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"QUICK_COMPARE mode requires exactly 2 documents, received {len(files)}.",
            )
    elif session.comparison_mode == ComparisonMode.MULTI_DOCUMENT:
        if len(files) < 2 or len(files) > DEFAULT_MAX_DOCUMENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"MULTI_DOCUMENT mode requires between 2 and {DEFAULT_MAX_DOCUMENTS} documents, received {len(files)}.",
            )
    else:
        if len(files) < 2 or len(files) > DEFAULT_MAX_DOCUMENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Comparison requires between 2 and {DEFAULT_MAX_DOCUMENTS} documents, received {len(files)}.",
            )

    session_dir = session_store.resolve_session_path(session.session_id)
    docs_dir = session_dir / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    validated_files = []
    written_files: List[Path] = []
    current_total_bytes = 0

    try:
        for i, file in enumerate(files):
            content, file_fmt, safe_name = await read_and_validate_upload(file, current_total_bytes)
            current_total_bytes += len(content)
            slot = _SLOT_SEQUENCE[i]
            doc_id = slot.value
            file_path = docs_dir / f"{doc_id}_{safe_name}"

            with open(file_path, "wb") as f:
                f.write(content)

            written_files.append(file_path)
            validated_files.append((file_path, doc_id, slot, file_fmt, safe_name))

        # Bounded concurrent parsing
        tasks = [
            parse_document_file(
                file_path=vf[0],
                doc_id=vf[1],
                slot=vf[2],
                file_format=vf[3],
                original_filename=vf[4],
                session_dir=session_dir,
            )
            for vf in validated_files
        ]
        parsed_results = await asyncio.gather(*tasks)
        comp_docs = [r[0] for r in parsed_results]

    except Exception:
        # Partial upload failure cleanup: unlink all files written in this batch
        for fp in written_files:
            try:
                if fp.exists():
                    fp.unlink()
            except Exception as cleanup_err:
                logger.warning(f"Error cleaning up partial file {fp}: {cleanup_err}")
        raise

    consent_flag = bool(
        gemini_consent_acknowledged
        and gemini_consent_acknowledged.strip().lower() in ("true", "1")
    )
    session.consent_granted = consent_flag
    session.approved_payload_hash = None
    session.document_ids = [d.doc_id for d in comp_docs]

    session_store.save_session_documents(session.session_id, comp_docs)

    # 1. State machine transition: FILES_UPLOADED
    if session.can_transition_to(SessionStatus.FILES_UPLOADED):
        session.transition_to(SessionStatus.FILES_UPLOADED)

    # Automatically extract metadata for all uploaded documents
    metadata_map: Dict[str, DocumentMetadata] = {}
    for comp_doc, extraction in parsed_results:
        meta = MetadataExtractor.extract_metadata(comp_doc, extraction)
        metadata_map[comp_doc.doc_id] = meta
    session_store.save_session_metadata(session.session_id, metadata_map)

    # Deterministically evaluate session compatibility
    comp_report = CompatibilityEngine.evaluate_session(metadata_map, session_id=session.session_id)
    session_store.save_session_compatibility(session.session_id, comp_report)

    # 2. State machine transition: METADATA_EXTRACTED
    if session.can_transition_to(SessionStatus.METADATA_EXTRACTED):
        session.transition_to(SessionStatus.METADATA_EXTRACTED)

    session_store.update_manifest(session)

    logger.info(
        f"Uploaded, parsed, and extracted metadata for {len(comp_docs)} documents in session {session.session_id} "
        f"(status={session.status}, consent={consent_flag})"
    )

    return UploadSuccessResponse(
        session_id=session.session_id,
        uploaded_documents=comp_docs,
        consent_granted=session.consent_granted,
    )


@compare_router.post(
    "/session/{session_id}/retry/{doc_id}",
    response_model=ComparisonDocument,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error / Bad file / Invalid slot"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
        413: {"model": ErrorResponse, "description": "Payload Too Large (>20 MiB)"},
    },
)
async def retry_document_slot(
    session_id: str,
    doc_id: str,
    request: Request,
    file: UploadFile = File(...),
    session: ComparisonSession = Depends(get_authenticated_session),
) -> ComparisonDocument:
    """Replaces a corrupted or unreadable document in a single slot without invalidating sibling documents."""
    _check_query_params_for_token(request)
    doc_id_clean = doc_id.strip().lower()
    valid_slots = {s.value: s for s in _SLOT_SEQUENCE}

    if doc_id_clean not in valid_slots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document slot identifier '{doc_id}'. Must be one of {list(valid_slots.keys())}.",
        )

    slot = valid_slots[doc_id_clean]
    session_dir = session_store.resolve_session_path(session.session_id)
    docs_dir = session_dir / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    content, file_fmt, safe_name = await read_and_validate_upload(file, 0)
    file_path = docs_dir / f"{doc_id_clean}_{safe_name}"

    with open(file_path, "wb") as f:
        f.write(content)

    comp_doc, extraction = await parse_document_file(
        file_path=file_path,
        doc_id=doc_id_clean,
        slot=slot,
        file_format=file_fmt,
        original_filename=safe_name,
        session_dir=session_dir,
    )

    existing_docs = session_store.get_session_documents(session.session_id)
    updated = False
    for idx, d in enumerate(existing_docs):
        if d.doc_id == doc_id_clean:
            existing_docs[idx] = comp_doc
            updated = True
            break
    if not updated:
        existing_docs.append(comp_doc)

    if doc_id_clean not in session.document_ids:
        session.document_ids.append(doc_id_clean)

    session_store.save_session_documents(session.session_id, existing_docs)

    # 1. State machine transition: FILES_UPLOADED
    if session.can_transition_to(SessionStatus.FILES_UPLOADED):
        session.transition_to(SessionStatus.FILES_UPLOADED)

    # Re-extract metadata and re-evaluate compatibility
    metadata_map = session_store.get_session_metadata(session.session_id)
    new_meta = MetadataExtractor.extract_metadata(comp_doc, extraction)
    metadata_map[doc_id_clean] = new_meta
    session_store.save_session_metadata(session.session_id, metadata_map)

    comp_report = CompatibilityEngine.evaluate_session(metadata_map, session_id=session.session_id)
    session_store.save_session_compatibility(session.session_id, comp_report)

    # Invalidate existing consent on document replacement
    session.consent_granted = False
    session.approved_payload_hash = None

    # 2. State machine transition: METADATA_EXTRACTED
    if session.can_transition_to(SessionStatus.METADATA_EXTRACTED):
        session.transition_to(SessionStatus.METADATA_EXTRACTED)

    session_store.update_manifest(session)

    logger.info(f"Retried slot {doc_id_clean} for session {session.session_id} with file {safe_name}")
    return comp_doc


@compare_router.get(
    "/session/{session_id}/metadata",
    response_model=SessionMetadataResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_session_metadata(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> SessionMetadataResponse:
    """Returns automatically identified institutional metadata for all session documents."""
    _check_query_params_for_token(request)
    meta_map = session_store.get_session_metadata(session.session_id)
    return SessionMetadataResponse(session_id=session.session_id, metadata=meta_map)


@compare_router.put(
    "/session/{session_id}/metadata/{doc_id}",
    response_model=DocumentMetadata,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Document slot not found"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def update_document_metadata(
    session_id: str,
    doc_id: str,
    payload: MetadataUpdateRequest,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> DocumentMetadata:
    """Allows user inspection and manual correction of detected metadata fields."""
    _check_query_params_for_token(request)
    doc_id_clean = doc_id.strip().lower()
    meta_map = session_store.get_session_metadata(session.session_id)

    if doc_id_clean not in meta_map:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata for document slot '{doc_id}' not found in session.",
        )

    target_meta = meta_map[doc_id_clean]
    updates = payload.model_dump(exclude_unset=True)

    for field, new_val in updates.items():
        if new_val is not None:
            curr_val = getattr(target_meta, field, None)
            if curr_val != new_val:
                target_meta.user_overrides[field] = new_val
                setattr(target_meta, field, new_val)
                target_meta.is_user_overridden = True

    meta_map[doc_id_clean] = target_meta
    session_store.save_session_metadata(session.session_id, meta_map)

    # Re-evaluate compatibility matrix upon user metadata override
    comp_report = CompatibilityEngine.evaluate_session(meta_map, session_id=session.session_id)
    session_store.save_session_compatibility(session.session_id, comp_report)

    logger.info(f"User updated metadata for {doc_id_clean} in session {session.session_id}")
    return target_meta


@compare_router.get(
    "/session/{session_id}/compatibility",
    response_model=CompatibilityReport,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_session_compatibility(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> CompatibilityReport:
    """Executes the deterministic compatibility rules matrix across all uploaded documents."""
    _check_query_params_for_token(request)
    meta_map = session_store.get_session_metadata(session.session_id)
    comp_report = CompatibilityEngine.evaluate_session(meta_map, session_id=session.session_id)
    session_store.save_session_compatibility(session.session_id, comp_report)
    return comp_report


# ---------------------------------------------------------------------------
# Slice 5: Consent Management Endpoints (Endpoints 7 & 8)
# ---------------------------------------------------------------------------

AI_CONSENT_TERMS_DISCLOSURE = (
    "AI Processing Consent Notice (Google Gemini Standard Free Tier):\n"
    "1. Provider Data Terms: External AI processing uses Google Gemini Standard Free Tier. "
    "Under Google's published Standard Free Tier terms, submitted data may be processed and reviewed to improve Google products and services. "
    "Free-tier processing does not have the same data confidentiality terms as enterprise/paid tiers. Do not upload confidential or personally identifiable financial documents.\n"
    "2. Local Mode Guarantee: Bharat Investor Copilot operates 100% offline in Local Mode by default with zero cloud transmission. Local Mode remains available at all times.\n"
    "3. Withdrawal Limitations: Consent may be withdrawn at any time via DELETE /api/compare/session/{id}/consent. "
    "Withdrawal prevents future external AI requests and purges locally cached AI synthesis results. "
    "Pending requests are cancelled where technically possible. However, requests already transmitted over the network "
    "to the external provider cannot necessarily be recalled, and withdrawal does not guarantee deletion of data already received by the provider."
)

AI_WITHDRAWAL_LIMITATIONS_NOTICE = (
    "Consent Withdrawal Confirmation & Limitation Notice:\n"
    "1. Effect: User consent has been withdrawn. Future external AI requests for this session are blocked, and local AI synthesis cache has been flushed.\n"
    "2. In-Flight & Upstream Limitation: Pending local tasks are cancelled where technically possible. However, requests already transmitted over the network to the external AI provider cannot necessarily be recalled, and withdrawal does not guarantee deletion of data already transmitted to the external provider."
)


@compare_router.get(
    "/session/{session_id}/consent",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_consent_terms(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> ConsentResponse:
    """Pre-consent disclosure endpoint: returns terms disclosure, Google Standard Free Tier data-use notice, and withdrawal limitations. A GET request strictly NEVER grants consent."""
    _check_query_params_for_token(request)
    is_granted = session_store.is_consent_granted(session.session_id)
    now_str = datetime.now(timezone.utc).isoformat()
    msg = (
        "Consent is currently ACTIVE for external AI processing in this session."
        if is_granted
        else "Review the external AI processing terms and withdrawal limitations prior to providing affirmative consent. A GET request never grants consent."
    )
    return ConsentResponse(
        consent_granted=is_granted,
        message=msg,
        updated_at=now_str,
        terms_disclosure=AI_CONSENT_TERMS_DISCLOSURE,
        withdrawal_limitations=AI_WITHDRAWAL_LIMITATIONS_NOTICE,
        payload_hash=getattr(session, "approved_payload_hash", None),
    )


@compare_router.post(
    "/session/{session_id}/consent",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def grant_ai_consent(
    session_id: str,
    payload: ConsentRequest,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> ConsentResponse:
    """Records user agreement for external AI cloud processing for this session (Endpoint 7). Requires explicit affirmative acceptance ('consent_granted': true)."""
    _check_query_params_for_token(request)
    if not payload.consent_granted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Affirmative acceptance ('consent_granted': true) is strictly required to record consent. Missing or false values do not grant consent.",
        )
    session_store.grant_consent(session.session_id)
    if payload.payload_hash:
        session.approved_payload_hash = payload.payload_hash
    session_store.update_manifest(session)
    now_str = datetime.now(timezone.utc).isoformat()
    return ConsentResponse(
        consent_granted=True,
        message="Affirmative AI processing consent recorded for this session.",
        updated_at=now_str,
        terms_disclosure=AI_CONSENT_TERMS_DISCLOSURE,
        withdrawal_limitations=AI_WITHDRAWAL_LIMITATIONS_NOTICE,
        payload_hash=session.approved_payload_hash,
    )


@compare_router.delete(
    "/session/{session_id}/consent",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def withdraw_ai_consent(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> ConsentResponse:
    """Revokes AI processing consent, halts cloud requests, purges AI cache, reverts to Local Mode (Endpoint 8)."""
    _check_query_params_for_token(request)
    info = session_store.withdraw_consent_detailed(session.session_id)
    session.approved_payload_hash = None
    session_store.update_manifest(session)
    now_str = datetime.now(timezone.utc).isoformat()
    msg = (
        "AI processing consent withdrawn. Active request committed prior to withdrawal cannot necessarily be recalled."
        if info.get("potentially_transmitted")
        else "AI processing halted. Reverted to Local Mode."
    )
    return ConsentResponse(
        consent_granted=False,
        message=msg,
        updated_at=now_str,
        withdrawal_limitations=AI_WITHDRAWAL_LIMITATIONS_NOTICE,
        payload_hash=None,
    )


@compare_router.get(
    "/session/{session_id}/transmission-preview",
    response_model=TransmissionPreview,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_transmission_preview(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> TransmissionPreview:
    """Pre-transmission transparency endpoint (Endpoint 7.1). Returns exact sanitized payload preview and SHA-256 hash."""
    _check_query_params_for_token(request)
    docs = session_store.get_session_documents(session.session_id)
    if not docs or len(docs) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 documents must be uploaded to generate transmission preview.",
        )
    metadata_map = session_store.get_session_metadata(session.session_id)
    comp_report = session_store.get_session_compatibility(session.session_id)
    if not comp_report:
        comp_report = CompatibilityEngine.evaluate_session(metadata_map, session_id=session.session_id)
        session_store.save_session_compatibility(session.session_id, comp_report)

    stored_fvs, _, _ = session_store.get_session_financials(session.session_id)
    financial_values = stored_fvs or {}
    variances = session_store.get_session_calculations(session.session_id)

    if not financial_values:
        all_candidates: Dict[str, List[ValueCandidate]] = {}
        financial_values = {}
        all_conflicts: Dict[str, Dict[str, ConflictResolution]] = {}
        for comp_doc in docs:
            doc_id = comp_doc.doc_id
            meta = metadata_map.get(doc_id)
            if not meta:
                continue
            extraction = session_store.get_document_extraction(session.session_id, doc_id)
            if not extraction:
                extraction = DocumentExtractionResult(
                    doc_id=doc_id,
                    slot=comp_doc.slot,
                    file_format=comp_doc.file_format,
                    is_scanned=comp_doc.is_scanned,
                    extraction_status=comp_doc.extraction_status,
                )
            cands = FinancialExtractor.extract_candidates(comp_doc, extraction, meta)
            all_candidates[doc_id] = cands
            doc_fvs, doc_confs = ConflictArbitrator.arbitrate_document_metrics(doc_id, cands, meta)
            for m_key, fv in doc_fvs.items():
                financial_values.setdefault(m_key, {})[doc_id] = fv
            all_conflicts[doc_id] = doc_confs

        session_store.save_session_financials(
            session.session_id,
            financial_values=financial_values,
            candidates=all_candidates,
            conflicts=all_conflicts,
        )

    if not variances:
        doc_ids_ordered = order_documents_chronologically([d.doc_id for d in docs], metadata_map)
        variances = FinancialCalculator.compute_all_variances(
            financial_values=financial_values,
            doc_ids=doc_ids_ordered,
            compatibility_report=comp_report,
            metadata_map=metadata_map,
        )
        session_store.save_session_calculations(session.session_id, variances)

    preview = CompareSynthesisService.build_transmission_preview(
        session_id=session.session_id,
        documents=docs,
        metadata_map=metadata_map,
        compatibility=comp_report,
        financial_values=financial_values,
        variances=variances,
    )
    return preview


# ---------------------------------------------------------------------------
# Slice 4 & 5: Financial Processing, Metrics, Calculation & Synthesis Pipeline
# ---------------------------------------------------------------------------

@compare_router.post(
    "/session/{session_id}/process",
    response_model=ProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def process_comparison_session(
    session_id: str,
    request: Request,
    payload: Optional[ProcessPayload] = None,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> ProcessingStatusResponse:
    """Executes comparison pipeline: candidate extraction, arbitration, calculations, and synthesis (Endpoint 9)."""
    _check_query_params_for_token(request)

    # State transition: must be able to transition to PROCESSING
    if session.status != SessionStatus.PROCESSING:
        if session.can_transition_to(SessionStatus.PROCESSING):
            session.transition_to(SessionStatus.PROCESSING)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot process session currently in state '{session.status}'. Expected FILES_UPLOADED or METADATA_EXTRACTED.",
            )

    docs = session_store.get_session_documents(session.session_id)
    if len(docs) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 documents are required for comparative financial processing.",
        )

    metadata_map = session_store.get_session_metadata(session.session_id)
    comp_report = session_store.get_session_compatibility(session.session_id)
    if not comp_report:
        comp_report = CompatibilityEngine.evaluate_session(metadata_map, session_id=session.session_id)
        session_store.save_session_compatibility(session.session_id, comp_report)

    completed_stages: List[str] = [
        ProcessingStage.INITIALIZED.value,
        ProcessingStage.IDENTIFYING_METADATA.value,
        ProcessingStage.VALIDATING_COMPATIBILITY.value,
    ]

    all_candidates: Dict[str, List[ValueCandidate]] = {}
    financial_values: Dict[str, Dict[str, FinancialValue]] = {}
    all_conflicts: Dict[str, Dict[str, ConflictResolution]] = {}

    # Stage 1: EXTRACTING_FINANCIAL_DATA
    for comp_doc in docs:
        doc_id = comp_doc.doc_id
        meta = metadata_map.get(doc_id)
        if not meta:
            continue
        extraction = session_store.get_document_extraction(session.session_id, doc_id)
        if not extraction:
            extraction = DocumentExtractionResult(
                doc_id=doc_id,
                slot=comp_doc.slot,
                file_format=comp_doc.file_format,
                is_scanned=comp_doc.is_scanned,
                extraction_status=comp_doc.extraction_status,
            )

        cands = FinancialExtractor.extract_candidates(comp_doc, extraction, meta)
        all_candidates[doc_id] = cands

    completed_stages.append(ProcessingStage.EXTRACTING_FINANCIAL_DATA.value)

    # Stage 2: RESOLVING_CONFLICTS (8-factor priority rules per document)
    for comp_doc in docs:
        doc_id = comp_doc.doc_id
        meta = metadata_map.get(doc_id)
        if not meta:
            continue
        cands = all_candidates.get(doc_id, [])
        doc_fvs, doc_confs = ConflictArbitrator.arbitrate_document_metrics(doc_id, cands, meta)

        for m_key, fv in doc_fvs.items():
            financial_values.setdefault(m_key, {})[doc_id] = fv
        all_conflicts[doc_id] = doc_confs

    session_store.save_session_financials(
        session.session_id,
        financial_values=financial_values,
        candidates=all_candidates,
        conflicts=all_conflicts,
    )
    completed_stages.append(ProcessingStage.RESOLVING_CONFLICTS.value)

    # Stage 3: COMPUTING_CALCULATIONS (deterministic Decimal math & negative base handling)
    doc_ids_ordered = order_documents_chronologically([d.doc_id for d in docs], metadata_map)
    variances = FinancialCalculator.compute_all_variances(
        financial_values=financial_values,
        doc_ids=doc_ids_ordered,
        compatibility_report=comp_report,
        metadata_map=metadata_map,
    )
    session_store.save_session_calculations(session.session_id, variances)
    completed_stages.append(ProcessingStage.COMPUTING_CALCULATIONS.value)

    # Stage 4: SYNTHESIZING_REPORT (Evidence-grounded synthesis in Local or AI Mode)
    lang = payload.language if payload and payload.language else "English"
    req_hash = payload.payload_hash if payload else None
    expected_hash = req_hash or getattr(session, "approved_payload_hash", None)
    is_consent = session_store.is_consent_granted(session.session_id)
    comp_result = CompareSynthesisService.synthesize_comparison(
        session_id=session.session_id,
        documents=docs,
        metadata_map=metadata_map,
        compatibility=comp_report,
        financial_values=financial_values,
        variances=variances,
        consent_granted=is_consent,
        language=lang,
        expected_payload_hash=expected_hash,
    )
    session_store.save_session_comparison_result(session.session_id, comp_result)
    completed_stages.append(ProcessingStage.SYNTHESIZING_REPORT.value)

    # Pipeline Complete: Transition to COMPLETED
    if session.can_transition_to(SessionStatus.COMPLETED):
        session.transition_to(SessionStatus.COMPLETED)
    session_store.update_manifest(session)

    status_resp = ProcessingStatusResponse(
        session_id=session.session_id,
        current_stage=ProcessingStage.COMPLETED,
        completed_stages=completed_stages,
        stage_message=f"Financial extraction, conflict arbitration, calculations, and {comp_result.mode} synthesis completed.",
        is_cancelled=False,
        is_completed=True,
    )
    session_store.save_processing_status(session.session_id, status_resp)

    logger.info(f"Processed comparison pipeline for session {session.session_id} (mode={comp_result.mode}, lang={lang})")
    return status_resp


@compare_router.get(
    "/session/{session_id}/financials",
    response_model=SessionFinancialsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_session_financials(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> SessionFinancialsResponse:
    """Retrieve normalized financial values, candidate extractions, and conflict resolution logs."""
    _check_query_params_for_token(request)
    fvs, cands, confs = session_store.get_session_financials(session.session_id)
    return SessionFinancialsResponse(
        session_id=session.session_id,
        financial_values=fvs,
        all_candidates=cands,
        conflicts=confs,
    )


@compare_router.get(
    "/session/{session_id}/calculations",
    response_model=SessionCalculationsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_session_calculations(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> SessionCalculationsResponse:
    """Retrieve deterministic mathematical variances across document pairs."""
    _check_query_params_for_token(request)
    calcs = session_store.get_session_calculations(session.session_id)
    return SessionCalculationsResponse(
        session_id=session.session_id,
        variances=calcs,
    )


# ---------------------------------------------------------------------------
# Slice 6: Manual Financial Correction, Recalculation & Undo (Endpoints 10.1, 10.2, 10.3)
# ---------------------------------------------------------------------------

@compare_router.post(
    "/session/{session_id}/financials/correct",
    response_model=FinancialCorrectionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
        422: {"model": ErrorResponse, "description": "Validation Error"},
    },
)
async def correct_financial_metric(
    session_id: str,
    payload: FinancialCorrectionRequest,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> FinancialCorrectionResponse:
    """Manually correct an extracted financial figure and trigger deterministic recalculation (Endpoint 10.1)."""
    _check_query_params_for_token(request)

    m_key = payload.metric_key.strip()
    if not m_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric key cannot be empty.",
        )

    # Negative Total Assets is prohibited under Ind AS balance sheet reporting
    if m_key.upper() in ("TOTAL_ASSETS", "total_assets") and payload.corrected_amount < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total Assets cannot be negative under Ind AS reporting principles.",
        )

    try:
        updated_result, corr_record, recalculated = session_store.apply_financial_correction(
            session_id=session.session_id,
            doc_id=payload.doc_id.strip(),
            metric_key=m_key,
            corrected_amount=payload.corrected_amount,
            reason=payload.reason.strip() if payload.reason else None,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Failed to apply financial correction for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply financial correction: {exc}",
        )

    return FinancialCorrectionResponse(
        session_id=session.session_id,
        status="CORRECTED",
        correction=corr_record,
        comparison_result=updated_result,
        recalculated_metrics=recalculated,
    )


@compare_router.post(
    "/session/{session_id}/financials/undo",
    response_model=FinancialUndoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request / No Corrections Remaining"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def undo_latest_financial_correction(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> FinancialUndoResponse:
    """Undoes the latest manual financial correction in strict LIFO order (Endpoint 10.2)."""
    _check_query_params_for_token(request)

    try:
        updated_result, undone_record, remaining_count, recalculated = session_store.undo_latest_correction(
            session_id=session.session_id
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Failed to undo financial correction for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to undo financial correction: {exc}",
        )

    return FinancialUndoResponse(
        session_id=session.session_id,
        status="UNDONE",
        undone_correction=undone_record,
        remaining_corrections_count=remaining_count,
        comparison_result=updated_result,
        recalculated_metrics=recalculated,
    )


@compare_router.get(
    "/session/{session_id}/financials/corrections",
    response_model=SessionCorrectionsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_session_corrections_history(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> SessionCorrectionsResponse:
    """Retrieves session-scoped correction history in LIFO order (Endpoint 10.3)."""
    _check_query_params_for_token(request)
    corrections = session_store.get_session_corrections(session.session_id)
    return SessionCorrectionsResponse(
        session_id=session.session_id,
        corrections_count=len(corrections),
        corrections=corrections,
    )



@compare_router.get(
    "/session/{session_id}/status",
    response_model=ProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_session_processing_status(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> ProcessingStatusResponse:
    """Check asynchronous pipeline stage progression and health for recovery upon page refresh."""
    _check_query_params_for_token(request)
    stat = session_store.get_processing_status(session.session_id)
    if not stat:
        is_comp = session.status == SessionStatus.COMPLETED
        current_stg = ProcessingStage.COMPLETED if is_comp else ProcessingStage.INITIALIZED
        stat = ProcessingStatusResponse(
            session_id=session.session_id,
            current_stage=current_stg,
            completed_stages=[current_stg.value] if is_comp else [],
            stage_message=f"Session status is {session.status}",
            is_cancelled=session.status == SessionStatus.CANCELLED,
            is_completed=is_comp,
        )
    return stat


@compare_router.post(
    "/session/{session_id}/cancel",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def cancel_comparison_session(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> Dict[str, str]:
    """Cooperatively abort active comparison processing pipeline."""
    _check_query_params_for_token(request)
    session_store.cancel_session(session.session_id)
    return {
        "status": "CANCELLED",
        "message": "Pipeline halted successfully. Storage cleaned.",
    }


# ---------------------------------------------------------------------------
# Slice 5: Comparison Results & Comparative Grounded Chat (Endpoints 12 & 14)
# ---------------------------------------------------------------------------

@compare_router.get(
    "/session/{session_id}/results",
    response_model=ComparisonResult,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Results Not Found"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_comparison_results(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> ComparisonResult:
    """Delivers complete financial matrix, variances, and 8-section synthesis (Endpoint 12)."""
    _check_query_params_for_token(request)
    result = session_store.get_session_comparison_result(session.session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison results have not been generated yet. Please run POST /process first.",
        )
    return result


@compare_router.get(
    "/session/{session_id}/evidence/{doc_id}/page/{num}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"content": {"image/png": {}}, "description": "150 DPI Page Image Stream"},
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Page or Document Not Found"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_evidence_page_image(
    session_id: str,
    doc_id: str,
    num: int,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> Response:
    """Delivers rendered 150 DPI PNG of requested page for evidence viewer (Endpoint 13)."""
    _check_query_params_for_token(request)
    doc_id_clean = doc_id.strip().lower()
    docs = session_store.get_session_documents(session.session_id)
    target_doc = next((d for d in docs if d.doc_id.lower() == doc_id_clean), None)
    if not target_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document slot '{doc_id}' not found in active session.",
        )

    file_path = session_store.resolve_session_path(session.session_id, target_doc.storage_rel_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Underlying document filing not found in session storage.",
        )

    if target_doc.file_format in (SupportedFileFormat.PDF_DIGITAL, SupportedFileFormat.PDF_SCANNED):
        import pymupdf
        try:
            pdf_doc = pymupdf.open(str(file_path))
            try:
                total_pages = len(pdf_doc)
                if num < 1 or num > total_pages:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Page number {num} is out of bounds for document with {total_pages} pages.",
                    )
                page = pdf_doc.load_page(num - 1)
                pix = page.get_pixmap(dpi=150)
                png_bytes = pix.tobytes("png")
                return Response(content=png_bytes, media_type="image/png")
            finally:
                pdf_doc.close()
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Failed to render PDF page {num}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to render document page.",
            )

    elif target_doc.file_format in (SupportedFileFormat.IMAGE_PNG, SupportedFileFormat.IMAGE_JPG, SupportedFileFormat.IMAGE_JPEG):
        if num != 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image filings only contain page 1 (requested page {num}).",
            )
        media_type = "image/png" if target_doc.file_format == SupportedFileFormat.IMAGE_PNG else "image/jpeg"
        content_bytes = file_path.read_bytes()
        return Response(content=content_bytes, media_type=media_type)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Visual page rendering is only supported for PDF and image filings. Document format is {target_doc.file_format}.",
        )


@compare_router.get(
    "/session/{session_id}/evidence/{doc_id}/context",
    response_model=DocumentExtractionResult,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Extraction Not Found"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def get_evidence_context(
    session_id: str,
    doc_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> DocumentExtractionResult:
    """Delivers parsed structured extraction outcome (tables, sheets, text blocks) for evidence navigation (Endpoint 13.1)."""
    _check_query_params_for_token(request)
    doc_id_clean = doc_id.strip().lower()
    extraction = session_store.get_document_extraction(session.session_id, doc_id_clean)
    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction context for document '{doc_id}' not found.",
        )
    return extraction


class ComparisonChatPayload(BaseModel):
    message: str
    language: str = "English"


@compare_router.post(
    "/session/{session_id}/chat",
    response_model=ComparisonChatMessage,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def comparative_chat(
    session_id: str,
    payload: ComparisonChatPayload,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> ComparisonChatMessage:
    """Answers user comparative questions strictly grounded in comparison results (Endpoint 14)."""
    _check_query_params_for_token(request)
    result = session_store.get_session_comparison_result(session.session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please process comparison filings via POST /process before initiating comparative chat.",
        )

    is_consent = session_store.is_consent_granted(session.session_id)
    chat_msg = CompareSynthesisService.answer_comparison_question(
        session_id=session.session_id,
        user_message=payload.message,
        comparison_result=result,
        language=payload.language,
        consent_granted=is_consent,
    )

    # Save to session chat history
    history = session_store.get_session_chat_history(session.session_id)
    user_msg = ComparisonChatMessage(
        message_id=f"msg_user_{uuid.uuid4().hex[:8]}",
        role="user",
        content=payload.message,
    )
    history.extend([user_msg, chat_msg])
    session_store.save_session_chat_history(session.session_id, history)

    return chat_msg


# ---------------------------------------------------------------------------
# Slice 8: PDF Report Generation & 7-Tab Excel Workbook Export
# ---------------------------------------------------------------------------

@compare_router.post(
    "/session/{session_id}/export/pdf",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "High-fidelity PDF report"},
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def export_comparison_pdf(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> Response:
    """Compiles and streams an authoritative comparative PDF report using PyMuPDF (Endpoint 15)."""
    _check_query_params_for_token(request)
    result = session_store.get_session_comparison_result(session.session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please process comparison filings via POST /process before exporting reports.",
        )

    try:
        pdf_bytes = ExportPdfService.generate_comparison_pdf(result)
    except Exception as exc:
        logger.error(f"Failed to generate PDF export for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compile PDF export: {exc}",
        )

    # Persist in session temporary exports directory (bound to session lifecycle)
    session_dir = session_store.resolve_session_path(session.session_id)
    exports_dir = session_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    temp_file = exports_dir / f"comparison_{session.session_id[:8]}.pdf"
    try:
        temp_file.write_bytes(pdf_bytes)
    except Exception as exc:
        logger.warning(f"Could not cache temporary export file: {exc}")

    filename = f"BharatInvestorCopilot_Comparison_{session.session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@compare_router.post(
    "/session/{session_id}/export/xlsx",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
            "description": "Formatted 7-tab Excel workbook",
        },
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        410: {"model": ErrorResponse, "description": "Session Expired"},
    },
)
async def export_comparison_xlsx(
    session_id: str,
    request: Request,
    session: ComparisonSession = Depends(get_authenticated_session),
) -> Response:
    """Generates and streams a formatted 7-tab Excel workbook using openpyxl (Endpoint 16)."""
    _check_query_params_for_token(request)
    result = session_store.get_session_comparison_result(session.session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please process comparison filings via POST /process before exporting reports.",
        )

    try:
        xlsx_bytes = ExportExcelService.generate_comparison_workbook(result)
    except Exception as exc:
        logger.error(f"Failed to generate Excel export for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Excel workbook: {exc}",
        )

    # Persist in session temporary exports directory (bound to session lifecycle)
    session_dir = session_store.resolve_session_path(session.session_id)
    exports_dir = session_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    temp_file = exports_dir / f"comparison_{session.session_id[:8]}.xlsx"
    try:
        temp_file.write_bytes(xlsx_bytes)
    except Exception as exc:
        logger.warning(f"Could not cache temporary export file: {exc}")

    filename = f"BharatInvestorCopilot_Comparison_{session.session_id[:8]}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(xlsx_bytes)),
        },
    )

