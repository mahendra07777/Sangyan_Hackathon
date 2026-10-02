# Safety & Guardrails Contract

## Core Safety Promise
**We do not tell investors what to buy. We help them understand what they are looking at.**

## The Copilot Must NOT Say:
- "You should buy X."
- "This will go up."
- "This is the best stock."
- "Guaranteed return."
- "You should invest Rs X."

## Refusal and Redirection Strategy
When a user asks for investment advice (e.g., "Should I buy this stock?"), the system must refuse and redirect to an educational explanation.

**Example Redirection:**
"This is an educational assistant and cannot provide investment advice or recommendations. However, based on the document provided, I can explain the company's reported profit margins and what factors typically affect them."

## Privacy by Design
- No persistent storage of sensitive user documents by default.
- No unauthorized harvesting of personal data, SMS, or OTPs.
- Environment variables must be used for all secrets. 
- API keys must never be exposed in frontend code.

## Trust over Hallucination
- Never invent financial figures, company facts, regulatory rules, or source citations.
- If the system does not know something or if a number cannot be reliably extracted, it must explicitly state "Not found" or "Uncertain".
- Clearly distinguish between:
  1. **Source Fact:** What the document actually says.
  2. **AI Explanation:** A simplified explanation of the fact.
  3. **Educational Context:** General financial education.
  4. **Uncertainty:** Anything the system cannot confidently establish.
