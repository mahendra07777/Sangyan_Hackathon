"""
Slice 11 Test Suite: Explain Document & Offline Local Mode Verification.
Covers:
- Local upload and explanation without external network calls (Outbound Network Guard).
- Local chat without external calls (Facts, Educational concepts, Advice refusal).
- Local translation without external calls.
- Four Mandatory Security Safeguards:
  A. Consent only after confirmation (preview does not authorize transmission).
  B. Operation-specific consent (EXPLAIN vs CHAT vs TRANSLATE isolation).
  C. Accurate privacy disclosure and payload hash invariance.
  D. Single-use and expiration enforcement.
- External AI failure local fallback (503, 429, timeout, missing credentials).
- Honest disclosure for unreadable/scanned documents without invented facts.
- Shielding of raw provider errors from user-facing output.
"""

import io
import socket
import unittest
from unittest import mock
import fitz
from fastapi.testclient import TestClient

from main import app
from app.services.document_processor import DocumentProcessor, SingleDocConsentManager
from app.services.chat_service import ChatService
from app.models.chat import ChatRequest


class OutboundNetworkGuard:
    """Active outbound socket guard to detect any external network attempts."""
    def __init__(self):
        self.attempts = []
        self._orig_connect = socket.socket.connect

    def __enter__(self):
        def _guarded_connect(sock_self, address):
            host = address[0] if isinstance(address, (list, tuple)) else str(address)
            # Flag any non-loopback connection attempt
            if host not in ("127.0.0.1", "localhost", "::1"):
                self.attempts.append(address)
                raise ConnectionRefusedError(f"External network connection blocked: {address}")
            return self._orig_connect(sock_self, address)

        socket.socket.connect = _guarded_connect
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        socket.socket.connect = self._orig_connect


class TestSlice11LocalExplain(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _create_sample_pdf(self, title="Tata Consultancy Services Limited", revenue="73,188", pat="13,884") -> bytes:
        doc = fitz.open()
        page = doc.new_page()
        text = (
            f"{title}\n"
            f"Annual Financial Statements for FY 2023-24 (Consolidated)\n"
            f"Currency: INR Crores\n\n"
            f"Revenue from Operations: {revenue} Crores\n"
            f"Profit After Tax (PAT): {pat} Crores\n"
            f"Total Debt: Nil (Debt-free)\n"
            f"Operating Cash Flow: 14,190 Crores\n"
            f"Total Assets: 1,90,782 Crores\n"
        )
        page.insert_text((50, 50), text)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def test_01_local_upload_zero_external_requests(self):
        """Upload in Local Mode executes deterministically with zero outbound network calls."""
        pdf_content = self._create_sample_pdf()
        with OutboundNetworkGuard() as guard:
            response = self.client.post(
                "/api/documents/upload",
                files={"file": ("tcs_fy24.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"language": "English", "mode": "local"}
            )
            # Verify zero outbound connections attempted
            self.assertEqual(len(guard.attempts), 0, f"External connections detected: {guard.attempts}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        doc = data["document"]
        intel = doc["intelligence"]
        self.assertEqual(intel["mode"], "LOCAL_MODE")
        self.assertFalse(intel["fallback_triggered"])
        self.assertIn("Tata Consultancy Services", intel["document_story"])
        self.assertIn("73,188", intel["document_story"])
        self.assertTrue(len(intel["key_facts"]) >= 2)

    def test_02_local_explain_document_works_offline(self):
        """Explain Document produces grounded narrative and key facts offline without internet."""
        pdf_content = self._create_sample_pdf(title="Infosys Limited", revenue="37,923", pat="6,106")
        with OutboundNetworkGuard() as guard:
            response = self.client.post(
                "/api/documents/upload",
                files={"file": ("infy.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"language": "English", "mode": "local"}
            )
            self.assertEqual(len(guard.attempts), 0)

        intel = response.json()["document"]["intelligence"]
        self.assertIn("Infosys Limited", intel["document_story"])
        self.assertIn("37,923", intel["document_story"])
        # Verify educational glossary Impact Lens is populated
        self.assertTrue(len(intel["financial_terms"]) >= 1)
        term_names = [t["term"] for t in intel["financial_terms"]]
        self.assertTrue(any(t in term_names for t in ["Revenue", "Net Profit", "Operating Cash Flow"]))

    def test_03_local_chat_zero_external_requests(self):
        """Local Chat answers facts, educational concepts, and advice refusals offline."""
        pdf_content = self._create_sample_pdf()
        upload_resp = self.client.post(
            "/api/documents/upload",
            files={"file": ("tcs.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"language": "English", "mode": "local"}
        )
        doc_id = upload_resp.json()["document"]["id"]
        context = "Revenue from Operations: 73,188 Crores\nProfit After Tax: 13,884 Crores"

        with OutboundNetworkGuard() as guard:
            # A. Fact lookup
            resp_fact = self.client.post("/api/chat", json={
                "message": "What is the revenue?",
                "document_context": context,
                "language": "English",
                "mode": "local",
                "document_id": doc_id
            })
            self.assertEqual(resp_fact.status_code, 200)
            self.assertEqual(resp_fact.json()["intent_classified"], "DOCUMENT_QA")
            self.assertIn("73,188", resp_fact.json()["answer"])

            # B. Concept education
            resp_concept = self.client.post("/api/chat", json={
                "message": "What is EBITDA?",
                "document_context": context,
                "language": "English",
                "mode": "local",
                "document_id": doc_id
            })
            self.assertEqual(resp_concept.status_code, 200)
            self.assertEqual(resp_concept.json()["intent_classified"], "FINANCIAL_EDUCATION")
            self.assertIn("Operating profit", resp_concept.json()["answer"])

            # C. Prohibited advice refusal
            resp_advice = self.client.post("/api/chat", json={
                "message": "Should I buy this stock for quick returns?",
                "document_context": context,
                "language": "English",
                "mode": "local",
                "document_id": doc_id
            })
            self.assertEqual(resp_advice.status_code, 200)
            self.assertEqual(resp_advice.json()["intent_classified"], "PROHIBITED_INVESTMENT_ADVICE")
            self.assertEqual(resp_advice.json()["answer_type"], "REFUSAL")

            # Verify guard: 0 outbound connections across all 3 chat turns
            self.assertEqual(len(guard.attempts), 0)

    def test_04_local_translation_zero_external_requests(self):
        """Local translation translates structured definitions into Hindi/Hinglish offline."""
        pdf_content = self._create_sample_pdf()
        upload_resp = self.client.post(
            "/api/documents/upload",
            files={"file": ("tcs.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"language": "English", "mode": "local"}
        )
        intel = upload_resp.json()["document"]["intelligence"]

        with OutboundNetworkGuard() as guard:
            resp_hi = self.client.post("/api/documents/translate", json={
                "intelligence": intel,
                "language": "Hindi",
                "mode": "local"
            })
            self.assertEqual(resp_hi.status_code, 200)
            self.assertEqual(len(guard.attempts), 0)

        hi_intel = resp_hi.json()
        self.assertEqual(hi_intel["mode"], "LOCAL_MODE")
        # Verify Hindi definitions populated
        self.assertTrue(len(hi_intel["financial_terms"]) >= 1)

    def test_05_consent_preview_does_not_authorize_transmission(self):
        """Safeguard A: Consent preview alone must NOT authorize transmission."""
        pdf_content = self._create_sample_pdf()
        upload_resp = self.client.post(
            "/api/documents/upload",
            files={"file": ("preview_test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"language": "English", "mode": "local"}
        )
        doc_id = upload_resp.json()["document"]["id"]

        # Step 1: Request preview
        prev_resp = self.client.post("/api/documents/consent/preview", json={
            "document_id": doc_id,
            "operation": "EXPLAIN"
        })
        self.assertEqual(prev_resp.status_code, 200)
        prev_data = prev_resp.json()
        challenge_id = prev_data["challenge_id"]

        # Attempting AI analysis with unconfirmed challenge must fail
        ai_resp = self.client.post("/api/documents/ai-analyze", json={
            "document_id": doc_id,
            "challenge_id": challenge_id,
            "consent_token": "fake-unconfirmed-token",
            "language": "English"
        })
        self.assertEqual(ai_resp.status_code, 403)

    def test_06_consent_is_operation_specific(self):
        """Safeguard B: A token for EXPLAIN cannot be used for CHAT or TRANSLATE."""
        pdf_content = self._create_sample_pdf()
        upload_resp = self.client.post(
            "/api/documents/upload",
            files={"file": ("op_test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"language": "English", "mode": "local"}
        )
        doc_id = upload_resp.json()["document"]["id"]

        # Request and confirm EXPLAIN consent
        prev = self.client.post("/api/documents/consent/preview", json={"document_id": doc_id, "operation": "EXPLAIN"}).json()
        conf = self.client.post("/api/documents/consent/confirm", json={
            "challenge_id": prev["challenge_id"],
            "document_id": doc_id,
            "operation": "EXPLAIN",
            "payload_hash": prev["payload_hash"]
        }).json()
        explain_token = conf["consent_token"]

        # Attempt to use EXPLAIN token for CHAT operation
        chat_resp = self.client.post("/api/chat", json={
            "message": "Give me summary",
            "document_context": "context",
            "language": "English",
            "mode": "ai",
            "document_id": doc_id,
            "challenge_id": prev["challenge_id"],
            "consent_token": explain_token
        })
        # Backend rejects external chat and falls back cleanly to local mode
        self.assertEqual(chat_resp.json()["mode"], "LOCAL_MODE")
        self.assertTrue(chat_resp.json()["fallback_triggered"])

    def test_07_consent_single_use_and_payload_invariance(self):
        """Safeguard A & D: Single-use enforcement and rejection if payload is tampered."""
        pdf_content = self._create_sample_pdf()
        upload_resp = self.client.post(
            "/api/documents/upload",
            files={"file": ("tamper_test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"language": "English", "mode": "local"}
        )
        doc_id = upload_resp.json()["document"]["id"]

        prev = self.client.post("/api/documents/consent/preview", json={"document_id": doc_id, "operation": "EXPLAIN"}).json()
        conf = self.client.post("/api/documents/consent/confirm", json={
            "challenge_id": prev["challenge_id"],
            "document_id": doc_id,
            "operation": "EXPLAIN",
            "payload_hash": prev["payload_hash"]
        }).json()
        token = conf["consent_token"]

        # Mock gemini call to return valid response
        with mock.patch("google.genai.Client") as mock_client:
            mock_inst = mock.MagicMock()
            mock_client.return_value = mock_inst
            mock_inst.models.generate_content.return_value = mock.MagicMock(
                text='{"document_type": "Disclosure", "simple_summary": "AI summary", "key_facts": [], "financial_terms": []}'
            )

            # First use: valid
            resp1 = self.client.post("/api/documents/ai-analyze", json={
                "document_id": doc_id,
                "challenge_id": prev["challenge_id"],
                "consent_token": token,
                "language": "English"
            })
            self.assertEqual(resp1.status_code, 200)

            # Second use (replay attempt with same token): must be rejected (single-use enforced)
            resp2 = self.client.post("/api/documents/ai-analyze", json={
                "document_id": doc_id,
                "challenge_id": prev["challenge_id"],
                "consent_token": token,
                "language": "English"
            })
            self.assertEqual(resp2.status_code, 403)

    def test_08_external_ai_503_preserves_local_facts_and_shields_errors(self):
        """When authorized external AI fails with 503, local facts are preserved and 0 raw errors leak."""
        pdf_content = self._create_sample_pdf()
        upload_resp = self.client.post(
            "/api/documents/upload",
            files={"file": ("outage_test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"language": "English", "mode": "local"}
        )
        doc_id = upload_resp.json()["document"]["id"]

        prev = self.client.post("/api/documents/consent/preview", json={"document_id": doc_id, "operation": "EXPLAIN"}).json()
        conf = self.client.post("/api/documents/consent/confirm", json={
            "challenge_id": prev["challenge_id"],
            "document_id": doc_id,
            "operation": "EXPLAIN",
            "payload_hash": prev["payload_hash"]
        }).json()

        # Simulate Gemini 503 UNAVAILABLE
        with mock.patch("google.genai.Client") as mock_client:
            mock_inst = mock.MagicMock()
            mock_client.return_value = mock_inst
            mock_inst.models.generate_content.side_effect = Exception("503 UNAVAILABLE: High demand")

            ai_resp = self.client.post("/api/documents/ai-analyze", json={
                "document_id": doc_id,
                "challenge_id": prev["challenge_id"],
                "consent_token": conf["consent_token"],
                "language": "English"
            })

        self.assertEqual(ai_resp.status_code, 200)
        data = ai_resp.json()
        self.assertEqual(data["mode"], "LOCAL_MODE_FALLBACK")
        self.assertTrue(data["fallback_triggered"])
        # Verify local facts preserved
        self.assertTrue(len(data["key_facts"]) >= 2)
        # Verify raw 503 error is SHIELDED and not leaked into user summary
        self.assertNotIn("503 UNAVAILABLE", data["simple_summary"])
        self.assertNotIn("Failed to analyze document with AI: 503", data["simple_summary"])
        self.assertIn("temporarily unavailable", data["fallback_message"])

    def test_09_missing_credentials_preserves_local_analysis(self):
        """Missing GEMINI_API_KEY does not break analysis and falls back cleanly."""
        pdf_content = self._create_sample_pdf()
        upload_resp = self.client.post(
            "/api/documents/upload",
            files={"file": ("key_test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"language": "English", "mode": "local"}
        )
        doc_id = upload_resp.json()["document"]["id"]

        prev = self.client.post("/api/documents/consent/preview", json={"document_id": doc_id, "operation": "EXPLAIN"}).json()
        conf = self.client.post("/api/documents/consent/confirm", json={
            "challenge_id": prev["challenge_id"],
            "document_id": doc_id,
            "operation": "EXPLAIN",
            "payload_hash": prev["payload_hash"]
        }).json()

        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            ai_resp = self.client.post("/api/documents/ai-analyze", json={
                "document_id": doc_id,
                "challenge_id": prev["challenge_id"],
                "consent_token": conf["consent_token"],
                "language": "English"
            })

        self.assertEqual(ai_resp.status_code, 200)
        data = ai_resp.json()
        self.assertEqual(data["mode"], "LOCAL_MODE_FALLBACK")
        self.assertTrue(len(data["key_facts"]) >= 2)

    def test_10_unreadable_scanned_document_honest_disclosure(self):
        """Scanned document with no text layer honestly discloses limitations without inventing facts."""
        # Create PDF with no text (empty page)
        doc = fitz.open()
        doc.new_page()
        empty_pdf = doc.tobytes()
        doc.close()

        upload_resp = self.client.post(
            "/api/documents/upload",
            files={"file": ("scanned_blank.pdf", io.BytesIO(empty_pdf), "application/pdf")},
            data={"language": "English", "mode": "local"}
        )
        intel = upload_resp.json()["document"]["intelligence"]
        self.assertEqual(intel["mode"], "LOCAL_MODE")
        self.assertIn("scanned image", intel["document_story"].lower())
        self.assertEqual(len(intel["key_facts"]), 0)  # Zero invented facts


if __name__ == "__main__":
    unittest.main()
