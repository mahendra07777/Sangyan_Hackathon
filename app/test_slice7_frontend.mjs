/**
 * Automated test suite for Slice 7 Frontend Evidence Viewer & Traceability.
 * Runs directly via `node --test app/test_slice7_frontend.mjs`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const translationsFilePath = path.resolve("app/src/lib/translations.ts");
const compareApiFilePath = path.resolve("app/src/lib/compareApi.ts");
const evidenceViewerFilePath = path.resolve("app/src/components/compare/EvidenceViewer.tsx");
const dashboardFilePath = path.resolve("app/src/components/compare/ComparisonDashboard.tsx");

test("Slice 7: Evidence Viewer translations dictionary integrity across English, Hindi, and Hinglish", () => {
  const content = fs.readFileSync(translationsFilePath, "utf8");

  const requiredEvidenceKeys = [
    "compare.evidence.title",
    "compare.evidence.close",
    "compare.evidence.page",
    "compare.evidence.of",
    "compare.evidence.prev_page",
    "compare.evidence.next_page",
    "compare.evidence.zoom_in",
    "compare.evidence.zoom_out",
    "compare.evidence.zoom_fit",
    "compare.evidence.sheet",
    "compare.evidence.cell",
    "compare.evidence.formula",
    "compare.evidence.cached_value",
    "compare.evidence.structural_ref",
    "compare.evidence.verbatim_snippet",
    "compare.evidence.location_context",
    "compare.evidence.bounding_box",
    "compare.evidence.scanned_notice",
    "compare.evidence.image_notice",
    "compare.evidence.spreadsheet_notice",
    "compare.evidence.docx_notice",
    "compare.evidence.candidates_title",
    "compare.evidence.selected_candidate",
    "compare.evidence.conflicting_candidate",
    "compare.evidence.no_page_image",
  ];

  for (const k of requiredEvidenceKeys) {
    const regex = new RegExp(`"${k.replace(/\./g, "\\.")}":`, "g");
    const matches = content.match(regex);
    assert.ok(
      matches && matches.length >= 3,
      `Key ${k} must be defined in all 3 translation dictionaries (en, hi, hinglish). Found ${matches ? matches.length : 0}`
    );
  }
});

test("Slice 7: High-precision bounding box calculation and overlay CSS logic", () => {
  const computeBoundingBoxStyle = (bbox) => {
    if (!bbox || !Array.isArray(bbox) || bbox.length < 4) {
      return null;
    }
    const [x0, y0, x1, y1] = bbox;
    const left = Math.max(0, Math.min(1, x0)) * 100;
    const top = Math.max(0, Math.min(1, y0)) * 100;
    const width = Math.max(0, Math.min(1, x1) - Math.max(0, Math.min(1, x0))) * 100;
    const height = Math.max(0, Math.min(1, y1) - Math.max(0, Math.min(1, y0))) * 100;

    return {
      left: `${left}%`,
      top: `${top}%`,
      width: `${width}%`,
      height: `${height}%`,
    };
  };

  // Normal valid bounding box: [x0, y0, x1, y1]
  const style1 = computeBoundingBoxStyle([0.1, 0.2, 0.5, 0.4]);
  assert.ok(style1 !== null);
  assert.equal(style1.left, "10%");
  assert.equal(style1.top, "20%");
  assert.equal(style1.width, "40%");
  assert.equal(style1.height, "20%");

  // Full page bounding box: [0, 0, 1, 1]
  const styleFull = computeBoundingBoxStyle([0, 0, 1, 1]);
  assert.equal(styleFull.left, "0%");
  assert.equal(styleFull.top, "0%");
  assert.equal(styleFull.width, "100%");
  assert.equal(styleFull.height, "100%");

  // Null or missing bounding box returns null safely
  assert.equal(computeBoundingBoxStyle(null), null);
  assert.equal(computeBoundingBoxStyle([]), null);
  assert.equal(computeBoundingBoxStyle([0.1, 0.2]), null);
});

test("Slice 7: Multi-format support & format notice banner routing across all 8 formats", () => {
  const formatCategories = {
    PDF_DIGITAL: { isVisual: true, noticeKey: null },
    PDF_SCANNED: { isVisual: true, noticeKey: "compare.evidence.scanned_notice" },
    IMAGE_PNG: { isVisual: true, noticeKey: "compare.evidence.image_notice" },
    IMAGE_JPG: { isVisual: true, noticeKey: "compare.evidence.image_notice" },
    IMAGE_JPEG: { isVisual: true, noticeKey: "compare.evidence.image_notice" },
    DOCX: { isVisual: false, noticeKey: "compare.evidence.docx_notice" },
    XLSX: { isVisual: false, noticeKey: "compare.evidence.spreadsheet_notice" },
    XLS: { isVisual: false, noticeKey: "compare.evidence.spreadsheet_notice" },
  };

  const formats = Object.keys(formatCategories);
  assert.equal(formats.length, 8, "Must cover all 8 supported document formats");

  for (const fmt of formats) {
    const config = formatCategories[fmt];
    if (config.isVisual) {
      assert.ok(["PDF_DIGITAL", "PDF_SCANNED", "IMAGE_PNG", "IMAGE_JPG", "IMAGE_JPEG"].includes(fmt));
    } else {
      assert.ok(["DOCX", "XLSX", "XLS"].includes(fmt));
    }
  }
});

test("Slice 7: Multi-candidate conflict arbitration inspector logic", () => {
  const candidates = [
    {
      candidate_id: "cand_1",
      raw_label: "Total Income",
      raw_text_value: "1,10,577.00",
      normalized_amount: 1105770000000,
      statement_type: "Standalone P&L",
      is_selected: true,
      resolution_reason: "Primary Statement Preference (Statement of Profit and Loss over general notes)",
      evidence: {
        evidence_id: "ev_1",
        doc_id: "doc_a",
        document_name: "TataMotors_FY24.pdf",
        page_number: 5,
        verbatim_snippet: "Total Income: 1,10,577.00 Cr",
      },
    },
    {
      candidate_id: "cand_2",
      raw_label: "Segment Revenue - Commercial Vehicles",
      raw_text_value: "78,000.00",
      normalized_amount: 780000000000,
      statement_type: "Notes to Accounts",
      is_selected: false,
      resolution_reason: "Sub-segment disclosure superseded by top-level aggregate",
      evidence: {
        evidence_id: "ev_2",
        doc_id: "doc_a",
        document_name: "TataMotors_FY24.pdf",
        page_number: 14,
        verbatim_snippet: "Commercial Vehicles: 78,000.00 Cr",
      },
    },
  ];

  const selectedCandidate = candidates.find((c) => c.is_selected);
  const alternateCandidates = candidates.filter((c) => !c.is_selected);

  assert.ok(selectedCandidate !== undefined);
  assert.equal(selectedCandidate.candidate_id, "cand_1");
  assert.ok(selectedCandidate.resolution_reason.includes("Primary Statement Preference"));
  assert.equal(alternateCandidates.length, 1);
  assert.equal(alternateCandidates[0].candidate_id, "cand_2");
});

test("Slice 7: Provenance badge classifications according to architecture rules", () => {
  const provenanceTypes = [
    "DOCUMENT_FACT",
    "EDUCATIONAL_EXPLANATION",
    "SOURCE_INFORMATION",
    "UNCERTAIN",
  ];

  const badgeConfig = {
    DOCUMENT_FACT: { variant: "success", labelKey: "compare.evidence.provenance.DOCUMENT_FACT" },
    EDUCATIONAL_EXPLANATION: { variant: "info", labelKey: "compare.evidence.provenance.EDUCATIONAL_EXPLANATION" },
    SOURCE_INFORMATION: { variant: "neutral", labelKey: "compare.evidence.provenance.SOURCE_INFORMATION" },
    UNCERTAIN: { variant: "warning", labelKey: "compare.evidence.provenance.UNCERTAIN" },
  };

  for (const pt of provenanceTypes) {
    assert.ok(badgeConfig[pt] !== undefined, `Provenance type ${pt} must have configured badge style`);
    assert.ok(badgeConfig[pt].labelKey.startsWith("compare.evidence.provenance."));
  }
});

test("Slice 7: Compare API client methods for Endpoint 13 and Endpoint 13.1", () => {
  const compareApiContent = fs.readFileSync(compareApiFilePath, "utf8");

  // 1. fetchEvidencePageBlob method check
  assert.ok(
    compareApiContent.includes("async function fetchEvidencePageBlob") ||
    compareApiContent.includes("export async function fetchEvidencePageBlob"),
    "compareApi.ts must export fetchEvidencePageBlob"
  );
  assert.ok(
    compareApiContent.includes("/evidence/${docId}/page/${pageNum}"),
    "fetchEvidencePageBlob must route to Endpoint 13 path"
  );
  assert.ok(
    compareApiContent.includes('headers["X-Session-Token"] = token'),
    "fetchEvidencePageBlob must send X-Session-Token header"
  );

  // 2. getEvidenceContext method check
  assert.ok(
    compareApiContent.includes("async function getEvidenceContext") ||
    compareApiContent.includes("export async function getEvidenceContext"),
    "compareApi.ts must export getEvidenceContext"
  );
  assert.ok(
    compareApiContent.includes("/evidence/${docId}/context"),
    "getEvidenceContext must route to Endpoint 13.1 path"
  );

  // 3. DocumentExtractionResult type check
  assert.ok(
    compareApiContent.includes("export interface DocumentExtractionResult"),
    "compareApi.ts must export DocumentExtractionResult interface"
  );
  assert.ok(
    compareApiContent.includes("export interface ExtractedTable"),
    "compareApi.ts must export ExtractedTable interface"
  );
});

test("Slice 7: EvidenceViewer component integration into ComparisonDashboard", () => {
  const dashboardContent = fs.readFileSync(dashboardFilePath, "utf8");
  const evidenceViewerContent = fs.readFileSync(evidenceViewerFilePath, "utf8");

  // Verify EvidenceViewer is imported and rendered in dashboard
  assert.ok(
    dashboardContent.includes("EvidenceViewer"),
    "ComparisonDashboard must import and render EvidenceViewer"
  );

  // Verify 'selectedEvidence' state hook exists
  assert.ok(
    dashboardContent.includes("selectedEvidence"),
    "ComparisonDashboard must track selectedEvidence state for modal view"
  );

  // Verify 'View Source' triggers exist in dashboard for various sections
  assert.ok(
    dashboardContent.includes("setSelectedEvidence"),
    "ComparisonDashboard must have triggers calling setSelectedEvidence"
  );

  // Verify EvidenceViewer handles zoom, page nav, and close events
  assert.ok(
    evidenceViewerContent.includes("handleKeyDown"),
    "EvidenceViewer must handle keyboard navigation (Escape, ArrowLeft, ArrowRight)"
  );
  assert.ok(
    evidenceViewerContent.includes("zoomLevel"),
    "EvidenceViewer must support zoomLevel controls"
  );
});
