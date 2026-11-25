# Bharat Investor Copilot — Compare Documents
## Comprehensive Requirements Traceability Matrix (Slice 0)

**Project:** Bharat Investor Copilot (SANGYAN 2026 Hackathon — IIT BHU)  
**File:** `docs/compare_documents_traceability_matrix.md`  
**Status:** Approved Specification (Slice 0 Deliverable)  
**Author:** Senior Software Architect, Backend Architect, Frontend Architect & Security Reviewer  

---

## 1. Traceability Mapping

This matrix maps every approved requirement to its authoritative data schema, API contract, implementation slice, required verification tests, and acceptance criteria.

| Req ID | Category | Requirement Description | Relevant Schemas | API Endpoints | Implementation Slice | Required Automated Test Suite | Acceptance Criteria | Status |
|---|---|---|---|---|---|---|---|---|
| `SCN-01` | Scenario | Same company across financial years | `ComparisonResult`, `CalculationResult` | `POST /process`, `GET /results` | Slice 3, Slice 4, Slice 9 | `tests/test_slice9_e2e_integration.py` | Calculates inter-year variances; identifies FY periods accurately | `VERIFIED` |
| `SCN-02` | Scenario | Same company across quarters | `DocumentMetadata`, `CalculationResult` | `POST /process`, `GET /results` | Slice 3, Slice 4, Slice 9 | `tests/test_slice9_e2e_integration.py` | Compares sequential quarters without quarterly duration mismatch errors | `VERIFIED` |
| `SCN-03` | Scenario | Different companies in same industry | `DocumentMetadata`, `CompatibilityReport` | `GET /compatibility`, `GET /results` | Slice 3, Slice 4, Slice 9 | `tests/test_slice9_e2e_integration.py` | Detects distinct companies, validates common currency/units | `VERIFIED` |
| `SCN-04` | Scenario | IPO prospectus vs IPO prospectus | `DocumentMetadata`, `RiskDisclosure` | `POST /process`, `GET /results` | Slice 3, Slice 5 | `tests/test_slice3_metadata_compatibility.py` | Extracts issue details, objectives, and disclosed risks | `VERIFIED` |
| `SCN-05` | Scenario | Annual report vs quarterly report | `CompatibilityFinding`, `Severity: WARNING` | `GET /compatibility` | Slice 3, Slice 9 | `tests/test_slice9_e2e_integration.py` | Triggers explicit non-blocking WARNING about differing durations | `VERIFIED` |
| `FMT-01` | Format | Digital PDF extraction | `ComparisonDocument`, `EvidenceReference` | `POST /upload` | Slice 2, Slice 9 | `tests/test_slice9_e2e_integration.py` | PyMuPDF extracts text, tables, and exact page bounding boxes | `VERIFIED` |
| `FMT-02` | Format | Scanned PDF extraction | `ComparisonDocument`, `is_scanned: True` | `POST /upload` | Slice 2, Slice 9 | `tests/test_slice9_e2e_integration.py` | Flags low text density; reports OCR_UNAVAILABLE_LOCAL_MODE | `VERIFIED` |
| `FMT-03` | Format | PNG image extraction | `ComparisonDocument`, `IMAGE_PNG` | `POST /upload` | Slice 2, Slice 9 | `tests/test_slice9_e2e_integration.py` | Ingests image; reports VISION_EXTRACTION_REQUIRED in Local Mode | `VERIFIED` |
| `FMT-04` | Format | JPG image extraction | `ComparisonDocument`, `IMAGE_JPEG` | `POST /upload` | Slice 2, Slice 9 | `tests/test_slice9_e2e_integration.py` | Validates JFIF magic bytes; reports VISION_EXTRACTION_REQUIRED in Local Mode | `VERIFIED` |
| `FMT-05` | Format | JPEG image extraction | `ComparisonDocument`, `IMAGE_JPEG` | `POST /upload` | Slice 2, Slice 9 | `tests/test_slice9_e2e_integration.py` | Validates JPEG magic bytes; reports VISION_EXTRACTION_REQUIRED in Local Mode | `VERIFIED` |
| `FMT-06` | Format | DOCX document extraction | `ComparisonDocument`, `structural_ref` | `POST /upload` | Slice 2, Slice 9 | `tests/test_slice9_e2e_integration.py` | Parses `w:p` paragraphs and `w:tbl` tables via standard OpenXML | `VERIFIED` |
| `FMT-07` | Format | XLSX spreadsheet extraction | `ComparisonDocument`, `sheet_names` | `POST /upload` | Slice 2, Slice 9 | `tests/test_slice9_e2e_integration.py` | Reads with `data_only=True`; handles merged cells & formula cache | `VERIFIED` |
| `FMT-08` | Format | XLS legacy spreadsheet extraction | `ComparisonDocument`, `XLS` | `POST /upload` | Slice 2, Slice 9 | `tests/test_slice9_e2e_integration.py` | Reads BIFF8 via `xlrd`; handles sheets and numerical cells | `VERIFIED` |
| `MOD-01` | Mode | Quick Compare (2 documents) | `ComparisonSession`, `QUICK_COMPARE` | `POST /session`, `POST /upload` | Slice 1, Slice 6, Slice 9 | `tests/test_slice9_e2e_integration.py` | Strictly enforces exactly two documents; 1 or 3 rejected (400) | `VERIFIED` |
| `MOD-02` | Mode | Multi-Document Compare (up to 5 docs) | `ComparisonSession`, `MULTI_DOCUMENT` | `POST /session`, `POST /upload` | Slice 1, Slice 6, Slice 9 | `tests/test_slice9_e2e_integration.py` | Ingests 2-5 docs; 6 rejected (400); generates full pairwise matrix | `VERIFIED` |
| `OUT-01` | Output | Executive summary | `ExecutiveSummary` | `GET /results` | Slice 5 | `tests/test_slice5_synthesis.py` | Assembles high-level narrative grounded in extracted facts | `VERIFIED` |
| `OUT-02` | Output | Side-by-side comparison tables | `FinancialValue`, `CalculationResult` | `GET /results` | Slice 6, Slice 9 | `tests/test_slice9_e2e_integration.py` | Normalized numbers with variance badges and unit consistency | `VERIFIED` |
| `OUT-03` | Output | Automatically identified metrics | `FinancialMetric`, `ValueCandidate` | `POST /process`, `GET /financials` | Slice 4 | `tests/test_slice4_financial_engine.py` | Discovers Revenue, PAT, EBITDA, Debt, Assets without manual selection | `VERIFIED` |
| `OUT-04` | Output | Absolute variance calculation | `CalculationResult`, `absolute_variance` | `POST /process`, `GET /calculations` | Slice 4, Slice 9 | `tests/test_slice9_e2e_integration.py` | Exact `decimal.Decimal` subtraction; 2-place display precision | `VERIFIED` |
| `OUT-05` | Output | Percentage change calculation | `CalculationResult`, `percentage_change` | `POST /process`, `GET /calculations` | Slice 4, Slice 9 | `tests/test_slice9_e2e_integration.py` | Implements zero denominator & negative base loss-to-profit rules | `VERIFIED` |
| `OUT-06` | Output | Responsive financial charts | Native SVG rendering contracts | Frontend Client | Slice 6 | `app/test_slice6_frontend.mjs` | Native SVG bar & column charts without external dependencies | `VERIFIED` |
| `OUT-07` | Output | Positive, negative, neutral, uncertain | `ChangeClassification` | `GET /results` | Slice 5 | `tests/test_slice5_synthesis.py` | Factual classification; zero investment recommendation phrasing | `VERIFIED` |
| `OUT-08` | Output | Disclosed risks & warning signals | `RiskDisclosure` | `GET /results` | Slice 5 | `tests/test_slice5_synthesis.py`| Categorizes operational, financial, and regulatory risks | `VERIFIED` |
| `OUT-09` | Output | Accounting policy differences | `AccountingDifference` | `GET /results` | Slice 5 | `tests/test_slice5_synthesis.py` | Highlights depreciation, lease, and revenue recognition differences | `VERIFIED` |
| `OUT-10` | Output | Page-level evidence citations | `EvidenceReference` | `GET /results`, `GET /evidence` | Slice 7, Slice 9 | `tests/test_slice9_e2e_integration.py` | Unbreakable chain of custody; page render, bounding box, cell range, and arbitration inspector | `VERIFIED` |
| `OUT-11` | Output | Trilingual explanations (EN/HI/Hinglish)| `translations.ts`, `compare_translator.py` | `POST /process` | Slice 5, Slice 6, Slice 9 | `app/test_slice9_frontend.mjs` | Equal depth and natural vocabulary across all 3 languages | `VERIFIED` |
| `OUT-12` | Output | High-fidelity PDF report export | CSS `@media print` + PyMuPDF | `POST /export/pdf` | Slice 8, Slice 9 | `tests/test_slice9_e2e_integration.py` | Multi-page publication-quality PDF with Devanagari Hindi font support | `VERIFIED` |
| `OUT-13` | Output | Formatted 7-tab Excel workbook export | `export_excel_service.py` (`openpyxl`) | `POST /export/xlsx` | Slice 8, Slice 9 | `tests/test_slice9_e2e_integration.py` | Generates all 7 approved worksheets with static numbers, filters, and frozen panes | `VERIFIED` |
| `OUT-14` | Output | Grounded comparative chat | `ComparisonChatMessage` | `POST /chat` | Slice 5, Slice 9 | `tests/test_slice9_e2e_integration.py` | Answers comparative questions citing documents; refuses advice | `VERIFIED` |
| `CON-01` | Conflict | Context-aware automatic resolution | `ConflictResolution`, `ValueCandidate` | `POST /process`, `GET /financials` | Slice 4 | `tests/test_slice4_financial_engine.py`| 8-factor hierarchy resolves discrepancies; unresolvable marked UNCERTAIN | `VERIFIED` |
| `VER-01` | Registry | External official verification | `VerificationResult` | `POST /process` | Slice 5 | `tests/test_slice5_synthesis.py` | SEBI/NSE checks labelled SIMULATED / NOT_AVAILABLE; no live external calls; not verified against external sources | `SIMULATED` |
| `PRV-01` | Privacy | Local Mode (zero cloud invocations) | `consent_granted: False` | All Endpoints | Slice 1, Slice 9 | `tests/test_slice9_e2e_integration.py` | All tables, math, and charts operate 100% offline | `VERIFIED` |
| `PRV-02` | Privacy | AI Consent & immediate revocation | `POST /consent`, `DELETE /consent` | Slice 1, Slice 9 | `tests/test_slice9_e2e_integration.py` | Immediate revocation drops cloud jobs and flushes AI cache | `VERIFIED` |
| `SEC-01` | Security | 256-bit hashed capability tokens | `secrets.token_urlsafe(32)`, `hmac` | `All /session/{id}/*` | Slice 1, Slice 9 | `tests/test_slice9_e2e_integration.py` | Tokens validated in constant time; rejected in query strings | `VERIFIED` |
| `SEC-02` | Security | Dual backend timeouts (30m / 4h) | `expires_at`, `idle_timeout_at` | Session Store | Slice 1 | `tests/test_slice1_security.py` | Lazy check and 5-min background sweeper delete expired directories | `VERIFIED` |
| `SEC-03` | Security | Ephemeral filesystem isolation | `temporary_compare_storage/session_<uuid>`| Backend FS | Slice 1, Slice 9 | `tests/test_slice9_e2e_integration.py` | Internal UUID paths; unlinked on session deletion and startup | `VERIFIED` |
| `SAF-01` | Safety | SEBI non-advisory refusal guardrails | System prompts in `chat_service.py` | `POST /chat` | Slice 5, Slice 9 | `tests/test_slice9_e2e_integration.py` | Firmly refuses buy/sell/hold/target requests; redirects educationally | `VERIFIED` |
| `REG-01` | Intact | Existing single-doc regression protection| `routes.py`, `Workspace.tsx` | App Root | All Slices, Slice 9 | `tests/test_slice9_e2e_integration.py` | Single-document upload and Q&A remain 100% operational | `VERIFIED` |
| `BUD-01` | Budget | Strict ₹0 budget compliance | Local packages + Gemini Free Tier | All Slices | All Slices, Slice 9 | Audit check | Zero paid dependencies or cloud billing services introduced | `VERIFIED` |
