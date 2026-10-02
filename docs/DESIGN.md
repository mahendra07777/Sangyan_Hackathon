# Bharat Investor Copilot - Design.md

## Design objective

Create a calm, trustworthy, multilingual public-good interface for first-time and less-finance-literate Indian investors. The product should feel closer to a public-service learning tool than a brokerage terminal.

## Brand direction

**Name:** Bharat Investor Copilot

**Tagline:** Understand finance. In your language. Before you act.

**Tone:** Calm, respectful, simple, evidence-led, non-promotional.

## Design principles

1. Understanding before action.
2. One clear next step per screen.
3. Voice as a useful accessibility layer, not a visual gimmick.
4. Sources visible near claims.
5. Facts, explanations, and uncertainty clearly separated.
6. Mobile-first and low cognitive load.
7. No trading-terminal visual language.
8. No dark patterns or urgency cues.

## Visual system

### Typography

- Primary: Inter or a system sans-serif.
- Use 3-4 text levels only.
- Body text should prioritize readability.
- Prefer short paragraphs.

### Color strategy

Use a neutral base with one accessible accent. Reserve semantic colors for status only:

- success for supported/grounded content;
- warning for needs-context/uncertainty;
- error for actual system failures or safety blocks.

Do not use red/green as the main product identity because users may associate it with trading.

### Components

- Header
- Language switcher
- Voice button
- Upload dropzone
- Document preview
- Summary card
- Key-fact card
- Explain drawer
- Term chip
- Evidence/source chip
- Uncertainty badge
- Chat composer
- Audio player
- Error banner
- Empty state
- Privacy/AI disclosure panel

## Information architecture

```text
Home
  |
  +-- Upload / Speak / Paste
          |
          v
       Analysis
          |
          +-- Summary
          +-- Key facts
          +-- Terms
          +-- Ask
          +-- Sources
          +-- Language
          +-- Voice
```

## Screen specifications

### 1. Home

Hero:

> Understand finance. In your language. Before you act.

Primary action:

> Upload a document

Secondary actions:

> Speak a question
> Paste text

Trust line:

> Educational assistant - not investment advice.

### 2. Upload

Show supported file types and a short privacy note.

### 3. Analysis

Use a calm progress sequence:

- Reading document
- Finding important information
- Preparing simple explanations

Avoid fake percentages and fake confidence meters.

### 4. Results

Top order:

1. What this document is.
2. Simple summary.
3. Key facts.
4. Important terms.
5. Ask about this document.

### 5. Explain drawer

Template:

**Term:** Debt

**In simple words:** ...

**In this document:** ...

**Why it matters generally:** ...

**Source:** ...

### 6. Q&A

Use conversational but restrained styling.

Each answer can show:

- answer;
- evidence;
- source;
- uncertainty if necessary.

### 7. Voice

Use a large microphone control.

States:

- idle;
- listening;
- processing;
- speaking;
- error.

Always show transcript.

### 8. Language

Allow switching without losing the current context.

Do not translate entity names or numbers incorrectly.

## Accessibility

- Keyboard navigation for all controls.
- Visible focus state.
- Minimum comfortable touch targets.
- Accessible labels for icons.
- Transcript for all audio.
- Color is never the only signal.
- Do not rely on tiny helper text.

## Figma master prompt

```text
Design a high-fidelity responsive web app called "Bharat Investor Copilot".

This is an investor-education public-good product for SANGYAN 2026 Track C. It helps Indian users understand financial documents and financial concepts in simple language, with Hindi/Kannada and voice support.

It must NOT look like a trading app, broker dashboard, stock screener, or investment recommendation product.

Primary persona: Kavita, 39, Tier-2 homemaker managing family savings, not fluent in English and uncomfortable with financial jargon.

Core journey:
Home -> Upload financial document -> Analyze -> Simple summary -> Key facts -> Explain a difficult term -> Ask a document question -> Switch to Hindi/Kannada -> Ask by voice -> Listen to answer -> View source/evidence.

Create:
- desktop and mobile layouts;
- component library;
- design tokens;
- empty/loading/error states;
- accessibility states;
- source/evidence UI;
- AI disclosure/privacy screen;
- one polished end-to-end demo flow.

Visual direction (V5 Art Direction):
Premium Fintech, Financial Intelligence, AI Educator, Bharat-First. 
Canvas: warm stone/soft neutral. Primary: deep navy. Accent: intelligent blue.
Distinctive typography and whitespace. No neon trading aesthetic. No stock tickers. No buy/sell buttons. No fake urgency.
Use a recurring vertical intelligence line motif. High visual contrast for primary information.
Make the interface feel like a premium, signature financial intelligence product.
```
