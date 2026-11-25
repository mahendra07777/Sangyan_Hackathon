# Bharat Investor Copilot — Project Status & Competition Report

> **Live project tracker & competition readiness status for Bharat Investor Copilot.**  
> **Competition:** SANGYAN 2026 — IIT BHU  
> **Core Principle:** **UNDERSTANDING BEFORE ACTION**  
> **Last Updated:** November 2026 (Phase 8 Final Implementation)  
> **Current Status:** All 8 Engineering & Delivery Phases Completed (100% Phase Scope)  

---

## 1. Project Purpose & Core Philosophy

**Bharat Investor Copilot** is an educational, neutral, and evidence-grounded financial document analysis and multi-document comparison platform built for Indian retail investors, students, and citizens.

### Foundational Principles:
- **UNDERSTANDING BEFORE ACTION:** Retail investors are routinely bombarded with speculative stock tips, buy/sell/hold ratings, and complex jargon. Bharat Investor Copilot exists to foster comprehension, not speculation.
- **Strictly Non-Advisory:** The platform NEVER provides buy, sell, or hold recommendations, stock rankings, price targets, guaranteed returns, or portfolio suitability claims.
- **Evidence-Grounded (Provenance First):** Every extracted financial metric and computed variance links directly back to primary source document citations (page number, bounding box coordinates, and source text excerpt).
- **₹0 Budget, Local-First Architecture:** Operates entirely without paid cloud infrastructure, proprietary APIs, or subscription services. All ingestion, parsing, arithmetic, and export compilation execute locally.

---

## 2. Overall Phase Tracker

### Feature Track: Compare Documents (SANGYAN 2026)

| Phase | Description | Status | Verification Baseline |
|---|---|---|---|
| **Phase 1** | Security, Ingestion & Ephemeral Token Store | 🟢 Complete | HMAC-SHA256 session auth, 2–5 file queue, 20/100 MiB limits |
| **Phase 2** | High-Precision Multi-Format Document Parsers | 🟢 Complete | PyMuPDF PDF parser, CSV, Excel, TXT, JSON, HTML, DOCX |
| **Phase 3** | Metadata Extraction & Compatibility Gate | 🟢 Complete | Fiscal year, currency, scale, scope, warnings & blockers |
| **Phase 4** | Deterministic Financial Engine & Canonical Keys | 🟢 Complete | 9 core metrics, Decimal arithmetic, conflict arbitration |
| **Phase 5** | High-Density Comparison Dashboard & SVG Charts | 🟢 Complete | Accessible SVG charts, baseline selector, neutral trends |
| **Phase 6** | Manual Financial Corrections & LIFO Undo | 🟢 Complete | `User entered` badges, dynamic recalculation, audit trail |
| **Phase 7** | UI Polish, Warnings, Accessibility & i18n | 🟢 Complete | 413 dictionary keys (EN/HI/Hinglish), dialog focus trap |
| **Phase 8** | Final Packaging, Demo Script & Bundle Optimization | 🟢 Complete | Sub-300 kB main chunk, 4-min demo script, sample guidance |

---

## 3. Actual System Architecture

```
[ User Browser: React 19 + TypeScript + Vite 8 + Tailwind CSS v4 ]
       │
       ├── Trilingual i18n Layer (English, Hindi, Hinglish — 413 keys)
       ├── CompareWorkflow State Machine (Upload ➔ Metadata ➔ Compare)
       ├── Accessible SVG Visualizations (Keyboard focusable, aria-labels)
       ├── EvidenceViewer Modal (Dialog role, focus trap, Escape restore)
       └── Export Triggers (Mutual exclusion guards, duplicate prevention)
       │
   (HTTP / REST with HMAC-SHA256 Authorization Headers)
       │
[ Local Backend: FastAPI / Python 3.12 ]
       │
       ├── Ephemeral Session Store (HMAC capability tokens, 2-hour TTL)
       ├── Multi-Format Document Parsers (PyMuPDF, openpyxl, csv, python-docx)
       ├── Metadata & Compatibility Engine (Temporal, currency, scope alignment)
       ├── PII Redactor (Regex masking of PAN, Aadhaar, CIN, DIN, accounts)
       ├── Deterministic Financial Engine (Python decimal.Decimal, ROUND_HALF_UP)
       ├── Audit Trail & Undo Stack (LIFO rollback, persistent original values)
       ├── Dual Export Generators (ReportLab PDF & openpyxl 7-tab Excel)
       └── Optional AI Synthesis Layer (Gemini API with affirmative user consent)
```

---

## 4. Major Implemented Features

1. **Multi-Document Upload & Validation:**
   - Ingestion of 2 to 5 disclosures concurrently across 8 file formats (`.pdf`, `.txt`, `.csv`, `.xlsx`, `.xls`, `.json`, `.html`, `.docx`).
   - Strict size governance: 20 MiB per-file limit, 100 MiB total session limit.
   - MIME type and magic-byte header validation preventing malicious payloads.

2. **Metadata Extraction & Compatibility Gate:**
   - Automated detection of entity names, fiscal periods (e.g. FY 2023-24), reporting currency (`INR`), accounting standards (`Ind AS`), and disclosure scope (`Consolidated` vs `Standalone`).
   - Real-time compatibility evaluation distinguishing non-blocking `WARNINGS` from hard `BLOCKERS`.

3. **Deterministic Financial Calculation Engine:**
   - 9 Standardized Core Metrics: Revenue, Net Profit (PAT), EBITDA Margin, Total Assets, Total Debt, Operating Cash Flow, Debt-to-Equity Ratio, ROE, Current Ratio.
   - 100% reproducible math utilizing Python `decimal.Decimal` with strict `ROUND_HALF_UP` rounding.
   - Zero hallucinated numbers: missing disclosures are explicitly flagged as `"Not disclosed"` rather than coerced to 0.

4. **Interactive Comparison Dashboard:**
   - Dynamic baseline selection re-anchoring all pairwise absolute ($\Delta$) and percentage ($\%$) variances on demand.
   - Directional neutral trends ($\uparrow$ / $\downarrow$ / $\text{—}$) without speculative green/red color bias.
   - Clickable numbers triggering the `EvidenceViewer` modal displaying exact page numbers, table rows, and bounding box overlays.

5. **Manual Financial Corrections & LIFO Undo:**
   - In-place correction of extracted figures with optional user audit notes.
   - Instant re-computation of dependent ratios and baseline variances.
   - Visual `User entered` badges with tooltips showing original extracted values.
   - Strict LIFO (Last-In, First-Out) undo banner to revert corrections safely.

6. **Dual Format Audited Exports:**
   - **Executive PDF Report:** Clean, printable executive summary with metadata, core financials, and disclaimers.
   - **7-Tab Audited Excel Workbook:** Complete institutional model (`Executive Summary`, `Core Financials`, `Extended Financials`, `Compatibility Matrix`, `Audit Trail`, `Source Provenance`, `Methodology & Disclaimers`).

7. **Trilingual Localization & Accessibility:**
   - Full 413-key parity across English, Hindi, and Hinglish.
   - WAI-ARIA dialog compliance (`role="dialog"`, `aria-modal="true"`), keyboard focus trapping, focus restoration, and Escape key listeners.

8. **Vite Bundle Optimization (Phase 8):**
   - Implemented Rollup `manualChunks` in `app/vite.config.ts`.
   - Main JavaScript bundle reduced from 522.11 kB to **289.41 kB** (gzip: 65.85 kB).
   - Zero chunks exceeding Vite's 500 kB limit.

---

## 5. Verified Test Baselines & Quality Metrics

All test suites and production build commands have been independently executed and verified in the environment:

| Test Suite | Commands Run | Tests Passed | Failures | Status | Execution Time |
|---|---|---|---|---|---|
| **Backend Unit & Integration Tests** | `python -m unittest discover tests` | **218** | 0 | 🟢 100% Pass | ~1.6s |
| **Frontend Test Suite (Slices 6–10)** | `node --test app/test_slice*.mjs` | **56** | 0 | 🟢 100% Pass | 141 ms |
| **Production Build** | `cd app && npm run build` | **Build OK** | 0 | 🟢 Zero Warnings | 690 ms |

### Build Asset Breakdown (Post-Optimization):
- `dist/index.html`: 0.71 kB (gzip: 0.36 kB)
- `dist/assets/index-BacIz6li.css`: 58.80 kB (gzip: 10.46 kB)
- `dist/assets/rolldown-runtime-CbXtAM7H.js`: 0.58 kB (gzip: 0.36 kB)
- `dist/assets/vendor-icons-HRXjh7vW.js`: 21.55 kB (gzip: 7.78 kB)
- `dist/assets/vendor-react-C8c3VSa6.js`: 210.99 kB (gzip: 65.84 kB)
- `dist/assets/index-BVlgQpkg.js`: **289.41 kB** (gzip: 65.85 kB) — *Reduced from 522.11 kB*

---

## 6. Honest Verified Limitations & Gaps

In adherence to the core rules of **NO FABRICATION**, **VERIFY BEFORE CLAIMING**, and **GAP-ROUND**, the following explicit limitations are documented:

1. **Live Browser Screenshots Across 5 Viewports Not Captured:**  
   Automated browser screenshot captures across responsive breakpoints (360px, 390px, 768px, 1024px, 1440px) could not be recorded programmatically due to Windows sandboxed process isolation preventing local child server console buffer probing. Responsive CSS grid classes (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`) were verified via DOM code analysis.
2. **Physical Screen Readers Not Tested:**  
   Assistive technology screen reader audio (NVDA, JAWS, VoiceOver) was not tested in this headless terminal development environment. While semantic HTML, ARIA dialog roles, focus management, and keyboard accessibility were validated in code, complete WCAG compliance is not claimed.
3. **Dynamic Multilingual AI Narrative Defaults to English:**  
   While static UI text maintains 100% parity across English, Hindi, and Hinglish via client-side dictionaries, dynamic AI narrative synthesis generated by the free-tier Gemini API returns English text unless an auxiliary backend translation service is configured.
4. **Simulated SEBI Verification:**  
   Official regulatory filing verification is simulated offline (`VerificationStatus.SIMULATED`). Live cryptographic verification against BSE/NSE/SEBI repositories requires institutional API credentials not available in a local zero-budget sandbox.
5. **Scanned PDF OCR Unsupported Offline:**  
   Document parsers rely on digital text layers and vector tables via PyMuPDF. Scanned image-only PDFs lacking embedded text layers cannot be OCR-processed without local Tesseract binaries or paid cloud vision APIs.
6. **Sample Documents Not Pre-Bundled:**  
   Public corporate annual reports are not pre-packaged in the repository to prevent copyright ambiguity. Evaluators should follow `sample_documents/README.md` to acquire public BSE/NSE filings for demonstration.
7. **No Institutional Deployment or Regulatory Certification:**  
   This software is an educational prototype developed for the SANGYAN 2026 hackathon. It has not been submitted for regulatory certification or institutional deployment.

---

## 7. Competition Demonstration Readiness

The platform is fully prepared for evaluation at SANGYAN 2026:
- **Demonstration Flow:** Detailed in `docs/demo-script.md` (Part 2), covering a strict 4-minute timed walkthrough with presenter actions, evaluator observations, speaking notes, and fallback recovery steps.
- **Local Startup Commands:**
  ```powershell
  # Terminal 1: Backend
  cd backend
  python main.py

  # Terminal 2: Frontend
  cd app
  npm run dev
  ```
- **Evaluator Sample Preparation:** Step-by-step instructions available in `sample_documents/README.md`.

---

## 8. Remaining Optional Post-Competition Improvements

These non-blocking enhancements can be explored after the competition:
1. **Local OCR Pipeline:** Bundle lightweight Tesseract.js or local Tesseract OCR binaries for scanned disclosures.
2. **Direct SEBI / Exchange Ingestion:** Connect to official BSE/NSE XBRL APIs using institutional data partner feeds.
3. **Client-Side WebAssembly Export:** Compile Excel and PDF generators to WebAssembly to eliminate any backend requirement for document compilation.
4. **Expanded Regional Languages:** Extend the 413-key dictionary to include Tamil, Telugu, Kannada, Bengali, and Marathi.
