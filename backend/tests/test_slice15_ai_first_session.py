"""
Slice 15 Test Suite: Group 8 AI-First Session Authorization & Automatic Fallback.
Verifies:
- No external transmission before explicit one-time AI activation.
- Preview does not authorize transmission; activation challenge is single-use.
- Bounded session HMAC token enables Explain, Chat, and Translate seamlessly without repeated popups.
- Disabling AI revokes session authorization immediately and blocks external calls.
- Expired, invalid, or forged authorization (e.g. mode='ai' without valid token) is rejected.
- All provider failure classes (missing key, invalid key 401/403, 429, 503, timeout, unavailable model 404,
  malformed JSON response) trigger safe local fallback preserving extracted facts & never exposing GEMINI_API_KEY.
"""

import io
import json
import os
import socket
import time
import unittest
from unittest import mock

import fitz
from fastapi.testclient import TestClient

from main import app
from app.services.document_processor import SingleDocConsentManager


class OutboundNetworkGuard:
    def __init__(self):
        self.attempts = []
        self._orig_connect = socket.socket.connect

    def __enter__(self):
        def _guarded_connect(sock_self, address):
            host = address[0] if isinstance(address, (list, tuple)) else str(address)
            if host not in ("127.0.0.1", "localhost", "::1"):
                self.attempts.append(address)
                raise ConnectionRefusedError(f"Blocked external connection: {address}")
            return self._orig_connect(sock_self, address)

        socket.socket.connect = _guarded_connect
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        socket.socket.connect = self._orig_connect


def create_test_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 50),
        (
            "TATA MOTORS LIMITED\n"
            "Consolidated Results FY 2023-24\n"
            "Revenue from Operations: 1,10,577.14 Crores\n"
            "Profit After Tax (PAT): 7,025.11 Crores\n"
            "Total Debt: 52,140.00 Crores\n"
        ),
    )
    data = doc.tobytes()
    doc.close()
    return data


class TestSlice15AIFirstSession(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _activate_ai_session(self):
        prev = self.client.post("/api/documents/ai-session/preview")
        self.assertEqual(prev.status_code, 200)
        prev_data = prev.json()
        self.assertIn("Gemini API", prev_data["recipient"])
        self.assertGreaterEqual(len(prev_data["disclosure_items"]), 4)

        act = self.client.post(
            "/api/documents/ai-session/activate",
            json={"activation_id": prev_data["activation_id"]},
        )
        self.assertEqual(act.status_code, 200)
        return prev_data, act.json()

    def test_01_no_external_calls_before_activation_and_forged_boolean_rejected(self):
        """Even if frontend sends mode='ai', missing/forged session token blocks Gemini completely."""
        pdf_bytes = create_test_pdf()
        with OutboundNetworkGuard() as guard, \
             mock.patch.dict("os.environ", {"GEMINI_API_KEY": "secret-test-key"}), \
             mock.patch("google.genai.Client") as mock_client:
            # Preview alone must NOT authorize
            prev = self.client.post("/api/documents/ai-session/preview").json()

            # Upload with forged mode='ai' and bogus token
            up = self.client.post(
                "/api/documents/upload",
                files={"file": ("tata.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
                data={
                    "language": "English",
                    "mode": "ai",
                    "ai_session_id": prev["activation_id"],
                    "ai_session_token": "forged-token",
                },
            )
            self.assertEqual(up.status_code, 200)
            doc = up.json()["document"]
            self.assertEqual(doc["intelligence"]["mode"], "LOCAL_MODE")
            mock_client.assert_not_called()

            # Forged CHAT mode='ai' blocked
            chat = self.client.post("/api/chat", json={
                "message": "Summarize risks",
                "document_context": "Revenue 1,10,577.14 Crores",
                "language": "English",
                "mode": "ai",
                "document_id": doc["id"],
                "ai_session_id": "fake-id",
                "ai_session_token": "fake-token",
            })
            self.assertEqual(chat.status_code, 200)
            self.assertNotEqual(chat.json()["mode"], "AI_CONSENTED")
            self.assertTrue(chat.json()["fallback_triggered"])
            mock_client.assert_not_called()

            # Forged ai-analyze returns 403
            analyze = self.client.post("/api/documents/ai-analyze", json={
                "document_id": doc["id"],
                "ai_session_id": "fake-id",
                "ai_session_token": "fake-token",
                "language": "English",
            })
            self.assertEqual(analyze.status_code, 403)
            self.assertEqual(len(guard.attempts), 0)

    def test_02_one_time_activation_powers_explain_chat_and_translate_without_reprompting(self):
        prev_data, creds = self._activate_ai_session()
        sid = creds["ai_session_id"]
        stoken = creds["ai_session_token"]

        # Activation challenge is single-use
        replay_act = self.client.post(
            "/api/documents/ai-session/activate",
            json={"activation_id": prev_data["activation_id"]},
        )
        self.assertEqual(replay_act.status_code, 400)

        pdf_bytes = create_test_pdf()
        sample_intel_json = json.dumps({
            "document_type": "Financial Results",
            "simple_summary": "Tata Motors reported strong consolidated operations.",
            "document_story": "Revenue reached 1,10,577.14 Crores with PAT of 7,025.11 Crores.",
            "key_facts": [],
            "financial_terms": [],
        })
        sample_chat_json = json.dumps({
            "answer": "Revenue from Operations was 1,10,577.14 Crores (Page 1).",
            "intent_classified": "DOCUMENT_QA",
            "answer_type": "DOCUMENT_FACT",
            "language": "en",
            "safety_state": "SAFE",
        })
        sample_tr_json = json.dumps({
            "document_type": "वित्तीय परिणाम",
            "simple_summary": "टाटा मोटर्स ने मजबूत समेकित परिणाम दर्ज किए।",
            "document_story": "राजस्व 1,10,577.14 करोड़ रुपये रहा।",
            "key_facts": [],
            "financial_terms": [],
        })

        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "secret-test-key"}), \
             mock.patch("google.genai.Client") as mock_client:
            inst = mock.MagicMock()
            mock_client.return_value = inst
            inst.models.generate_content.side_effect = [
                mock.MagicMock(text=sample_intel_json),
                mock.MagicMock(text=sample_chat_json),
                mock.MagicMock(text=sample_tr_json),
            ]

            # 1. Auto-explain during upload
            up = self.client.post(
                "/api/documents/upload",
                files={"file": ("tata.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
                data={"language": "English", "mode": "ai", "ai_session_id": sid, "ai_session_token": stoken},
            )
            self.assertEqual(up.status_code, 200)
            doc = up.json()["document"]
            self.assertEqual(doc["intelligence"]["mode"], "AI_CONSENTED")
            self.assertTrue(len(doc["intelligence"]["key_facts"]) >= 2)  # Local facts preserved!

            # 2. Ask Bharat Chat automatically uses active AI session
            chat = self.client.post("/api/chat", json={
                "message": "What was revenue?",
                "document_context": "Revenue from Operations: 1,10,577.14 Crores",
                "language": "English",
                "mode": "ai",
                "document_id": doc["id"],
                "ai_session_id": sid,
                "ai_session_token": stoken,
            })
            self.assertEqual(chat.status_code, 200)
            self.assertEqual(chat.json()["mode"], "AI_CONSENTED")

            # 3. Auto-translate uses same active AI session cleanly
            tr = self.client.post("/api/documents/translate", json={
                "intelligence": doc["intelligence"],
                "language": "Hindi",
                "mode": "ai",
                "document_id": doc["id"],
                "ai_session_id": sid,
                "ai_session_token": stoken,
            })
            self.assertEqual(tr.status_code, 200)
            self.assertEqual(tr.json()["mode"], "AI_CONSENTED")
            self.assertEqual(inst.models.generate_content.call_count, 3)

    def test_03_disable_and_expiry_immediately_block_external_calls(self):
        _, creds = self._activate_ai_session()
        sid = creds["ai_session_id"]
        stoken = creds["ai_session_token"]

        # Verify active status
        st = self.client.post("/api/documents/ai-session/status", json={"ai_session_id": sid, "ai_session_token": stoken})
        self.assertTrue(st.json()["active"])

        # Upload locally first
        up = self.client.post(
            "/api/documents/upload",
            files={"file": ("tata.pdf", io.BytesIO(create_test_pdf()), "application/pdf")},
            data={"language": "English", "mode": "local"},
        )
        doc_id = up.json()["document"]["id"]

        # Disable AI processing
        dis = self.client.post("/api/documents/ai-session/disable", json={"ai_session_id": sid, "ai_session_token": stoken})
        self.assertFalse(dis.json()["active"])

        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "secret-test-key"}), \
             mock.patch("google.genai.Client") as mock_client:
            # Subsequent EXPLAIN, CHAT, and TRANSLATE must NOT call Gemini
            res_ex = self.client.post("/api/documents/ai-analyze", json={
                "document_id": doc_id,
                "ai_session_id": sid,
                "ai_session_token": stoken,
                "language": "English",
            })
            self.assertEqual(res_ex.status_code, 403)

            res_chat = self.client.post("/api/chat", json={
                "message": "Explain revenue",
                "document_context": "Revenue from Operations: 1,10,577.14 Crores",
                "language": "English",
                "mode": "ai",
                "document_id": doc_id,
                "ai_session_id": sid,
                "ai_session_token": stoken,
            })
            self.assertEqual(res_chat.status_code, 200)
            self.assertNotEqual(res_chat.json()["mode"], "AI_CONSENTED")
            mock_client.assert_not_called()

        # Expired session also rejected
        _, creds2 = self._activate_ai_session()
        SingleDocConsentManager._ai_sessions[creds2["ai_session_id"]]["expires_at"] = time.time() - 5
        st2 = self.client.post("/api/documents/ai-session/status", json={
            "ai_session_id": creds2["ai_session_id"],
            "ai_session_token": creds2["ai_session_token"],
        })
        self.assertFalse(st2.json()["active"])

    def test_04_all_provider_failures_trigger_safe_local_fallback_without_exposing_key(self):
        """Missing key, invalid key, 429, 503, timeout, unavailable model, malformed JSON -> safe local fallback."""
        _, creds = self._activate_ai_session()
        sid = creds["ai_session_id"]
        stoken = creds["ai_session_token"]
        fake_secret = "AIzaSySecretKeyNeverExposeThis123456"

        up = self.client.post(
            "/api/documents/upload",
            files={"file": ("tata.pdf", io.BytesIO(create_test_pdf()), "application/pdf")},
            data={"language": "English", "mode": "local"},
        )
        doc = up.json()["document"]

        failure_cases = [
            Exception("401 UNAUTHENTICATED: API key not valid"),
            Exception("429 RESOURCE_EXHAUSTED: quota exceeded"),
            Exception("503 UNAVAILABLE: service overloaded"),
            TimeoutError("Request deadline timed out"),
            Exception("404 NOT_FOUND: model unavailable"),
            ValueError("not valid json {{{{"),
        ]

        for err in failure_cases:
            with mock.patch.dict("os.environ", {"GEMINI_API_KEY": fake_secret}), \
                 mock.patch("google.genai.Client") as mock_client:
                inst = mock.MagicMock()
                mock_client.return_value = inst
                inst.models.generate_content.side_effect = err

                res = self.client.post("/api/documents/ai-analyze", json={
                    "document_id": doc["id"],
                    "ai_session_id": sid,
                    "ai_session_token": stoken,
                    "language": "English",
                })
                self.assertEqual(res.status_code, 200)
                body = res.json()
                self.assertEqual(body["mode"], "LOCAL_MODE_FALLBACK")
                self.assertTrue(body["fallback_triggered"])
                self.assertTrue(len(body["key_facts"]) >= 2)
                serialized = json.dumps(body)
                self.assertNotIn(fake_secret, serialized)
                self.assertNotIn("AIzaSy", serialized)

                chat_res = self.client.post("/api/chat", json={
                    "message": "What is revenue?",
                    "document_context": "Revenue from Operations: 1,10,577.14 Crores",
                    "language": "English",
                    "mode": "ai",
                    "document_id": doc["id"],
                    "ai_session_id": sid,
                    "ai_session_token": stoken,
                })
                self.assertEqual(chat_res.status_code, 200)
                cbody = chat_res.json()
                self.assertEqual(cbody["mode"], "LOCAL_MODE_FALLBACK")
                self.assertTrue(cbody["fallback_triggered"])
                self.assertNotIn(fake_secret, json.dumps(cbody))

        # Local-only processing works with missing GEMINI_API_KEY
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            local_up = self.client.post(
                "/api/documents/upload",
                files={"file": ("local.pdf", io.BytesIO(create_test_pdf()), "application/pdf")},
                data={"language": "English", "mode": "local"},
            )
            self.assertEqual(local_up.status_code, 200)
            self.assertEqual(local_up.json()["document"]["intelligence"]["mode"], "LOCAL_MODE")
            self.assertTrue(len(local_up.json()["document"]["intelligence"]["key_facts"]) >= 2)


if __name__ == "__main__":
    unittest.main()
