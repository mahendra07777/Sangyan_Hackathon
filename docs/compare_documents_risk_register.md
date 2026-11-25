# Bharat Investor Copilot — Compare Documents
## Integration Analysis & Risk Register (Slice 0)

**Project:** Bharat Investor Copilot (SANGYAN 2026 Hackathon — IIT BHU)  
**File:** `docs/compare_documents_risk_register.md`  
**Status:** Approved Specification (Slice 0 Deliverable)  
**Author:** Senior Software Architect, Backend Architect, Frontend Architect & Security Reviewer  

---

## 1. Existing Code Reuse Inventory

The Compare Documents feature is architected to maximize reuse of existing, verified repository assets without duplication:

1. **Layout & Shell:** [app/src/components/layout/Header.tsx](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/app/src/components/layout/Header.tsx) and [AppLayout.tsx](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/app/src/components/layout/AppLayout.tsx) provide the header bar, logo, and language picker trigger.
2. **UI Kit Primitives:** [Button.tsx](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/app/src/components/ui/Button.tsx), [Card.tsx](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/app/src/components/ui/Card.tsx), and [Badge.tsx](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/app/src/components/ui/Badge.tsx) are used directly across all new Compare panels.
3. **Reactive Trilingual Dictionary:** Global state management in [app/src/App.tsx](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/app/src/App.tsx#L14-L38) and the string lookup engine in [translations.ts](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/app/src/lib/translations.ts) are extended with Compare-specific keys without altering single-document dictionary entries.
4. **PyMuPDF Document Extraction:** PyMuPDF (`fitz`) routines in [document_processor.py](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/backend/app/services/document_processor.py#L113-L140) provide the baseline for text block and page rasterization logic.
5. **Safety Classification & Refusal Prompting:** The SEBI non-advisory refusal patterns in [chat_service.py](file:///C:/Users/mayur/.gemini/antigravity/scratch/Sangyan_Hackathon_Fresh/backend/app/services/chat_service.py#L48-L54) serve as the foundation for multi-document comparative Q&A safety.

---

## 2. Comprehensive Risk Register

| Risk ID | Risk Domain | Description | Impact | Likelihood | Mitigation Strategy & Architectural Guardrail | Implementation Slice |
|---|---|---|---|---|---|---|
| `RSK-01` | Backward Compatibility | Accidental mutation of existing single-doc upload routes or models | High | Low | Isolate Compare completely in `/api/compare/*` and `backend/app/models/comparison.py`. Mount `compare_router` independently in `main.py`. Run regression tests. | Slices 1–9 |
| `RSK-02` | Security (Tokens) | Leakage of session capability tokens in URLs or browser history | Critical | Low | Reject any request containing `token` or `session_token` in query parameters with HTTP 400. Enforce header `X-Session-Token` exclusively. Redact in logs. | Slice 1 |
| `RSK-03` | Security (Filesystem) | Path traversal attacks via malicious filenames (e.g. `../../etc/passwd`) | Critical | Low | Sanitize all filenames via regex (`[^a-zA-Z0-9_.-]`); verify `Path.resolve().is_relative_to(session_dir)`. Store on disk using internal UUIDs. | Slice 1, Slice 2 |
| `RSK-04` | Security (Archive) | ZIP bomb or nested archive expansion attacks in DOCX / XLSX | High | Medium | Inspect uncompressed archive size before extraction; enforce 50 MiB uncompressed limit and max 10:1 compression ratio check. | Slice 2 |
| `RSK-05` | Data Integrity (Math) | Floating-point rounding inaccuracies in financial variances | High | Low | Execute all additions, variances, and ratios strictly using Python `decimal.Decimal` with 4-place internal and 2-place display precision. | Slice 4 |
| `RSK-06` | Data Integrity (Conflicts) | LLM silently picking conflicting numbers across footnotes/tables | High | Low | Pure deterministic Python 8-factor source-priority hierarchy. Equal-priority candidates are marked `UNCERTAIN` for user review. Gemini is barred from math. | Slice 4 |
| `RSK-07` | Resource Limits (Memory) | Heap exhaustion when processing five 200-page annual reports | High | Medium | Process documents sequentially or bounded by `asyncio.Semaphore(2)`. Page rasterization executed on-demand per HTTP request, not buffered in RAM. | Slice 2, Slice 7 |
| `RSK-08` | Resource Limits (API) | Gemini Free-Tier HTTP 429 rate limit during multi-doc synthesis | Medium | Medium | Wrap Gemini calls in `tenacity` exponential backoff (1s, 2s, 4s, 8s, up to 5 attempts). Degrade gracefully to Local Mode if quota exhausts. | Slice 5 |
| `RSK-09` | Cancellation | In-flight background threads or external HTTP calls lingering after cancel | Medium | Medium | Multi-layer cancellation: check cooperative `cancel_event` between pages/sheets; abort `httpx` sockets; unlink partial files in `finally:` block. | Slice 1 |
| `RSK-10` | Dependency (XLS) | Legacy binary `.xls` files unparseable if `xlrd` missing | Medium | High | `xlrd` is absent in fresh host environment. Documented as an implementation-time dependency to install in Slice 2 (`pip install xlrd`). | Slice 2 |
| `RSK-11` | Dependency (OCR) | Local scanned OCR unavailable without host Tesseract binary | Medium | High | Tesseract is absent on host PATH. In Local Mode, flag `OCR_UNAVAILABLE_LOCAL_MODE` without crashing; in AI Mode, leverage Gemini Vision. | Slice 2 |
| `RSK-12` | Export Reliability | Missing Devanagari Hindi font glyphs in server-generated PDF | Medium | Medium | Adopt Client-Side CSS Paged Media (`@media print`) as primary PDF engine, utilizing browser-native typography and infinite-DPI SVG chart printing. | Slice 8 |

---

## 3. Required Testing & Quality Assurance Plan

Every slice will follow strict Red-Green test-driven development:
1. **Security & Boundary Test Suite:**
   - Query string token rejection (HTTP 400).
   - Tampered / expired token rejection (HTTP 401 / 410).
   - Filename path traversal sanitization.
   - Multipart payload limits (20 MiB per file, 100 MiB total).
2. **Financial Precision Test Suite:**
   - Decimal exactness ($10.50 - 5.25 = 5.25$).
   - Zero denominator handling (`DIV_BY_ZERO`).
   - Negative base loss-to-profit transition validation (`NON_POSITIVE_BASE`).
   - Missing value propagation (`NOT_DISCLOSED`).
3. **Conflict Engine Test Suite:**
   - Audited superseding unaudited.
   - Schedules superseding narrative commentary.
   - Restatements superseding historical disclosures.
   - Entity scope mismatch triggering warning without data destruction.
4. **Lifecycle & Cancellation Test Suite:**
   - Inactivity timeout sweeping after 30 minutes.
   - In-flight cancellation purging partial disk artifacts.
   - Startup hook purging orphan session directories.
5. **Trilingual Parity Test Suite:**
   - 100% key parity across English, Hindi, and Hinglish.
   - Zero raw untranslated enum keys in client views.
