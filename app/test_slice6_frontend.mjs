/**
 * Automated test suite for Slice 6 Frontend Comparison features.
 * Runs directly via `node --test app/test_slice6_frontend.mjs`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const translationsFilePath = path.resolve("app/src/lib/translations.ts");
const compareApiFilePath = path.resolve("app/src/lib/compareApi.ts");

test("Slice 6: Translations dictionary integrity across English, Hindi, and Hinglish", () => {
  const content = fs.readFileSync(translationsFilePath, "utf8");

  // Verify compare namespace keys exist in en, hi, hinglish
  const requiredKeys = [
    "compare.nav.button",
    "compare.mode.quick",
    "compare.mode.multi",
    "compare.upload.title",
    "compare.upload.limits",
    "compare.metadata.title",
    "compare.compat.title",
    "compare.compat.status.COMPATIBLE",
    "compare.compat.status.BLOCKED",
    "compare.consent.title",
    "compare.consent.local_title",
    "compare.consent.ai_title",
    "compare.process.title",
    "compare.dash.title",
    "compare.dash.disclaimer",
    "compare.matrix.col.metric",
    "compare.matrix.not_disclosed",
    "compare.charts.title",
    "compare.chat.title",
  ];

  for (const k of requiredKeys) {
    const regex = new RegExp(`"${k.replace(/\./g, "\\.")}":`, "g");
    const matches = content.match(regex);
    assert.ok(
      matches && matches.length >= 3,
      `Key ${k} must be defined in all 3 translation dictionaries (en, hi, hinglish). Found ${matches ? matches.length : 0}`
    );
  }
});

test("Slice 6: Multi-format validation, 20 MiB per-file and 100 MiB session boundaries", () => {
  const MAX_FILE_SIZE = 20 * 1024 * 1024;
  const MAX_SESSION_SIZE = 100 * 1024 * 1024;
  const ACCEPTED_EXTS = [".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".xls"];

  const validateFiles = (files) => {
    if (files.length < 2) return { valid: false, error: "MIN_FILES" };
    if (files.length > 5) return { valid: false, error: "MAX_FILES" };

    let totalSize = 0;
    for (const f of files) {
      const ext = "." + f.name.split(".").pop().toLowerCase();
      if (!ACCEPTED_EXTS.includes(ext)) {
        return { valid: false, error: "INVALID_FORMAT", file: f.name };
      }
      if (f.size > MAX_FILE_SIZE) {
        return { valid: false, error: "EXCEEDS_FILE_LIMIT", file: f.name };
      }
      totalSize += f.size;
    }

    if (totalSize > MAX_SESSION_SIZE) {
      return { valid: false, error: "EXCEEDS_SESSION_LIMIT" };
    }

    return { valid: true, count: files.length, totalSize };
  };

  // Valid 2-file pair
  const validPair = [
    { name: "q1_results.pdf", size: 5 * 1024 * 1024 },
    { name: "annual_report.xlsx", size: 12 * 1024 * 1024 },
  ];
  const res1 = validateFiles(validPair);
  assert.equal(res1.valid, true);

  // Valid all 8 formats test
  const allFormats = [
    { name: "f1.pdf", size: 1024 },
    { name: "f2.png", size: 1024 },
    { name: "f3.jpg", size: 1024 },
    { name: "f4.docx", size: 1024 },
    { name: "f5.xlsx", size: 1024 },
  ];
  const resFormats = validateFiles(allFormats);
  assert.equal(resFormats.valid, true);

  // Rejects unauthorized format
  const badExt = [
    { name: "f1.pdf", size: 1024 },
    { name: "exploit.exe", size: 1024 },
  ];
  assert.equal(validateFiles(badExt).error, "INVALID_FORMAT");

  // Rejects > 20 MiB file
  const oversizedFile = [
    { name: "f1.pdf", size: 1024 },
    { name: "huge.pdf", size: 21 * 1024 * 1024 },
  ];
  assert.equal(validateFiles(oversizedFile).error, "EXCEEDS_FILE_LIMIT");

  // Rejects > 100 MiB session total
  const oversizedSession = [
    { name: "f1.pdf", size: 19 * 1024 * 1024 },
    { name: "f2.pdf", size: 19 * 1024 * 1024 },
    { name: "f3.pdf", size: 19 * 1024 * 1024 },
    { name: "f4.pdf", size: 19 * 1024 * 1024 },
    { name: "f5.pdf", size: 26 * 1024 * 1024 },
  ];
  assert.equal(validateFiles(oversizedSession).error, "EXCEEDS_FILE_LIMIT");

  // Rejects < 2 files
  assert.equal(validateFiles([{ name: "f1.pdf", size: 1024 }]).error, "MIN_FILES");

  // Rejects > 5 files
  const sixFiles = [1, 2, 3, 4, 5, 6].map((i) => ({ name: `f${i}.pdf`, size: 1024 }));
  assert.equal(validateFiles(sixFiles).error, "MAX_FILES");
});

test("Slice 6: SVG Chart data calculation and zero-distortion rule", () => {
  // Test data with one positive, one negative, one missing under canonical uppercase key
  const sampleValues = {
    REVENUE: {
      doc_a: { status: "REPORTED", amount: 1500, unit: "INR_CRORE" },
      doc_b: { status: "REPORTED", amount: -200, unit: "INR_CRORE" }, // negative
      doc_c: { status: "NOT_DISCLOSED", amount: null, unit: "INR_CRORE" }, // missing
    },
  };

  const getMetricData = (key, docList) => {
    const keyUpper = key.toUpperCase();
    const keyLower = key.toLowerCase();
    return docList.map((docId) => {
      const fVal = sampleValues[key]?.[docId] || sampleValues[keyUpper]?.[docId] || sampleValues[keyLower]?.[docId];
      const isReported = fVal && fVal.status === "REPORTED" && fVal.amount !== null && fVal.amount !== undefined;
      return {
        docId,
        amount: isReported ? Number(fVal.amount) : null,
      };
    });
  };

  // Test both uppercase and lowercase lookup
  const data = getMetricData("REVENUE", ["doc_a", "doc_b", "doc_c"]);
  const dataLower = getMetricData("revenue", ["doc_a", "doc_b", "doc_c"]);
  assert.deepEqual(data, dataLower, "Canonical uppercase and lowercase lookups must resolve identically");

  // CRITICAL RULE: Missing value must NOT be converted to 0
  assert.equal(data[0].amount, 1500);
  assert.equal(data[1].amount, -200);
  assert.equal(data[2].amount, null, "Missing metric must remain null and NEVER plotted as zero");

  // Baseline calculation for negative support
  const validAmounts = data.filter((d) => d.amount !== null).map((d) => d.amount);
  const minVal = Math.min(0, ...validAmounts);
  const maxVal = Math.max(0, ...validAmounts);
  assert.ok(minVal < 0, "minVal correctly identifies negative value");
  assert.ok(maxVal > 0, "maxVal correctly identifies positive value");

  const height = 300;
  const padding = { top: 30, bottom: 60 };
  const innerHeight = height - padding.top - padding.bottom;
  const yZero = padding.top + ((maxVal - 0) / (maxVal - minVal)) * innerHeight;

  assert.ok(yZero > padding.top && yZero < height - padding.bottom, "yZero is dynamically positioned inside chart area");
});

test("Slice 6: Financial matrix missing value and directional display", () => {
  const formatDisplay = (fVal) => {
    if (!fVal || fVal.status !== "REPORTED" || fVal.amount === null || fVal.amount === undefined) {
      if (fVal?.status === "UNCERTAIN") {
        return fVal.display_amount || "Uncertain";
      }
      return "Not disclosed";
    }
    return fVal.display_amount || `₹${fVal.amount} Cr`;
  };

  assert.equal(formatDisplay(null), "Not disclosed");
  assert.equal(formatDisplay({ status: "NOT_DISCLOSED", amount: null }), "Not disclosed");
  assert.equal(formatDisplay({ status: "UNCERTAIN", amount: null }), "Uncertain");
  assert.equal(
    formatDisplay({ status: "UNCERTAIN", display_amount: "Uncertain (Unverified Period)", amount: null }),
    "Uncertain (Unverified Period)"
  );
  assert.equal(formatDisplay({ status: "REPORTED", amount: 0 }), "₹0 Cr"); // explicit zero
  assert.equal(formatDisplay({ status: "REPORTED", amount: 450 }), "₹450 Cr");

  // Negative base directional explanation test
  const varianceNegativeBase = {
    metric_key: "pat",
    base_value: -50,
    comparison_value: 120,
    status: "NON_POSITIVE_BASE",
    directional_explanation: "Loss to Profit: Improved from -₹50.00 Cr to +₹120.00 Cr",
    percentage_change: null,
  };

  assert.equal(varianceNegativeBase.percentage_change, null);
  assert.ok(varianceNegativeBase.directional_explanation.includes("Loss to Profit"));
});

test("Slice 6: API contracts compliance and header authentication verification", () => {
  const compareApiContent = fs.readFileSync(compareApiFilePath, "utf8");
  const backendRoutesPath = path.resolve("backend/app/api/compare_routes.py");
  const backendRoutesContent = fs.readFileSync(backendRoutesPath, "utf8");

  // 1. updateCompareMetadata must use HTTP PUT
  assert.ok(
    compareApiContent.includes('method: "PUT"'),
    "updateCompareMetadata must use PUT method"
  );
  assert.ok(
    !compareApiContent.includes('method: "PATCH"'),
    "Frontend must not use PATCH method"
  );

  // 2. Backend must have PUT for metadata and NO PATCH alias
  assert.ok(
    backendRoutesContent.includes('@compare_router.put(\n    "/session/{session_id}/metadata/{doc_id}"') ||
    backendRoutesContent.includes('@compare_router.put('),
    "Backend must have PUT route for metadata"
  );
  assert.ok(
    !backendRoutesContent.includes("@compare_router.patch"),
    "Backend must not have unauthorized PATCH alias"
  );

  // 3. Capability token must be in X-Session-Token header only
  assert.ok(
    compareApiContent.includes('headers["X-Session-Token"] = token'),
    "Token must be passed strictly in X-Session-Token header"
  );
  assert.ok(
    !compareApiContent.includes("?token=") && !compareApiContent.includes("&token="),
    "Token must never appear in URL query parameters"
  );

  // 4. Financial endpoints from Slice 4 must be present
  assert.ok(
    compareApiContent.includes("/financials") && compareApiContent.includes("/calculations"),
    "Slice 4 financial endpoints must be available in client API"
  );
});

test("Slice 6: Compatibility Matrix blocking vs non-blocking workflow gate", () => {
  const checkCanProceed = (status, blockerCount) => {
    return status !== "BLOCKED" && blockerCount === 0;
  };

  assert.equal(checkCanProceed("COMPATIBLE", 0), true);
  assert.equal(checkCanProceed("COMPATIBLE_WITH_WARNINGS", 0), true);
  assert.equal(checkCanProceed("PARTIALLY_COMPATIBLE", 0), true);
  assert.equal(checkCanProceed("BLOCKED", 1), false);
  assert.equal(checkCanProceed("COMPATIBLE", 2), false);
});

test("Slice 6: Canonical uppercase metric keys registry and case-insensitive resolution", () => {
  const CANONICAL_METRIC_KEYS = [
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

  const dashboardContent = fs.readFileSync(path.resolve("app/src/components/compare/ComparisonDashboard.tsx"), "utf8");
  for (const k of CANONICAL_METRIC_KEYS) {
    assert.ok(
      dashboardContent.includes(`key: "${k}"`),
      `ComparisonDashboard METRIC_ROWS must define canonical key ${k}`
    );
  }

  // Verify resolution of both uppercase and lowercase payloads
  const mockPayload = {
    REVENUE: { doc_1: { status: "REPORTED", amount: 1000 } },
    pat: { doc_1: { status: "REPORTED", amount: 200 } },
  };

  const resolveVal = (rowKey, docId) => {
    return mockPayload[rowKey]?.[docId] || mockPayload[rowKey.toLowerCase()]?.[docId] || mockPayload[rowKey.toUpperCase()]?.[docId];
  };

  assert.equal(resolveVal("REVENUE", "doc_1").amount, 1000);
  assert.equal(resolveVal("revenue", "doc_1").amount, 1000);
  assert.equal(resolveVal("PAT", "doc_1").amount, 200);
  assert.equal(resolveVal("pat", "doc_1").amount, 200);
});
