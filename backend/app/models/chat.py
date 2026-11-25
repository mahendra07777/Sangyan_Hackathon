from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    document_context: str = ""
    language: str = "English"
    mode: str = "local"  # "local" or "ai"
    document_id: Optional[str] = None
    challenge_id: Optional[str] = None
    consent_token: Optional[str] = None
    ai_session_id: Optional[str] = None
    ai_session_token: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    intent_classified: Literal[
        "DOCUMENT_QA",
        "FINANCIAL_EDUCATION",
        "SOURCE_LOOKUP",
        "UNSUPPORTED_OR_AMBIGUOUS",
        "PROHIBITED_INVESTMENT_ADVICE"
    ]
    answer_type: Literal[
        "DOCUMENT_FACT",
        "EDUCATIONAL_EXPLANATION",
        "SOURCE_INFORMATION",
        "UNCERTAIN",
        "REFUSAL"
    ]
    evidence_snippet: Optional[str] = None
    source_reference: Optional[str] = None
    uncertainty_note: Optional[str] = None
    language: str = "en"
    safety_state: str = "SAFE"
    mode: str = "LOCAL_MODE"
    fallback_triggered: bool = False
    fallback_message: Optional[str] = None

