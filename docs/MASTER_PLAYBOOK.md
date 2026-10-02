# SANGYAN 2026 - Bharat Investor Copilot
## Master Build Playbook for a 4-Person Team

**Version:** 1.0
**Date:** 1 October 2026
**Primary track:** Track C - Investor Education for Bharat
**Product:** Bharat Investor Copilot
**Tagline:** *Understand finance. In your language. Before you act.*

---

## 0. Executive decision

We are building a **public-good, multilingual, voice-first financial understanding platform** for Indian retail investors, with a primary focus on users who are more comfortable in Indian regional languages and users who find financial documents, disclosures, and terminology difficult to understand.

The MVP will focus on one deep journey:

> **A user gives us a financial document, screenshot, or text -> the product extracts useful information -> explains it in plain language -> lets the user ask follow-up questions -> switches language -> can speak the explanation -> teaches the underlying financial concept.**

This is intentionally **not** a stock-picking app, trading assistant, broker funnel, or investment-advice product.

### Product promise

> **We do not tell investors what to buy. We help them understand what they are looking at.**

### Why this direction fits SANGYAN

The official SANGYAN page lists Track C as **Investor Education for Bharat**, with suggested directions including **Voice-First Explainer, Consequence Simulator, and Plain-Language Disclosure Reader**. It also states that depth on one real user journey is valued over breadth. The judging criteria give 30% to resilience/safety impact, 25% to Bharat-first usability/accessibility, 15% to guardrail compliance/trust, 15% to technical execution, and 15% to feasibility/scalability.

SANGYAN also states that no stock tips, buy/sell/hold signals, price predictions, trading algorithms, or promotion of a specific instrument/broker are allowed; privacy by design is required.

### Current event facts to track

- Teams: 1-4 members.
- Prize pool: Rs 1,70,000; listed top prizes: Rs 1,00,000 / Rs 50,000 / Rs 20,000.
- Official SANGYAN site currently shows a 1-4 October build sprint, shortlist 5 October, final jury 6 October, results 7 October.
- The current Unstop page shows an updated submission window around 3-4 October 2026. Because event pages can change, the team should treat **the current Unstop submission window and organiser Discord announcements as operational truth** if they differ from the descriptive schedule on the public site.
- SANGYAN's official FAQ says third-party/open-source/commercial technology is allowed, with third-party components disclosed in the submission.
- The official site says submission IP vests with NSDL under its Terms & Conditions. Read the current Terms & Conditions before submitting any code or material you may want to commercialize later.

Sources: See the Source Registry at the end of this document.

---

# 1. Product thesis

## 1.1 Problem

Indian investors can increasingly access financial products and information, but access is not the same as understanding. Complex disclosures, jargon, English-heavy content, fragmented information, and unfamiliar financial concepts can create a gap between having information and being able to understand it.

SEBI's Investor Survey 2025 covered more than 90,000 households across urban and rural India. In its chapter on investor education, the survey reports that fraud prevention, risk management, and investor rights are among the most demanded education topics; it also reports language preferences of approximately 47% Hindi, 47% regional languages, and 5% English for investor-education content. The report also identifies mobile apps and social media as important channels.

These data points support a product that makes financial education simpler, local-language, mobile-friendly, and interactive.

## 1.2 Target user

Primary persona:

### Kavita, 39 - Tier-2 homemaker

- Manages family savings.
- Comfortable with everyday financial decisions, but not with financial jargon.
- Not fluent in English.
- May encounter IPOs, mutual funds, company disclosures, investment promotions, or financial messages online.
- Wants to understand information before acting.

Secondary personas:

### Praveen, 22 - Tier-3 graduate / gig worker

Newer market participant exposed to social-media and messaging-based financial content.

### Babulal, 63 - retired investor

May hold old/dormant folios and find digital financial processes difficult.

The first demo should be centered on **Kavita**, because the product's strongest differentiator is understanding-first, regional-language access.

---

# 2. Product scope

## 2.1 Core user journey

```text
LANDING PAGE
    |
    +--> Upload PDF
    +--> Upload screenshot/image
    +--> Paste text/link
    +--> Speak a question
    |
    v
DOCUMENT / CONTENT UNDERSTANDING
    |
    +--> Extract key facts
    +--> Detect financial terms
    +--> Build grounded context
    |
    v
UNDERSTAND
    |
    +--> Plain-language summary
    +--> Key facts
    +--> Explain buttons
    +--> "Why does this matter?" prompts
    |
    v
ASK
    |
    +--> Text Q&A
    +--> Voice Q&A
    +--> Answers grounded in uploaded content
    |
    v
BHARAT MODE
    |
    +--> English
    +--> Hindi
    +--> Kannada
    +--> Voice response
    |
    v
LEARN
    |
    +--> Explain the underlying concept
    +--> Mini examples
    +--> Optional 1-question comprehension check
```

## 2.2 MVP features

### A. Universal input

- PDF upload.
- Screenshot/image upload.
- Text paste.
- Optional URL input only if it is safe, reliable, and feasible within the sprint.

### B. Plain-language disclosure reader

The AI should produce:

- what the document is;
- what it says in simple language;
- key numbers/facts found in the content;
- important financial terms;
- what is directly stated vs. what is explanatory interpretation;
- source/reference location when possible.

### C. Explain button

Each important metric or financial term gets:

- What it means.
- Why it matters generally.
- What the current document says about it.
- A simple example.

### D. Document-grounded Q&A

Users can ask:

- "What happened to profit?"
- "What does debt mean?"
- "Where does the document mention cash flow?"
- "Explain this paragraph in simple Hindi."

Answers must be grounded in the provided document when the question concerns that document.

### E. Multilingual mode

MVP languages:

- English
- Hindi
- Kannada

Architecture should make additional Indian languages easy to add later.

### F. Voice mode

- Speech-to-text for user questions.
- Text-to-speech for the answer.
- Same-language response mode where feasible.
- Visible transcript for accessibility and debugging.

### G. Trust layer

Every substantive response should have a visible classification where useful:

- **Document-backed** - directly supported by the user's content.
- **Educational explanation** - general concept explanation.
- **Interpretive/contextual** - model-generated explanation that should not be mistaken for an official conclusion.

When a source is available, show it.

---

# 3. Explicit non-goals and safety rails

## Never build

- Buy/sell/hold recommendations.
- Stock or mutual-fund "best picks".
- Price targets or price predictions.
- Trading signals.
- Automated trading algorithms.
- Broker promotion.
- Affiliate or paid upsell funnels.
- Personalized investment suitability decisions.
- Portfolio allocation instructions that function as investment advice.
- Unauthorised harvesting of SMS, OTPs, contacts, or personal financial records.

## The copilot can say

- "The document states ..."
- "Here is a simple explanation ..."
- "I could not verify this claim from the sources available to this prototype."
- "This is educational information, not an investment recommendation."
- "For an official regulatory answer, consult the relevant authority/source."

## The copilot must not say

- "You should buy X."
- "This will go up."
- "This is the best stock."
- "Guaranteed return."
- "You should invest Rs X."

---

# 4. Tool strategy - use each tool where it is strongest

## Primary engineering cockpit: Google Antigravity

Use **Antigravity** as the production workspace and source of truth for the codebase.

Why:

- Its agent can operate across editor, terminal, and browser.
- It supports multi-step engineering tasks, browser-based verification, artifacts, and parallel agent conversations.
- Antigravity 2.0 can orchestrate agents, web searches, skills/MCP integrations, Chrome interaction, and implementation plans.
- This makes it the best single cockpit for a time-boxed hackathon build.

Rule: **one repository, one canonical production codebase, one architecture.**

## Design exploration: Figma

Use **Figma Design + Figma AI/Make** before production frontend implementation.

Figma Make is useful for quickly turning ideas/designs into interactive prototypes and can use existing designs, files, web references, and collaborative iteration.

But do not maintain a separate production app inside Figma Make. Treat Figma as the **design/prototype truth**, then implement the approved design in the Antigravity repository.

## Document/AI research and model experimentation: Gemini

Use **Gemini** especially for:

- understanding long financial PDFs;
- document images/tables/charts;
- structured extraction;
- multilingual experiments;
- prompt evaluation on financial documents.

Google's Gemini document-understanding documentation says Gemini can process PDFs with native vision, including text, images, diagrams, charts, and tables, and can produce structured outputs; the Files API is recommended for larger/reused documents.

For the application, use the Gemini API only after the product contract is defined.

## Critical review and adversarial QA: Claude

Use your Claude subscription for:

- product critique;
- prompt red-teaming;
- code review;
- UX critique;
- finding hidden failure modes;
- simplifying the final architecture;
- preparing judge Q&A.

Do not ask Claude to independently rebuild the whole app unless there is a concrete reason; this increases tool fragmentation.

## Independent engineering audit: Codex

Use Codex as an optional second-opinion engineer for:

- bug finding;
- refactoring;
- test generation;
- security review;
- frontend polish review.

Codex is an agentic coding system designed for writing, reviewing, editing, and debugging code. Use it as a **reviewer/backup**, not as a second competing source of truth.

### Final tool map

| Phase | Primary | Secondary | Output |
|---|---|---|---|
| 0. Requirements + research | Claude + Gemini | Web/SEBI sources | PRD + source registry |
| 1. UX/product design | Figma | Claude | Design system + clickable prototype |
| 2. Project skeleton | Antigravity | Codex | Clean repo + architecture |
| 3. Document engine | Gemini API + Antigravity | Claude | PDF/image understanding |
| 4. Grounded Q&A + trust | Antigravity | Claude | RAG/grounding + labels |
| 5. Multilingual + voice | Gemini/API stack | Claude | Hindi/Kannada + voice |
| 6. UX polish | Antigravity | Figma | Production UI |
| 7. QA + red-team | Antigravity | Claude + Codex | Test report + fixes |
| 8. Demo + submission | Claude + Antigravity | Figma | Demo flow + evidence |

---

# 5. Repository contract

Antigravity must maintain this structure unless there is a strong technical reason to change it:

```text
bharat-investor-copilot/
├── app/                    # frontend
├── server/                 # backend/API
├── ai/                     # prompts, schemas, evaluation helpers
├── data/
│   ├── sources/            # approved public source metadata
│   ├── demo/               # synthetic/demo documents only
│   └── eval/               # test questions + expected behaviors
├── docs/
│   ├── product.md
│   ├── design.md
│   ├── architecture.md
│   ├── safety.md
│   ├── sources.md
│   ├── evaluation.md
│   └── demo-script.md
├── public/
├── tests/
├── .env.example
├── README.md
└── antigravity/
    ├── rules.md
    └── phase-status.md
```

## Source-of-truth rule

No model is allowed to silently invent official facts.

The system should preserve provenance:

```text
Answer
  -> evidence chunks
  -> source/document
  -> page/section if available
```

---

# 6. Phase 0 - Requirements, domain research, and product contract

## Objective

Before writing production code, lock:

- exact track fit;
- problem statement;
- primary persona;
- core journey;
- MVP/non-MVP features;
- safety boundaries;
- approved source hierarchy;
- success metrics;
- demo scenario.

## Deliverables

- `docs/product.md`
- `docs/sources.md`
- `docs/safety.md`
- `docs/evaluation.md`
- `docs/demo-script.md`

## Sources to consult in this phase

1. SANGYAN official site: challenge, Track C, judging criteria, constraints, personas, submission.
2. Current Unstop listing: submission window and operational event information.
3. SEBI Investor Survey 2025: language preference, investor-education needs, information channels, user barriers.
4. SEBI Investor education reading material: topics and educational content.
5. SEBI due-diligence guidance.
6. SEBI scam/fraud-awareness material.
7. Current SANGYAN Terms & Conditions and organiser announcements.

## PHASE 0 ANTIGRAVITY PROMPT

```text
You are the product lead, principal engineer, financial-domain research assistant, and hackathon strategist for SANGYAN 2026.

We are building "Bharat Investor Copilot" for SANGYAN Track C - Investor Education for Bharat.

MISSION
Build a real, useful, public-good product for Indian retail investors that turns complex financial information into simple, multilingual, voice-first understanding.

NON-NEGOTIABLE EVENT RULES
- No stock tips.
- No buy/sell/hold recommendations.
- No price predictions.
- No trading algorithms.
- No promotion of a specific security or broker.
- No monetisation funnel.
- No unauthorised harvesting of SMS, OTPs, PII, or financial records.
- Clearly disclose AI and third-party components.
- Explain uncertainty.

PRIMARY USER
Kavita, 39, Tier-2 homemaker managing family savings and not fluent in English.
Secondary personas are Praveen, 22, and Babulal, 63.

CORE USER JOURNEY
User provides a financial PDF, screenshot, or text -> system understands it -> extracts key facts -> explains jargon in plain language -> answers grounded follow-up questions -> switches to Hindi/Kannada -> provides voice interaction -> teaches the underlying concept.

YOUR TASK
1. Research the latest official SANGYAN requirements from the official site, current Unstop listing, and organiser announcements.
2. Research SEBI's Investor Survey 2025 and official SEBI investor education materials.
3. Build a concise problem statement backed by evidence.
4. Define the single most important user journey.
5. Define the MVP and explicitly reject low-value features.
6. Define the source hierarchy: official regulator/issuer material first, then other high-trust sources, with unknown/unsupported claims clearly labeled.
7. Define a safety and refusal contract for the AI.
8. Define measurable product KPIs, including comprehension improvement, answer grounding rate, latency, and usability.
9. Define the 3-5 minute demo scenario.
10. Produce docs/product.md, docs/sources.md, docs/safety.md, docs/evaluation.md, and docs/demo-script.md.

DO NOT CODE THE APP YET.

For every important factual claim, record the source title, URL, date accessed, and the exact reason it matters to the product.

Do not invent statistics. If an event page or source conflicts with another source, record the discrepancy and identify which source should be treated as operational truth.

Finish with a "BUILD GATE": a checklist the team must satisfy before Phase 1.
```

## Phase 0 gate

Do not proceed until the team can answer in one sentence:

> **Who is the user, what exact understanding problem do we solve, and why is AI genuinely useful here?**

---

# 7. Phase 1 - UX and design system

## Objective

Create a calm, trustworthy, Indian-first interface with very low cognitive load.

## Design principles

### 1. Understanding first
Do not make the home page look like a trading terminal.

### 2. Trust without fear
Use clear labels and source indicators, not alarmist red screens everywhere.

### 3. Mobile-first
The primary persona should be able to use it on a modest phone.

### 4. Voice-first option
The microphone should be prominent but not gimmicky.

### 5. Bilingual clarity
Support a language toggle everywhere it matters.

### 6. Source visibility
The user can always understand where a factual answer came from.

### 7. Explain at the point of confusion
Every important financial number/term should have an Explain action.

## Core screens

1. Landing / upload.
2. Workspace / document analysis.
3. Plain-language summary.
4. Key facts and terms.
5. Explain modal/drawer.
6. Ask-about-document chat.
7. Voice mode.
8. Language selector.
9. Sources/evidence view.
10. Safety/AI information panel.
11. Optional onboarding for first-time users.

## Visual direction

- Modern public-service product, not a brokerage app.
- Use a restrained neutral palette with one accessible accent.
- Rounded cards, strong typography, clear hierarchy.
- Avoid neon trading colors as primary visual language.
- Avoid excessive gradients and dashboard clutter.
- Use familiar icons and large touch targets.
- Make accessibility states visible.

## PHASE 1 FIGMA PROMPT

```text
Design a production-ready web application named "Bharat Investor Copilot" for SANGYAN 2026 Track C - Investor Education for Bharat.

PRODUCT POSITIONING
This is a public-good investor education product, not a trading platform or investment advisor.
Tagline: "Understand finance. In your language. Before you act."

PRIMARY USER
Kavita, 39, Tier-2 homemaker managing family savings, not fluent in English, comfortable with smartphones but not financial jargon.

CORE EXPERIENCE
1. Upload a financial PDF, screenshot, or paste text.
2. Receive a simple summary.
3. See key facts and financial terms.
4. Tap "Explain" on any difficult item.
5. Ask questions about the document.
6. Switch English/Hindi/Kannada.
7. Use voice input and voice output.
8. See clear evidence/source references.

CREATE THESE SCREENS
- Home
- Upload state
- Processing state
- Analysis dashboard
- Summary
- Key facts
- Explain drawer/modal
- Document Q&A
- Voice Q&A
- Sources/evidence
- Empty/error/offline-like state
- Privacy + AI disclosure

UX RULES
- Minimal cognitive load.
- Mobile-first.
- Large touch targets.
- No trading-terminal aesthetic.
- No buy/sell language.
- No investment recommendation widgets.
- Source indicators must be easy to understand.
- Include realistic sample content.

DESIGN SYSTEM
Define typography, spacing, radius, elevation, component states, button hierarchy, cards, chips, source badges, confidence/grounding labels, audio controls, upload dropzone, chat, and accessibility rules.

OUTPUT
- High-fidelity frames.
- Component library.
- Responsive behavior.
- Design tokens.
- Developer handoff notes.
- One complete 3-5 minute demo journey from Home -> Upload -> Explain -> Hindi/Kannada -> Voice -> Sources.

Before finalizing, critique the design for:
1. Cognitive overload.
2. Whether it looks too much like a trading app.
3. Whether an older or less finance-literate user can understand the next action.
4. Whether trust and sources are visible without dominating the UI.
```

## Phase 1 gate

The team should be able to click through one complete demo journey in Figma without explaining what every button means.

---

# 8. Phase 2 - Production skeleton and architecture

## Objective

Create a clean, boring, reliable foundation before adding AI complexity.

## Recommended stack

### Frontend

- React
- TypeScript
- Tailwind CSS
- accessible component system
- browser audio APIs where appropriate

### Backend

- Python + FastAPI
- structured API contracts
- environment variables for secrets

### Data

- Supabase/Postgres for application state and optional pgvector.
- Object storage for temporary documents only where necessary.

### AI

- Gemini API for document understanding and multilingual tasks.
- Provider interface so the model can be swapped later.

### Deployment

- Vercel/Netlify for frontend if convenient.
- Render/Railway/Fly/Cloud Run for backend depending on team familiarity.
- Use the simplest reliable hosted stack available to the team.

## PHASE 2 ANTIGRAVITY PROMPT

```text
Act as the principal software architect and staff engineer.

Create the production foundation for Bharat Investor Copilot.

IMPORTANT
Do not add fake AI results. Do not create large mock dashboards pretending the AI works. Establish clean interfaces so real AI can be connected later.

STACK
Frontend: React + TypeScript + Tailwind.
Backend: Python + FastAPI.
Database: Supabase/Postgres.
AI provider abstraction: Gemini implementation first.

CREATE
1. Clean monorepo/repository structure.
2. Frontend routing and layout shell.
3. API client.
4. Backend health endpoint.
5. Typed schemas for:
   - UserInput
   - UploadedDocument
   - DocumentAnalysis
   - ExtractedFact
   - FinancialTerm
   - SourceReference
   - Answer
   - EvidenceChunk
   - Language
   - VoiceRequest
6. Environment variable handling.
7. Error boundary and API error format.
8. Logging with privacy-safe defaults.
9. Basic test setup.
10. README with local setup.
11. docs/architecture.md.
12. docs/safety.md with placeholder sections linked to the product contract.

ARCHITECTURE RULES
- Provider-agnostic AI interface.
- No secrets in frontend.
- No persistent storage of sensitive user documents by default.
- Make document retention configurable.
- Store only what is necessary for the demo.
- Every AI response object should support evidence/source metadata.
- Build observability hooks for latency, failures, and model errors.

UI
Implement the approved Figma structure closely, but do not chase pixel-perfect details before the core product works.

VERIFICATION
Run type checks, linting, unit tests, build, backend tests, and a basic browser smoke test.
Fix all errors before finishing.

At the end, report:
- files created/changed;
- architecture decisions;
- commands run;
- test results;
- remaining risks;
- exact next integration point for Gemini document analysis.
```

## Phase 2 gate

`npm run build` / backend tests must be clean, the app must run locally, and no API secret may exist in the browser bundle.

---

# 9. Phase 3 - Document intelligence

## Objective

Make the central experience work on real documents.

## Recommended approach

For the hackathon MVP, prioritize **Gemini native document understanding** over building an elaborate document parser from scratch.

Gemini's current documentation says its document understanding can process PDFs with text, images, diagrams, charts, and tables, and can return structured output. It recommends the Files API for larger/reused documents.

## Pipeline

```text
PDF/image
   |
   v
Upload validation
   |
   v
Gemini document understanding
   |
   +--> document type
   +--> summary
   +--> key facts
   +--> terms
   +--> evidence references
   +--> questions the document can answer
   |
   v
Typed JSON schema
   |
   v
Frontend rendering
```

## PHASE 3 ANTIGRAVITY PROMPT

```text
Implement the real document-understanding engine for Bharat Investor Copilot.

MODEL STRATEGY
Use Gemini's current document-understanding capabilities and Files API where appropriate. Follow the latest official Gemini API documentation for the exact SDK and model names available to this project. Do not hard-code an outdated model name if the SDK exposes a better current option.

INPUTS
- PDF
- PNG/JPG screenshot
- pasted text when available

OUTPUT SCHEMA
Return strict structured JSON containing:

{
  document_type,
  simple_summary,
  key_facts: [
    {
      label,
      value,
      unit,
      explanation,
      evidence_reference
    }
  ],
  financial_terms: [
    {
      term,
      plain_language_definition,
      why_it_matters_general,
      document_context,
      evidence_reference
    }
  ],
  important_sections,
  uncertainty_notes,
  source_references
}

GROUNDING RULES
- Never invent a financial number.
- If a number is not present or cannot be reliably extracted, say "Not found".
- Preserve units and periods.
- Distinguish reported facts from calculations.
- If the document is ambiguous, say so.
- Do not infer an investment recommendation.
- Do not infer future price movement.

UX
Implement:
- upload validation;
- progress state;
- analysis skeleton;
- success state;
- parse failure state;
- document summary;
- key fact cards;
- term cards;
- source/evidence references.

EVIDENCE
For every key fact and document-specific answer, preserve enough metadata to trace back to the document page/section or source reference when technically available.

TEST SET
Create at least 10 synthetic/demo test cases covering:
- clean PDF text;
- tables;
- charts;
- scanned image;
- missing value;
- ambiguous period;
- Hindi question;
- Kannada question;
- misleading wording;
- unsupported question.

Do not use real users' financial records.

VERIFY
Run automated tests plus browser tests for upload -> analysis -> render.
```

## Phase 3 source pack

- Gemini document processing documentation.
- SEBI investor education material to design realistic educational examples.
- Demo documents should be public documents or deliberately synthetic.
- Do not upload private financial records to the prototype for testing.

## Phase 3 gate

A judge can upload a representative PDF and get a structured, visually clear summary without seeing placeholder text.

---

# 10. Phase 4 - Grounded Q&A, explanation engine, and trust

## Objective

Turn a summary tool into an interactive educational assistant without allowing hallucinated financial advice.

## Response architecture

```text
USER QUESTION
    |
    v
Intent check
    |
    +--> document question
    +--> general education question
    +--> prohibited/advice request
    |
    v
Evidence retrieval
    |
    v
Answer generation
    |
    v
Safety + grounding check
    |
    v
Answer + evidence + uncertainty
```

## Intent classes

1. `DOCUMENT_QA`
2. `FINANCIAL_EDUCATION`
3. `SOURCE_LOOKUP`
4. `UNSUPPORTED_OR_AMBIGUOUS`
5. `PROHIBITED_INVESTMENT_ADVICE`

## PHASE 4 ANTIGRAVITY PROMPT

```text
Implement the grounded Q&A and trust layer.

PRIMARY GOAL
The assistant should answer questions about the uploaded content accurately and explain financial concepts in simple language while refusing prohibited investment-advice behavior.

PIPELINE
1. Classify intent.
2. Retrieve evidence from uploaded document and approved source registry.
3. Generate answer.
4. Run a separate safety/grounding validation step.
5. Return:
   - answer;
   - answer_type;
   - evidence;
   - source references;
   - uncertainty note;
   - language;
   - safety state.

EXAMPLES
Allowed:
- "What is debt?"
- "Why did revenue change according to this document?"
- "Explain this in simple Hindi."
- "Where in the document is this mentioned?"

Must refuse/redirect:
- "Should I buy this stock?"
- "Will this stock double?"
- "Which stock is best?"
- "Give me an F&O signal."

REFUSAL STYLE
Be brief and helpful. Redirect to explanation, factual document interpretation, or official source information.

GROUNDING
When the user asks about the uploaded document, answer from retrieved document evidence first.
If evidence is insufficient, do not fabricate.

SOURCE HIERARCHY
1. Uploaded official document.
2. SEBI official material.
3. Other named official regulator/exchange/depository/company sources where appropriate.
4. Secondary sources only when explicitly allowed by the source policy.

IMPORTANT
Do not call an uncertain interpretation a fact.
Do not present model-generated financial conclusions as official regulatory guidance.
Do not expose hidden chain-of-thought. Return concise explanations and evidence snippets/locations.

BUILD
- chat UI;
- source chips;
- evidence drawer;
- uncertainty badge;
- intent classifier;
- safety filter;
- document Q&A endpoint;
- education endpoint;
- test suite with at least 30 adversarial questions.

Create docs/evaluation.md with measured grounding and refusal results.
```

## Phase 4 source pack

- Uploaded source documents.
- SEBI Investor education material.
- SEBI due diligence guidance.
- SEBI fraud/scam awareness guidance.

---

# 11. Phase 5 - Multilingual + voice

## Objective

Make the Bharat-first promise tangible instead of just adding a language dropdown.

## MVP language flow

English document -> Hindi explanation -> voice question -> Hindi answer.

Then repeat one critical interaction in Kannada.

## Voice principles

- Always show a text transcript.
- Let users replay audio.
- Give a text fallback if speech fails.
- Keep voice prompts short.
- Don't hide sources behind audio.

## PHASE 5 ANTIGRAVITY PROMPT

```text
Implement the Bharat-first language and voice experience.

LANGUAGES
- English
- Hindi
- Kannada

REQUIRED FEATURES
1. Global language selector.
2. Document explanation in selected language.
3. User can ask a question by voice.
4. Speech-to-text transcript appears before/with the answer.
5. Answer is returned in the chosen language.
6. Optional text-to-speech playback.
7. Error and fallback states.

LANGUAGE QUALITY
- Preserve financial terminology accurately.
- Prefer simple, natural language over word-for-word translation.
- Keep important English terms in parentheses when that improves understanding.
- Do not translate regulatory/entity names incorrectly.
- Never change numeric values during translation.

VOICE UX
- Large microphone button.
- Recording state.
- Stop/cancel control.
- Transcript confirmation.
- Playback control.
- Clear error state.
- Avoid autoplay unless user explicitly asks/initiates.

ACCESSIBILITY
- Keyboard accessible.
- Visible focus states.
- Good contrast.
- Screen-reader labels.
- Text transcript always available.

DEMO
Create one polished voice journey in Hindi and one in Kannada.

VERIFY
Test code-switching, numbers, financial abbreviations, names, and refusal behavior in all three languages.
```

## Phase 5 source pack

- SEBI Investor Survey 2025 language-preference findings.
- SEBI Investor educational content available in Indian languages.
- Current official Gemini/API speech documentation for the selected implementation.
- Any voice provider documentation actually used.

---

# 12. Phase 6 - Product polish, accessibility, and "future product" quality

## Objective

Make the prototype feel like an actual product that could continue after the hackathon.

## Product-quality checklist

### Navigation

- Clear next action.
- No dead-end screens.
- Back navigation works.
- Loading states are understandable.

### Empty states

Explain what the user can do rather than showing generic "No data".

### Errors

Every error should explain:

- what happened;
- what the user can do next;
- whether the document needs re-uploading;
- whether the problem is temporary.

### Trust

The UI should visibly distinguish:

- document facts;
- educational explanations;
- uncertainty;
- sources.

### Privacy

Show a simple "What happens to my document?" panel.

The app should store the minimum information necessary.

### No dark patterns

No pressure countdowns, fake urgency, investment prompts, or monetisation funnels.

## PHASE 6 CLAUDE CRITIQUE PROMPT

```text
Act as a skeptical senior product designer, accessibility reviewer, and financial-product UX critic.

Review the current Bharat Investor Copilot UI from the perspective of:
- a 39-year-old Tier-2 user not fluent in English;
- a 63-year-old retired investor;
- a first-time investor;
- a hackathon judge.

Do not praise it generically.
Find the top usability failures, trust problems, cognitive overload, ambiguous language, accessibility problems, misleading visual cues, and features that accidentally resemble an investment-advice product.

For every issue, give:
1. severity;
2. why it matters;
3. exact UI/content change;
4. test case.

Pay special attention to:
- whether the user understands what to do next;
- whether the source/evidence relationship is clear;
- whether language switching feels natural;
- whether voice adds utility rather than novelty;
- whether an older user can recover from errors;
- whether the interface feels like public-good investor infrastructure rather than a brokerage app.
```

---

# 13. Phase 7 - Red-team QA and engineering audit

## Objective

Assume the judges are trying to break the product.

## Required tests

### Hallucination

- Unsupported numbers.
- Wrong units.
- Wrong year/period.
- Invented company claims.

### Advice boundary

- Buy/sell requests.
- Price predictions.
- "Best stock" questions.
- Personalized allocation requests.

### Multilingual safety

The same prohibited request in English, Hindi, and Kannada.

### Document attacks

- Empty PDF.
- Very large PDF.
- Scanned PDF.
- Image-only document.
- Corrupted file.
- Password-protected file if unsupported.

### Privacy

- Ensure secrets are not returned.
- Ensure uploaded content isn't accidentally logged.
- Ensure frontend cannot access backend secrets.

### Performance

Measure:

- upload latency;
- analysis latency;
- Q&A latency;
- voice latency;
- error rate.

## PHASE 7 CODEX AUDIT PROMPT

```text
Act as an independent senior software engineer performing a hostile pre-submission audit of Bharat Investor Copilot.

You are not the primary implementer. Assume another agent wrote this system and you must find defects.

Audit:
1. Security and secret handling.
2. Input validation.
3. API error handling.
4. Race conditions.
5. Broken states.
6. Type safety.
7. Prompt injection risk in uploaded documents.
8. Prompt injection risk in web/source content.
9. Hallucination pathways.
10. Investment-advice leakage.
11. Multilingual safety consistency.
12. Accessibility.
13. Performance bottlenecks.
14. Deployment reliability.
15. Data retention/privacy.

Do not rewrite everything.
Produce a prioritized defect report with:
- severity;
- reproduction steps;
- affected files;
- recommended fix;
- whether the fix is required before submission.

Then run relevant tests and verify each critical fix.
```

## PHASE 7 ANTIGRAVITY VERIFICATION PROMPT

```text
Act as the release engineer.

Run a full pre-submission verification of Bharat Investor Copilot.

Required:
- install/build from a clean environment;
- frontend lint/type checks;
- backend tests;
- integration tests;
- browser smoke tests;
- upload/analyze/Q&A/voice/language flow;
- prohibited advice tests;
- mobile viewport checks;
- error-state checks;
- source/evidence rendering;
- privacy/secrets scan;
- production build.

Do not stop at the first error. Fix critical and high-severity defects, then rerun the affected tests.

Produce docs/release-checklist.md with PASS/FAIL evidence for every item.
```

---

# 14. Phase 8 - Demo, story, and submission package

## Objective

Convert a good product into a judge-friendly demonstration.

## 3-5 minute story

### 0:00-0:30 - Human problem

Show a realistic disclosure/message that is difficult to understand.

Narrative:

> "Financial information is available. Understanding it is still a barrier."

### 0:30-1:15 - Upload

Upload the sample document.

Show:

- summary;
- key facts;
- important terms.

### 1:15-2:00 - Explain

Tap a difficult term.

Show:

- simple explanation;
- why it matters generally;
- source/evidence.

### 2:00-2:45 - Bharat moment

Switch to Hindi.

Ask by voice.

Answer comes back in Hindi with transcript.

### 2:45-3:30 - Learn

Ask:

> "Debt kya hota hai?"

Explain the concept in simple language.

### 3:30-4:00 - Trust

Show source references and uncertainty handling.

### 4:00-4:30 - Safety close

> "We don't tell investors what to buy. We help them understand what they're looking at."

If the allowed presentation length is different, adapt to the organiser's current submission instruction.

## Demo rules

- Never demo a fragile live dependency unless you have a fallback recording.
- Keep a local/screenshot backup of the critical result.
- Use a deliberately prepared test document.
- Keep a second backup document.
- Never use private financial data in the demo.
- Never improvise financial facts.

---

# 15. The "killer feature" strategy

Our differentiation is not "AI chatbot".

It is the combination:

> **Document -> plain-language explanation -> evidence -> regional language -> voice -> learning**

The strongest product moment should be:

### "Explain this to me in my language."

The second strongest moment:

### "Show me where that came from."

The third:

### "Teach me the concept behind it."

This creates a product loop that is useful today and extensible later.

---

# 16. Future roadmap after the hackathon

Do not build these during the core sprint unless the primary flow is stable.

## Version 1.1

- More Indian languages.
- Better document citations.
- More accessible voice UX.
- Saved learning history.
- Personal learning goals.

## Version 1.2

- Claim evidence checker as a separate mode.
- Public-source retrieval with clear provenance.
- Financial-content literacy mode for social posts.

## Version 2

- Offline/low-bandwidth mode.
- IVR or assisted access.
- More accessibility for elderly/low-literacy users.
- Structured educational courses.
- Grievance/right-process navigation as an adjacent module.

The future roadmap should remain consistent with SANGYAN's public-good ethos.

---

# 17. Metrics to collect during the hackathon

## Product metrics

### Comprehension improvement

Before explanation:

> "I do not understand this."

After explanation:

> 1-question or 3-question comprehension check.

Track the percentage of answers correct after explanation.

### Grounding rate

Percentage of document-specific answers with valid evidence references.

### Unsupported-answer rate

Percentage of questions correctly answered with "insufficient evidence" rather than hallucination.

### Safety rate

Percentage of prohibited investment-advice requests correctly redirected.

### Accessibility

- successful voice interaction rate;
- language switch success;
- mobile completion rate.

## Suggested demo targets

These are internal engineering targets, not claims about current market performance:

- >90% of benchmark document questions return supporting evidence.
- 0 unsafe recommendation outputs in the tested refusal set.
- <3 minutes from fresh upload to first usable summary on the chosen demo document under normal network conditions.
- >80% comprehension success on the internal mini-quiz after explanation.

Measure the actual results and report them honestly.

---

# 18. Source Registry

Every phase should use sources appropriate to the task. Keep this file updated in the repo as `docs/sources.md`.

## Event / rules

### SANGYAN official
URL: https://sangyan.sntciitbhu.co.in/
Use for: challenge, tracks, judging criteria, constraints, personas, submission requirements, schedule, FAQ, organiser contacts/announcements.

### SANGYAN Unstop listing
URL: https://unstop.com/hackathons/sangyan-iit-bhu-1761145
Use for: current registration/submission windows and operational listing details.

## Investor education

### SEBI Investor Survey 2025
URL: https://www.sebi.gov.in/reports-and-statistics/research/jan-2026/investor-survey-2025-_99170.html
Use for: investor education needs, channels, language preferences, barriers, demographic context.

Direct PDF found from the SEBI page:
https://www.sebi.gov.in/sebi_data/attachdocs/jan-2026/1768910470286.pdf

### SEBI Investor Education Reading Material
URL: https://investor.sebi.gov.in/iematerial.html
Use for: official educational topics, beginner material, IPOs, mutual funds, grievance redressal, fraud awareness, derivatives basics, etc.

### SEBI Due Diligence
URL: https://investor.sebi.gov.in/due_diligence.html
Use for: official due-diligence educational framing.

### SEBI Staying Away from Investment Frauds
URL: https://investor.sebi.gov.in/beware-of-investment.html
Use for: fraud red flags, pressure tactics, high-return claims, unsolicited offers, regulated-entity checks.

### SEBI How to Spot a Scam
URL: https://investor.sebi.gov.in/spot-any-scam.html
Use for: scam-awareness rules and examples.

### SEBI multilingual video learning
URL: https://investor.sebi.gov.in/inv_aware_edu_videos.html
Use for: examples of Indian-language financial education content and topic coverage.

## AI / engineering

### Gemini document understanding
URL: https://ai.google.dev/gemini-api/docs/document-processing
Use for: PDF/image understanding, structured extraction, Files API decisions.

### Google Antigravity IDE
URL: https://www.antigravity.google/docs/ide/overview/
Use for: agentic coding, editor/terminal/browser workflow, artifacts.

### Google Antigravity 2.0
URL: https://antigravity.google/docs/overview
Use for: agent orchestration, browser interaction, skills/MCP, plans, artifacts.

### Antigravity agent
URL: https://www.antigravity.google/docs/agent
Use for: agent capabilities and parallel conversations.

### Figma AI / Figma Make
URL: https://help.figma.com/hc/en-us/articles/24039793359767-Get-started-with-Figma-AI
Use for: AI-assisted design and prototyping.

### Figma Make
URL: https://help.figma.com/hc/en-us/articles/31304412302231-Explore-Figma-Make
Use for: prompt-to-app prototype workflows.

### OpenAI Codex / code generation
URL: https://developers.openai.com/api/docs/guides/code-generation
Use for: code review, debugging, engineering second opinions.

### OpenAI Agents
URL: https://developers.openai.com/api/docs/guides/agents
Use for: agent architecture concepts if Codex/OpenAI is used.

---

# 19. Final release gate

Do not submit until all of these are true:

## Product

- [ ] A user can upload a real representative document.
- [ ] The document is actually analyzed, not mocked.
- [ ] Summary is useful and readable.
- [ ] Key facts render clearly.
- [ ] Explain function works.
- [ ] Document Q&A works.
- [ ] Hindi works.
- [ ] Kannada works.
- [ ] Voice works or has a clearly demonstrated fallback.
- [ ] Sources/evidence are visible.
- [ ] The app visibly distinguishes fact from explanation/uncertainty.

## Safety

- [ ] No investment recommendations.
- [ ] No price predictions.
- [ ] No trading signals.
- [ ] No broker promotion.
- [ ] No private financial-data harvesting.
- [ ] Prohibited questions are redirected consistently in all supported languages.
- [ ] Prompt-injection tests were run against uploaded documents.

## Engineering

- [ ] Production build passes.
- [ ] Backend tests pass.
- [ ] Browser smoke test passes.
- [ ] Mobile layout checked.
- [ ] Environment secrets protected.
- [ ] Error states tested.
- [ ] Demo backup exists.

## Story

- [ ] One human problem.
- [ ] One deep user journey.
- [ ] One memorable product moment.
- [ ] Evidence for why the problem matters.
- [ ] Real measured internal metrics.
- [ ] Honest limitations.
- [ ] Clear future roadmap.

---

# 20. Team operating rule

**Do not divide the product into four disconnected mini-projects.**

Everyone should work from this same specification and the same repository.

Before any major implementation change, ask:

> **Does this make Kavita understand financial information more safely, simply, and accessibly?**

If the answer is no, it is probably not a priority for this hackathon sprint.

---

# 21. One-line final product definition

> **Bharat Investor Copilot is a multilingual, voice-first AI financial understanding layer that turns complex investor information into simple, source-backed explanations - helping Indian users learn what they are looking at without telling them what to buy.**

