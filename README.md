# Bharat Investor Copilot --- SANGYAN 2026
> **Understand finance. In your language. Before you act.**
This is the root-level operating manual for the **Bharat Investor
Copilot** project.


The project is being built for the **SANGYAN 2026 hackathon by IIT
(BHU)**.

The goal is to build a polished, trustworthy, multilingual, voice-first
financial education and comprehension product for Indian investors ---
especially users who may struggle with complex financial documents,
terminology, and English-first financial content.

------------------------------------------------------------------------

## 1. IMPORTANT: READ THIS FIRST

Before changing or generating code, you MUST understand the project
documentation.

The repository should contain:

``` text
/
├── README.md                         ← YOU ARE HERE
│
├── docs/
│   ├── MASTER_PLAYBOOK.md            ← Product requirements & strategy
│   ├── DESIGN.md                     ← UI/UX design system
│   ├── PHASE_PROMPTS.md              ← Phase-by-phase implementation instructions
│   ├── PROJECT_STATUS.md             ← Current build status
│   ├── product.md                    ← Product contract and MVP definition
│   ├── sources.md                    ← Allowed sources and hierarchy
│   ├── safety.md                     ← Guardrails and safety constraints
│   ├── evaluation.md                 ← KPIs and success metrics
│   └── demo-script.md                ← Final demo narrative
│
├── src/
├── public/
├── ...
```

### Documentation hierarchy

Treat the files as follows:

  ---------------------------------------------------------------------------
  File                        Purpose                 Authority
  --------------------------- ----------------------- -----------------------
  `README.md`                 How the project should  Operating rules
                              be operated             

  `docs/MASTER_PLAYBOOK.md`   What we are building    **Product truth**
                              and why                 

  `docs/DESIGN.md`            How the product should  **Design truth**
                              look and feel           

  `docs/PHASE_PROMPTS.md`     How to build it phase   **Execution truth**
                              by phase                

  `docs/PROJECT_STATUS.md`    What has actually been  **Current-state truth**
                              completed               
  ---------------------------------------------------------------------------

If two documents appear to conflict:

1.  Check `PROJECT_STATUS.md` for the actual current state.
2.  Check `MASTER_PLAYBOOK.md` for product requirements.
3.  Check `DESIGN.md` for visual/UX requirements.
4.  Check `PHASE_PROMPTS.md` for implementation order.
5.  Do not silently invent a resolution. Report the conflict.

------------------------------------------------------------------------

# 2. WHAT WE ARE BUILDING

## Bharat Investor Copilot

A multilingual AI assistant that helps Indian users **understand
financial information before they act**.

The product is NOT an investment advisor.

It should help users:

-   understand financial documents
-   simplify difficult financial language
-   extract important information
-   understand financial terms
-   ask questions about a document
-   translate explanations
-   interact using voice
-   learn basic financial concepts
-   identify the source behind important information
-   distinguish source-backed facts from AI explanations

### Core user journey

``` text
Upload PDF / Image / Text
          ↓
Understand the content
          ↓
Extract important information
          ↓
Simplify complex language
          ↓
Explain difficult terms
          ↓
Ask questions
          ↓
Switch language
          ↓
Use voice
          ↓
Learn
```

The product should feel like:

> "A trusted financial translator and teacher."

Not:

> "An AI stock-picking or trading tool."

------------------------------------------------------------------------

# 3. NON-NEGOTIABLE PRODUCT RULES

These rules apply throughout the entire project.

## Rule 1 --- No investment advice

The product must NOT:

-   recommend buying a stock
-   recommend selling a stock
-   recommend holding a stock
-   provide personalized investment recommendations
-   predict stock prices
-   generate trading signals
-   provide trading strategies
-   rank investments as "best"
-   tell users what investment they should choose
-   pretend to be a SEBI-registered investment adviser
-   encourage users to take financial risks

The product explains information.

It does not make investment decisions for users.

------------------------------------------------------------------------

## Rule 2 --- Trust over hallucination

Never invent:

-   financial figures
-   company facts
-   regulatory rules
-   SEBI requirements
-   investor rights
-   statistics
-   citations
-   sources
-   document content

If the system does not know something, it should say so.

When information comes from a document, distinguish:

``` text
SOURCE FACT
What the document actually says.

AI EXPLANATION
A simplified explanation of that information.

EDUCATIONAL CONTEXT
General financial education that helps the user understand it.

UNCERTAINTY
Anything the system cannot confidently establish.
```

------------------------------------------------------------------------

## Rule 3 --- Official sources first

For regulatory and investor-education information, prefer authoritative
sources.

Examples include:

-   SEBI
-   NSDL
-   RBI
-   Government of India
-   official company filings/documents when relevant
-   other primary/official sources

Do not treat random blogs, social media posts, or unverified websites as
authoritative sources for regulatory facts.

------------------------------------------------------------------------

## Rule 4 --- Privacy by design

Treat uploaded financial documents and user conversations as sensitive.

Do not:

-   expose uploaded documents unnecessarily
-   log sensitive document content unnecessarily
-   expose API keys in frontend code
-   commit secrets
-   store credentials in source code
-   send user data to unnecessary third-party services
-   create unnecessary tracking

Use environment variables for secrets.

Example:

``` text
.env
.env.local
```

These must not be committed to Git.

Provide:

``` text
.env.example
```

when environment variables are required.

------------------------------------------------------------------------

## Rule 5 --- Never break existing functionality casually

Before modifying an existing feature:

1.  inspect the current implementation
2.  understand its dependencies
3.  identify what may be affected
4.  make the smallest reasonable change
5.  test the affected functionality
6.  check for regressions

Do not rewrite working systems just because another implementation looks
cleaner.

------------------------------------------------------------------------

# 4. ANTIGRAVITY OPERATING MODE

Antigravity is the **main engineering headquarters** for this project.

It owns:

-   application architecture
-   frontend implementation
-   backend implementation
-   API integration
-   database integration
-   AI integration
-   authentication
-   testing
-   debugging
-   integration
-   deployment preparation
-   browser testing

There must be **ONE canonical application codebase**.

Do not create separate competing applications using:

-   Figma Make
-   Claude
-   Gemini
-   Codex
-   other AI coding tools

Other AI tools may review, design, research, or audit the project, but
Antigravity should remain the main implementation environment.

------------------------------------------------------------------------

# 5. HOW ANTIGRAVITY MUST WORK

For every task, follow this sequence:

``` text
READ
 ↓
INSPECT
 ↓
PLAN
 ↓
IMPLEMENT
 ↓
TEST
 ↓
REVIEW
 ↓
REPORT
```

## READ

Before implementing a phase, read:

``` text
README.md
docs/MASTER_PLAYBOOK.md
docs/DESIGN.md
docs/PHASE_PROMPTS.md
docs/PROJECT_STATUS.md
```

Only read the files relevant to the current task if the repository is
large, but always understand their purpose.

------------------------------------------------------------------------

## INSPECT

Before changing code:

-   inspect the repository
-   inspect the existing architecture
-   identify the framework
-   inspect package/dependency files
-   inspect routing
-   inspect components
-   inspect API/backend structure
-   inspect database setup
-   inspect environment configuration
-   identify existing reusable components

Do not assume the repository is empty.

------------------------------------------------------------------------

## PLAN

Before making a substantial change, briefly state:

``` text
What I found
What I will change
Which files will be affected
How I will test it
```

Do not implement unrelated future features.

------------------------------------------------------------------------

## IMPLEMENT

Implement only the requested phase/task.

Keep code:

-   modular
-   readable
-   maintainable
-   type-safe where applicable
-   reusable
-   production-oriented
-   easy for another teammate to understand

Avoid unnecessary complexity.

------------------------------------------------------------------------

## TEST

After implementation, test:

-   build
-   type checking
-   linting if configured
-   relevant unit tests
-   relevant API endpoints
-   important UI flows
-   error states
-   responsive behavior
-   browser console errors

If browser testing is available, use it.

------------------------------------------------------------------------

## REPORT

After every meaningful phase/task, report:

``` text
STATUS: Complete / Partial / Blocked

Implemented:
- ...

Files changed:
- ...

Tests performed:
- ...

Known issues:
- ...

Next recommended step:
- ...
```

Then update:

``` text
docs/PROJECT_STATUS.md
```

------------------------------------------------------------------------

# 6. PHASE DISCIPLINE

The project is built in phases.

The phase definitions live in:

``` text
docs/PHASE_PROMPTS.md
```

### Critical rule

**Do not implement future phases automatically.**

If Phase 2 is currently requested:

-   do Phase 2
-   do not silently implement Phase 3
-   do not add unrelated "nice-to-have" features
-   do not redesign the entire application

If a future dependency is required, explain it first.

------------------------------------------------------------------------

# 7. PHASE EXECUTION PROTOCOL

For each phase:

### Step 1

Read the relevant phase from:

``` text
docs/PHASE_PROMPTS.md
```

### Step 2

Read the relevant requirements from:

``` text
docs/MASTER_PLAYBOOK.md
```

### Step 3

Check the current state:

``` text
docs/PROJECT_STATUS.md
```

### Step 4

Check visual requirements:

``` text
docs/DESIGN.md
```

### Step 5

Inspect the actual repository.

### Step 6

Implement only the current phase.

### Step 7

Test it.

### Step 8

Fix problems.

### Step 9

Update `PROJECT_STATUS.md`.

### Step 10

Report completion.

------------------------------------------------------------------------

# 8. DESIGN & UI/UX RULES

The product must feel like a serious modern financial product.

Avoid:

-   generic AI chatbot appearance
-   excessive gradients
-   unnecessary glassmorphism
-   cluttered dashboards
-   huge walls of text
-   excessive animations
-   random colors
-   inconsistent spacing
-   inconsistent buttons
-   inconsistent typography
-   fake financial charts
-   decorative elements that do not help the user

Prioritize:

-   clarity
-   trust
-   accessibility
-   hierarchy
-   whitespace
-   readable typography
-   clear information architecture
-   responsive design
-   excellent mobile experience
-   obvious actions
-   meaningful feedback
-   understandable financial language

The detailed visual system lives in:

``` text
docs/DESIGN.md
```

That file should be followed instead of inventing a new design system
during implementation.

------------------------------------------------------------------------

# 9. CORE MVP

The MVP should focus on one excellent user journey.

### Required capabilities

#### Input

Users should be able to provide:

-   PDF
-   image/screenshot
-   text
-   questions

#### Understanding

The system should be able to:

-   summarize
-   extract important information
-   explain financial terminology
-   answer questions about the supplied content

#### Language

Initial target languages:

-   English
-   Hindi
-   Kannada

The architecture should make additional Indian languages possible later.

#### Voice

Where supported by the chosen implementation:

-   voice input
-   spoken output

#### Trust

The UI should communicate:

-   where important information came from
-   whether something is directly stated in the source
-   whether something is an AI explanation
-   when the system is uncertain

#### Guardrails

The assistant should refuse or redirect investment-advice requests into
educational explanations.

Example:

User:

> "Should I buy this stock?"

The system should not answer with a buy/sell/hold recommendation.

Instead, it can explain relevant information such as:

-   what the company reports
-   what a financial metric means
-   what risks are disclosed
-   what questions an investor may want to understand

------------------------------------------------------------------------

# 10. AI ARCHITECTURE

The preferred high-level flow is:

``` text
USER
 │
 ├── PDF
 ├── IMAGE
 ├── TEXT
 └── VOICE
       │
       ▼
INPUT PROCESSING
       │
       ▼
DOCUMENT / OCR PROCESSING
       │
       ▼
CHUNKING + STRUCTURED EXTRACTION
       │
       ▼
TRUSTED SOURCE CONTEXT
       │
       ▼
AI ENGINE
       │
       ├── SUMMARY
       ├── EXPLANATION
       ├── Q&A
       ├── TRANSLATION
       └── EDUCATION
       │
       ▼
VOICE / TEXT RESPONSE
       │
       ▼
USER
```

Use the actual architecture specified in the master playbook and phase
instructions rather than blindly following this diagram if
implementation details evolve.

------------------------------------------------------------------------

# 11. RECOMMENDED TECHNOLOGY DIRECTION

The current intended stack is approximately:

### Frontend

-   React
-   TypeScript
-   Tailwind CSS
-   Lucide icons

### Backend

-   Python
-   FastAPI

### AI

-   Gemini API where appropriate for document understanding and
    multilingual processing

### Database / Retrieval

-   Supabase
-   PostgreSQL
-   pgvector or an equivalent retrieval layer if required

### OCR / Vision

Use the most appropriate reliable document/vision capability available
to the chosen AI architecture.

### Voice

Use suitable speech-to-text and text-to-speech services.

Do not add technologies simply because they are fashionable.

Choose technologies based on:

``` text
Reliability
+
Speed of implementation
+
Cost
+
Hackathon feasibility
+
Maintainability
```

------------------------------------------------------------------------

# 12. ROLE OF OTHER AI TOOLS

Other tools should complement Antigravity.

## Antigravity

**Main builder**

Use for:

-   coding
-   integration
-   debugging
-   browser testing
-   architecture
-   implementation

------------------------------------------------------------------------

## Figma

**Design laboratory**

Use for:

-   UX exploration
-   wireframes
-   visual concepts
-   component design
-   design refinement

Once a design is approved, implement it in the canonical application.

Do not maintain a second production application in Figma.

------------------------------------------------------------------------

## Gemini

**Document intelligence specialist**

Use for:

-   document understanding
-   PDFs
-   tables
-   charts
-   multilingual analysis
-   testing difficult financial documents

------------------------------------------------------------------------

## Claude

**Critical reviewer**

Use Claude primarily to review the existing implementation.

Ask it to look for:

-   hallucination risks
-   UX problems
-   accessibility problems
-   prompt-injection risks
-   privacy issues
-   weak product decisions
-   unnecessary features
-   broken user flows
-   demo weaknesses

Do not ask Claude to create an unrelated second application unless
specifically required.

------------------------------------------------------------------------

## Codex

**Engineering auditor**

Use later in the build for:

-   code review
-   bug discovery
-   security review
-   refactoring suggestions
-   test gaps
-   deployment issues

Again, the canonical codebase remains the Antigravity project.

------------------------------------------------------------------------

# 13. SOURCE & RESEARCH RULES

When adding financial, regulatory, or investor-education information:

### Prefer

``` text
Official government source
        ↓
Regulator
        ↓
Official organization
        ↓
Primary company/document source
        ↓
High-quality secondary source
```

Do not present unsupported claims as facts.

For important claims, preserve the source URL or source metadata where
practical.

The product should make source provenance understandable to users.

------------------------------------------------------------------------

# 14. FINANCIAL SAFETY LANGUAGE

The application should consistently communicate its purpose.

Good:

> "This explanation is for financial education and understanding. It is
> not investment advice."

Good:

> "Here is what the document says."

Good:

> "Here is a simple explanation of this term."

Avoid:

> "You should buy this."

Avoid:

> "This stock will rise."

Avoid:

> "This is the best investment."

Avoid:

> "Guaranteed return."

Avoid:

> "Buy now."

------------------------------------------------------------------------

# 15. ERROR HANDLING

Every important user flow must have useful states.

At minimum consider:

``` text
Loading
Success
Empty
Error
Unsupported input
Invalid file
AI unavailable
Network failure
Source unavailable
Low-confidence answer
Rate limit
Timeout
```

Do not leave the user staring at a blank screen.

Errors should be understandable to normal users, not just developers.

Bad:

> `ERR_DOCUMENT_PIPELINE_500`

Better:

> "We couldn't read this document. Please try another PDF or image."

------------------------------------------------------------------------

# 16. SECURITY RULES

Never commit:

``` text
API keys
access tokens
passwords
private credentials
service-account secrets
database passwords
```

Never place private API keys in frontend code.

Use environment variables.

Before deployment, inspect the repository for accidentally exposed
secrets.

------------------------------------------------------------------------

# 17. PERFORMANCE RULES

Do not optimize prematurely.

But avoid obvious problems such as:

-   unnecessary API calls
-   repeated document processing
-   sending entire documents repeatedly when chunks would work
-   unnecessary frontend rerenders
-   huge client bundles
-   unbounded chat history
-   unnecessary database queries

For AI requests, consider:

-   token usage
-   latency
-   caching where appropriate
-   chunking
-   retrieval
-   request limits
-   graceful failures

------------------------------------------------------------------------

# 18. RESPONSIVE DESIGN

The application must work well on:

-   desktop
-   laptop
-   tablet
-   mobile

Do not build only for a desktop screenshot.

The target audience includes users who may primarily access the product
through mobile devices.

------------------------------------------------------------------------

# 19. ACCESSIBILITY

Prioritize:

-   readable text
-   sufficient contrast
-   keyboard accessibility
-   visible focus states
-   descriptive buttons
-   accessible form labels
-   meaningful error messages
-   reasonable touch targets
-   screen-reader-friendly structure where practical

Do not rely only on color to communicate important information.

------------------------------------------------------------------------

# 20. DEMO-FIRST THINKING

This is a hackathon project.

The final demo should tell one clear story.

Preferred flow:

``` text
1. User opens Bharat Investor Copilot
              ↓
2. Uploads a realistic financial document
              ↓
3. AI understands it
              ↓
4. Important information appears
              ↓
5. User clicks "Explain"
              ↓
6. A difficult term becomes simple
              ↓
7. User switches language
              ↓
8. User asks a voice question
              ↓
9. AI answers in the chosen language
              ↓
10. Source / trust information is visible
              ↓
11. Closing message:
    "We don't tell investors what to buy.
     We help them understand what they're looking at."
```

Do not add features that make this journey harder to demonstrate.

------------------------------------------------------------------------

# 21. REALISTIC DATA ONLY

For demos, do not fabricate realistic-looking financial facts and
present them as real.

If mock data is necessary:

-   clearly label it as demo/sample data
-   do not imply it is a real company filing
-   do not create fake citations
-   do not fabricate regulatory statements

When possible, use appropriate public/official documents for
demonstrations.

------------------------------------------------------------------------

# 22. DO NOT OVERBUILD

The most common failure mode is building too many features.

Avoid adding:

-   stock recommendation engines
-   trading dashboards
-   portfolio optimization
-   price prediction
-   social feeds
-   complex gamification
-   unnecessary fintech integrations
-   unrelated financial calculators
-   dozens of languages before the core flow works
-   complicated dashboards

First make the core journey excellent.

------------------------------------------------------------------------

# 23. DEFINITION OF DONE

A phase is NOT complete merely because code was generated.

A phase is complete when:

-   requirements were implemented
-   the code builds
-   relevant tests pass
-   important user flows work
-   obvious UI issues are fixed
-   errors are handled
-   no secrets were exposed
-   documentation is updated
-   `PROJECT_STATUS.md` is updated

------------------------------------------------------------------------

# 24. PROJECT STATUS

Maintain:

``` text
docs/PROJECT_STATUS.md
```

Recommended structure:

``` markdown
# Project Status

## Current Phase
Phase X

## Completed
- ...

## In Progress
- ...

## Not Started
- ...

## Known Bugs
- ...

## Technical Debt
- ...

## Current Blockers
- ...

## Last Tested
- ...

## Next Step
- ...
```

Never claim something is complete if it has not actually been tested.

------------------------------------------------------------------------

# 25. WHEN SOMETHING IS UNCLEAR

Do not guess when guessing could affect:

-   financial safety
-   regulatory claims
-   architecture
-   security
-   user privacy
-   product requirements
-   existing functionality

Instead:

1.  inspect the relevant documentation
2.  inspect the code
3.  identify the ambiguity
4.  state the assumption
5.  ask for clarification if necessary

For minor implementation details, use the simplest reasonable choice
consistent with the documentation.

------------------------------------------------------------------------

# 26. RECOVERY FROM A BAD CHANGE

If a change breaks the application:

1.  stop adding new features
2.  identify the last known working state
3.  inspect the affected files
4.  determine the root cause
5.  revert or repair the smallest necessary area
6.  run the build/tests again
7.  document the issue if useful

Do not stack more changes on top of a broken state.

------------------------------------------------------------------------

# 27. GIT / VERSION CONTROL

Use clear, small commits where Git is available.

Examples:

``` text
feat: add document upload flow
feat: add multilingual explanation
fix: handle invalid PDF uploads
fix: prevent empty AI responses
refactor: simplify document service
test: add document parser tests
docs: update project status
```

Avoid commits such as:

``` text
changes
final
final2
new
working
everything
```

------------------------------------------------------------------------

# 28. FIRST ACTION IN A NEW ANTIGRAVITY SESSION

When starting work in this repository, do NOT immediately start coding.

First read:

``` text
README.md
docs/MASTER_PLAYBOOK.md
docs/DESIGN.md
docs/PHASE_PROMPTS.md
docs/PROJECT_STATUS.md
```

Then inspect the repository.

Use this operating sequence:

``` text
UNDERSTAND CURRENT STATE
        ↓
IDENTIFY CURRENT PHASE
        ↓
READ PHASE REQUIREMENTS
        ↓
PLAN
        ↓
IMPLEMENT
        ↓
TEST
        ↓
FIX
        ↓
UPDATE PROJECT STATUS
        ↓
REPORT
```

------------------------------------------------------------------------

# 29. MASTER ANTIGRAVITY START PROMPT

When opening the project for the first time, use:

> Read `README.md`, `docs/MASTER_PLAYBOOK.md`, `docs/DESIGN.md`,
> `docs/PHASE_PROMPTS.md`, and `docs/PROJECT_STATUS.md` before making
> changes.
>
> Then inspect the entire existing repository and understand its current
> architecture, framework, dependencies, routes, components, backend
> structure, database setup, environment configuration, and current
> implementation status.
>
> Do not implement any future phase yet.
>
> First report:
>
> 1.  What the product is.
> 2.  What the documentation requires.
> 3.  What already exists in the repository.
> 4.  What is missing.
> 5.  Which phase the project is currently in.
> 6.  Any conflicts or risks you found.
> 7.  The exact next implementation step.
>
> Do not invent requirements. Do not create a second application. Do not
> add investment-advice functionality. Do not change the architecture
> unnecessarily.
>
> Wait for the phase-specific instruction before implementing
> substantial changes.

------------------------------------------------------------------------

# 30. MASTER RULE

## Build less. Build better. Build trustworthy.

The success of Bharat Investor Copilot depends more on:

``` text
ONE excellent user journey
+
excellent UX
+
multilingual accessibility
+
voice interaction
+
trustworthy explanations
+
clear source attribution
+
strong safety guardrails
+
reliable technical execution
```

than on the number of features.

The product should leave a user with one clear feeling:

> **"Now I understand what I am looking at."**

------------------------------------------------------------------------

## Official / Important References

Keep the current source links and research references in the project
documentation rather than scattering them throughout code.

Important sources include:

-   SANGYAN official website: https://sangyan.sntciitbhu.co.in/
-   SANGYAN Unstop page:
    https://unstop.com/hackathons/sangyan-iit-bhu-1761145
-   SEBI Investor Education:
    https://investor.sebi.gov.in/iematerial.html
-   SEBI Due Diligence: https://investor.sebi.gov.in/due_diligence.html
-   SEBI Fraud Awareness:
    https://investor.sebi.gov.in/beware-of-investment.html
-   SEBI Scam Awareness: https://investor.sebi.gov.in/spot-any-scam.html
-   SEBI Investor Education Videos:
    https://investor.sebi.gov.in/inv_aware_edu_videos.html
-   SEBI Investor Survey 2025:
    https://www.sebi.gov.in/reports-and-statistics/research/jan-2026/investor-survey-2025-\_99170.html
-   Gemini document processing documentation:
    https://ai.google.dev/gemini-api/docs/document-processing
-   Antigravity documentation:
    https://www.antigravity.google/docs/ide/overview/
-   Figma AI help:
    https://help.figma.com/hc/en-us/articles/24039793359767-Get-started-with-Figma-AI

Verify current hackathon rules, submission requirements, dates, and
terms from the official organizer/Unstop sources before final
submission.

------------------------------------------------------------------------

# END OF README
