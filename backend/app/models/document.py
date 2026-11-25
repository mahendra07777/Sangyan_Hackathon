from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class KeyFact(BaseModel):
    label: str
    value: str
    unit: Optional[str] = None
    explanation: str
    evidence_reference: str

class FinancialTerm(BaseModel):
    term: str
    plain_language_definition: str
    why_it_matters_general: str
    document_context: str
    evidence_reference: str

class MetricChange(BaseModel):
    metric: str
    previous_value: Optional[str] = None
    current_value: Optional[str] = None
    change: str
    change_type: str
    period: str
    explanation: str
    evidence_reference: str

class Relationship(BaseModel):
    facts: List[str]
    observation: str
    why_it_may_matter: str
    uncertainty: str
    evidence_references: List[str]

class AreaToUnderstand(BaseModel):
    title: str
    description: str
    related_facts: List[str]
    questions: List[str]
    evidence_references: List[str]

class InvestigationPath(BaseModel):
    question: str
    related_facts: List[str]
    evidence_references: List[str]

class DocumentIntelligence(BaseModel):
    document_type: str
    simple_summary: str
    document_story: Optional[str] = None
    key_facts: List[KeyFact] = Field(default_factory=list)
    financial_terms: List[FinancialTerm] = Field(default_factory=list)
    changes: List[MetricChange] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    areas_to_understand: List[AreaToUnderstand] = Field(default_factory=list)
    investigation_paths: List[InvestigationPath] = Field(default_factory=list)
    important_sections: List[str] = Field(default_factory=list)
    uncertainty_notes: List[str] = Field(default_factory=list)
    source_references: List[str] = Field(default_factory=list)
    mode: str = "LOCAL_MODE"  # LOCAL_MODE, AI_CONSENTED, LOCAL_MODE_FALLBACK
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    fallback_message: Optional[str] = None


class DocumentChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentSection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    page_number: int
    content: str
    chunks: List[DocumentChunk] = Field(default_factory=list)

class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_type: str
    file_size_bytes: int
    status: str = "uploaded"  # uploaded, processing, ready, error
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    page_count: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sections: List[DocumentSection] = Field(default_factory=list)
    intelligence: Optional[DocumentIntelligence] = None
    
class DocumentProcessResult(BaseModel):
    document: Document
    message: str = "Processing completed"
    error: Optional[str] = None


class ConsentPreviewRequest(BaseModel):
    document_id: str
    operation: str  # "EXPLAIN", "CHAT", "TRANSLATE"


class ConsentPreviewResponse(BaseModel):
    challenge_id: str
    document_id: str
    operation: str
    recipient: str = "Google Gemini API"
    purpose: str
    payload_preview: str
    payload_hash: str
    expires_in_seconds: int = 600
    disclosure_statement: str


class ConsentConfirmRequest(BaseModel):
    challenge_id: str
    document_id: str
    operation: str
    payload_hash: str


class ConsentConfirmResponse(BaseModel):
    challenge_id: str
    consent_token: str
    expires_in_seconds: int = 600
    operation: str
    document_id: str


class AIAnalyzeRequest(BaseModel):
    document_id: str
    challenge_id: Optional[str] = None
    consent_token: Optional[str] = None
    ai_session_id: Optional[str] = None
    ai_session_token: Optional[str] = None
    language: str = "English"


class AISessionPreviewResponse(BaseModel):
    activation_id: str
    recipient: str = "Google Gemini API"
    purpose: str
    disclosure_items: List[str]
    disclosure_statement: str
    expires_in_seconds: int = 600


class AISessionActivateRequest(BaseModel):
    activation_id: str


class AISessionActivateResponse(BaseModel):
    ai_session_id: str
    ai_session_token: str
    expires_in_seconds: int = 3600
    active: bool = True


class AISessionCredentialsRequest(BaseModel):
    ai_session_id: str
    ai_session_token: str


class AISessionStatusResponse(BaseModel):
    active: bool
    expires_in_seconds: int = 0

