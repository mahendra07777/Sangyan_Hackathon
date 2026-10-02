# SANGYAN 2026 - Antigravity Phase Prompt Pack

Paste these prompts into Antigravity **one phase at a time**. Do not paste all phases at once.

## How to use this file

- Keep one canonical Git repository.
- Read the phase gate before moving forward.
- Ask Antigravity to report tests and changed files after every phase.
- Never allow fake AI outputs to masquerade as working features.
- Keep all important product/safety/source decisions in `docs/`.

---

# PHASE 0 - Product contract and research

**Sources to consult:** SANGYAN official site; current Unstop listing; SEBI Investor Survey 2025; SEBI Investor Education Reading Material; SEBI due-diligence guidance; SANGYAN Terms & Conditions/organiser announcements.

```text
You are the product lead, principal engineer, financial-domain research assistant, and hackathon strategist for SANGYAN 2026.

We are building Bharat Investor Copilot for SANGYAN Track C - Investor Education for Bharat.

MISSION
Build a public-good, multilingual, voice-first financial understanding product for Indian retail investors.

CORE USER JOURNEY
User gives a financial PDF, screenshot, or text -> system understands it -> extracts key facts -> explains jargon in plain language -> answers grounded follow-up questions -> switches to Hindi/Kannada -> supports voice -> teaches the underlying concept.

NON-NEGOTIABLE SAFETY
- No stock tips.
- No buy/sell/hold recommendations.
- No price predictions.
- No trading algorithms.
- No promotion of a specific security or broker.
- No monetisation funnel.
- No unauthorised harvesting of SMS, OTPs, PII, or financial records.

PRIMARY PERSONA
Kavita, 39, Tier-2 homemaker managing family savings and not fluent in English.

TASK
Research current SANGYAN rules and Track C requirements using official sources.
Research SEBI Investor Survey 2025 and official SEBI investor education materials.
Define the problem, user journey, MVP, non-goals, source hierarchy, safety contract, KPIs, and demo scenario.

DO NOT CODE.
Create:
- docs/product.md
- docs/sources.md
- docs/safety.md
- docs/evaluation.md
- docs/demo-script.md

For every factual claim, store source title, URL, date accessed, and why it matters.
Record any conflicts between the official site and Unstop instead of silently choosing.
Finish with a BUILD GATE checklist.
```

---

# PHASE 1 - Design

**Sources to consult:** SANGYAN Track C + judging criteria; SEBI Investor Survey 2025 language/channel findings; SEBI multilingual education material; approved `docs/product.md` and `docs/sources.md`.

Use Figma first. Approve the UX direction before production frontend work.

```text
Design a production-ready responsive web app called Bharat Investor Copilot for SANGYAN Track C.

Positioning: public-good investor education, not investment advice.
Tagline: Understand finance. In your language. Before you act.

Primary persona: Kavita, 39, Tier-2 homemaker, not fluent in English, uncomfortable with financial jargon.

Core flow:
Home -> Upload -> Analyze -> Simple Summary -> Key Facts -> Explain -> Ask -> Hindi/Kannada -> Voice -> Sources.

Design requirements:
- mobile-first;
- very low cognitive load;
- calm public-service aesthetic;
- no trading-terminal design;
- source/evidence visible;
- fact vs explanation vs uncertainty visually distinct;
- voice is useful and accessible;
- strong error and empty states;
- accessible controls;
- AI/privacy disclosure.

Create high-fidelity screens, components, design tokens, responsive rules, and developer handoff notes.

Create one polished end-to-end demo flow and include realistic synthetic/sample content.
```

---

# PHASE 2 - Repo and architecture

**Sources to consult:** approved `docs/product.md`, `docs/safety.md`, `docs/sources.md`; SANGYAN technology/guardrail requirements; current Antigravity documentation.

```text
Act as a principal software architect.

Create the production foundation for Bharat Investor Copilot.

STACK
Frontend: React + TypeScript + Tailwind.
Backend: Python + FastAPI.
Database: Supabase/Postgres.
AI provider abstraction: Gemini first.

Create:
- monorepo structure;
- routing/layout shell;
- typed API contracts;
- upload abstractions;
- database layer;
- environment variable handling;
- privacy-safe logging;
- error handling;
- basic test setup;
- docs/architecture.md;
- README.

Important:
- No fake AI results.
- No secrets in frontend.
- No persistent financial-data storage by default.
- Preserve source/evidence metadata in AI response schemas.

Use the approved Figma design as the UX source, but production code must live only in this repo.

Run lint/type checks/build/tests/browser smoke test. Fix errors before finishing.
```

---

# PHASE 3 - Document intelligence

**Sources to consult:** current Gemini document-understanding documentation; approved SANGYAN/SEBI source registry; public or synthetic demo documents.

```text
Implement the real document-understanding engine.

Use the current official Gemini document-understanding API and Files API guidance. Do not hard-code an outdated model name; use the current SDK/model supported by this project.

INPUTS
- PDF
- PNG/JPG image
- pasted text

STRICT STRUCTURED OUTPUT
Return:
- document_type
- simple_summary
- key_facts[]
- financial_terms[]
- important_sections[]
- uncertainty_notes[]
- source_references[]

Rules:
- Never invent numbers.
- Preserve units and periods.
- If information is missing, say so.
- Separate facts from explanations.
- No recommendations or price predictions.

UI states:
- upload;
- validating;
- processing;
- success;
- partial result;
- error.

Create at least 10 synthetic/demo evaluation cases.
Run automated and browser tests.
```

---

# PHASE 4 - Grounded Q&A + trust

**Sources to consult:** SEBI Investor Education Reading Material; SEBI due-diligence guidance; SEBI scam-awareness material; uploaded official documents; approved `docs/sources.md`.

```text
Implement grounded document Q&A and the trust layer.

Intent classes:
DOCUMENT_QA
FINANCIAL_EDUCATION
SOURCE_LOOKUP
UNSUPPORTED_OR_AMBIGUOUS
PROHIBITED_INVESTMENT_ADVICE

Flow:
1. classify intent;
2. retrieve document/source evidence;
3. generate answer;
4. safety/grounding validation;
5. return answer + answer_type + evidence + sources + uncertainty + language.

Allowed examples:
- What is debt?
- Why did profit change according to this document?
- Explain this in simple Hindi.
- Where is this mentioned?

Redirect examples:
- Should I buy this stock?
- Will this stock double?
- Which stock is best?
- Give me an F&O signal.

Do not fabricate.
Do not call model interpretation an official conclusion.
Do not expose hidden chain-of-thought.

Build source chips, evidence drawer, uncertainty badge, safety filter, and at least 30 adversarial test cases.
```

---

# PHASE 5 - Hindi/Kannada + voice

**Sources to consult:** SEBI Investor Survey 2025; SEBI multilingual investor-education pages/videos; current documentation for the selected Gemini/voice APIs.

```text
Implement Bharat-first language and voice support.

Languages:
- English
- Hindi
- Kannada

Requirements:
- language selector;
- explanation in selected language;
- voice input;
- transcript;
- answer in selected language;
- text-to-speech playback if supported;
- error/fallback states;
- accessible keyboard and screen-reader controls.

Quality requirements:
- do not corrupt numbers;
- preserve financial terminology;
- use simple natural language;
- preserve official entity names;
- test the same safety refusal in all supported languages.

Demo:
Create a polished Hindi voice interaction and a Kannada interaction.
```

---

# PHASE 6 - Product polish

**Sources to consult:** approved Figma design system; SANGYAN Bharat-first accessibility criteria; current accessibility guidance used by the implementation; `docs/safety.md`.

```text
Act as a senior product engineer and accessibility specialist.

Polish the app without adding large new features.

Focus on:
- mobile UX;
- loading states;
- error recovery;
- source visibility;
- AI disclosure;
- privacy explanation;
- accessibility;
- typography;
- touch targets;
- empty states;
- consistent wording.

Do not introduce investment-advice language or trading aesthetics.

Run browser checks on desktop and mobile viewports.
```

---

# PHASE 7 - Hostile QA

**Sources to consult:** SANGYAN constraints; `docs/safety.md`; `docs/evaluation.md`; current Antigravity/stack security documentation; approved SEBI source registry.

```text
Act as a release engineer and red-team tester.

Test:
- hallucinated numbers;
- wrong periods/units;
- unsupported claims;
- prompt injection in uploaded files;
- prompt injection in source content;
- buy/sell requests;
- price predictions;
- best-stock requests;
- personalized allocation requests;
- Hindi/Kannada safety consistency;
- empty/corrupt/scanned PDFs;
- oversized inputs;
- privacy and secret leakage;
- API error paths;
- accessibility;
- performance.

Fix critical/high defects and rerun affected tests.
Create docs/release-checklist.md with evidence.
```

---

# PHASE 8 - Demo and submission

**Sources to consult:** current SANGYAN official submission instructions; current Unstop submission window; SANGYAN judging criteria; measured internal evaluation results; approved source registry.

```text
Act as the final demo director and submission engineer.

Prepare a 3-5 minute judge demo around one person: Kavita.

Story:
1. difficult financial information;
2. upload;
3. simple summary;
4. key fact;
5. explain a term;
6. switch to Hindi;
7. ask by voice;
8. show source/evidence;
9. teach the concept;
10. close with the safety message.

Safety close:
"We don't tell investors what to buy. We help them understand what they're looking at."

Create:
- docs/demo-script.md;
- docs/release-checklist.md;
- final README section;
- backup demo data;
- exact browser steps for the live demo.

Do not invent impact numbers. Use actual internal measurements from the evaluation set.
```

---

# Emergency prompt - when Antigravity gets confused

```text
STOP.
Do not add new features.
Read docs/product.md, docs/design.md, docs/architecture.md, docs/safety.md, docs/sources.md, and docs/evaluation.md.

Summarize:
1. current product goal;
2. current phase;
3. current failure;
4. exact root cause;
5. smallest fix that preserves the architecture.

Do not refactor unrelated code.
Do not change the product scope.
Do not introduce mock/fake AI outputs.
Run the narrowest relevant tests, then the main build.
```

---

# Review prompt - Claude

```text
You are reviewing an AI financial-education hackathon product before judging.

Do not be polite. Find concrete weaknesses.

Evaluate:
- problem clarity;
- actual usefulness;
- Bharat-first usability;
- multilingual quality;
- voice utility;
- grounding and source transparency;
- safety and investment-advice leakage;
- privacy;
- technical credibility;
- feasibility;
- demo clarity.

Return the 10 highest-value changes, each with severity and exact fix.
Do not invent missing evidence.
```

---

# Review prompt - Codex

```text
Perform an independent engineering audit of the current repository.

Do not rebuild the app.
Find:
- security bugs;
- secret leakage;
- broken error handling;
- type issues;
- prompt injection paths;
- unsafe investment-advice paths;
- test gaps;
- deployment failures;
- performance problems.

Return a prioritized defect list with reproduction steps and fixes.
```

