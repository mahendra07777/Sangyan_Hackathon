"""In-memory comparison session registry and temporary filesystem storage lifecycle."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.security import (
    generate_capability_token,
    generate_internal_session_id,
    hash_capability_token,
    verify_capability_token,
)
from ..models.comparison import (
    CalculationResult,
    CompatibilityReport,
    ComparisonChatMessage,
    ComparisonDocument,
    ComparisonMode,
    ComparisonResult,
    ComparisonSession,
    ConflictResolution,
    DocumentExtractionResult,
    DocumentMetadata,
    FinancialCorrectionRecord,
    FinancialValue,
    ProcessingStatusResponse,
    SessionManifest,
    SessionStatus,
    ValueCandidate,
)
from .financial_calculator import FinancialCalculator
from .financial_normalizer import FOUR_PLACES, TWO_PLACES, FinancialNormalizer

logger = logging.getLogger(__name__)

# Configurable baselines (default: 30m idle, 4h max lifetime)
DEFAULT_IDLE_TIMEOUT_MINUTES = int(os.environ.get("COMPARE_IDLE_TIMEOUT_MINUTES", "30"))
DEFAULT_ABSOLUTE_LIFETIME_HOURS = int(os.environ.get("COMPARE_ABSOLUTE_LIFETIME_HOURS", "4"))
DEFAULT_MAX_DOCUMENTS = int(os.environ.get("COMPARE_MAX_DOCUMENTS", "5"))

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ComparisonSessionStore:
    """Thread-safe comparison session registry with ephemeral filesystem isolation."""

    def __init__(self, storage_root: Optional[Path] = None) -> None:
        if storage_root is not None:
            self._storage_root = storage_root.resolve()
        else:
            base_dir = Path(__file__).resolve().parents[2]
            env_root = os.environ.get("COMPARE_STORAGE_ROOT")
            if env_root:
                self._storage_root = Path(env_root).resolve()
            else:
                self._storage_root = (base_dir / "temporary_compare_storage").resolve()

        self._storage_root.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, ComparisonSession] = {}
        self._cancellation_events: Dict[str, threading.Event] = {}
        self._session_locks: Dict[str, threading.Lock] = {}
        self._active_dispatches: Dict[str, int] = {}
        self._committed_dispatch_tokens: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    def _get_session_lock(self, session_id: str) -> threading.Lock:
        s_id = session_id.lower()
        with self._lock:
            if s_id not in self._session_locks:
                self._session_locks[s_id] = threading.Lock()
            return self._session_locks[s_id]

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    def create_session(
        self,
        comparison_mode: ComparisonMode = ComparisonMode.QUICK_COMPARE,
        now: Optional[datetime] = None,
    ) -> Tuple[ComparisonSession, str]:
        """Create a new ephemeral session, allocate storage, write manifest, return session and raw token."""
        current_time = now or datetime.now(timezone.utc)
        session_id = generate_internal_session_id()
        raw_token = generate_capability_token()
        token_hash = hash_capability_token(raw_token)

        expires_at = current_time + timedelta(hours=DEFAULT_ABSOLUTE_LIFETIME_HOURS)
        idle_timeout_at = current_time + timedelta(minutes=DEFAULT_IDLE_TIMEOUT_MINUTES)
        if idle_timeout_at > expires_at:
            idle_timeout_at = expires_at

        session_dir_name = f"session_{session_id}"
        session_dir = (self._storage_root / session_dir_name).resolve()

        # Guard against symlinks or path traversal
        if not session_dir.is_relative_to(self._storage_root):
            raise ValueError("Session directory escapes storage root.")

        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "documents").mkdir(exist_ok=True)
        (session_dir / "extracted").mkdir(exist_ok=True)
        (session_dir / "evidence").mkdir(exist_ok=True)
        (session_dir / "exports").mkdir(exist_ok=True)

        session = ComparisonSession(
            session_id=session_id,
            token_hash=token_hash,
            comparison_mode=comparison_mode,
            status=SessionStatus.INITIALIZED,
            created_at=current_time,
            last_accessed_at=current_time,
            expires_at=expires_at,
            idle_timeout_at=idle_timeout_at,
            document_ids=[],
            consent_granted=False,
            storage_rel_path=session_dir_name,
        )

        self._write_manifest(session, current_time)

        with self._lock:
            self._sessions[session_id] = session
            self._cancellation_events[session_id] = threading.Event()

        logger.info(f"Initialized comparison session: {session_id} (mode={comparison_mode.value})")
        return session, raw_token

    def get_session(
        self,
        session_id: str,
        touch: bool = False,
        now: Optional[datetime] = None,
    ) -> Optional[ComparisonSession]:
        """Lookup session with lazy expiration verification and optional activity touch."""
        if not session_id or not _UUID_PATTERN.match(session_id):
            return None

        current_time = now or datetime.now(timezone.utc)

        with self._lock:
            session = self._sessions.get(session_id.lower())
            if session is None:
                return None

            # Verify expiration
            if self._is_expired(session, current_time):
                if session.status != SessionStatus.TERMINATED and session.status != SessionStatus.EXPIRED:
                    if session.can_transition_to(SessionStatus.EXPIRED):
                        session.transition_to(SessionStatus.EXPIRED)
                    else:
                        session.status = SessionStatus.EXPIRED
                    self._cleanup_session_storage(session.session_id)
                return session

            # Touch activity timestamp if requested and session is active
            if touch and session.status not in (SessionStatus.TERMINATED, SessionStatus.EXPIRED, SessionStatus.CANCELLED):
                session.last_accessed_at = current_time
                new_idle = current_time + timedelta(minutes=DEFAULT_IDLE_TIMEOUT_MINUTES)
                session.idle_timeout_at = min(new_idle, session.expires_at)
                self._write_manifest(session, current_time)

            return session

    def verify_and_get_session(
        self,
        session_id: str,
        supplied_token: str,
        touch: bool = True,
        now: Optional[datetime] = None,
    ) -> Tuple[Optional[ComparisonSession], Optional[str]]:
        """Verify token in constant time. Returns (session, error_code)."""
        session = self.get_session(session_id, touch=touch, now=now)
        if session is None:
            return None, "SESSION_NOT_FOUND"

        if not verify_capability_token(session.token_hash, supplied_token):
            return None, "INVALID_TOKEN"

        if session.status == SessionStatus.EXPIRED:
            return session, "SESSION_EXPIRED"

        if session.status == SessionStatus.TERMINATED:
            return session, "SESSION_TERMINATED"

        return session, None

    def terminate_session(self, session_id: str) -> bool:
        """Explicitly terminate session, purge storage, and retain memory tombstone."""
        if not session_id or not _UUID_PATTERN.match(session_id):
            return False

        with self._lock:
            session = self._sessions.get(session_id.lower())
            if session is None:
                # Still check and clean any leftover directory on disk
                self._cleanup_session_storage(session_id.lower())
                return False

            if session.can_transition_to(SessionStatus.TERMINATED):
                session.transition_to(SessionStatus.TERMINATED)
            else:
                session.status = SessionStatus.TERMINATED

            self._set_cancellation_event(session_id)
            self._cleanup_session_storage(session_id.lower())

        logger.info(f"Terminated comparison session: {session_id}")
        return True

    def cancel_session(self, session_id: str) -> bool:
        """Signal cooperative cancellation to running operations."""
        with self._lock:
            session = self._sessions.get(session_id.lower())
            if session is None:
                return False
            if session.can_transition_to(SessionStatus.CANCELLED):
                session.transition_to(SessionStatus.CANCELLED)
            else:
                session.status = SessionStatus.CANCELLED
            self._set_cancellation_event(session_id)
        return True

    def save_session_documents(self, session_id: str, documents: List[ComparisonDocument]) -> None:
        """Atomically persist parsed document records to session storage."""
        session_dir = self.resolve_session_path(session_id)
        docs_file = session_dir / "documents.json"
        tmp_file = session_dir / "documents.json.tmp"
        docs_data = [doc.model_dump() for doc in documents]
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(docs_data, f, indent=2, default=str)
        tmp_file.replace(docs_file)

    def get_session_documents(self, session_id: str) -> List[ComparisonDocument]:
        """Retrieve stored document records from session storage."""
        session_dir = self.resolve_session_path(session_id)
        docs_file = session_dir / "documents.json"
        if not docs_file.exists():
            return []
        try:
            with open(docs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [ComparisonDocument.model_validate(item) for item in data]
        except Exception as exc:
            logger.warning(f"Error reading documents for session {session_id}: {exc}")
            return []

    def get_document_extraction(self, session_id: str, doc_id: str) -> Optional[DocumentExtractionResult]:
        """Retrieve stored DocumentExtractionResult JSON for a document."""
        session_dir = self.resolve_session_path(session_id)
        json_path = session_dir / "extracted" / f"{doc_id}_extraction.json"
        if not json_path.exists():
            return None
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return DocumentExtractionResult.model_validate_json(f.read())
        except Exception as exc:
            logger.warning(f"Error reading extraction for {doc_id} in {session_id}: {exc}")
            return None

    def save_document_extraction(self, session_id: str, doc_id: str, extraction: DocumentExtractionResult) -> None:
        """Persist DocumentExtractionResult JSON for a document."""
        session_dir = self.resolve_session_path(session_id)
        extracted_dir = session_dir / "extracted"
        extracted_dir.mkdir(parents=True, exist_ok=True)
        json_path = extracted_dir / f"{doc_id}_extraction.json"
        tmp_json = extracted_dir / f"{doc_id}_extraction.json.tmp"
        with open(tmp_json, "w", encoding="utf-8") as f:
            f.write(extraction.model_dump_json(indent=2))
        tmp_json.replace(json_path)

    def save_session_metadata(self, session_id: str, metadata: Dict[str, DocumentMetadata]) -> None:
        """Atomically persist identified metadata to session storage."""
        session_dir = self.resolve_session_path(session_id)
        meta_file = session_dir / "metadata.json"
        tmp_file = session_dir / "metadata.json.tmp"
        data = {k: v.model_dump() for k, v in metadata.items()}
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp_file.replace(meta_file)

    def get_session_metadata(self, session_id: str) -> Dict[str, DocumentMetadata]:
        """Retrieve stored metadata from session storage."""
        session_dir = self.resolve_session_path(session_id)
        meta_file = session_dir / "metadata.json"
        if not meta_file.exists():
            return {}
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: DocumentMetadata.model_validate(v) for k, v in data.items()}
        except Exception as exc:
            logger.warning(f"Error reading metadata for session {session_id}: {exc}")
            return {}

    def save_session_compatibility(self, session_id: str, report: CompatibilityReport) -> None:
        """Atomically persist compatibility evaluation to session storage."""
        session_dir = self.resolve_session_path(session_id)
        comp_file = session_dir / "compatibility.json"
        tmp_file = session_dir / "compatibility.json.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        tmp_file.replace(comp_file)

    def get_session_compatibility(self, session_id: str) -> Optional[CompatibilityReport]:
        """Retrieve stored compatibility report from session storage."""
        session_dir = self.resolve_session_path(session_id)
        comp_file = session_dir / "compatibility.json"
        if not comp_file.exists():
            return None
        try:
            with open(comp_file, "r", encoding="utf-8") as f:
                return CompatibilityReport.model_validate_json(f.read())
        except Exception as exc:
            logger.warning(f"Error reading compatibility for session {session_id}: {exc}")
            return None

    def save_session_financials(
        self,
        session_id: str,
        financial_values: Dict[str, Dict[str, FinancialValue]],
        candidates: Dict[str, List[ValueCandidate]],
        conflicts: Dict[str, Dict[str, ConflictResolution]],
    ) -> None:
        """Atomically persist extracted financial metrics, candidates, and conflict resolutions."""
        session_dir = self.resolve_session_path(session_id)
        extracted_dir = session_dir / "extracted"
        evidence_dir = session_dir / "evidence"
        extracted_dir.mkdir(exist_ok=True)
        evidence_dir.mkdir(exist_ok=True)

        # 1. Financial values (metric_key -> doc_id -> FinancialValue)
        fv_file = extracted_dir / "financial_values.json"
        fv_tmp = extracted_dir / "financial_values.json.tmp"
        fv_data = {
            m_key: {d_id: fv.model_dump(mode="json") for d_id, fv in d_map.items()}
            for m_key, d_map in financial_values.items()
        }
        with open(fv_tmp, "w", encoding="utf-8") as f:
            json.dump(fv_data, f, indent=2)
        fv_tmp.replace(fv_file)

        # 2. Metric candidates (doc_id -> List[ValueCandidate])
        cand_file = extracted_dir / "candidates.json"
        cand_tmp = extracted_dir / "candidates.json.tmp"
        cand_data = {
            d_id: [c.model_dump(mode="json") for c in c_list]
            for d_id, c_list in candidates.items()
        }
        with open(cand_tmp, "w", encoding="utf-8") as f:
            json.dump(cand_data, f, indent=2)
        cand_tmp.replace(cand_file)

        # 3. Conflict resolutions (doc_id -> metric_key -> ConflictResolution)
        conf_file = evidence_dir / "conflicts.json"
        conf_tmp = evidence_dir / "conflicts.json.tmp"
        conf_data = {
            d_id: {m_key: cr.model_dump(mode="json") for m_key, cr in c_map.items()}
            for d_id, c_map in conflicts.items()
        }
        with open(conf_tmp, "w", encoding="utf-8") as f:
            json.dump(conf_data, f, indent=2)
        conf_tmp.replace(conf_file)

    def get_session_financials(
        self,
        session_id: str,
    ) -> Tuple[
        Dict[str, Dict[str, FinancialValue]],
        Dict[str, List[ValueCandidate]],
        Dict[str, Dict[str, ConflictResolution]],
    ]:
        """Retrieve stored financial values, candidates, and conflicts from session storage."""
        session_dir = self.resolve_session_path(session_id)
        extracted_dir = session_dir / "extracted"
        evidence_dir = session_dir / "evidence"

        financial_values: Dict[str, Dict[str, FinancialValue]] = {}
        fv_file = extracted_dir / "financial_values.json"
        if fv_file.exists():
            try:
                with open(fv_file, "r", encoding="utf-8") as f:
                    raw_fv = json.load(f)
                for m_key, d_map in raw_fv.items():
                    financial_values[m_key] = {
                        d_id: FinancialValue.model_validate(val)
                        for d_id, val in d_map.items()
                    }
            except Exception as exc:
                logger.warning(f"Error reading financial values for session {session_id}: {exc}")

        candidates: Dict[str, List[ValueCandidate]] = {}
        cand_file = extracted_dir / "candidates.json"
        if cand_file.exists():
            try:
                with open(cand_file, "r", encoding="utf-8") as f:
                    raw_cand = json.load(f)
                for d_id, c_list in raw_cand.items():
                    candidates[d_id] = [ValueCandidate.model_validate(c) for c in c_list]
            except Exception as exc:
                logger.warning(f"Error reading candidates for session {session_id}: {exc}")

        conflicts: Dict[str, Dict[str, ConflictResolution]] = {}
        conf_file = evidence_dir / "conflicts.json"
        if conf_file.exists():
            try:
                with open(conf_file, "r", encoding="utf-8") as f:
                    raw_conf = json.load(f)
                for d_id, c_map in raw_conf.items():
                    conflicts[d_id] = {
                        m_key: ConflictResolution.model_validate(c)
                        for m_key, c in c_map.items()
                    }
            except Exception as exc:
                logger.warning(f"Error reading conflicts for session {session_id}: {exc}")

        return financial_values, candidates, conflicts

    def save_session_calculations(self, session_id: str, calculations: List[CalculationResult]) -> None:
        """Atomically persist deterministic calculation results to session storage."""
        session_dir = self.resolve_session_path(session_id)
        extracted_dir = session_dir / "extracted"
        extracted_dir.mkdir(exist_ok=True)
        calc_file = extracted_dir / "calculations.json"
        calc_tmp = extracted_dir / "calculations.json.tmp"
        calc_data = [c.model_dump(mode="json") for c in calculations]
        with open(calc_tmp, "w", encoding="utf-8") as f:
            json.dump(calc_data, f, indent=2)
        calc_tmp.replace(calc_file)

    def get_session_calculations(self, session_id: str) -> List[CalculationResult]:
        """Retrieve stored calculation results from session storage."""
        session_dir = self.resolve_session_path(session_id)
        calc_file = session_dir / "extracted" / "calculations.json"
        if not calc_file.exists():
            return []
        try:
            with open(calc_file, "r", encoding="utf-8") as f:
                raw_calcs = json.load(f)
            return [CalculationResult.model_validate(c) for c in raw_calcs]
        except Exception as exc:
            logger.warning(f"Error reading calculations for session {session_id}: {exc}")
            return []

    def save_processing_status(self, session_id: str, status_payload: ProcessingStatusResponse) -> None:
        """Persist current asynchronous pipeline progression state."""
        session_dir = self.resolve_session_path(session_id)
        stat_file = session_dir / "processing_status.json"
        stat_tmp = session_dir / "processing_status.json.tmp"
        with open(stat_tmp, "w", encoding="utf-8") as f:
            f.write(status_payload.model_dump_json(indent=2))
        stat_tmp.replace(stat_file)

    def get_processing_status(self, session_id: str) -> Optional[ProcessingStatusResponse]:
        """Retrieve pipeline progression state for frontend polling or page refresh recovery."""
        session_dir = self.resolve_session_path(session_id)
        stat_file = session_dir / "processing_status.json"
        if not stat_file.exists():
            return None
        try:
            with open(stat_file, "r", encoding="utf-8") as f:
                return ProcessingStatusResponse.model_validate_json(f.read())
        except Exception as exc:
            logger.warning(f"Error reading processing status for session {session_id}: {exc}")
            return None

    def grant_consent(self, session_id: str) -> bool:
        """Explicitly record user consent for external AI cloud processing for this session under session lock."""
        s_id = session_id.lower()
        session_lock = self._get_session_lock(s_id)
        with session_lock:
            with self._lock:
                session = self._sessions.get(s_id)
                if session is None or session.status in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
                    return False
                session.consent_granted = True
                # Reset cancellation event for newly authorized operations
                self._cancellation_events[s_id] = threading.Event()
                self._write_manifest(session, datetime.now(timezone.utc))
        logger.info(f"Granted AI processing consent for session {session_id}")
        return True

    def commit_external_dispatch(
        self, session_id: str
    ) -> Tuple[bool, str, Optional[str], Optional[threading.Event]]:
        """
        Atomic Dispatch Linearization Point.
        Coordinates through per-session synchronization.
        Validates session status and affirmative consent atomically.
        Commits dispatch initiation, increments active dispatch counter, and releases lock immediately.
        """
        s_id = session_id.lower()
        session_lock = self._get_session_lock(s_id)
        with session_lock:
            with self._lock:
                session = self._sessions.get(s_id)
                cancel_ev = self._cancellation_events.get(s_id)
                # Standalone test/service invocation without registered session
                if session is None:
                    if cancel_ev and cancel_ev.is_set():
                        return False, "CONSENT_WITHDRAWN", None, None
                    dispatch_token = f"disp_{uuid.uuid4().hex[:12]}"
                    if s_id not in self._active_dispatches:
                        self._active_dispatches[s_id] = 0
                    self._active_dispatches[s_id] += 1
                    if s_id not in self._committed_dispatch_tokens:
                        self._committed_dispatch_tokens[s_id] = set()
                    self._committed_dispatch_tokens[s_id].add(dispatch_token)
                    return True, "COMMITTED", dispatch_token, cancel_ev

                if session.status in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
                    return False, "SESSION_INACTIVE", None, None
                if not session.consent_granted:
                    return False, "CONSENT_NOT_GRANTED", None, None
                if cancel_ev and cancel_ev.is_set():
                    return False, "CONSENT_WITHDRAWN", None, None

                # Commit dispatch
                dispatch_token = f"disp_{uuid.uuid4().hex[:12]}"
                if s_id not in self._active_dispatches:
                    self._active_dispatches[s_id] = 0
                self._active_dispatches[s_id] += 1
                if s_id not in self._committed_dispatch_tokens:
                    self._committed_dispatch_tokens[s_id] = set()
                self._committed_dispatch_tokens[s_id].add(dispatch_token)

                logger.info(f"Committed external AI dispatch {dispatch_token} for session {session_id}")
                return True, "COMMITTED", dispatch_token, cancel_ev

    def complete_external_dispatch(
        self, session_id: str, dispatch_token: Optional[str] = None
    ) -> None:
        """
        Safely unregister committed dispatch upon completion or exception.
        Guaranteed to release dispatch counters and tokens under session lock.
        """
        s_id = session_id.lower()
        session_lock = self._get_session_lock(s_id)
        with session_lock:
            with self._lock:
                if s_id in self._committed_dispatch_tokens and dispatch_token:
                    self._committed_dispatch_tokens[s_id].discard(dispatch_token)
                if s_id in self._active_dispatches and self._active_dispatches[s_id] > 0:
                    self._active_dispatches[s_id] -= 1
        logger.info(f"Completed external dispatch {dispatch_token} for session {session_id}")

    def withdraw_consent_detailed(self, session_id: str) -> Dict[str, Any]:
        """
        Atomic Consent Withdrawal with Detailed Dispatch Accounting.
        Under the per-session lock:
        1. Sets session.consent_granted = False.
        2. Cooperatively signals cancellation to in-flight dispatch.
        3. Detects active committed dispatches.
        4. Purges on-disk AI caches and AI chat history responses.
        Idempotent and deadlock-free across repeated invocations.
        """
        s_id = session_id.lower()
        session_lock = self._get_session_lock(s_id)
        with session_lock:
            with self._lock:
                session = self._sessions.get(s_id)
                self._set_cancellation_event(s_id)
                active_count = self._active_dispatches.get(s_id, 0)
                potentially_transmitted = active_count > 0

                if session is not None and session.status not in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
                    session.consent_granted = False
                    self._write_manifest(session, datetime.now(timezone.utc))

        # Purge any cached AI-generated summary from session storage
        try:
            session_dir = self.resolve_session_path(session_id)
            ai_summary_file = session_dir / "comparison_result_ai.json"
            if ai_summary_file.exists():
                ai_summary_file.unlink(missing_ok=True)
            res_file = session_dir / "comparison_result.json"
            if res_file.exists():
                try:
                    with open(res_file, "r", encoding="utf-8") as rf:
                        cr_data = json.load(rf)
                    if cr_data.get("mode") in ("AI_ASSISTED", "LOCAL_MODE_FALLBACK"):
                        res_file.unlink(missing_ok=True)
                except Exception:
                    pass
            # Purge AI responses from chat_history.json to ensure no cached AI output persists
            chat_file = session_dir / "chat_history.json"
            if chat_file.exists():
                try:
                    with open(chat_file, "r", encoding="utf-8") as cf:
                        chat_data = json.load(cf)
                    filtered_chat = [msg for msg in chat_data if msg.get("role") != "assistant"]
                    with open(chat_file, "w", encoding="utf-8") as cf:
                        json.dump(filtered_chat, cf, indent=2)
                except Exception:
                    chat_file.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning(f"Error purging AI cache upon consent revocation for {session_id}: {exc}")

        logger.info(
            f"Withdrew AI processing consent for session {session_id}. "
            f"Active committed dispatches: {active_count} (potentially_transmitted={potentially_transmitted})."
        )
        return {
            "success": True,
            "active_dispatches_at_withdrawal": active_count,
            "potentially_transmitted": potentially_transmitted,
        }

    def withdraw_consent(self, session_id: str) -> bool:
        """Revoke user consent, cancel running jobs, revert to Local Mode. Backward-compatible wrapper."""
        info = self.withdraw_consent_detailed(session_id)
        return bool(info.get("success", False))

    def is_consent_granted(self, session_id: str) -> bool:
        """Check whether user has actively granted AI processing consent for this specific session."""
        with self._lock:
            session = self._sessions.get(session_id.lower())
            if session is None or session.status in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
                return False
            return bool(session.consent_granted)

    def save_session_comparison_result(self, session_id: str, result: ComparisonResult) -> None:
        """Atomically persist final comparison result (Local Mode or AI-Assisted)."""
        session_dir = self.resolve_session_path(session_id)
        res_file = session_dir / "comparison_result.json"
        res_tmp = session_dir / "comparison_result.json.tmp"
        with open(res_tmp, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        res_tmp.replace(res_file)

    def get_session_comparison_result(self, session_id: str) -> Optional[ComparisonResult]:
        """Retrieve stored comparison result from session storage."""
        session_dir = self.resolve_session_path(session_id)
        res_file = session_dir / "comparison_result.json"
        if not res_file.exists():
            return None
        try:
            with open(res_file, "r", encoding="utf-8") as f:
                return ComparisonResult.model_validate_json(f.read())
        except Exception as exc:
            logger.warning(f"Error reading comparison result for session {session_id}: {exc}")
            return None

    def get_session_corrections(self, session_id: str) -> List[FinancialCorrectionRecord]:
        """Retrieve active correction journal (LIFO order) from session storage."""
        session_dir = self.resolve_session_path(session_id)
        corr_file = session_dir / "extracted" / "corrections.json"
        if not corr_file.exists():
            return []
        try:
            with open(corr_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [FinancialCorrectionRecord.model_validate(c) for c in data]
        except Exception as exc:
            logger.warning(f"Error reading corrections for session {session_id}: {exc}")
            return []

    def save_session_corrections(
        self, session_id: str, corrections: List[FinancialCorrectionRecord]
    ) -> None:
        """Atomically persist correction journal to session storage."""
        session_dir = self.resolve_session_path(session_id)
        extracted_dir = session_dir / "extracted"
        extracted_dir.mkdir(exist_ok=True)
        corr_file = extracted_dir / "corrections.json"
        corr_tmp = extracted_dir / "corrections.json.tmp"
        data = [c.model_dump(mode="json") for c in corrections]
        with open(corr_tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        corr_tmp.replace(corr_file)

    def apply_financial_correction(
        self,
        session_id: str,
        doc_id: str,
        metric_key: str,
        corrected_amount: Decimal,
        reason: Optional[str] = None,
    ) -> Tuple[ComparisonResult, FinancialCorrectionRecord, List[str]]:
        """
        Atomically applies user correction to a financial metric:
        1. Validates metric and document exist within session.
        2. Preserves original extracted value and previous state.
        3. Appends journal record to corrections.json (LIFO stack).
        4. Updates target FinancialValue (amount, is_user_corrected=True, fact_classification='USER_ENTERED').
        5. Re-runs deterministic FinancialCalculator.compute_all_variances.
        6. Updates ComparisonResult and regenerates narrative observations cleanly.
        7. Atomically commits all changes under session lock.
        """
        s_id = session_id.lower()
        session_lock = self._get_session_lock(s_id)
        with session_lock:
            # 1. Validate session
            session = self.get_session(s_id, touch=True)
            if not session or session.status in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
                raise ValueError("Session is expired or inactive.")

            docs = self.get_session_documents(s_id)
            target_doc = next((d for d in docs if d.doc_id == doc_id), None)
            if not target_doc:
                raise ValueError(f"Document '{doc_id}' not found in session '{session_id}'.")

            # 2. Load current data
            financial_values, candidates, conflicts = self.get_session_financials(s_id)
            comp_result = self.get_session_comparison_result(s_id)
            if not comp_result:
                raise ValueError("Comparison results must be generated before applying corrections.")

            corrections = self.get_session_corrections(s_id)
            meta_map = self.get_session_metadata(s_id)
            meta = meta_map.get(doc_id)

            # Metric normalization & units
            m_key_upper = metric_key.upper()
            m_key_canonical = metric_key
            if metric_key not in financial_values and m_key_upper in financial_values:
                m_key_canonical = m_key_upper

            if m_key_canonical.upper() in ("TOTAL_ASSETS", "TOTALASSETS") and corrected_amount < 0:
                raise ValueError("Total Assets cannot be negative under Ind AS reporting principles.")

            doc_map = financial_values.setdefault(m_key_canonical, {})
            target_fv = doc_map.get(doc_id)

            unit = target_fv.unit if target_fv else ("INR" if m_key_canonical in ("EPS", "basic_eps") else "INR_CRORE")
            currency = target_fv.currency if target_fv else (meta.currency if meta else "INR")

            # Quantize corrected amount
            quantized_num = corrected_amount.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
            disp_amount = FinancialNormalizer.format_display_amount(quantized_num, unit)

            # Determine original extracted amount
            original_extracted = (
                target_fv.original_amount
                if (target_fv and target_fv.is_user_corrected and target_fv.original_amount is not None)
                else (target_fv.amount if target_fv else None)
            )

            # 3. Create Correction Record
            corr_id = f"corr_{uuid.uuid4().hex[:12]}"
            corr_record = FinancialCorrectionRecord(
                correction_id=corr_id,
                session_id=s_id,
                doc_id=doc_id,
                metric_key=m_key_canonical,
                previous_effective_amount=target_fv.amount if target_fv else None,
                original_extracted_amount=original_extracted,
                previous_status=target_fv.status if target_fv else "NOT_DISCLOSED",
                previous_fact_classification=target_fv.fact_classification if target_fv else "DOCUMENT_FACT",
                previous_display_amount=target_fv.display_amount if target_fv else "Not Disclosed",
                new_user_entered_amount=quantized_num,
                corrected_display_amount=disp_amount,
                reason=reason,
                timestamp=datetime.now(timezone.utc),
                unit=unit,
                currency=currency,
            )

            # 4. Update FinancialValue
            if not target_fv:
                target_fv = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key_canonical,
                    label=m_key_canonical.replace("_", " ").title(),
                    amount=quantized_num,
                    reported_amount=None,
                    display_amount=disp_amount,
                    unit=unit,
                    currency=currency,
                    status="REPORTED",
                    reporting_scope=meta.reporting_scope if meta else "CONSOLIDATED",
                    evidence=None,
                    fact_classification="USER_ENTERED",
                    is_user_corrected=True,
                    original_amount=original_extracted,
                    user_entered_amount=quantized_num,
                    correction_reason=reason,
                    correction_timestamp=corr_record.timestamp,
                )
            else:
                if not target_fv.is_user_corrected:
                    target_fv.original_amount = target_fv.amount
                target_fv.amount = quantized_num
                target_fv.user_entered_amount = quantized_num
                target_fv.display_amount = disp_amount
                target_fv.is_user_corrected = True
                target_fv.fact_classification = "USER_ENTERED"
                target_fv.status = "REPORTED"
                target_fv.correction_reason = reason
                target_fv.correction_timestamp = corr_record.timestamp

            doc_map[doc_id] = target_fv

            # 5. Deterministic Recalculation
            doc_ids_ordered = [d.doc_id for d in docs]
            comp_report = self.get_session_compatibility(s_id)
            recomputed_variances = FinancialCalculator.compute_all_variances(
                financial_values=financial_values,
                doc_ids=doc_ids_ordered,
                compatibility_report=comp_report,
            )

            # 6. Update ComparisonResult
            comp_result.financial_values = financial_values
            comp_result.variances = recomputed_variances

            # Invalidate/neutralize stale narrative claims if previously generated
            if comp_result.executive_summary:
                cls_es = comp_result.executive_summary
                cls_es.fact_classification = "EDUCATIONAL_EXPLANATION"
                new_pos = []
                new_neg = []
                new_neutral = []
                for v in recomputed_variances:
                    if v.status == "CALCULATED" and v.absolute_variance is not None:
                        diff_str = f"{v.display_absolute_variance} ({v.display_percentage_change})" if v.display_percentage_change else f"{v.display_absolute_variance}"
                        if v.metric_key in ("REVENUE", "TOTAL_INCOME", "EBITDA", "PAT", "PBT", "OPERATING_CASH_FLOW", "EPS"):
                            if v.absolute_variance > 0:
                                new_pos.append(f"{v.label} increased by {diff_str}.")
                            elif v.absolute_variance < 0:
                                new_neg.append(f"{v.label} contracted by {diff_str}.")
                            else:
                                new_neutral.append(f"{v.label} remained flat at {diff_str}.")
                        elif v.metric_key == "TOTAL_DEBT":
                            if v.absolute_variance < 0:
                                new_pos.append(f"Total Debt decreased by {v.display_absolute_variance} (deleveraging).")
                            elif v.absolute_variance > 0:
                                new_neg.append(f"Total Debt increased by {v.display_absolute_variance} (higher leverage).")
                cls_es.core_positive_changes = new_pos
                cls_es.core_negative_changes = new_neg
                cls_es.neutral_observations = new_neutral
                cls_es.overview_story = (
                    f"Educational comparison of {len(docs)} documents. "
                    "Reflects verified document data and user-entered adjustments. "
                    "Calculations are computed deterministically using standard Indian accounting conventions (INR Crore)."
                )

            # 7. Atomic Write Strategy with transactional rollback under session lock
            session_dir = self.resolve_session_path(s_id)
            extracted_dir = session_dir / "extracted"
            corr_file = extracted_dir / "corrections.json"
            fv_file = extracted_dir / "financial_values.json"
            calc_file = extracted_dir / "calculations.json"
            res_file = session_dir / "comparison_result.json"

            backup_corr = corr_file.read_bytes() if corr_file.exists() else None
            backup_fv = fv_file.read_bytes() if fv_file.exists() else None
            backup_calc = calc_file.read_bytes() if calc_file.exists() else None
            backup_res = res_file.read_bytes() if res_file.exists() else None

            corrections.append(corr_record)
            try:
                self.save_session_corrections(s_id, corrections)
                self.save_session_financials(s_id, financial_values, candidates, conflicts)
                self.save_session_calculations(s_id, recomputed_variances)
                self.save_session_comparison_result(s_id, comp_result)
            except Exception:
                if backup_corr is not None:
                    corr_file.write_bytes(backup_corr)
                elif corr_file.exists():
                    corr_file.unlink(missing_ok=True)
                if backup_fv is not None:
                    fv_file.write_bytes(backup_fv)
                elif fv_file.exists():
                    fv_file.unlink(missing_ok=True)
                if backup_calc is not None:
                    calc_file.write_bytes(backup_calc)
                elif calc_file.exists():
                    calc_file.unlink(missing_ok=True)
                if backup_res is not None:
                    res_file.write_bytes(backup_res)
                elif res_file.exists():
                    res_file.unlink(missing_ok=True)
                raise

            logger.info(
                f"Applied financial correction {corr_id} for session {session_id}: "
                f"doc={doc_id}, metric={m_key_canonical}, amount={quantized_num}"
            )
            return comp_result, corr_record, [m_key_canonical]

    def undo_latest_correction(
        self, session_id: str
    ) -> Tuple[ComparisonResult, FinancialCorrectionRecord, int, List[str]]:
        """
        Atomically undoes the latest manual financial correction in LIFO order:
        1. Pops the latest record from corrections.json.
        2. Restores target FinancialValue to original state (or previous correction if edited multiple times).
        3. Re-runs deterministic FinancialCalculator.compute_all_variances.
        4. Updates and atomically saves ComparisonResult, financial_values, calculations, and corrections.
        """
        s_id = session_id.lower()
        session_lock = self._get_session_lock(s_id)
        with session_lock:
            session = self.get_session(s_id, touch=True)
            if not session or session.status in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
                raise ValueError("Session is expired or inactive.")

            corrections = self.get_session_corrections(s_id)
            if not corrections:
                raise ValueError("No manual corrections remain to undo.")

            # Pop latest correction (LIFO)
            latest_corr = corrections.pop()
            doc_id = latest_corr.doc_id
            m_key = latest_corr.metric_key

            # Load current state
            financial_values, candidates, conflicts = self.get_session_financials(s_id)
            comp_result = self.get_session_comparison_result(s_id)
            if not comp_result:
                raise ValueError("Comparison results must be available to undo correction.")

            docs = self.get_session_documents(s_id)
            doc_map = financial_values.get(m_key, {})
            target_fv = doc_map.get(doc_id)

            if target_fv:
                # Check if there is an earlier correction for the same (doc_id, metric_key)
                earlier_corr = next(
                    (c for c in reversed(corrections) if c.doc_id == doc_id and c.metric_key == m_key),
                    None,
                )
                if earlier_corr:
                    target_fv.amount = earlier_corr.new_user_entered_amount
                    target_fv.user_entered_amount = earlier_corr.new_user_entered_amount
                    target_fv.display_amount = earlier_corr.corrected_display_amount
                    target_fv.is_user_corrected = True
                    target_fv.fact_classification = "USER_ENTERED"
                    target_fv.correction_reason = earlier_corr.reason
                    target_fv.correction_timestamp = earlier_corr.timestamp
                else:
                    target_fv.amount = latest_corr.original_extracted_amount
                    target_fv.user_entered_amount = None
                    target_fv.original_amount = None
                    target_fv.is_user_corrected = False
                    target_fv.fact_classification = latest_corr.previous_fact_classification or "DOCUMENT_FACT"
                    target_fv.status = latest_corr.previous_status or ("REPORTED" if target_fv.amount is not None else "NOT_DISCLOSED")
                    target_fv.display_amount = (
                        latest_corr.previous_display_amount
                        or FinancialNormalizer.format_display_amount(target_fv.amount, target_fv.unit)
                    )
                    target_fv.correction_reason = None
                    target_fv.correction_timestamp = None

            # Recompute variances
            doc_ids_ordered = [d.doc_id for d in docs]
            comp_report = self.get_session_compatibility(s_id)
            recomputed_variances = FinancialCalculator.compute_all_variances(
                financial_values=financial_values,
                doc_ids=doc_ids_ordered,
                compatibility_report=comp_report,
            )

            # Update comparison result
            comp_result.financial_values = financial_values
            comp_result.variances = recomputed_variances

            # Refresh summary narrative if present
            if comp_result.executive_summary:
                cls_es = comp_result.executive_summary
                cls_es.fact_classification = "EDUCATIONAL_EXPLANATION"
                new_pos = []
                new_neg = []
                new_neutral = []
                for v in recomputed_variances:
                    if v.status == "CALCULATED" and v.absolute_variance is not None:
                        diff_str = f"{v.display_absolute_variance} ({v.display_percentage_change})" if v.display_percentage_change else f"{v.display_absolute_variance}"
                        if v.metric_key in ("REVENUE", "TOTAL_INCOME", "EBITDA", "PAT", "PBT", "OPERATING_CASH_FLOW", "EPS"):
                            if v.absolute_variance > 0:
                                new_pos.append(f"{v.label} increased by {diff_str}.")
                            elif v.absolute_variance < 0:
                                new_neg.append(f"{v.label} contracted by {diff_str}.")
                            else:
                                new_neutral.append(f"{v.label} remained flat at {diff_str}.")
                        elif v.metric_key == "TOTAL_DEBT":
                            if v.absolute_variance < 0:
                                new_pos.append(f"Total Debt decreased by {v.display_absolute_variance} (deleveraging).")
                            elif v.absolute_variance > 0:
                                new_neg.append(f"Total Debt increased by {v.display_absolute_variance} (higher leverage).")
                cls_es.core_positive_changes = new_pos
                cls_es.core_negative_changes = new_neg
                cls_es.neutral_observations = new_neutral

            # Atomic commit with transactional rollback under session lock
            session_dir = self.resolve_session_path(s_id)
            extracted_dir = session_dir / "extracted"
            corr_file = extracted_dir / "corrections.json"
            fv_file = extracted_dir / "financial_values.json"
            calc_file = extracted_dir / "calculations.json"
            res_file = session_dir / "comparison_result.json"

            backup_corr = corr_file.read_bytes() if corr_file.exists() else None
            backup_fv = fv_file.read_bytes() if fv_file.exists() else None
            backup_calc = calc_file.read_bytes() if calc_file.exists() else None
            backup_res = res_file.read_bytes() if res_file.exists() else None

            try:
                self.save_session_corrections(s_id, corrections)
                self.save_session_financials(s_id, financial_values, candidates, conflicts)
                self.save_session_calculations(s_id, recomputed_variances)
                self.save_session_comparison_result(s_id, comp_result)
            except Exception:
                if backup_corr is not None:
                    corr_file.write_bytes(backup_corr)
                elif corr_file.exists():
                    corr_file.unlink(missing_ok=True)
                if backup_fv is not None:
                    fv_file.write_bytes(backup_fv)
                elif fv_file.exists():
                    fv_file.unlink(missing_ok=True)
                if backup_calc is not None:
                    calc_file.write_bytes(backup_calc)
                elif calc_file.exists():
                    calc_file.unlink(missing_ok=True)
                if backup_res is not None:
                    res_file.write_bytes(backup_res)
                elif res_file.exists():
                    res_file.unlink(missing_ok=True)
                raise

            logger.info(
                f"Undid financial correction {latest_corr.correction_id} for session {session_id}: "
                f"doc={doc_id}, metric={m_key}. Remaining: {len(corrections)}"
            )
            return comp_result, latest_corr, len(corrections), [m_key]


    def save_session_chat_history(self, session_id: str, history: List[ComparisonChatMessage]) -> None:
        """Atomically persist grounded comparative chat history."""
        session_dir = self.resolve_session_path(session_id)
        chat_file = session_dir / "chat_history.json"
        chat_tmp = session_dir / "chat_history.json.tmp"
        data = [msg.model_dump(mode="json") for msg in history]
        with open(chat_tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        chat_tmp.replace(chat_file)

    def get_session_chat_history(self, session_id: str) -> List[ComparisonChatMessage]:
        """Retrieve grounded comparative chat history."""
        session_dir = self.resolve_session_path(session_id)
        chat_file = session_dir / "chat_history.json"
        if not chat_file.exists():
            return []
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            return [ComparisonChatMessage.model_validate(msg) for msg in raw_list]
        except Exception as exc:
            logger.warning(f"Error reading chat history for session {session_id}: {exc}")
            return []

    def update_manifest(self, session: ComparisonSession) -> None:
        """Public trigger to update session manifest on disk."""
        self._write_manifest(session, datetime.now(timezone.utc))

    def get_cancellation_event(self, session_id: str) -> Optional[threading.Event]:
        """Retrieve cooperative cancellation event for checking in synchronous loops."""
        with self._lock:
            return self._cancellation_events.get(session_id.lower())

    def _set_cancellation_event(self, session_id: str) -> None:
        event = self._cancellation_events.get(session_id.lower())
        if event is not None:
            event.set()

    def sweep_expired_sessions(self, now: Optional[datetime] = None) -> int:
        """Scan registry for expired sessions and safely unlink storage."""
        current_time = now or datetime.now(timezone.utc)
        expired_ids: List[str] = []

        with self._lock:
            for s_id, session in list(self._sessions.items()):
                if self._is_expired(session, current_time):
                    session.status = SessionStatus.EXPIRED
                    expired_ids.append(s_id)

        count = 0
        for s_id in expired_ids:
            self._cleanup_session_storage(s_id)
            with self._lock:
                session = self._sessions.get(s_id)
                if session is not None:
                    session.status = SessionStatus.EXPIRED
                self._cancellation_events.pop(s_id, None)
            count += 1

        if count > 0:
            logger.info(f"Swept {count} expired comparison sessions.")
        return count

    def startup_cleanup_orphans(self) -> int:
        """On process startup, remove leftover session directories from prior runs."""
        if not self._storage_root.exists():
            return 0

        cleaned_count = 0
        for entry in self._storage_root.iterdir():
            if entry.is_dir() and entry.name.startswith("session_"):
                suffix = entry.name[len("session_"):]
                if _UUID_PATTERN.match(suffix):
                    resolved_dir = entry.resolve()
                    if resolved_dir.is_relative_to(self._storage_root):
                        try:
                            shutil.rmtree(resolved_dir, ignore_errors=True)
                            cleaned_count += 1
                        except Exception as exc:
                            logger.warning(f"Failed to clean orphan session directory {entry.name}: {exc}")

        if cleaned_count > 0:
            logger.info(f"Startup clean: removed {cleaned_count} orphan comparison directories.")
        return cleaned_count

    def resolve_session_path(self, session_id: str, relative_path: str = "") -> Path:
        """Validate and resolve a path inside the session directory. Prevents traversal."""
        if not session_id or not _UUID_PATTERN.match(session_id):
            raise ValueError("Invalid session identifier.")

        session_dir = (self._storage_root / f"session_{session_id.lower()}").resolve()
        if not session_dir.is_relative_to(self._storage_root):
            raise ValueError("Session directory escapes storage root.")

        if not relative_path:
            return session_dir

        target_path = (session_dir / relative_path).resolve()
        if not target_path.is_relative_to(session_dir):
            raise ValueError(f"Path traversal detected: {relative_path}")

        return target_path

    def _is_expired(self, session: ComparisonSession, now: datetime) -> bool:
        if session.status in (SessionStatus.TERMINATED, SessionStatus.EXPIRED):
            return True
        return now >= session.expires_at or now >= session.idle_timeout_at

    def _write_manifest(self, session: ComparisonSession, now: datetime) -> None:
        """Write minimal on-disk session manifest. Strictly zero secrets or raw tokens."""
        try:
            session_dir = (self._storage_root / session.storage_rel_path).resolve()
            if not session_dir.is_relative_to(self._storage_root):
                return

            manifest = SessionManifest(
                schema_version="1.0.0",
                session_id=session.session_id,
                comparison_mode=session.comparison_mode,
                status=session.status,
                created_at=session.created_at.isoformat(),
                last_accessed_at=session.last_accessed_at.isoformat(),
                expires_at=session.expires_at.isoformat(),
                idle_timeout_at=session.idle_timeout_at.isoformat(),
                document_ids=session.document_ids,
                consent_granted=session.consent_granted,
            )

            manifest_path = session_dir / "manifest.json"
            tmp_path = session_dir / "manifest.json.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(manifest.model_dump_json(indent=2))
            tmp_path.replace(manifest_path)
        except Exception as exc:
            logger.warning(f"Failed to write session manifest for {session.session_id}: {exc}")

    def _cleanup_session_storage(self, session_id: str) -> None:
        """Safely remove a session directory tree."""
        try:
            session_dir = (self._storage_root / f"session_{session_id.lower()}").resolve()
            if session_dir.exists() and session_dir.is_relative_to(self._storage_root):
                shutil.rmtree(session_dir, ignore_errors=True)
        except Exception as exc:
            logger.warning(f"Error purging storage for session {session_id}: {exc}")


# Global singleton instance
session_store = ComparisonSessionStore()
