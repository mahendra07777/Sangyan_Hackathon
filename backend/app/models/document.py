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
