"""Comprehensive security, lifecycle, and isolation tests for Slice 1."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
import sys
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import main as app_main
from app.core.security import (
    generate_capability_token,
    hash_capability_token,
    verify_capability_token,
)
from app.models.comparison import ComparisonMode, SessionStatus
from app.services.comparison_session_store import (
    ComparisonSessionStore,
    session_store,
)


class TestSlice1SecurityAndSessionLifecycle(unittest.TestCase):
    """Test suite covering capability token security, directory isolation, timeouts, and cleanup."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_main.app)

    def setUp(self) -> None:
        # Use an isolated temporary directory for test storage
        self.test_dir = tempfile.mkdtemp(prefix="test_compare_storage_")
        self.custom_store = ComparisonSessionStore(storage_root=Path(self.test_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # 1. Token Cryptographic Security
    # -----------------------------------------------------------------------

    def test_token_generation_and_hashing(self) -> None:
        token = generate_capability_token()
        self.assertIsInstance(token, str)
        self.assertGreaterEqual(len(token), 32)

        digest = hash_capability_token(token)
        self.assertEqual(len(digest), 64)  # SHA-256 hex length
        self.assertTrue(verify_capability_token(digest, token))
        self.assertFalse(verify_capability_token(digest, "tampered_token"))
        self.assertFalse(verify_capability_token("", token))
        self.assertFalse(verify_capability_token(digest, ""))

    # -----------------------------------------------------------------------
    # 2. Session Creation API & Manifest Integrity
    # -----------------------------------------------------------------------

    def test_create_session_endpoint_success(self) -> None:
        response = self.client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(response.status_code, 201)
        data = response.json()

        self.assertIn("session_id", data)
        self.assertIn("session_token", data)
        self.assertEqual(data["comparison_mode"], "QUICK_COMPARE")
        self.assertEqual(data["idle_timeout_seconds"], 1800)
        self.assertEqual(data["absolute_timeout_seconds"], 14400)
        self.assertEqual(data["max_documents"], 5)

        session_id = data["session_id"]
        raw_token = data["session_token"]

        # Verify token is NEVER stored in plaintext in the in-memory registry
        in_memory_session = session_store.get_session(session_id)
        self.assertIsNotNone(in_memory_session)
        self.assertNotEqual(in_memory_session.token_hash, raw_token)
        self.assertEqual(in_memory_session.token_hash, hash_capability_token(raw_token))

        # Verify filesystem storage layout and manifest
        session_dir = session_store.storage_root / f"session_{session_id}"
        self.assertTrue(session_dir.exists())
        self.assertTrue((session_dir / "documents").exists())
        self.assertTrue((session_dir / "extracted").exists())
        self.assertTrue((session_dir / "evidence").exists())
        self.assertTrue((session_dir / "exports").exists())

        # Verify manifest contains zero raw tokens or secrets
        manifest_path = session_dir / "manifest.json"
        self.assertTrue(manifest_path.exists())
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_content = json.load(f)

        self.assertEqual(manifest_content["session_id"], session_id)
        self.assertNotIn("session_token", manifest_content)
        self.assertNotIn("token_hash", manifest_content)
        self.assertNotIn(raw_token, json.dumps(manifest_content))

    # -----------------------------------------------------------------------
    # 3. Query Parameter Rejection & Header Authentication
    # -----------------------------------------------------------------------

    def test_query_parameter_token_rejected_with_400(self) -> None:
        # Create session
        resp = self.client.post("/api/compare/session")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        session_id = data["session_id"]
        token = data["session_token"]

        # Passing token in query parameter MUST be rejected with HTTP 400
        res = self.client.delete(f"/api/compare/session/{session_id}?token={token}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("query parameters", res.json()["detail"].lower())

        res2 = self.client.delete(f"/api/compare/session/{session_id}?session_token={token}")
        self.assertEqual(res2.status_code, 400)

    def test_missing_header_rejected_with_401(self) -> None:
        resp = self.client.post("/api/compare/session")
        session_id = resp.json()["session_id"]

        # Call DELETE without X-Session-Token
        res = self.client.delete(f"/api/compare/session/{session_id}")
        self.assertEqual(res.status_code, 401)
        self.assertIn("X-Session-Token header missing", res.json()["detail"])

    def test_invalid_token_rejected_with_401(self) -> None:
        resp = self.client.post("/api/compare/session")
        session_id = resp.json()["session_id"]

        # Call with incorrect token
        headers = {"X-Session-Token": "invalid_wrong_token_1234567890"}
        res = self.client.delete(f"/api/compare/session/{session_id}", headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid or expired", res.json()["detail"])

    def test_session_isolation_cross_token_access_denied(self) -> None:
        # Create Session A and Session B
        resp_a = self.client.post("/api/compare/session").json()
        resp_b = self.client.post("/api/compare/session").json()

        session_a_id = resp_a["session_id"]
        session_a_token = resp_a["session_token"]

        session_b_id = resp_b["session_id"]
        session_b_token = resp_b["session_token"]

        # Attempt to access / delete Session B using Session A's token
        headers = {"X-Session-Token": session_a_token}
        res = self.client.delete(f"/api/compare/session/{session_b_id}", headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid or expired", res.json()["detail"])

        # Verify Session B is still alive and intact
        session_b_dir = session_store.storage_root / f"session_{session_b_id}"
        self.assertTrue(session_b_dir.exists())

    def test_malformed_session_id_rejected_with_400(self) -> None:
        headers = {"X-Session-Token": "some_dummy_token"}
        res = self.client.delete("/api/compare/session/not-a-valid-uuid", headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid session identifier", res.json()["detail"])

    # -----------------------------------------------------------------------
    # 4. Session Deletion & Cleanup
    # -----------------------------------------------------------------------

    def test_delete_session_success_and_storage_wipe(self) -> None:
        resp = self.client.post("/api/compare/session").json()
        session_id = resp.json()["session_id"] if isinstance(resp, dict) and "json" in dir(resp) else resp["session_id"]
        token = resp["session_token"]

        session_dir = session_store.storage_root / f"session_{session_id}"
        self.assertTrue(session_dir.exists())

        headers = {"X-Session-Token": token}
        del_res = self.client.delete(f"/api/compare/session/{session_id}", headers=headers)
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "DELETED")

        # Verify directory is wiped from disk
        self.assertFalse(session_dir.exists())

        # Accessing after deletion MUST return 410 Gone for authenticated owner
        retry_res = self.client.delete(f"/api/compare/session/{session_id}", headers=headers)
        self.assertEqual(retry_res.status_code, 410)
        self.assertIn("terminated", retry_res.json()["detail"].lower())

        # Unauthenticated request for the terminated session returns 401, not 410
        wrong_res = self.client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": "wrong_token"})
        self.assertEqual(wrong_res.status_code, 401)

    def test_session_status_lifecycle_transitions(self) -> None:
        """Verify explicit lifecycle state machine transitions and terminal state locking."""
        session, _ = self.custom_store.create_session()
        self.assertEqual(session.status, SessionStatus.INITIALIZED)

        # Legal progression
        self.assertTrue(session.can_transition_to(SessionStatus.ACTIVE))
        session.transition_to(SessionStatus.ACTIVE)
        self.assertEqual(session.status, SessionStatus.ACTIVE)

        self.assertTrue(session.can_transition_to(SessionStatus.FILES_UPLOADED))
        session.transition_to(SessionStatus.FILES_UPLOADED)

        self.assertTrue(session.can_transition_to(SessionStatus.METADATA_EXTRACTED))
        session.transition_to(SessionStatus.METADATA_EXTRACTED)

        self.assertTrue(session.can_transition_to(SessionStatus.PROCESSING))
        session.transition_to(SessionStatus.PROCESSING)

        self.assertTrue(session.can_transition_to(SessionStatus.COMPLETED))
        session.transition_to(SessionStatus.COMPLETED)
        self.assertEqual(session.status, SessionStatus.COMPLETED)

        # Transition to terminal state: EXPIRED
        self.assertTrue(session.can_transition_to(SessionStatus.EXPIRED))
        session.transition_to(SessionStatus.EXPIRED)
        self.assertEqual(session.status, SessionStatus.EXPIRED)

        # Terminal state locks: CANNOT transition out of EXPIRED
        self.assertFalse(session.can_transition_to(SessionStatus.ACTIVE))
        self.assertFalse(session.can_transition_to(SessionStatus.INITIALIZED))
        self.assertFalse(session.can_transition_to(SessionStatus.COMPLETED))
        with self.assertRaises(ValueError):
            session.transition_to(SessionStatus.ACTIVE)

    def test_backend_restart_behavior_and_zero_information_leakage(self) -> None:
        """Verify behavior when memory is cleared (process restart): returns 401 with uniform detail."""
        # 1. Create a session on the server
        resp = self.client.post("/api/compare/session").json()
        prior_session_id = resp["session_id"]
        prior_token = resp["session_token"]

        # Verify active session works
        headers = {"X-Session-Token": prior_token}
        del_resp = self.client.delete(f"/api/compare/session/{prior_session_id}", headers=headers)
        self.assertEqual(del_resp.status_code, 200)

        # 2. Simulate process restart by clearing the in-memory registry completely
        with session_store._lock:
            session_store._sessions.clear()

        # 3. Present previously valid session ID and token to restarted server
        restart_req = self.client.delete(f"/api/compare/session/{prior_session_id}", headers=headers)
        # Because in-memory state is wiped, the server cannot verify token ownership
        self.assertEqual(restart_req.status_code, 401)
        self.assertEqual(restart_req.json()["detail"], "Invalid or expired comparison session token.")

        # 4. Present a completely fabricated/unknown UUID and token
        unknown_uuid = "99999999-8888-7777-6666-555555555555"
        unknown_req = self.client.delete(
            f"/api/compare/session/{unknown_uuid}",
            headers={"X-Session-Token": "some_random_token_123456789"},
        )
        self.assertEqual(unknown_req.status_code, 401)
        # Detail must be identical: zero session enumeration or timing leakage
        self.assertEqual(unknown_req.json()["detail"], restart_req.json()["detail"])

    # -----------------------------------------------------------------------
    # 5. Controlled Time Injection & Expiry Tests
    # -----------------------------------------------------------------------

    def test_inactivity_timeout_enforced(self) -> None:
        now_t0 = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
        session, token = self.custom_store.create_session(now=now_t0)
        session_id = session.session_id

        # Activity within 25 minutes: valid
        t1 = now_t0 + timedelta(minutes=25)
        s1 = self.custom_store.get_session(session_id, touch=True, now=t1)
        self.assertIsNotNone(s1)
        self.assertEqual(s1.status, SessionStatus.INITIALIZED)

        # Inactivity for 35 minutes after t1: expired
        t2 = t1 + timedelta(minutes=35)
        s2 = self.custom_store.get_session(session_id, touch=False, now=t2)
        self.assertEqual(s2.status, SessionStatus.EXPIRED)

        # Verify session directory was purged
        session_dir = self.custom_store.storage_root / f"session_{session_id}"
        self.assertFalse(session_dir.exists())

    def test_absolute_lifetime_timeout_enforced(self) -> None:
        now_t0 = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
        session, token = self.custom_store.create_session(now=now_t0)
        session_id = session.session_id

        # Touch session frequently (every 20 minutes) up to 3 hours 40 minutes: still valid
        current_step = now_t0
        for _ in range(11):  # 11 steps of 20 min = 220 min (3h 40m)
            current_step += timedelta(minutes=20)
            s_step = self.custom_store.get_session(session_id, touch=True, now=current_step)
            self.assertIsNotNone(s_step)
            self.assertEqual(s_step.status, SessionStatus.INITIALIZED)

        # After 4 hours 5 minutes from start: absolute expiration triggers regardless of recent activity
        t_expired = now_t0 + timedelta(hours=4, minutes=5)
        s_expired = self.custom_store.get_session(session_id, touch=False, now=t_expired)
        self.assertEqual(s_expired.status, SessionStatus.EXPIRED)

        # Verify storage was purged
        session_dir = self.custom_store.storage_root / f"session_{session_id}"
        self.assertFalse(session_dir.exists())

    # -----------------------------------------------------------------------
    # 6. Path Traversal & Filesystem Security
    # -----------------------------------------------------------------------

    def test_path_traversal_attempts_prevented(self) -> None:
        session, _ = self.custom_store.create_session()
        session_id = session.session_id

        # Valid subpaths resolve inside session dir
        p_docs = self.custom_store.resolve_session_path(session_id, "documents")
        self.assertTrue(p_docs.is_relative_to(self.custom_store.storage_root))

        # Path traversal attempts MUST raise ValueError
        with self.assertRaises(ValueError):
            self.custom_store.resolve_session_path(session_id, "../../etc/passwd")

        with self.assertRaises(ValueError):
            self.custom_store.resolve_session_path(session_id, "../session_other")

        with self.assertRaises(ValueError):
            self.custom_store.resolve_session_path(session_id, "/absolute/path")

    # -----------------------------------------------------------------------
    # 7. Startup Orphan Recovery
    # -----------------------------------------------------------------------

    def test_startup_orphan_cleanup_removes_stale_directories(self) -> None:
        # Create an orphan session directory simulating an interrupted prior run
        orphan_uuid = "11111111-2222-3333-4444-555555555555"
        orphan_dir = self.custom_store.storage_root / f"session_{orphan_uuid}"
        orphan_dir.mkdir(parents=True, exist_ok=True)
        (orphan_dir / "orphaned_file.txt").write_text("interrupted payload", encoding="utf-8")

        # Also create a non-session file that must NOT be touched
        keep_file = self.custom_store.storage_root / "keep_me.txt"
        keep_file.write_text("important", encoding="utf-8")

        # Execute startup cleanup
        cleaned = self.custom_store.startup_cleanup_orphans()
        self.assertEqual(cleaned, 1)

        # Verify orphan session dir was deleted
        self.assertFalse(orphan_dir.exists())

        # Verify unrelated file was preserved
        self.assertTrue(keep_file.exists())

    # -----------------------------------------------------------------------
    # 8. Single-Document Workflow Regression Protection
    # -----------------------------------------------------------------------

    def test_existing_single_doc_workflow_intact(self) -> None:
        # Health endpoint
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "healthy"})

        # Single document upload endpoint without file returns 422 or 400 (not 404)
        upload_res = self.client.post("/api/documents/upload")
        self.assertIn(upload_res.status_code, (400, 422))


if __name__ == "__main__":
    unittest.main()
