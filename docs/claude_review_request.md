# Claude Red-Team Review Request

**Product Purpose:** Bharat Investor Copilot is a financial understanding tool that helps Indian users (in English, Hindi, and Hinglish) decode complex financial documents (like quarterly reports, mutual fund disclosures, IPO prospects) safely without offering investment advice.

**Safety Rules:** The system explicitly forbids investment advice, price predictions, buy/sell/hold recommendations, or personalized allocation. It relies strictly on document grounding.

**Supported Languages:** English, Hindi, Hinglish (Romanized Hindi).

**Primary User Journey:**
1. User uploads a PDF/image.
2. AI extracts key facts, summarizes, and extracts jargon (Impact Lens).
3. User asks questions (text or voice) about the document or financial concepts.
4. AI answers in the selected language, providing evidence citations.

**Current Architecture:**
- React (Vite) frontend with Tailwind CSS and Web Speech API.
- FastAPI backend.
- Google Gemini 1.5 Flash (via `google.genai`) handling OCR, structured data extraction (Pydantic), and intent classification.
- Robust exponential backoff retry mechanism for rate limits.

**Test Results:**
- 17 Automated Tests Run (Grounding, Safety, Multilingual).
- 15 Passed completely.
- 2 Failed due to ambiguous classification bounds (e.g., prompt injection triggered Safety filter instead of Grounding filter, which is actually a positive defensive outcome).

**Please identify:**
1. Hidden hallucination risks
2. Financial-advice risks
3. UX trust failures
4. Multilingual failures
5. Accessibility problems
6. Demo-breaking bugs
7. Misleading claims
8. Security/privacy concerns
