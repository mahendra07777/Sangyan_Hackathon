/**
 * Automated regression test suite for Group 8: AI-First Integration & Automatic Fallback.
 * Runs via `node --test app/test_slice*.mjs`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const workspacePath = path.resolve("app/src/pages/Workspace.tsx");
const appPath = path.resolve("app/src/App.tsx");
const homePath = path.resolve("app/src/pages/Home.tsx");
const modalPath = path.resolve("app/src/components/workspace/SingleDocConsentModal.tsx");
const apiPath = path.resolve("app/src/lib/api.ts");
const translationsPath = path.resolve("app/src/lib/translations.ts");

test("Group 8: Workspace removes obsolete Local/Cloud mode switches and repeated consent buttons", () => {
  const ws = fs.readFileSync(workspacePath, "utf8");

  // Obsolete manual controls must NOT exist
  assert.doesNotMatch(ws, /Enable Cloud AI/i);
  assert.doesNotMatch(ws, /Switch to Local Mode/i);
  assert.doesNotMatch(ws, /Cloud Translate/i);
  assert.doesNotMatch(ws, /Local Chat/i);
  assert.doesNotMatch(ws, /Cloud AI Chat/i);
  assert.doesNotMatch(ws, /enable-cloud-ai-btn/);
  assert.doesNotMatch(ws, /cloud-chat-toggle/);

  // Unified AI-first processing status indicators must exist
  assert.match(ws, /data-testid="workspace-status-indicator"/);
  assert.match(ws, /t\("ai\.status\.processing"\)/);
  assert.match(ws, /t\("ai\.status\.ai_response"\)/);
  assert.match(ws, /t\("ai\.status\.local_fallback"\)/);
  assert.match(ws, /data-testid="chat-response-source-badge"/);

  // Honest fallback banner preservation
  assert.match(ws, /data-testid="workspace-fallback-notice"/);
  assert.match(ws, /intel\?\.mode === "AI_CONSENTED" && !intel\?\.fallback_triggered/);
});

test("Group 8: One-time AI activation dialog discloses Gemini usage without transmitting on preview", () => {
  const modal = fs.readFileSync(modalPath, "utf8");

  assert.match(modal, /getAiSessionPreview\(\)/);
  assert.match(modal, /activateAiSession\(preview\.activation_id\)/);
  assert.match(modal, /data-testid="confirm-ai-activation-btn"/);
  assert.match(modal, /data-testid="decline-ai-activation-btn"/);

  // Accessibility semantics
  assert.match(modal, /role="dialog"/);
  assert.match(modal, /aria-modal="true"/);
  assert.match(modal, /e\.key === "Escape"/);
  assert.match(modal, /e\.key === "Tab"/);
});

test("Group 8: App verifies session token against backend and automatically drives Explain, Chat, and Translate", () => {
  const app = fs.readFileSync(appPath, "utf8");
  const home = fs.readFileSync(homePath, "utf8");
  const ws = fs.readFileSync(workspacePath, "utf8");

  // Never trust client storage alone: App checks backend session status on load
  assert.match(app, /getAiSessionStatus\(/);
  assert.match(app, /disableAiSession\(/);

  // Home passes active session credentials automatically on upload when activated
  assert.match(home, /uploadDocument\(\s*file,\s*language,\s*aiSession \? "ai" : "local",\s*aiSession\s*\)/);

  // App prompts one-time activation before external calls if not yet activated
  assert.match(app, /if \(!aiSession && !hasPromptedActivation\)/);
  assert.match(app, /runAutoAiExplain\(document\.id, language, creds\)/);

  // App runs automatic Gemini translation when AI session is active, local otherwise
  assert.match(app, /aiSession \? "ai" : "local"/);

  // Workspace sends Chat automatically using active aiSession (no per-question consent popup)
  assert.match(ws, /mode:\s*aiSession \? "ai" : "local"/);
  assert.match(ws, /ai_session_id:\s*aiSession\?\.aiSessionId/);
  assert.match(ws, /ai_session_token:\s*aiSession\?\.aiSessionToken/);
});

test("Group 8: All new AI-first status, disclosure, and control keys exist across English, Hindi, and Hinglish", () => {
  const content = fs.readFileSync(translationsPath, "utf8");
  const enSection = content.slice(content.indexOf("const en:"), content.indexOf("const hi:"));
  const hiSection = content.slice(content.indexOf("const hi:"), content.indexOf("const hinglish:"));
  const hinglishSection = content.slice(content.indexOf("const hinglish:"), content.indexOf("const dictionaries:"));

  const requiredGroup8Keys = [
    "ai.status.processing",
    "ai.status.ai_response",
    "ai.status.local_fallback",
    "ai.status.unavailable",
    "ai.control.enable",
    "ai.control.disable",
    "ai.activation.title",
    "ai.activation.subtitle",
    "ai.activation.loading",
    "ai.activation.recipient_label",
    "ai.activation.scope_label",
    "ai.activation.scope_value",
    "ai.activation.purpose_label",
    "ai.activation.disclosure_heading",
    "ai.activation.fallback_note",
    "ai.activation.decline_btn",
    "ai.activation.enable_btn",
    "ai.activation.activating",
    "ai.activation.close_aria",
  ];

  for (const key of requiredGroup8Keys) {
    const token = `"${key}":`;
    assert.ok(enSection.includes(token), `Missing ${key} in en`);
    assert.ok(hiSection.includes(token), `Missing ${key} in hi`);
    assert.ok(hinglishSection.includes(token), `Missing ${key} in hinglish`);
  }

  const api = fs.readFileSync(apiPath, "utf8");
  assert.match(api, /export async function getAiSessionPreview/);
  assert.match(api, /export async function activateAiSession/);
  assert.match(api, /export async function disableAiSession/);
  assert.match(api, /export async function getAiSessionStatus/);
});
