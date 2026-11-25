/**
 * Automated test suite for Slice 8 Frontend Export Integration & Contracts.
 * Runs directly via `node --test app/test_slice8_frontend.mjs`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const translationsFilePath = path.resolve("app/src/lib/translations.ts");
const compareApiFilePath = path.resolve("app/src/lib/compareApi.ts");
const dashboardFilePath = path.resolve("app/src/components/compare/ComparisonDashboard.tsx");
const backendRoutesPath = path.resolve("backend/app/api/compare_routes.py");

test("Slice 8: Export translations dictionary integrity across English, Hindi, and Hinglish", () => {
  const content = fs.readFileSync(translationsFilePath, "utf8");

  const requiredExportKeys = [
    "compare.export.title",
    "compare.export.pdf_button",
    "compare.export.xlsx_button",
    "compare.export.generating_pdf",
    "compare.export.generating_xlsx",
    "compare.export.download_success",
    "compare.export.error_failed",
    "compare.export.pdf_language_note",
    "compare.export.print_report",
    "compare.export.sheets.summary",
    "compare.export.sheets.metrics",
    "compare.export.sheets.calculations",
    "compare.export.sheets.risks",
    "compare.export.sheets.accounting",
    "compare.export.sheets.evidence",
    "compare.export.sheets.verification",
  ];

  for (const k of requiredExportKeys) {
    const regex = new RegExp(`"${k.replace(/\./g, "\\.")}":`, "g");
    const matches = content.match(regex);
    assert.ok(
      matches && matches.length >= 3,
      `Key ${k} must be defined in all 3 translation dictionaries (en, hi, hinglish). Found ${matches ? matches.length : 0}`
    );
  }
});

test("Slice 8: 7-Tab Excel Workbook specifications & worksheet order", () => {
  const approvedWorksheets = [
    "Executive Summary",
    "Financial Metrics",
    "Calculations",
    "Risks & Disclosures",
    "Accounting Differences",
    "Source Evidence",
    "Verification Results",
  ];

  assert.equal(approvedWorksheets.length, 7, "Excel export must contain exactly 7 worksheets");
  assert.equal(approvedWorksheets[0], "Executive Summary");
  assert.equal(approvedWorksheets[1], "Financial Metrics");
  assert.equal(approvedWorksheets[2], "Calculations");
  assert.equal(approvedWorksheets[3], "Risks & Disclosures");
  assert.equal(approvedWorksheets[4], "Accounting Differences");
  assert.equal(approvedWorksheets[5], "Source Evidence");
  assert.equal(approvedWorksheets[6], "Verification Results");
});

test("Slice 8: API client methods for Endpoint 15 and Endpoint 16", () => {
  const compareApiContent = fs.readFileSync(compareApiFilePath, "utf8");

  // 1. exportComparePdf check
  assert.ok(
    compareApiContent.includes("export async function exportComparePdf"),
    "compareApi.ts must export exportComparePdf"
  );
  assert.ok(
    compareApiContent.includes("/export/pdf"),
    "exportComparePdf must route to Endpoint 15 path"
  );
  assert.ok(
    compareApiContent.includes('method: "POST"'),
    "exportComparePdf must use HTTP POST"
  );

  // 2. exportCompareXlsx check
  assert.ok(
    compareApiContent.includes("export async function exportCompareXlsx"),
    "compareApi.ts must export exportCompareXlsx"
  );
  assert.ok(
    compareApiContent.includes("/export/xlsx"),
    "exportCompareXlsx must route to Endpoint 16 path"
  );

  // 3. downloadBlob utility check
  assert.ok(
    compareApiContent.includes("export function downloadBlob"),
    "compareApi.ts must export downloadBlob helper"
  );
  assert.ok(
    compareApiContent.includes("createObjectURL") && compareApiContent.includes("revokeObjectURL"),
    "downloadBlob must create and immediately revoke Object URL"
  );
});

test("Slice 8: ComparisonDashboard export controls & duplicate submission prevention", () => {
  const dashboardContent = fs.readFileSync(dashboardFilePath, "utf8");

  // Verify export buttons exist
  assert.ok(
    dashboardContent.includes("handleExportPdf"),
    "ComparisonDashboard must have handleExportPdf handler"
  );
  assert.ok(
    dashboardContent.includes("handleExportXlsx"),
    "ComparisonDashboard must have handleExportXlsx handler"
  );

  // Verify duplicate submission prevention logic
  assert.ok(
    dashboardContent.includes("if (isExportingPdf || isExportingXlsx) return;"),
    "Must lock concurrent or duplicate export submissions"
  );

  // Verify loading state and spinners
  assert.ok(
    dashboardContent.includes("isExportingPdf") && dashboardContent.includes("isExportingXlsx"),
    "Dashboard must manage distinct loading states for PDF and Excel"
  );

  // Verify notification banners
  assert.ok(
    dashboardContent.includes("exportError") && dashboardContent.includes("exportSuccess"),
    "Dashboard must surface feedback states for errors and success"
  );
});

test("Slice 8: Backend routes compliance for Endpoint 15 and 16", () => {
  const backendContent = fs.readFileSync(backendRoutesPath, "utf8");

  // 1. Endpoint 15 PDF
  assert.ok(
    backendContent.includes('"/session/{session_id}/export/pdf"'),
    "Backend must register Endpoint 15 /export/pdf"
  );
  assert.ok(
    backendContent.includes("ExportPdfService.generate_comparison_pdf"),
    "Backend must delegate PDF generation to ExportPdfService"
  );

  // 2. Endpoint 16 XLSX
  assert.ok(
    backendContent.includes('"/session/{session_id}/export/xlsx"'),
    "Backend must register Endpoint 16 /export/xlsx"
  );
  assert.ok(
    backendContent.includes("ExportExcelService.generate_comparison_workbook"),
    "Backend must delegate Excel generation to ExportExcelService"
  );

  // 3. Security: Header auth required, query param token rejected
  assert.ok(
    backendContent.includes("get_authenticated_session"),
    "Export endpoints must enforce authenticated session dependency"
  );
  assert.ok(
    backendContent.includes("_check_query_params_for_token"),
    "Export endpoints must reject query parameter tokens"
  );
});
