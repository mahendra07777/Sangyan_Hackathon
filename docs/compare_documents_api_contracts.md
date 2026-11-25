# Bharat Investor Copilot — Compare Documents
## Complete REST API Contracts & Endpoint Specification (Slice 0)

**Project:** Bharat Investor Copilot (SANGYAN 2026 Hackathon — IIT BHU)  
**File:** `docs/compare_documents_api_contracts.md`  
**Status:** Approved Specification (Slice 0 Deliverable)  
**Author:** Senior Software Architect, Backend Architect, Frontend Architect & Security Reviewer  

---

## 1. Global API Conventions & Security Standards

### 1.1 Base Path & Protocol
- All Compare Documents endpoints are mounted with prefix: `/api/compare`
- Data transport: JSON (`application/json`) for standard payloads; `multipart/form-data` for file uploads; binary streams (`image/png`, `application/pdf`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) for media and exports.

### 1.2 Authentication & Capability Token Handling
- **Header:** `X-Session-Token: <token>` is strictly required on all session endpoints (`/session/{id}/*`).
- **Query Parameter Rejection:** Any request containing `token` or `session_token` in query parameters (e.g., `?token=...`) is immediately rejected with `HTTP 400 Bad Request` to prevent leakage into browser history, server access logs, and HTTP Referer headers.
- **Server Verification:** Tokens are verified in constant time (`hmac.compare_digest`) against the stored SHA-256 hash.

### 1.3 Consistent Error Response Format
All 4xx and 5xx errors return a standardized JSON schema:
```json
{
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human-readable description in selected language",
    "details": {},
    "timestamp": "2026-11-23T18:00:00Z"
  }
}
```

---

## 2. The 17 Complete Endpoint Specifications

---

### Endpoint 1: Create Comparison Session
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session`
- **Purpose:** Initializes an ephemeral comparison session, issues the 256-bit client capability token, and allocates the isolated disk directory.
- **Auth:** None (initialization endpoint).
- **Request Body:**
  ```json
  {
    "comparison_mode": "QUICK_COMPARE"
  }
  ```
  *(Optional: `"QUICK_COMPARE"` or `"MULTI_DOCUMENT"`)*
- **Response Schema:** `SessionCreatedResponse` (HTTP 201 Created)
  ```json
  {
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "session_token": "u4W7r-8Q9Z2y_kL0pM1nO2pQ3rS4tU5vW6xY7zA8bC0=",
    "comparison_mode": "QUICK_COMPARE",
    "idle_timeout_seconds": 1800,
    "absolute_timeout_seconds": 14400,
    "max_documents": 5
  }
  ```
- **State Transition:** `[*] ➔ INITIALIZED`
- **Security:** Token generated via `secrets.token_urlsafe(32)`. Only SHA-256 hash is saved server-side.

---

### Endpoint 2: Upload Documents
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session/{id}/upload`
- **Purpose:** Ingests 2 to 5 financial filings (PDF, Scanned PDF, PNG, JPG, DOCX, XLSX, XLS).
- **Auth:** Header `X-Session-Token` required.
- **Request Schema:** `multipart/form-data`
  - `files`: Array of file binaries (min 2, max 5).
  - `gemini_consent_acknowledged`: String `"true"` | `"false"` (default `"false"`).
- **Validation Rules:**
  - File size: $\le 20\text{ MiB}$ per file.
  - Total upload: $\le 100\text{ MiB}$ across all files.
  - Supported signatures verified by magic bytes (`%PDF-`, `PK\x03\x04`, `\xD0\xCF\x11\xE0`, `\x89PNG`, `\xFF\xD8\xFF`).
- **Response Schema:** `UploadSuccessResponse` (HTTP 200 OK)
  ```json
  {
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "uploaded_documents": [
      {
        "doc_id": "doc_a",
        "slot": "doc_a",
        "original_filename": "TataMotors_Q3_FY24.pdf",
        "file_format": "PDF_DIGITAL",
        "file_size_bytes": 4829104,
        "page_count": 38,
        "is_scanned": false
      },
      {
        "doc_id": "doc_b",
        "slot": "doc_b",
        "original_filename": "MarutiSuzuki_Q3_FY24.pdf",
        "file_format": "PDF_DIGITAL",
        "file_size_bytes": 3910240,
        "page_count": 32,
        "is_scanned": false
      }
    ],
    "consent_granted": false
  }
  ```
- **State Transition:** `INITIALIZED ➔ FILES_UPLOADED`
- **Errors:** 400 (Bad file type/corrupt signature), 413 (File exceeds 20 MiB), 401 (Invalid token).

---

### Endpoint 3: Retry Single Document Slot
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session/{id}/retry/{doc_id}`
- **Purpose:** Replaces a corrupted or unreadable document in a single slot without invalidating other uploaded documents.
- **Auth:** Header `X-Session-Token` required.
- **Request Schema:** `multipart/form-data` with single `file`.
- **Response Schema:** `ComparisonDocument` (HTTP 200 OK)
- **State Transition:** Updates document record; re-triggers local Stage 1 metadata extraction for that slot.

---

### Endpoint 4: Get Identified Metadata
- **HTTP Method:** `GET`
- **Path:** `/api/compare/session/{id}/metadata`
- **Purpose:** Returns automatically extracted institutional metadata (Company, Period, FY, Quarter, Currency, Accounting standard, Audit status, Scope).
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `SessionMetadataResponse` (HTTP 200 OK)
  ```json
  {
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "metadata": {
      "doc_a": {
        "doc_id": "doc_a",
        "company_name": "Tata Motors Limited",
        "document_type": "Quarterly Financial Results",
        "financial_year": "FY 2023-24",
        "reporting_period": "Q3",
        "quarter": "Q3",
        "currency": "INR",
        "accounting_standard": "Ind AS",
        "reporting_scope": "CONSOLIDATED",
        "audit_status": "AUDITED",
        "is_user_overridden": false
      },
      "doc_b": {
        "doc_id": "doc_b",
        "company_name": "Maruti Suzuki India Limited",
        "document_type": "Quarterly Financial Results",
        "financial_year": "FY 2023-24",
        "reporting_period": "Q3",
        "quarter": "Q3",
        "currency": "INR",
        "accounting_standard": "Ind AS",
        "reporting_scope": "CONSOLIDATED",
        "audit_status": "AUDITED",
        "is_user_overridden": false
      }
    }
  }
  ```

---

### Endpoint 5: Update / Override Metadata
- **HTTP Method:** `PUT`
- **Path:** `/api/compare/session/{id}/metadata/{doc_id}`
- **Purpose:** Allows the user to inspect and correct identified company names, fiscal periods, currencies, or reporting scopes.
- **Auth:** Header `X-Session-Token` required.
- **Request Body:**
  ```json
  {
    "company_name": "Tata Motors Ltd",
    "reporting_period": "Q3",
    "financial_year": "FY 2023-24",
    "currency": "INR",
    "reporting_scope": "CONSOLIDATED"
  }
  ```
- **Response Schema:** Updated `DocumentMetadata` with `is_user_overridden: true` (HTTP 200 OK).

---

### Endpoint 6: Validate Compatibility
- **HTTP Method:** `GET`
- **Path:** `/api/compare/session/{id}/compatibility`
- **Purpose:** Executes the deterministic compatibility rules matrix across all uploaded documents.
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `CompatibilityReport` (HTTP 200 OK)
  ```json
  {
    "is_comparable": true,
    "blocker_count": 0,
    "warning_count": 1,
    "findings": [
      {
        "finding_id": "warn_01",
        "severity": "WARNING",
        "code": "PERIOD_DURATION_DIFFERENCE",
        "title": "Period Duration Difference",
        "description": "Document A reports Q3 (3 months) while Document B reports 9-Month Cumulative figures.",
        "affected_document_ids": ["doc_a", "doc_b"],
        "remediation_hint": "Comparison will isolate quarterly P&L from cumulative cash flow metrics."
      }
    ]
  }
  ```

---

### Endpoint 7: Grant AI Consent
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session/{id}/consent`
- **Purpose:** Records user agreement for external AI cloud processing, unlocking synthesis, translation, and chat.
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `{"consent_granted": true, "updated_at": "2026-11-23T18:05:00Z"}` (HTTP 200 OK).

---

### Endpoint 8: Withdraw AI Consent
- **HTTP Method:** `DELETE`
- **Path:** `/api/compare/session/{id}/consent`
- **Purpose:** Revokes AI consent, terminates running cloud requests, purges cached AI summaries, and reverts session to Local Mode.
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `{"consent_granted": false, "message": "AI processing halted. Reverted to Local Mode."}` (HTTP 200 OK).

---

### Endpoint 9: Initiate Processing Pipeline
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session/{id}/process`
- **Purpose:** Triggers the asynchronous background comparison pipeline (metric extraction, conflict resolution, Decimal arithmetic, synthesis).
- **Auth:** Header `X-Session-Token` required.
- **Request Body:**
  ```json
  {
    "language": "Hindi"
  }
  ```
- **Response Schema:** `{"status": "PROCESSING", "current_stage": "EXTRACTING_FINANCIAL_DATA"}` (HTTP 202 Accepted).
- **State Transition:** `FILES_UPLOADED ➔ PROCESSING`

---

### Endpoint 10: Get Processing Status
- **HTTP Method:** `GET`
- **Path:** `/api/compare/session/{id}/status`
- **Purpose:** Polls genuine stage progression; enables recovery upon frontend page refresh.
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `ProcessingStatus` (HTTP 200 OK)
  ```json
  {
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "current_stage": "RESOLVING_CONFLICTS",
    "completed_stages": [
      "UPLOADING",
      "EXTRACTING_TEXT_TABLES",
      "IDENTIFYING_METADATA",
      "VALIDATING_COMPATIBILITY",
      "EXTRACTING_FINANCIAL_DATA"
    ],
    "stage_message": "Applying 8-factor context-aware priority rules to extracted metrics...",
    "is_cancelled": false,
    "is_completed": false,
    "error": null
  }
  ```

---

### Endpoint 11: Cancel Processing Pipeline
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session/{id}/cancel`
- **Purpose:** Propagates cancellation across async tasks, thread pools, and external requests, wiping in-flight temporary artifacts.
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `{"status": "CANCELLED", "message": "Pipeline halted successfully. Storage cleaned."}` (HTTP 200 OK).
- **State Transition:** `PROCESSING ➔ CANCELLED`

---

### Endpoint 12: Get Comparison Results
- **HTTP Method:** `GET`
- **Path:** `/api/compare/session/{id}/results`
- **Query Params:** `mode=matrix` | `mode=pairwise&base=doc_a&target=doc_b` (default `matrix`).
- **Purpose:** Delivers complete financial matrix, Decimal variances, conflict resolution logs, and 8-section synthesis.
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `ComparisonResult` (HTTP 200 OK).

---

### Endpoint 13: Get Evidence Page Image
- **HTTP Method:** `GET`
- **Path:** `/api/compare/session/{id}/evidence/{doc_id}/page/{num}`
- **Purpose:** Delivers rendered 150 DPI PNG of requested page for side-by-side evidence viewer with highlighted snippet bounds.
- **Auth:** Header `X-Session-Token` required.
- **Response:** Binary image stream (`image/png`, HTTP 200 OK).
- **Errors:** 400 (Non-renderable format like DOCX/XLSX), 404 (Page number out of bounds or document not found).

---

### Endpoint 13.1: Get Evidence Structured Context
- **HTTP Method:** `GET`
- **Path:** `/api/compare/session/{id}/evidence/{doc_id}/context`
- **Purpose:** Delivers parsed structured extraction outcome (tables, sheet cells, text blocks) for non-rendered filings (DOCX, XLSX, XLS) and tabular evidence inspection.
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `DocumentExtractionResult` (HTTP 200 OK).
- **Errors:** 404 (Document extraction not found).

---

### Endpoint 14: Comparative Q&A Chat
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session/{id}/chat`
- **Purpose:** Answering user questions strictly grounded in comparison results; enforces SEBI non-advisory refusals.
- **Auth:** Header `X-Session-Token` required.
- **Request Body:**
  ```json
  {
    "message": "Which company reported higher revenue growth?",
    "language": "English"
  }
  ```
- **Response Schema:** `ComparisonChatMessage` (HTTP 200 OK)
  ```json
  {
    "message_id": "msg_01",
    "role": "assistant",
    "content": "Tata Motors reported revenue from operations of ₹110,577 Cr, representing an absolute growth of ₹5,200 Cr (+4.94%). In comparison, Maruti Suzuki reported ₹33,309 Cr (+14.56%).",
    "cited_evidence": [
      {
        "evidence_id": "ev_01",
        "doc_id": "doc_a",
        "document_name": "TataMotors_Q3_FY24.pdf",
        "page_number": 4,
        "verbatim_snippet": "Revenue from operations for the quarter stood at Rs 110,577 crores..."
      }
    ],
    "safety_disclaimer": "This is an educational comparison grounded in the uploaded documents and does not constitute investment advice."
  }
  ```

---

### Endpoint 15: Export PDF Report
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session/{id}/export/pdf`
- **Purpose:** Compiles and streams a high-fidelity comparative PDF report.
- **Auth:** Header `X-Session-Token` required.
- **Response:** Binary stream (`application/pdf`, HTTP 200 OK).

---

### Endpoint 16: Export 7-Tab Excel Workbook
- **HTTP Method:** `POST`
- **Path:** `/api/compare/session/{id}/export/xlsx`
- **Purpose:** Generates formatted 7-tab Excel workbook (`Executive Summary`, `Financial Metrics`, `Calculations`, `Risks & Disclosures`, `Accounting Differences`, `Source Evidence`, `Verification Results`).
- **Auth:** Header `X-Session-Token` required.
- **Response:** Binary stream (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, HTTP 200 OK).

---

### Endpoint 17: Delete Session & Cleanup
- **HTTP Method:** `DELETE`
- **Path:** `/api/compare/session/{id}`
- **Purpose:** Explicit session termination; recursively purges temporary filesystem directories and evicts token from memory.
- **Auth:** Header `X-Session-Token` required.
- **Response Schema:** `{"status": "DELETED", "message": "Session storage wiped cleanly."}` (HTTP 200 OK).
- **State Transition:** `* ➔ EXPIRED / DELETED`

---

## 3. Slice 4 Additions: Modular Stage-Level Financial Endpoints

The following two endpoints are additive diagnostic and stage-inspection contracts introduced in Slice 4. They preserve all 17 approved core contracts intact and enable modular frontend and testing verification of the financial extraction, arbitration, and calculation engines prior to full synthesis aggregation in `GET /results` (Endpoint 12).

---

### Endpoint 4.1: Get Extracted Session Financial Values & Conflict Resolutions
- **HTTP Method:** `GET`
- **Path:** `/api/compare/session/{id}/financials`
- **Purpose:** Returns the extracted and arbitrated financial metrics across all documents in the session, including value candidates, evidence citations, and explainable 8-factor conflict resolutions.
- **Auth:** Header `X-Session-Token` strictly required.
- **Response Schema:** `SessionFinancialsResponse` (HTTP 200 OK)
  ```json
  {
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "financial_values": {
      "REVENUE": {
        "doc_a": {
          "doc_id": "doc_a",
          "metric_key": "REVENUE",
          "label": "Revenue from Operations",
          "amount": "110577.0000",
          "reported_amount": "110577.00",
          "display_amount": "₹1,10,577.00 Cr",
          "unit": "INR_CRORE",
          "currency": "INR",
          "status": "REPORTED",
          "reporting_scope": "CONSOLIDATED",
          "fact_classification": "DOCUMENT_FACT"
        }
      }
    },
    "all_candidates": {
      "doc_a": [
        {
          "candidate_id": "cand_01",
          "metric_key": "REVENUE",
          "raw_text_value": "110,577",
          "normalized_amount": "110577.0000",
          "normalized_unit": "INR_CRORE",
          "reporting_scope": "CONSOLIDATED",
          "audit_status": "AUDITED"
        }
      ]
    },
    "conflicts": {
      "doc_a": {
        "REVENUE": {
          "conflict_id": "conf_01",
          "metric_key": "REVENUE",
          "status": "RESOLVED_AUTOMATIC",
          "resolution_reason": "Single authoritative disclosure identified in PROFIT_AND_LOSS."
        }
      }
    }
  }
  ```
- **Errors:** 401/403 (Invalid token), 404 (Session not found), 410 (Session expired).

---

### Endpoint 4.2: Get Pairwise Financial Calculations
- **HTTP Method:** `GET`
- **Path:** `/api/compare/session/{id}/calculations`
- **Purpose:** Delivers pairwise mathematical variances (absolute difference and percentage change) computed deterministically via `decimal.Decimal` with directional explanations for non-positive base transitions (Turnaround, Downturn, Loss reduction, Loss expansion) or blockers.
- **Auth:** Header `X-Session-Token` strictly required.
- **Response Schema:** `SessionCalculationsResponse` (HTTP 200 OK)
  ```json
  {
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "variances": [
      {
        "metric_key": "REVENUE",
        "label": "Revenue from Operations",
        "base_doc_id": "doc_a",
        "comparison_doc_id": "doc_b",
        "base_value": "105377.0000",
        "comparison_value": "110577.0000",
        "formula": "(comparison - base)",
        "absolute_variance": "5200.0000",
        "percentage_change": "4.9347",
        "display_absolute_variance": "₹5,200.00 Cr",
        "display_percentage_change": "+4.93%",
        "unit": "INR_CRORE",
        "status": "CALCULATED",
        "directional_explanation": null
      }
    ],
    "pairwise_matrix_summary": {
      "doc_a__doc_b": "CALCULATED"
    }
  }
  ```
- **Errors:** 401/403 (Invalid token), 404 (Session not found), 410 (Session expired).
