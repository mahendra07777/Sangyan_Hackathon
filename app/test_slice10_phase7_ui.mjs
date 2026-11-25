/**
 * Automated test suite for Phase 7:
 * UI Cleanup, Financial Warnings, Accessibility & Trilingual Localization.
 *
 * Runs directly via `node --test app/test_slice10_phase7_ui.mjs`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const translationsFilePath = path.resolve("app/src/lib/translations.ts");
const workflowFilePath = path.resolve("app/src/components/compare/CompareWorkflow.tsx");
const uploadFilePath = path.resolve("app/src/components/compare/CompareUpload.tsx");
const metadataFilePath = path.resolve("app/src/components/compare/MetadataReview.tsx");
const compatFilePath = path.resolve("app/src/components/compare/CompatibilityView.tsx");
const processingFilePath = path.resolve("app/src/components/compare/ProcessingView.tsx");
const consentFilePath = path.resolve("app/src/components/compare/ConsentModal.tsx");
const dashboardFilePath = path.resolve("app/src/components/compare/ComparisonDashboard.tsx");
const chartsFilePath = path.resolve("app/src/components/compare/CompareSvgCharts.tsx");
const evidenceViewerFilePath = path.resolve("app/src/components/compare/EvidenceViewer.tsx");

// ---------------------------------------------------------------------------
// 1. Trilingual Translation Dictionary Integrity & 100% Parity
// ---------------------------------------------------------------------------

test("Phase 7: Translation dictionaries maintain 100% parity across English, Hindi, and Hinglish", () => {
  const content = fs.readFileSync(translationsFilePath, "utf8");

  const enSection = content.slice(content.indexOf("const en:"), content.indexOf("const hi:"));
  const hiSection = content.slice(content.indexOf("const hi:"), content.indexOf("const hinglish:"));
  const hinglishSection = content.slice(content.indexOf("const hinglish:"), content.indexOf("const dictionaries:"));

  const extractKeys = (section) => {
    const matches = [...section.matchAll(/"([a-zA-Z0-9_.]+)"\s*:/g)];
    return new Set(matches.map((m) => m[1]));
  };

  const enKeys = extractKeys(enSection);
  const hiKeys = extractKeys(hiSection);
  const hinglishKeys = extractKeys(hinglishSection);

  // Must have preserved all 284 baseline keys and expanded to >= 400 keys
  assert.ok(enKeys.size >= 400, `Expected at least 400 keys, found ${enKeys.size}`);
  assert.equal(hiKeys.size, enKeys.size, `Hindi key count (${hiKeys.size}) must match English (${enKeys.size})`);
  assert.equal(hinglishKeys.size, enKeys.size, `Hinglish key count (${hinglishKeys.size}) must match English (${enKeys.size})`);

  // Verify zero missing keys in Hindi
  const missingInHi = [...enKeys].filter((k) => !hiKeys.has(k));
  assert.deepEqual(missingInHi, [], `Missing keys in Hindi dictionary: ${missingInHi.join(", ")}`);

  // Verify zero missing keys in Hinglish
  const missingInHinglish = [...enKeys].filter((k) => !hinglishKeys.has(k));
  assert.deepEqual(missingInHinglish, [], `Missing keys in Hinglish dictionary: ${missingInHinglish.join(", ")}`);

  // Verify essential Phase 7 keys exist
  const essentialKeys = [
    "compare.wizard.step.upload",
    "compare.wizard.step.metadata",
    "compare.wizard.step.compatibility",
    "compare.wizard.step.processing",
    "compare.wizard.step.results",
    "compare.upload.skipped_types",
    "compare.upload.total_label",
    "compare.upload.security_disclaimer",
    "compare.metadata.subtitle",
    "compare.metadata.reupload_btn",
    "compare.metadata.status_overridden",
    "compare.compat.summary_status",
    "compare.compat.zero_issues_title",
    "compare.processing.status_done",
    "compare.consent.modal_title",
    "compare.consent.preview_heading",
    "compare.consent.preview_ready_notice",
    "compare.workflow.dismiss_error_aria",
    "compare.correction.close_aria",
    "compare.dash.new_comparison",
    "compare.dash.core_indicators_badge",
    "compare.dash.comparative_story_title",
    "compare.charts.across_uploaded",
    "compare.evidence.scanned_badge",
    "compare.evidence.cited_excerpt_badge",
    "compare.evidence.educational_notice",
  ];

  for (const k of essentialKeys) {
    assert.ok(enKeys.has(k), `English dictionary must contain key '${k}'`);
    assert.ok(hiKeys.has(k), `Hindi dictionary must contain key '${k}'`);
    assert.ok(hinglishKeys.has(k), `Hinglish dictionary must contain key '${k}'`);
  }
});

test("Phase 7: Translation fallback function getTranslation is preserved", () => {
  const content = fs.readFileSync(translationsFilePath, "utf8");
  assert.match(
    content,
    /export function getTranslation\(/,
    "getTranslation export must be preserved"
  );
  assert.match(
    content,
    /dict\[key\]\s*\|\|\s*dictionaries\.English\[key\]\s*\|\|\s*key/,
    "getTranslation fallback mechanism must remain intact"
  );
});

// ---------------------------------------------------------------------------
// 2. Wizard & Upload Component Localization
// ---------------------------------------------------------------------------

test("Phase 7: CompareWorkflow localizes step breadcrumbs and session tag", () => {
  const content = fs.readFileSync(workflowFilePath, "utf8");

  assert.match(content, /t\("compare\.wizard\.step\.upload"\)/);
  assert.match(content, /t\("compare\.wizard\.step\.metadata"\)/);
  assert.match(content, /t\("compare\.wizard\.step\.compatibility"\)/);
  assert.match(content, /t\("compare\.wizard\.step\.processing"\)/);
  assert.match(content, /t\("compare\.wizard\.step\.results"\)/);
  assert.match(content, /t\("compare\.workflow\.ephemeral_session"\)/);

  // Hardcoded English strings must not be present in breadcrumbs
  assert.doesNotMatch(content, /<span className="text-neutral-500">1\. Upload<\/span>/);
  assert.doesNotMatch(content, /<span>5\. Results<\/span>/);
});

test("Phase 7: CompareUpload localizes error messages, totals, buttons, and security notice", () => {
  const content = fs.readFileSync(uploadFilePath, "utf8");

  assert.match(content, /t\("compare\.upload\.skipped_types"\)/);
  assert.match(content, /t\("compare\.upload\.failed"\)/);
  assert.match(content, /t\("compare\.upload\.total_label"\)/);
  assert.match(content, /t\("compare\.upload\.remove_title"\)/);
  assert.match(content, /t\("compare\.upload\.uploading_detecting"\)/);
  assert.match(content, /t\("compare\.upload\.security_disclaimer"\)/);

  // File remove button must have aria-label
  assert.match(
    content,
    /aria-label=\{`\$\{t\("compare\.upload\.remove_title"\)\}: \$\{file\.name\}`\}/,
    "Remove button must have accessible aria-label"
  );
});

// ---------------------------------------------------------------------------
// 3. Metadata Review Localization & Mobile Responsiveness
// ---------------------------------------------------------------------------

test("Phase 7: MetadataReview localizes all headings, options, badges, and buttons", () => {
  const content = fs.readFileSync(metadataFilePath, "utf8");

  assert.match(content, /t\("compare\.metadata\.subtitle"\)/);
  assert.match(content, /t\("compare\.metadata\.reupload_btn"\)/);
  assert.match(content, /t\("compare\.metadata\.back_upload_btn"\)/);
  assert.match(content, /t\("compare\.metadata\.confidence_suffix"\)/);
  assert.match(content, /t\("compare\.metadata\.cin_placeholder"\)/);
  assert.match(content, /t\("compare\.metadata\.fy_placeholder"\)/);
  assert.match(content, /t\("compare\.metadata\.period\.annual"\)/);
  assert.match(content, /t\("compare\.metadata\.period\.quarterly"\)/);
  assert.match(content, /t\("compare\.metadata\.quarter\.none"\)/);
  assert.match(content, /t\("compare\.metadata\.corrections_saved"\)/);
  assert.match(content, /t\("compare\.metadata\.status_overridden"\)/);
  assert.match(content, /t\("compare\.metadata\.status_detected"\)/);
});

test("Phase 7: MetadataReview responsive layout replaces rigid grid-cols-2 with grid-cols-1 sm:grid-cols-2", () => {
  const content = fs.readFileSync(metadataFilePath, "utf8");

  // Verify responsive classes are applied across metadata grids
  const responsiveMatches = [...content.matchAll(/grid grid-cols-1 sm:grid-cols-2 gap-3/g)];
  assert.ok(
    responsiveMatches.length >= 4,
    `Expected at least 4 responsive grid layouts, found ${responsiveMatches.length}`
  );

  // Verify old rigid grid layout is completely replaced
  assert.doesNotMatch(
    content,
    /<div className="grid grid-cols-2 gap-3">/,
    "Rigid grid-cols-2 without sm: breakpoint must not be present"
  );
});

// ---------------------------------------------------------------------------
// 4. Compatibility, Processing & Consent Localization and ARIA
// ---------------------------------------------------------------------------

test("Phase 7: CompatibilityView and ProcessingView are fully localized", () => {
  const compatContent = fs.readFileSync(compatFilePath, "utf8");
  assert.match(compatContent, /t\("compare\.compat\.title"\)/);
  assert.match(compatContent, /t\("compare\.compat\.summary_status"\)/);
  assert.match(compatContent, /t\("compare\.compat\.summary_blockers"\)/);
  assert.match(compatContent, /t\("compare\.compat\.summary_warnings"\)/);
  assert.match(compatContent, /t\("compare\.compat\.affects_prefix"\)/);
  assert.match(compatContent, /t\("compare\.compat\.zero_issues_title"\)/);
  assert.match(compatContent, /t\("compare\.compat\.back_metadata_btn"\)/);
  assert.match(compatContent, /t\("compare\.compat\.blocked_btn"\)/);

  const processingContent = fs.readFileSync(processingFilePath, "utf8");
  assert.match(processingContent, /t\("compare\.processing\.status_done"\)/);
  assert.match(processingContent, /t\("compare\.processing\.status_in_progress"\)/);
  assert.match(processingContent, /t\("compare\.processing\.status_pending"\)/);
  assert.match(processingContent, /t\("compare\.processing\.cancelling"\)/);
});

test("Phase 7: ConsentModal has proper dialog ARIA attributes and full localization", () => {
  const content = fs.readFileSync(consentFilePath, "utf8");

  // ARIA verification
  assert.match(content, /role="dialog"/);
  assert.match(content, /aria-modal="true"/);
  assert.match(content, /aria-labelledby="consent-modal-title"/);
  assert.match(content, /id="consent-modal-title"/);

  // Localization verification
  assert.match(content, /t\("compare\.consent\.modal_title"\)/);
  assert.match(content, /t\("compare\.consent\.mode_local_badge"\)/);
  assert.match(content, /t\("compare\.consent\.mode_ai_badge"\)/);
  assert.match(content, /t\("compare\.consent\.preview_heading"\)/);
  assert.match(content, /t\("compare\.consent\.target_filings"\)/);
  assert.match(content, /t\("compare\.consent\.trans_scope"\)/);
  assert.match(content, /t\("compare\.consent\.ai_service"\)/);
  assert.match(content, /t\("compare\.consent\.pii_sanitization"\)/);
  assert.match(content, /t\("compare\.consent\.pii_masked_count"\)/);
  assert.match(content, /t\("compare\.consent\.cancel_btn"\)/);
  assert.match(content, /t\("compare\.consent\.decline_btn"\)/);
  assert.match(content, /t\("compare\.consent\.allow_transmit_btn"\)/);
});

// ---------------------------------------------------------------------------
// 5. Comparison Dashboard Localization & ARIA
// ---------------------------------------------------------------------------

test("Phase 7: ComparisonDashboard localizes selectors, disclaimers, sections, and scale hints", () => {
  const content = fs.readFileSync(dashboardFilePath, "utf8");

  assert.match(content, /t\("compare\.dash\.new_comparison"\)/);
  assert.match(content, /t\("compare\.dash\.all_compatible_badge"\)/);
  assert.match(content, /t\("compare\.dash\.core_indicators_badge"\)/);
  assert.match(content, /t\("compare\.dash\.base_badge"\)/);
  assert.match(content, /t\("compare\.dash\.compare_selector"\)/);
  assert.match(content, /t\("compare\.dash\.active_corrections_subtitle"\)/);
  assert.match(content, /t\("compare\.dash\.missing_metrics_notice"\)/);
  assert.match(content, /t\("compare\.dash\.comparative_story_title"\)/);
  assert.match(content, /t\("compare\.dash\.pos_changes_title"\)/);
  assert.match(content, /t\("compare\.dash\.pressures_title"\)/);
  assert.match(content, /t\("compare\.dash\.neutral_shifts_title"\)/);
  assert.match(content, /t\("compare\.dash\.uncertain_title"\)/);
  assert.match(content, /t\("compare\.dash\.disclosed_risks_title"\)/);
  assert.match(content, /t\("compare\.dash\.accounting_diff_title"\)/);
  assert.match(content, /t\("compare\.dash\.chat_sub"\)/);
  assert.match(content, /t\("compare\.dash\.chat_empty"\)/);
  assert.match(content, /t\("compare\.dash\.eps_scale_hint"\)/);
  assert.match(content, /t\("compare\.dash\.crores_scale_hint"\)/);

  // Dismiss export error button must have accessible aria-label
  assert.match(content, /aria-label=\{t\("compare\.dash\.dismiss_error_aria"\)\}/);
});

// ---------------------------------------------------------------------------
// 6. CompareSvgCharts Accessibility & Localization
// ---------------------------------------------------------------------------

test("Phase 7: CompareSvgCharts bars implement accessible names, titles, and roles", () => {
  const content = fs.readFileSync(chartsFilePath, "utf8");

  // Verify chart bars have role="graphics-symbol" and accessible labels
  assert.match(content, /role="graphics-symbol"/);
  assert.match(content, /<title>/);
  assert.match(content, /t\("compare\.charts\.across_uploaded"\)/);
  assert.match(content, /t\("compare\.charts\.across_filings"\)/);
});

// ---------------------------------------------------------------------------
// 7. EvidenceViewer Accessibility & Localization
// ---------------------------------------------------------------------------

test("Phase 7: EvidenceViewer implements dialog role, modal accessibility, and full localization", () => {
  const content = fs.readFileSync(evidenceViewerFilePath, "utf8");

  // Accessibility assertions
  assert.match(content, /role="dialog"/, "EvidenceViewer must declare role='dialog'");
  assert.match(content, /aria-modal="true"/, "EvidenceViewer must declare aria-modal='true'");
  assert.match(content, /aria-labelledby="evidence-viewer-title"/, "EvidenceViewer must link aria-labelledby");
  assert.match(content, /id="evidence-viewer-title"/, "EvidenceViewer must provide title id target");
  assert.match(content, /aria-label=\{t\("compare\.evidence\.close"\)\}/, "Close button must have aria-label");

  // Localization assertions
  assert.match(content, /t\("compare\.evidence\.scanned_badge"\)/);
  assert.match(content, /t\("compare\.evidence\.reset_zoom"\)/);
  assert.match(content, /t\("compare\.evidence\.loading_page"\)/);
  assert.match(content, /t\("compare\.evidence\.page_err_title"\)/);
  assert.match(content, /t\("compare\.evidence\.cited_excerpt_badge"\)/);
  assert.match(content, /t\("compare\.evidence\.doc_label"\)/);
  assert.match(content, /t\("compare\.evidence\.section_label"\)/);
  assert.match(content, /t\("compare\.evidence\.context_label"\)/);
  assert.match(content, /t\("compare\.evidence\.reported_label"\)/);
  assert.match(content, /t\("compare\.evidence\.rule_label"\)/);
  assert.match(content, /t\("compare\.evidence\.educational_notice"\)/);
});

// ---------------------------------------------------------------------------
// 8. Financial Neutrality & Zero-Regression Verification
// ---------------------------------------------------------------------------

test("Phase 7: Financial neutrality is strictly maintained across all comparison components", () => {
  const components = [
    workflowFilePath,
    uploadFilePath,
    metadataFilePath,
    compatFilePath,
    processingFilePath,
    consentFilePath,
    dashboardFilePath,
    chartsFilePath,
    evidenceViewerFilePath,
  ];

  for (const compPath of components) {
    const text = fs.readFileSync(compPath, "utf8").toLowerCase();
    assert.doesNotMatch(text, /\bbuy rating\b/, `No buy recommendations in ${path.basename(compPath)}`);
    assert.doesNotMatch(text, /\bsell rating\b/, `No sell recommendations in ${path.basename(compPath)}`);
    assert.doesNotMatch(text, /\bhold rating\b/, `No hold recommendations in ${path.basename(compPath)}`);
    assert.doesNotMatch(text, /\btarget price\b/, `No target prices in ${path.basename(compPath)}`);
    assert.doesNotMatch(text, /\bguaranteed return\b/, `No guaranteed returns in ${path.basename(compPath)}`);
    assert.doesNotMatch(text, /\boutperform rating\b/, `No outperform ratings in ${path.basename(compPath)}`);
  }
});

// ---------------------------------------------------------------------------
// 9. Fix A & D: ConsentModal Keyboard Trapping, Escape & Localization Gaps
// ---------------------------------------------------------------------------

test("Phase 7 Gap-Closure: ConsentModal implements Escape handling, focus trap, restoration and localized preview notice", () => {
  const content = fs.readFileSync(consentFilePath, "utf8");

  // Escape handling
  assert.match(content, /e\.key === "Escape"/, "ConsentModal must handle Escape key");
  assert.match(content, /onClose\(\)/, "Escape must invoke onClose");
  // Verify Escape does NOT grant consent or invoke onConfirmAi
  assert.doesNotMatch(content, /e\.key === "Escape"[^}]*onConfirmAi/, "Escape must never grant AI consent");

  // Focus trap implementation
  assert.match(content, /modalRef = useRef<HTMLDivElement>/, "ConsentModal must declare modalRef");
  assert.match(content, /ref=\{modalRef\}/, "ConsentModal must bind modalRef to container");
  assert.match(content, /e\.key === "Tab"/, "ConsentModal must trap Tab navigation");
  assert.match(content, /firstElement\.focus\(\)/, "Focus trap must cycle forward to firstElement");
  assert.match(content, /lastElement\.focus\(\)/, "Focus trap must cycle backward to lastElement");

  // Initial focus and focus restoration
  assert.match(content, /previousActiveElement = useRef/, "ConsentModal must track previousActiveElement");
  assert.match(content, /previousActiveElement\.current\.focus\(\)/, "ConsentModal must restore focus upon close");
  assert.match(content, /closeButtonRef\.current\?\.focus\(\)/, "ConsentModal must set initial focus to close button");

  // Event listener cleanup
  assert.match(content, /window\.removeEventListener\("keydown", handleKeyDown\)/, "Keydown listener must be cleaned up");

  // Remaining preview notice localization (Fix D)
  assert.match(content, /t\("compare\.consent\.preview_ready_notice"\)/, "Preview notice must use translation lookup");
  assert.doesNotMatch(content, />Selective transmission preview is ready on request\.</, "Raw English preview string must be removed");
});

// ---------------------------------------------------------------------------
// 10. Fix B: EvidenceViewer Keyboard Trapping, Escape & Restoration
// ---------------------------------------------------------------------------

test("Phase 7 Gap-Closure: EvidenceViewer implements Escape handling, focus trap, restoration and cleanup", () => {
  const content = fs.readFileSync(evidenceViewerFilePath, "utf8");

  // Escape handling
  assert.match(content, /e\.key === "Escape"/, "EvidenceViewer must handle Escape key");
  assert.match(content, /onClose\(\)/, "Escape must invoke onClose");

  // Focus trap implementation
  assert.match(content, /modalRef = useRef<HTMLDivElement>/, "EvidenceViewer must declare modalRef");
  assert.match(content, /ref=\{modalRef\}/, "EvidenceViewer must bind modalRef to container");
  assert.match(content, /e\.key === "Tab"/, "EvidenceViewer must trap Tab navigation");
  assert.match(content, /firstElement\.focus\(\)/, "Focus trap must cycle forward to firstElement");
  assert.match(content, /lastElement\.focus\(\)/, "Focus trap must cycle backward to lastElement");

  // Initial focus and focus restoration
  assert.match(content, /previousActiveElement = useRef/, "EvidenceViewer must track previousActiveElement");
  assert.match(content, /previousActiveElement\.current\.focus\(\)/, "EvidenceViewer must restore focus upon close");
  assert.match(content, /closeButtonRef\.current\?\.focus\(\)/, "EvidenceViewer must set initial focus to close button");

  // Event listener cleanup
  assert.match(content, /window\.removeEventListener\("keydown", handleKeyDown\)/, "Keydown listener must be cleaned up");
});

// ---------------------------------------------------------------------------
// 11. Fix C: SVG Chart Bars Keyboard Focusability & Navigation
// ---------------------------------------------------------------------------

test("Phase 7 Gap-Closure: CompareSvgCharts bars are keyboard focusable with visible focus ring and descriptions", () => {
  const content = fs.readFileSync(chartsFilePath, "utf8");

  // Verify tabIndex={0} on chart bars
  assert.match(content, /tabIndex=\{0\}/, "Chart bars must declare tabIndex={0} for keyboard focusability");

  // Verify visible focus indicator classes
  assert.match(content, /focus:outline-none focus:ring-2 focus:ring-accent-500/, "Chart bars must have visible focus ring");

  // Verify accessible names, roles, and title tooltips
  assert.match(content, /role="graphics-symbol"/, "Bars must have role='graphics-symbol'");
  assert.match(content, /aria-label=\{/, "Bars must have dynamic aria-label");
  assert.match(content, /<title>\{/, "Bars must have descriptive SVG <title> child");
});

// ---------------------------------------------------------------------------
// 12. Fix D: Localized Dismiss and Close aria-labels
// ---------------------------------------------------------------------------

test("Phase 7 Gap-Closure: CompareWorkflow and ComparisonDashboard localize icon button aria-labels", () => {
  const workflowContent = fs.readFileSync(workflowFilePath, "utf8");
  assert.match(workflowContent, /aria-label=\{t\("compare\.workflow\.dismiss_error_aria"\)\}/, "Workflow dismiss error button must be localized");
  assert.doesNotMatch(workflowContent, /aria-label="Dismiss error"/, "Hardcoded 'Dismiss error' aria-label must not exist");

  const dashboardContent = fs.readFileSync(dashboardFilePath, "utf8");
  assert.match(dashboardContent, /aria-label=\{t\("compare\.correction\.close_aria"\)\}/, "Correction modal close button must be localized");
  assert.doesNotMatch(dashboardContent, /aria-label="Close"/, "Hardcoded 'Close' aria-label must not exist in correction modal");
});
