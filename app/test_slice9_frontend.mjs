/**
 * Automated test suite for Slice 9 Frontend End-to-End Integration,
 * Dashboard Navigation, Responsive Design, and Trilingual Verification.
 *
 * Runs directly via `node --test app/test_slice9_frontend.mjs`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const translationsFilePath = path.resolve("app/src/lib/translations.ts");
const compareApiFilePath = path.resolve("app/src/lib/compareApi.ts");
const dashboardFilePath = path.resolve("app/src/components/compare/ComparisonDashboard.tsx");
const evidenceViewerFilePath = path.resolve("app/src/components/compare/EvidenceViewer.tsx");
const chartsFilePath = path.resolve("app/src/components/compare/CompareSvgCharts.tsx");

// ---------------------------------------------------------------------------
// 1. Dashboard Navigation & Tab Architecture
// ---------------------------------------------------------------------------

test("Slice 9: ComparisonDashboard tab architecture contains all 5 required views", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify the 5 standard tabs exist in state and render logic
  const requiredTabs = ["matrix", "charts", "summary", "risks", "chat"];
  for (const tab of requiredTabs) {
    assert.match(
      content,
      new RegExp(`activeTab === "${tab}"`),
      `Dashboard must conditionally render tab view '${tab}'`
    );
  }

  // Verify tab button list contains all 5 keys
  assert.match(content, /key:\s*"matrix"/);
  assert.match(content, /key:\s*"charts"/);
  assert.match(content, /key:\s*"summary"/);
  assert.match(content, /key:\s*"risks"/);
  assert.match(content, /key:\s*"chat"/);
});

// ---------------------------------------------------------------------------
// 2. Export Button Handlers & Duplicate Submission Locks
// ---------------------------------------------------------------------------

test("Slice 9: Export handlers enforce mutual exclusion and duplicate submission prevention", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify early return guards if already exporting
  assert.match(
    content,
    /if\s*\(\s*isExportingPdf\s*\|\|\s*isExportingXlsx\s*\)\s*return;/,
    "handleExportPdf must abort if already exporting"
  );

  // Verify button disabled attribute enforces mutual exclusion
  assert.match(
    content,
    /disabled=\{isExportingPdf\s*\|\|\s*isExportingXlsx\}/,
    "Export buttons must be disabled while any export operation is in flight"
  );

  // Verify spinner loading indicators
  assert.match(content, /isExportingPdf\s*\?\s*t\("compare\.export\.generating_pdf"\)/);
  assert.match(content, /isExportingXlsx\s*\?\s*t\("compare\.export\.generating_xlsx"\)/);
});

// ---------------------------------------------------------------------------
// 3. Evidence Viewer Trigger & State Wiring
// ---------------------------------------------------------------------------

test("Slice 9: Evidence Viewer modal is bound to selectedEvidence and selectedCandidates state", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify EvidenceViewer component mount
  assert.match(content, /<EvidenceViewer/);
  assert.match(content, /evidence=\{selectedEvidence\}/);
  assert.match(content, /candidates=\{selectedCandidates\}/);
  assert.match(content, /onClose=\{\(\)\s*=>\s*\{/);
  assert.match(content, /setSelectedEvidence\(null\)/);
  assert.match(content, /setSelectedCandidates\(\[\]\)/);
});

// ---------------------------------------------------------------------------
// 4. Mobile & Desktop Responsive Design Classes
// ---------------------------------------------------------------------------

test("Slice 9: Responsive layout classes protect mobile screens and horizontal overflows", () => {
  const dashboardContent = fs.readFileSync(dashboardFilePath, "utf8");
  const evidenceContent = fs.readFileSync(evidenceViewerFilePath, "utf8");

  // Horizontal scroll wrapper for wide financial tables
  assert.match(dashboardContent, /overflow-x-auto/);
  assert.match(evidenceContent, /overflow-x-auto/);

  // Responsive flex / grid wraps
  assert.match(dashboardContent, /flex-wrap/);
  assert.match(dashboardContent, /md:flex-row/);
  assert.match(dashboardContent, /sm:px-6/);
});

// ---------------------------------------------------------------------------
// 5. Trilingual Completeness (English, Hindi, Hinglish)
// ---------------------------------------------------------------------------

test("Slice 9: Trilingual dictionary covers all comparison keys across English, Hindi, and Hinglish", () => {
  const content = fs.readFileSync(translationsFilePath, "utf8");

  const coreKeys = [
    "compare.dash.title",
    "compare.dash.disclaimer",
    "compare.dash.tabs.summary",
    "compare.dash.tabs.matrix",
    "compare.dash.tabs.charts",
    "compare.dash.tabs.risks",
    "compare.dash.tabs.chat",
    "compare.export.title",
    "compare.export.pdf_button",
    "compare.export.xlsx_button",
    "compare.evidence.title",
    "compare.evidence.close",
  ];

  for (const k of coreKeys) {
    const escaped = k.replace(/\./g, "\\.");
    const matches = content.match(new RegExp(`"${escaped}":`, "g"));
    assert.ok(
      matches && matches.length >= 3,
      `Key '${k}' must appear at least 3 times (EN, HI, Hinglish); found ${matches ? matches.length : 0}`
    );
  }
});

// ---------------------------------------------------------------------------
// 6. Prohibited Investment Advice Refusal in Comparative Chat
// ---------------------------------------------------------------------------

test("Slice 9: Comparative chat UI displays non-advisory educational disclaimers", () => {
  const dashboardContent = fs.readFileSync(dashboardFilePath, "utf8");
  const translationsContent = fs.readFileSync(translationsFilePath, "utf8");

  // Verify non-advisory banner in dashboard
  assert.match(dashboardContent, /compare\.dash\.disclaimer/);

  // Verify disclaimer text contains SEBI educational non-advisory wording across EN, HI, Hinglish
  assert.match(translationsContent, /SEBI Educational Notice/i);
  assert.match(translationsContent, /not provide investment advice|stock recommendations/i);
});

// ---------------------------------------------------------------------------
// 7. Key Financial Cards Grid for All 9 Core Metrics
// ---------------------------------------------------------------------------

test("Slice 9: Key Financial Cards Grid renders all 9 core metrics with test IDs and source evidence triggers", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify container test ID
  assert.match(content, /data-testid="key-financial-cards-grid"/);

  // Verify all 9 core metrics are registered and rendered
  const coreMetricKeys = [
    "REVENUE",
    "PAT",
    "EBITDA",
    "TOTAL_ASSETS",
    "TOTAL_LIABILITIES",
    "TOTAL_DEBT",
    "CASH_EQUIVALENTS",
    "EPS",
    "OPERATING_CASH_FLOW",
  ];

  for (const key of coreMetricKeys) {
    assert.match(
      content,
      new RegExp(`key:\\s*"${key}"`),
      `Metric row registry must contain core metric '${key}'`
    );
  }

  // Verify individual card test ID pattern
  assert.match(content, /data-testid=\{`card-\$\{row\.key\.toLowerCase\(\)\}`\}/);

  // Verify evidence button trigger inside cards
  assert.match(content, /compare\.cards\.view_evidence/);
  assert.match(content, /handleOpenValueEvidence\(valWithEv\)/);
});

// ---------------------------------------------------------------------------
// 8. Visual Charts Metadata & Expanded Metric Selection
// ---------------------------------------------------------------------------

test("Slice 9: CompareSvgCharts accepts metadata/compatibility and supports expanded metric selection", () => {
  const dashboardContent = fs.readFileSync(dashboardFilePath, "utf8");
  const chartsContent = fs.readFileSync(chartsFilePath, "utf8");

  // Verify Dashboard passes metadata and compatibility props to CompareSvgCharts
  assert.match(dashboardContent, /metadata=\{(?:activeResult|result)\.metadata\}/);
  assert.match(dashboardContent, /compatibility=\{(?:activeResult|result)\.compatibility\}/);

  // Verify CompareSvgCharts uses metadata company names and reporting periods
  assert.match(chartsContent, /meta\?\.company_name\s*\|\|\s*doc\.original_filename/);
  assert.match(chartsContent, /meta\?\.financial_year/);

  // Verify expanded metric selection keys (Debt, Cash, OCF, Balance Sheet)
  assert.match(chartsContent, /setSelectedMetric\("debt"\)/);
  assert.match(chartsContent, /setSelectedMetric\("cash"\)/);
  assert.match(chartsContent, /setSelectedMetric\("ocf"\)/);
  assert.match(chartsContent, /setSelectedMetric\("balance_sheet"\)/);

  // Verify compatibility notice pill in charts
  assert.match(chartsContent, /compare\.charts\.compat_notice/);
});

// ---------------------------------------------------------------------------
// 9. Multi-Document Baseline Selector in Financial Matrix
// ---------------------------------------------------------------------------

test("Slice 9: Multi-document baseline selector allows pairwise variance re-anchoring across 2-5 filings", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify baseline selector label and dropdown test ID
  assert.match(content, /compare\.matrix\.baseline_selector/);
  assert.match(content, /data-testid="baseline-doc-selector"/);
  assert.match(content, /data-testid="comparison-doc-selector"/);

  // Verify state tracking and pairing
  assert.match(content, /const \[baselineDocId, setBaselineDocId\] = useState/);
  assert.match(content, /const \[comparisonDocId, setComparisonDocId\] = useState/);
  assert.match(content, /getPairwiseVariance\(metricKey, baseId, compId\)/);
});

// ---------------------------------------------------------------------------
// 10. Dynamic Discovery of Additional Disclosed Metrics
// ---------------------------------------------------------------------------

test("Slice 9: Additional Disclosed Metrics dynamically renders non-core line items in expandable section", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify section test ID
  assert.match(content, /data-testid="additional-metrics-section"/);

  // Verify dynamic discovery filters out core keys
  assert.match(content, /CORE_METRIC_KEYS/);
  assert.match(content, /additionalMetricKeys = Object\.keys\((?:activeResult|result)\.financial_values\)\.filter/);

  // Verify expand/collapse toggle and empty state translation
  assert.match(content, /compare\.matrix\.additional_metrics/);
  assert.match(content, /compare\.matrix\.no_additional/);
});

// ---------------------------------------------------------------------------
// 11. Consolidated Compatibility Warnings Banner
// ---------------------------------------------------------------------------

test("Slice 9: Compatibility banner distinguishes BLOCKER vs WARNING issues with remediation context", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify banner test ID
  assert.match(content, /data-testid="compatibility-warnings-banner"/);

  // Verify severity categorization
  assert.match(content, /f\.severity === "BLOCKER"/);
  assert.match(content, /compare\.compat\.banner_title/);
  assert.match(content, /compare\.compat\.blocker_title/);
  assert.match(content, /compare\.compat\.warning_title/);

  // Verify expand/collapse toggle and remediation hint display
  assert.match(content, /compare\.compat\.expand/);
  assert.match(content, /compare\.compat\.collapse/);
  assert.match(content, /compare\.compat\.remediation/);
});

// ---------------------------------------------------------------------------
// 12. Interactive Financial Amount Clicks to Source Evidence
// ---------------------------------------------------------------------------

test("Slice 9: Financial amount clicks in cards and matrix table trigger EvidenceViewer provenance modal", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify interactive amount helper renders clickable button when evidence exists
  assert.match(content, /renderInteractiveAmount = \(/);
  assert.match(content, /handleOpenValueEvidence\(fVal\)/);
  assert.match(content, /title="Click to inspect verbatim source evidence in document viewer"/);

  // Verify click-to-evidence hint in table header
  assert.match(content, /compare\.matrix\.click_evidence_hint/);
});

// ---------------------------------------------------------------------------
// 13. Neutral Trend Indicators without Good/Bad Financial Bias
// ---------------------------------------------------------------------------

test("Slice 9: Trend indicators use factual neutral arrows (↑/↓/—) without green/red investment bias", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");
  const translationsContent = fs.readFileSync(translationsFilePath, "utf8");

  // Verify neutral trend labels in translations
  assert.match(translationsContent, /"compare\.trend\.increase":\s*"Increase"/);
  assert.match(translationsContent, /"compare\.trend\.decrease":\s*"Decrease"/);
  assert.match(translationsContent, /"compare\.trend\.flat":\s*"Unchanged"/);

  // Verify directional arrows render in neutral badge styling
  assert.match(content, /<span>↑<\/span>/);
  assert.match(content, /<span>↓<\/span>/);
  assert.match(content, /<span>—<\/span>/);

  // Verify variance percentage change in table uses neutral background styling
  assert.match(content, /bg-neutral-100 px-2 py-0\.5 rounded text-xs border border-neutral-200/);
});

// ---------------------------------------------------------------------------
// 14. Phase 6: Active Corrections Banner & LIFO Undo Wiring
// ---------------------------------------------------------------------------

test("Slice 9: Active corrections banner renders with LIFO undo button and count indicator", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify container test ID
  assert.match(content, /data-testid="active-corrections-banner"/);

  // Verify undo button test ID
  assert.match(content, /data-testid="undo-correction-btn"/);

  // Verify undo handler invocation
  assert.match(content, /onClick=\{handleUndoCorrection\}/);

  // Verify loading state indicator for undo
  assert.match(content, /isUndoingCorrection\s*\?\s*t\("compare\.correction\.undoing"\)/);

  // Verify corrections count badge and description
  assert.match(content, /compare\.correction\.active_banner/);
  assert.match(content, /activeCorrectionsCount/);
});

// ---------------------------------------------------------------------------
// 15. Phase 6: Edit Triggers on Cards, Matrix, and Additional Metrics
// ---------------------------------------------------------------------------

test("Slice 9: Edit triggers exist across Key Financial Cards, Matrix Table, and Additional Disclosed Metrics", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify edit button test ID patterns and open modal handler
  assert.match(content, /data-testid=\{`edit-btn-\$\{metricKey\.toLowerCase\(\)\}-\$\{docId\}`\}/);
  assert.match(content, /handleOpenEditModal\(docId,\s*metricKey,\s*fVal\)/);
  assert.match(content, /compare\.correction\.edit_btn/);
});

// ---------------------------------------------------------------------------
// 16. Phase 6: User-Entered Distinction Badge with Original Value Tooltip
// ---------------------------------------------------------------------------

test("Slice 9: User-entered badge clearly distinguishes corrected figures and displays original extracted tooltip", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify user-entered badge test ID
  assert.match(content, /data-testid="user-entered-badge"/);

  // Verify neutral amber badge styling (no green/red bias)
  assert.match(content, /bg-amber-100 text-amber-900 border border-amber-300/);

  // Verify tooltip displays original reported amount
  assert.match(content, /compare\.correction\.original_extracted/);
  assert.match(content, /fVal\?\.original_amount/);
});

// ---------------------------------------------------------------------------
// 17. Phase 6: Financial Correction Modal & Negative Total Assets Guard
// ---------------------------------------------------------------------------

test("Slice 9: Financial correction modal provides accessible inputs, validation, and negative assets block", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify modal dialog test ID
  assert.match(content, /data-testid="financial-correction-modal"/);

  // Verify required inputs and submit button test IDs
  assert.match(content, /data-testid="corrected-amount-input"/);
  assert.match(content, /data-testid="correction-reason-input"/);
  assert.match(content, /data-testid="apply-correction-btn"/);

  // Verify validation guard blocking negative Total Assets
  assert.match(content, /TOTAL_ASSETS/);
  assert.match(content, /numVal\s*<\s*0/);
  assert.match(content, /compare\.correction\.assets_negative/);

  // Verify submission handler wired to compareApi
  assert.match(content, /handleApplyCorrection/);
  assert.match(content, /correctFinancialValue\(/);
  assert.match(content, /undoFinancialCorrection\(/);
});

// ---------------------------------------------------------------------------
// 18. Phase 6: Trilingual Completeness for Manual Corrections & Undo
// ---------------------------------------------------------------------------

test("Slice 9: Trilingual dictionary covers all Phase 6 correction keys across English, Hindi, and Hinglish", () => {
  const content = fs.readFileSync(translationsFilePath, "utf8");

  const correctionKeys = [
    "compare.correction.modal_title",
    "compare.correction.modal_subtitle",
    "compare.correction.edit_btn",
    "compare.correction.user_entered",
    "compare.correction.original_extracted",
    "compare.correction.active_banner",
    "compare.correction.undo_btn",
    "compare.correction.undoing",
    "compare.correction.new_amount_label",
    "compare.correction.amount_placeholder",
    "compare.correction.reason_label",
    "compare.correction.reason_placeholder",
    "compare.correction.save_btn",
    "compare.correction.saving",
    "compare.correction.cancel_btn",
    "compare.correction.assets_negative",
    "compare.correction.invalid_amount",
  ];

  for (const k of correctionKeys) {
    const escaped = k.replace(/\./g, "\\.");
    const matches = content.match(new RegExp(`"${escaped}":`, "g"));
    assert.ok(
      matches && matches.length >= 3,
      `Key '${k}' must appear at least 3 times (EN, HI, Hinglish); found ${matches ? matches.length : 0}`
    );
  }
});

// ---------------------------------------------------------------------------
// 19. Phase 6: Compare API Client Definitions for Corrections & Undo
// ---------------------------------------------------------------------------

test("Slice 9: compareApi exports type definitions and endpoints for corrections and undo", () => {
  const content = fs.readFileSync(compareApiFilePath, "utf8");

  // Verify TypeScript interfaces
  assert.match(content, /export interface FinancialCorrectionRecord/);
  assert.match(content, /export interface FinancialCorrectionResponse/);
  assert.match(content, /export interface FinancialUndoResponse/);
  assert.match(content, /export interface SessionCorrectionsResponse/);

  // Verify API functions
  assert.match(content, /export async function correctFinancialValue\(/);
  assert.match(content, /export async function undoFinancialCorrection\(/);
  assert.match(content, /export async function getFinancialCorrections\(/);

  // Verify endpoint URL patterns
  assert.match(content, /\/api\/compare\/session\/\$\{sessionId\}\/financials\/correct/);
  assert.match(content, /\/api\/compare\/session\/\$\{sessionId\}\/financials\/undo/);
  assert.match(content, /\/api\/compare\/session\/\$\{sessionId\}\/financials\/corrections/);
});

// ---------------------------------------------------------------------------
// 20. Phase 6 Gap H: Frontend Error Isolation & Interface State Synchronization
// ---------------------------------------------------------------------------

test("Slice 9: API errors suppress false success messages, display error alert, and preserve input context", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify error state catch blocks in handleApplyCorrection and handleUndoCorrection
  assert.match(
    content,
    /catch\s*\(\s*err:\s*any\s*\)\s*\{\s*setCorrectionError\(err\.message\s*\|\|\s*"Failed to apply correction\."\);/
  );
  assert.match(
    content,
    /catch\s*\(\s*err:\s*any\s*\)\s*\{\s*setCorrectionError\(err\.message\s*\|\|\s*t\("compare\.correction\.no_corrections"\)\);/
  );

  // Verify that success state is ONLY set on successful response (inside try block)
  assert.match(
    content,
    /setActiveResult\(resp\.comparison_result\);\s*setEditingMetric\(null\);\s*setCorrectedAmountInput\(""\);\s*setCorrectionReasonInput\(""\);\s*setCorrectionSuccess\(t\("compare\.correction\.success"\)\);/
  );

  // Verify error container test ID
  assert.match(content, /data-testid="correction-error-message"/);
});

// ---------------------------------------------------------------------------
// 21. Phase 6 Gap H: User-Entered Visibility & Original Value Provenance Access
// ---------------------------------------------------------------------------

test("Slice 9: User-entered figures display persistent badges and expose original extracted values", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify persistent badge rendering when is_user_corrected is true
  assert.match(content, /isUserCorrected\s*&&\s*\(/);
  assert.match(content, /data-testid="user-entered-badge"/);

  // Verify badge title renders original extracted value tooltip
  assert.match(
    content,
    /title=\{originalText\s*\?\s*`\$\{t\("compare\.correction\.original_extracted"\)\}:\s*\$\{originalText\}`\s*:\s*t\("compare\.correction\.user_entered"\)\}/
  );

  // Verify modal displays original extracted number alongside current figure
  assert.match(content, /t\("compare\.correction\.original_extracted"\)/);
  assert.match(content, /editingMetric\.currentVal\.original_amount\.toLocaleString\(\)/);
});
