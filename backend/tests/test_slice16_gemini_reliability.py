"""
Slice 16 Test Suite: Group 9 Gemini Reliability & Model Compatibility.
Covers:
- First HTTP 503 retries once after a brief wait and succeeds (Explain, Chat, Translate).
- Two consecutive HTTP 503 responses trigger safe Local fallback preserving facts & evidence.
- HTTP 404, 400, 401, 403, and invalid API key errors do NOT trigger retry.
- Compare synthesis uses 'gemini-3.5-flash-lite' when GEMINI_MODEL_ID is unset.
- GEMINI_MODEL_ID environment variable overrides Compare synthesis default cleanly.
"""

import io
import json
import os
import unittest
from unittest import mock

import fitz
from fastapi.testclient import TestClient

from main import app
from app.services.compare_synthesis_service import CompareSynthesisService
from tests.test_slice5_synthesis import build_sample_comparison_inputs


def create_sample_pdf() -> bytes:
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


class TestSlice16GeminiReliability(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _activate_and_upload(self):
        prev = self.client.post("/api/documents/ai-session/preview").json()
        creds = self.client.post(
            "/api/documents/ai-session/activate",
            json={"activation_id": prev["activation_id"]},
        ).json()
        up = self.client.post(
            "/api/documents/upload",
            files={"file": ("tata.pdf", io.BytesIO(create_sample_pdf()), "application/pdf")},
            data={"language": "English", "mode": "local"},
        ).json()["document"]
        return creds, up

    def test_01_first_503_retries_once_and_succeeds_across_explain_chat_translate(self):
        """When Gemini fails once with HTTP 503 and succeeds on retry, return normal AI response."""
        creds, doc = self._activate_and_upload()
        sid, stoken = creds["ai_session_id"], creds["ai_session_token"]

        intel_ok = json.dumps({
            "document_type": "Financial Results",
            "simple_summary": "Tata Motors Q3 revenue was 1,10,577.14 Crores.",
            "document_story": "Strong consolidated operations in FY 2023-24.",
            "key_facts": [],
            "financial_terms": [],
        })
        chat_ok = json.dumps({
            "answer": "Revenue from Operations was 1,10,577.14 Crores.",
            "intent_classified": "DOCUMENT_QA",
            "answer_type": "DOCUMENT_FACT",
            "language": "en",
            "safety_state": "SAFE",
        })
        tr_ok = json.dumps({
            "document_type": "वित्तीय परिणाम",
            "simple_summary": "टाटा मोटर्स का राजस्व 1,10,577.14 करोड़ रहा।",
            "document_story": "मजबूत समेकित परिणाम।",
            "key_facts": [],
            "financial_terms": [],
        })

        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "secret-mock-key"}), \
             mock.patch("app.services.document_processor.time.sleep") as mock_sleep, \
             mock.patch("google.genai.Client") as mock_client:
            inst = mock.MagicMock()
            mock_client.return_value = inst

            # 1. Explain: 503 then success
            inst.models.generate_content.side_effect = [
                Exception("503 UNAVAILABLE: service overloaded"),
                mock.MagicMock(text=intel_ok),
            ]
            res_ex = self.client.post("/api/documents/ai-analyze", json={
                "document_id": doc["id"],
                "ai_session_id": sid,
                "ai_session_token": stoken,
                "language": "English",
            })
            self.assertEqual(res_ex.status_code, 200)
            self.assertEqual(res_ex.json()["mode"], "AI_CONSENTED")
            self.assertFalse(res_ex.json()["fallback_triggered"])
            self.assertEqual(inst.models.generate_content.call_count, 2)

            # 2. Chat: 503 then success
            inst.models.generate_content.reset_mock()
            inst.models.generate_content.side_effect = [
                Exception("503 Service Unavailable"),
                mock.MagicMock(text=chat_ok),
            ]
            res_ch = self.client.post("/api/chat", json={
                "message": "What was revenue?",
                "document_context": "Revenue from Operations: 1,10,577.14 Crores",
                "language": "English",
                "mode": "ai",
                "document_id": doc["id"],
                "ai_session_id": sid,
                "ai_session_token": stoken,
            })
            self.assertEqual(res_ch.status_code, 200)
            self.assertEqual(res_ch.json()["mode"], "AI_CONSENTED")
            self.assertFalse(res_ch.json()["fallback_triggered"])
            self.assertEqual(inst.models.generate_content.call_count, 2)

            # 3. Translate: 503 then success
            inst.models.generate_content.reset_mock()
            inst.models.generate_content.side_effect = [
                Exception("503 UNAVAILABLE"),
                mock.MagicMock(text=tr_ok),
            ]
            res_tr = self.client.post("/api/documents/translate", json={
                "intelligence": doc["intelligence"],
                "language": "Hindi",
                "mode": "ai",
                "document_id": doc["id"],
                "ai_session_id": sid,
                "ai_session_token": stoken,
            })
            self.assertEqual(res_tr.status_code, 200)
            self.assertEqual(res_tr.json()["mode"], "AI_CONSENTED")
            self.assertFalse(res_tr.json()["fallback_triggered"])
            self.assertEqual(inst.models.generate_content.call_count, 2)
            self.assertEqual(mock_sleep.call_count, 3)

    def test_02_two_consecutive_503_trigger_local_fallback_preserving_facts_and_evidence(self):
        """Two consecutive 503 errors stop after exactly one retry and fall back safely."""
        creds, doc = self._activate_and_upload()
        sid, stoken = creds["ai_session_id"], creds["ai_session_token"]

        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "secret-mock-key"}), \
             mock.patch("app.services.document_processor.time.sleep") as mock_sleep, \
             mock.patch("google.genai.Client") as mock_client:
            inst = mock.MagicMock()
            mock_client.return_value = inst
            inst.models.generate_content.side_effect = [
                Exception("503 UNAVAILABLE: attempt 1"),
                Exception("503 UNAVAILABLE: attempt 2"),
            ]

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
            self.assertEqual(inst.models.generate_content.call_count, 2)
            mock_sleep.assert_called_once()
            self.assertTrue(len(body["key_facts"]) >= 2)
            self.assertTrue(any(f.get("evidence_reference") == "Page 1" for f in body["key_facts"]))

            # Chat consecutive 503 also stops after 2 attempts and falls back safely
            inst.models.generate_content.reset_mock()
            mock_sleep.reset_mock()
            inst.models.generate_content.side_effect = [
                Exception("503 UNAVAILABLE"),
                Exception("503 UNAVAILABLE"),
            ]
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
            self.assertEqual(chat_res.json()["mode"], "LOCAL_MODE_FALLBACK")
            self.assertTrue(chat_res.json()["fallback_triggered"])
            self.assertEqual(inst.models.generate_content.call_count, 2)
            mock_sleep.assert_called_once()

    def test_03_non_retryable_errors_404_400_and_invalid_key_do_not_retry(self):
        """HTTP 404, 400, 401, 403, and invalid API keys fail immediately on attempt 1 without retry."""
        creds, doc = self._activate_and_upload()
        sid, stoken = creds["ai_session_id"], creds["ai_session_token"]
        fake_secret = "AIzaSyMockSecretDoNotLeak999"

        non_retryable = [
            Exception("404 NOT_FOUND: model unavailable"),
            Exception("400 INVALID_ARGUMENT: bad schema"),
            Exception("401 UNAUTHENTICATED: API key not valid"),
            Exception("403 PERMISSION_DENIED: invalid API key"),
        ]

        for err in non_retryable:
            with mock.patch.dict("os.environ", {"GEMINI_API_KEY": fake_secret}), \
                 mock.patch("app.services.document_processor.time.sleep") as mock_sleep, \
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
                self.assertEqual(res.json()["mode"], "LOCAL_MODE_FALLBACK")
                self.assertEqual(inst.models.generate_content.call_count, 1)
                mock_sleep.assert_not_called()
                self.assertNotIn(fake_secret, json.dumps(res.json()))

                inst.models.generate_content.reset_mock()
                chat_res = self.client.post("/api/chat", json={
                    "message": "What is PAT?",
                    "document_context": "Profit After Tax (PAT): 7,025.11 Crores",
                    "language": "English",
                    "mode": "ai",
                    "document_id": doc["id"],
                    "ai_session_id": sid,
                    "ai_session_token": stoken,
                })
                self.assertEqual(chat_res.status_code, 200)
                self.assertEqual(chat_res.json()["mode"], "LOCAL_MODE_FALLBACK")
                self.assertEqual(inst.models.generate_content.call_count, 1)
                mock_sleep.assert_not_called()
                self.assertNotIn(fake_secret, json.dumps(chat_res.json()))

    def test_04_compare_synthesis_default_model_and_env_override(self):
        """Compare synthesis defaults to gemini-3.5-flash-lite and respects GEMINI_MODEL_ID override."""
        docs, meta_map, compat, fvs, variances = build_sample_comparison_inputs()
        mock_summary_json = json.dumps({
            "overview_story": "Comparative analysis of Tata Motors and Maruti Suzuki.",
            "core_positive_changes": ["Tata Motors maintained higher revenue."],
            "core_negative_changes": [],
            "neutral_observations": [],
            "uncertain_findings": [],
            "critical_disclosures": [],
        })

        # 1. No GEMINI_MODEL_ID override -> resolves to gemini-3.5-flash-lite
        env_no_override = {k: v for k, v in os.environ.items() if k != "GEMINI_MODEL_ID"}
        env_no_override["GEMINI_API_KEY"] = "fake_test_key"
        env_no_override["GEMINI_FREE_TIER_CONFIRMED"] = "true"

        with mock.patch.dict(os.environ, env_no_override, clear=True), \
             mock.patch("google.genai.Client") as mock_client_cls:
            inst = mock_client_cls.return_value
            inst.models.generate_content.return_value = mock.MagicMock(text=mock_summary_json)

            result = CompareSynthesisService.synthesize_comparison(
                session_id="test_default_model",
                documents=docs,
                metadata_map=meta_map,
                compatibility=compat,
                financial_values=fvs,
                variances=variances,
                consent_granted=True,
                language="English",
            )
            self.assertEqual(result.mode, "AI_ASSISTED")
            _, kwargs = inst.models.generate_content.call_args
            self.assertEqual(kwargs["model"], "gemini-3.5-flash-lite")

        # 2. GEMINI_MODEL_ID override -> uses overridden model
        with mock.patch.dict(os.environ, {
            "GEMINI_API_KEY": "fake_test_key",
            "GEMINI_FREE_TIER_CONFIRMED": "true",
            "GEMINI_MODEL_ID": "gemini-3.8-flash",
        }), mock.patch("google.genai.Client") as mock_client_cls:
            inst = mock_client_cls.return_value
            inst.models.generate_content.return_value = mock.MagicMock(text=mock_summary_json)

            result = CompareSynthesisService.synthesize_comparison(
                session_id="test_override_model",
                documents=docs,
                metadata_map=meta_map,
                compatibility=compat,
                financial_values=fvs,
                variances=variances,
                consent_granted=True,
                language="English",
            )
            self.assertEqual(result.mode, "AI_ASSISTED")
            _, kwargs = inst.models.generate_content.call_args
            self.assertEqual(kwargs["model"], "gemini-3.8-flash")


if __name__ == "__main__":
    unittest.main()
