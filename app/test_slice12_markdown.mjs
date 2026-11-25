/**
 * Automated regression tests for Bharat Explains safe Markdown rendering.
 * Runs via `node --test app/test_slice*.mjs`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { parseInlineMarkdown, parseMarkdownBlocks } from "./src/lib/markdown.ts";

const workspacePath = path.resolve("app/src/pages/Workspace.tsx");
const safeMarkdownPath = path.resolve("app/src/components/ui/SafeMarkdown.tsx");

test("Markdown: renders exact EBITDA example and *Why it matters:* without literal markers", () => {
  const sample =
    "**EBITDA**: Operating profit before deducting interest, taxes, depreciation, and amortization.\n\n*Why it matters:* It helps measure core operating profitability.";

  const blocks = parseMarkdownBlocks(sample);
  assert.equal(blocks.length, 2);

  assert.equal(blocks[0].type, "paragraph");
  assert.deepEqual(blocks[0].lines[0], [
    { type: "bold", content: "EBITDA" },
    {
      type: "text",
      content:
        ": Operating profit before deducting interest, taxes, depreciation, and amortization.",
    },
  ]);

  assert.equal(blocks[1].type, "paragraph");
  assert.deepEqual(blocks[1].lines[0], [
    { type: "italic", content: "Why it matters:" },
    { type: "text", content: " It helps measure core operating profitability." },
  ]);
});

test("Markdown: parses unordered lists, ordered lists, blockquotes, and line breaks cleanly", () => {
  const input = [
    "Key points from **Q3 FY24**:",
    "Line two in same paragraph",
    "",
    "- **Revenue**: ₹1,10,577.14 Cr",
    "* *PAT*: ₹7,025.11 Cr",
    "",
    "1. First check cash flow",
    "2. Second check debt",
    "",
    "> Revenue from operations: 110,577.14",
  ].join("\n");

  const blocks = parseMarkdownBlocks(input);
  assert.equal(blocks.length, 4);

  assert.equal(blocks[0].type, "paragraph");
  assert.equal(blocks[0].lines.length, 2);
  assert.deepEqual(blocks[0].lines[0], [
    { type: "text", content: "Key points from " },
    { type: "bold", content: "Q3 FY24" },
    { type: "text", content: ":" },
  ]);

  assert.equal(blocks[1].type, "ul");
  assert.equal(blocks[1].items.length, 2);
  assert.deepEqual(blocks[1].items[0], [
    { type: "bold", content: "Revenue" },
    { type: "text", content: ": ₹1,10,577.14 Cr" },
  ]);
  assert.deepEqual(blocks[1].items[1], [
    { type: "italic", content: "PAT" },
    { type: "text", content: ": ₹7,025.11 Cr" },
  ]);

  assert.equal(blocks[2].type, "ol");
  assert.equal(blocks[2].items.length, 2);

  assert.equal(blocks[3].type, "blockquote");
  assert.deepEqual(blocks[3].lines[0], [
    { type: "text", content: "Revenue from operations: 110,577.14" },
  ]);
});

test("Markdown: treats HTML and scripts strictly as literal text without dangerouslySetInnerHTML", () => {
  const xss = '<script>alert("xss")</script> **SafeBold** <img src=x onerror=alert(1) />';
  const tokens = parseInlineMarkdown(xss);

  assert.deepEqual(tokens, [
    { type: "text", content: '<script>alert("xss")</script> ' },
    { type: "bold", content: "SafeBold" },
    { type: "text", content: " <img src=x onerror=alert(1) />" },
  ]);

  const componentSrc = fs.readFileSync(safeMarkdownPath, "utf8");
  assert.doesNotMatch(componentSrc, /dangerouslySetInnerHTML/);
  assert.doesNotMatch(componentSrc, /innerHTML/);
});

test("Markdown: Workspace uses SafeMarkdown uniformly for both Gemini AI and Local fallback responses", () => {
  const ws = fs.readFileSync(workspacePath, "utf8");
  assert.match(ws, /import \{ SafeMarkdown \} from "\.\.\/components\/ui\/SafeMarkdown"/);
  assert.match(ws, /<SafeMarkdown content=\{msg\.content\} \/>/);
  // Confirm single unified rendering path covers AI_CONSENTED and LOCAL_MODE / LOCAL_MODE_FALLBACK
  assert.equal((ws.match(/>\{msg\.content\}</g) || []).length, 1, "Only user message renders plain text; assistant uses SafeMarkdown");
});
