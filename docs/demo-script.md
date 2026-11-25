# Demo Scenario (3-5 Minutes)

**Target Persona:** Kavita (39, Tier-2 homemaker)

## The Journey

1. **Introduction & Live Preview:**
   - Kavita opens the Bharat Investor Copilot.
   - She sees the premium "FINANCIAL INTELLIGENCE FOR BHARAT" interface.
   - She looks at the Live Preview showing how a number (Revenue) transforms into a simple explanation with source evidence.

2. **Upload:**
   - She uploads a company disclosure (PDF).
   - The UI shows a calm, clear progress state within the new Premium Fintech aesthetic.

3. **Understanding & Key Numbers:**
   - The system displays a high-density Document Intelligence workspace.
   - It highlights key facts extracted from the text in a horizontal strip (e.g., "Revenue ₹722,750 Mn").

4. **Impact Lens (The Signature Feature):**
   - She uses the Impact Lens to explore terms.
   - The interface visually transforms, showing a vertical reasoning path: Number -> Concept -> Why it matters -> Questions -> Evidence.
   - She clicks "Verify" to open the Evidence Drawer and see the exact source text and document reference.

5. **Language Switch & AI Answer Format:**
   - Kavita toggles the language to Hindi.
   - The "Ask Bharat" interface updates subtly ("आप क्या समझना चाहते हैं?").
   - She asks a question. The AI answers using the "Bharat Explains" editorial format, showing "Source • Page X" directly below.

6. **Voice Q&A:**
   - Kavita uses the new prominent voice interaction button.
   - She asks (in Hindi): "Does this mean the company is in debt?"
   - The system listens (shows recording state), processes, and responds, citing the source page.

7. **Safety Close:**
   - The demo concludes by showing the clear distinction between AI explanation and Source Fact.
   - Final message: *"We don't tell investors what to buy. We help them understand what they're looking at."*

---

# Part 2: Compare Documents Demonstration (SANGYAN 2026 — 4-Minute Presentation Flow)

**Target Audience:** SANGYAN 2026 Evaluators, Financial Literacy Educators, Retail Investors  
**Core Principle:** **UNDERSTANDING BEFORE ACTION**  
**Core Philosophy:** Educational, strictly non-advisory, provenance-grounded financial comparison.  
**Strict Safety Rule:** The tool NEVER provides buy/sell/hold recommendations, stock rankings, target prices, or portfolio suitability claims. External AI synthesis is strictly optional and requires affirmative user consent.

---

## 4-Minute Presentation Flow

```
0:00 ─── 0:30 : Introduction & "Understanding Before Action" Principle
0:30 ─── 1:00 : Multi-Document Upload (2–5 Filings, 20/100 MiB Boundaries)
1:00 ─── 1:30 : Metadata Review, Hierarchy & Compatibility Engine Gate
1:30 ─── 2:30 : Comparison Dashboard, Baseline Selection, Variance Math & Provenance Modal
2:30 ─── 3:15 : Manual Financial Correction, Instant Recalculation & LIFO Undo
3:15 ─── 3:45 : Dual Export: Executive PDF & 7-Tab Audited Excel Workbook
3:45 ─── 4:00 : Privacy-First Local Processing & Non-Advisory Closing
```

---

### Segment 1: 0:00–0:30 — Introduction & Core Philosophy

- **Presenter Action:**  
  1. Open the application landing page.
  2. Point to the top navigation header and the prominent banner: *"Understanding Before Action"*.
  3. Toggle the language selector between English, Hindi (हिन्दी), and Hinglish to demonstrate trilingual interface parity.
- **What Evaluators Should Observe:**  
  - Clean, high-density, neutral fintech interface without aggressive hype or stock trading cues.
  - Prominent educational disclaimer: strictly non-advisory, zero stock tips or target prices.
  - Responsive trilingual support with 100% dictionary coverage.
- **Speaking Notes:**  
  > *"Every quarter, millions of Indian retail investors face hundreds of pages of complex annual reports, DRHPs, and quarterly disclosures. They are bombarded with social media stock tips and opaque recommendations.*  
  > *Bharat Investor Copilot operates on a foundational principle: **Understanding Before Action**. We do not tell investors what to buy, sell, or hold. We provide an educational, deterministic, and verifiable lens so citizens can understand and compare corporate disclosures with mathematical certainty."*
- **Fallback / Troubleshooting:**  
  - If network lag affects font loading, the application uses system-native monospace and sans-serif fallbacks gracefully.

---

### Segment 2: 0:30–1:00 — Multi-Document Upload Workflow

- **Presenter Action:**  
  1. Click **"Compare Documents"** from the navigation.
  2. Drag and drop 2 financial annual reports (e.g., two comparable Indian corporate filings in PDF format) into the upload dropzone.
  3. Show the dynamic file counter (e.g., `2 / 5 documents selected`), file size indicators, and total session size (e.g., `18.4 MiB / 100 MiB limit`).
  4. Point to the security notice: *"Local ephemeral processing — zero persistent retention"*.
  5. Click **"Continue to Metadata Review"**.
- **What Evaluators Should Observe:**  
  - Support for 2 to 5 concurrent documents across 8 supported formats (`.pdf`, `.txt`, `.csv`, `.xlsx`, `.xls`, `.json`, `.html`, `.docx`).
  - Strict enforcement of client-side validation gates: maximum 20 MiB per file, maximum 100 MiB aggregate session limit.
  - Interactive upload queue with instant file removal buttons and visual progress indicator.
- **Speaking Notes:**  
  > *"Users can upload between 2 and 5 disclosures concurrently. We enforce a strict 20 megabyte per-file limit and a 100 megabyte session cap to guarantee fast local execution on consumer hardware.*  
  > *All files are validated against MIME types and magic byte headers to prevent corrupted or malicious uploads. Processing occurs entirely in-memory."*
- **Fallback / Troubleshooting:**  
  - If a file is accidentally rejected, point out the localized error alert displaying the exact size or format policy violation, remove the file, and re-select valid filings.

---

### Segment 3: 1:00–1:30 — Metadata Review & Compatibility Engine Gate

- **Presenter Action:**  
  1. On the **Metadata Review** screen, show the auto-detected company names, reporting periods (e.g., FY 2023-24 vs FY 2022-23), currency (`INR`), accounting standard (`Ind AS`), and disclosure scopes (`Consolidated`).
  2. Demonstrate how users can adjust detected reporting periods or units if an unusual filing format requires correction.
  3. Highlight the **Compatibility Evaluation Banner**: show either "Compatible" (green badge) or explanatory "Warnings" (e.g., different fiscal year duration or currency conversion notes).
  4. Explain the difference between non-blocking **WARNINGS** and strict **BLOCKERS** (e.g., comparing standalone vs consolidated without reconciliation, or mismatched currencies).
  5. Click **"Run Comparison"**.
- **What Evaluators Should Observe:**  
  - Clear multi-card grid displaying extracted metadata for each filing side-by-side.
  - Real-time compatibility engine analysis flagging temporal or accounting scope discrepancies before computation.
  - Form validation preventing progression if a hard blocking condition is triggered.
- **Speaking Notes:**  
  > *"Before comparing numbers, the system performs a vital sanity check: are these documents actually comparable?*  
  > *Our compatibility engine examines fiscal periods, reporting currency, scale, and accounting scope—such as standalone versus consolidated. If an investor tries to compare different currencies or scopes, the system flags a clear warning. We prevent misleading comparisons at the gate."*
- **Fallback / Troubleshooting:**  
  - If metadata extraction marks a period as ambiguous, click the dropdown to select the verified fiscal year manually, which re-runs compatibility validation immediately.

---

### Segment 4: 1:30–2:30 — Comparison Dashboard, Variance Math & Provenance Modal

- **Presenter Action:**  
  1. Arrive at the **Comparison Dashboard**.
  2. Point to the **9 Core Financial Cards Grid**: Revenue, Net Profit (PAT), Operating Margin (EBITDA), Total Assets, Total Debt, Operating Cash Flow, Debt-to-Equity Ratio, ROE, and Current Ratio.
  3. Demonstrate the **Baseline Selector**: switch the baseline document from Document A to Document B. Show how all absolute variances ($\Delta$) and percentage variances ($\%$) dynamically re-anchor with zero rounding distortion.
  4. Point out the neutral trend indicators (directional arrows $\uparrow$ / $\downarrow$ / $\text{—}$) without speculative green/red color bias.
  5. Click directly on any financial figure (e.g., Revenue of ₹74,210 Cr) to trigger the **EvidenceViewer Modal**.
  6. In the modal, show the highlighted source excerpt, document page number, bounding box coordinates, and extraction confidence score.
  7. Press `Escape` or click "Close" to close the modal, showing focus restoration.
- **What Evaluators Should Observe:**  
  - 100% deterministic calculation using Python `decimal.Decimal` with strict `ROUND_HALF_UP` arithmetic.
  - Total absence of "investment recommendations", "stock ratings", or "buy/sell signals".
  - Missing metrics are honestly displayed as *"Not disclosed"* rather than artificially filled with zero.
  - The Evidence Viewer exposes complete provenance, linking every displayed number directly to the original filing text.
- **Speaking Notes:**  
  > *"Here is the Comparison Dashboard. We present nine standardized core financial metrics calculated using Python Decimal arithmetic. There is no guesswork and no LLM math hallucinations.*  
  > *Notice that we avoid green or red color biases that imply 'good' or 'bad' stock performance. Variances are presented factually.*  
  > *Crucially, every single number is clickable. Clicking a figure immediately opens the Evidence Viewer, showing the exact page, extracted table row, bounding coordinates, and confidence score. Investors can verify every claim against the primary document."*
- **Fallback / Troubleshooting:**  
  - If clicking a card does not open evidence, click the dedicated *"Source"* or *"Evidence"* badge on the card header.

---

### Segment 5: 2:30–3:15 — Manual Financial Correction, Instant Recalculation & LIFO Undo

- **Presenter Action:**  
  1. Hover over a metric card (e.g., *Total Debt* or *Operating Margin*) and click the **"Edit"** pencil icon.
  2. In the **Financial Correction Modal**, enter a revised audited figure (e.g., adjust a misclassified lease obligation from ₹1,200 Cr to ₹1,450 Cr).
  3. Enter an optional reason note: *"Audited adjustment per Note 24"*.
  4. Click **"Save Correction"**.
  5. Show the immediate visual response:
     - The metric updates instantly.
     - A persistent blue badge appears: `User entered`.
     - Hovering over the badge shows a tooltip with the original extracted value (`Original: ₹1,200 Cr`).
     - Derived ratios (e.g., Debt-to-Equity) recalculate dynamically.
     - An active correction banner appears at the top: *"1 active user correction"*.
  6. Click the **"Undo Last Correction"** button on the banner.
  7. Show the figure instantly reverting to its original extracted value and the badge disappearing.
- **What Evaluators Should Observe:**  
  - Full audit trail maintaining both original extracted and user-modified states.
  - Negative values blocked where mathematically invalid (e.g., Total Assets $\ge 0$).
  - Instant recalculation of derived financial formulas without page reload.
  - Clean LIFO (Last-In, First-Out) rollback capability restoring session state cleanly.
- **Speaking Notes:**  
  > *"Financial disclosures often contain complex footnotes, restatements, or OCR extraction anomalies. We empower the analyst to correct any figure directly.*  
  > *When a value is updated, derived metrics like Debt-to-Equity recalculate instantly. The system tags the number with a persistent 'User entered' badge, preserving the original extracted value in the audit trail.*  
  > *If the user makes an error, the one-click Undo banner rolls back the correction instantly using a strict LIFO stack."*
- **Fallback / Troubleshooting:**  
  - If modal input rejects the value, verify that standard positive numbers are entered without special currency symbols.

---

### Segment 6: 3:15–3:45 — Dual Format Export with Audit Provenance

- **Presenter Action:**  
  1. Point to the **Export Actions** in the dashboard header: **"Download PDF Report"** and **"Download Excel (.xlsx)"**.
  2. Click **"Download Excel"** to generate the comprehensive 7-tab audited workbook.
  3. Explain the workbook's 7 structured worksheets:
     1. `Executive Summary`: High-level company comparison and metadata.
     2. `Core Financials`: 9 core metrics with baseline variance math.
     3. `Extended Financials`: Complete disclosures and line items.
     4. `Compatibility Matrix`: Warning logs and parameter alignment.
     5. `Audit Trail`: Complete log of user corrections vs original extracted values.
     6. `Source Provenance`: Page numbers, bounding boxes, and extraction confidence.
     7. `Methodology & Disclaimers`: Full non-advisory educational disclaimers.
  4. Click **"Download PDF Report"** to show instant on-demand executive summary compilation.
- **What Evaluators Should Observe:**  
  - Zero third-party cloud export dependencies (generated locally via `openpyxl` and `ReportLab`).
  - Clear labeling distinguishing original extracted figures from user-corrected figures in exported reports.
  - Export buttons feature mutual-exclusion guards to prevent duplicate submission during generation.
- **Speaking Notes:**  
  > *"When an analyst needs to share findings, the system exports in two open formats.*  
  > *Our Excel export produces a full 7-tab audited financial model. It does not just dump numbers—it exports the complete audit trail, linking user corrections, original text, page citations, and disclaimers.*  
  > *Our PDF export creates a high-density, printable executive brief. In both files, user-adjusted figures are clearly marked so third-party reviewers never mistake a user edit for an official company disclosure."*
- **Fallback / Troubleshooting:**  
  - If browser blocks the file download popup, point to the browser download bar or click the alternative export format.

---

### Segment 7: 3:45–4:00 — Privacy-First Local Architecture & Non-Advisory Closing

- **Presenter Action:**  
  1. Open the **Privacy & Architecture Info Modal** or point to the footer security statement.
  2. Reiterate that all document ingestion, parsing, and arithmetic run entirely locally without sending user files to public cloud storage.
  3. Conclude the demonstration with the product's mission statement.
- **What Evaluators Should Observe:**  
  - Strict ephemeral storage model: HMAC-authenticated tokens expire after 2 hours; uploaded temp files are purged.
  - PII redactor active: PAN, Aadhaar, CIN, DIN, bank accounts, and contact details masked prior to any external API processing.
  - Unwavering adherence to educational neutrality.
- **Speaking Notes:**  
  > *"To conclude: Bharat Investor Copilot is built on a ₹0 cloud budget, local-first architecture. User documents never leave the local environment unless explicit consent is granted, and all sensitive PII is automatically masked beforehand.*  
  > *We do not give tips, we do not predict markets, and we do not replace human judgment.*  
  > *We provide the clarity, provenance, and mathematical rigor that every Indian citizen deserves.*  
  > ***Understanding Before Action.*** *Thank you."*

---

## Technical & Consent Disclosures for Evaluators

1. **Optional External AI Synthesis:**  
   The Comparative Insights tab features an AI narrative synthesis engine. This capability is **strictly optional** and requires the user to review a consent modal detailing that anonymized, PII-redacted metrics will be processed by Google Gemini. If consent is withheld, all 9 core cards, baseline variances, manual corrections, evidence modals, and dual exports remain 100% operational offline.
2. **Deterministic Offline Arithmetic:**  
   All variance computations ($\text{Baseline} - \text{Target}$ and $\frac{\Delta}{\text{Baseline}} \times 100$) are performed deterministically in Python `decimal.Decimal` with `ROUND_HALF_UP` rounding. No LLM is ever used to calculate financial variances.
3. **Simulated SEBI Verification:**  
   The offline prototype includes simulated SEBI verification badges (`VerificationStatus.SIMULATED`) for demonstration workflows. Live production integration with BSE/NSE/SEBI APIs requires institutional exchange access tokens.
4. **Assistive Technology & Browser Automation Notice:**  
   While standard WAI-ARIA dialog attributes, keyboard focus trapping, and Escape shortcuts are fully implemented in the DOM, physical screen readers (NVDA, JAWS, VoiceOver) were not tested in the headless evaluation environment.

