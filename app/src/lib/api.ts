const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface KeyFact {
  label: string;
  value: string;
  unit?: string;
  explanation: string;
  evidence_reference: string;
}

export interface FinancialTerm {
  term: string;
  plain_language_definition: string;
  why_it_matters_general: string;
  document_context: string;
  evidence_reference: string;
}

export interface MetricChange {
  metric: string;
  previous_value?: string;
  current_value?: string;
  change: string;
  change_type: string;
  period: string;
  explanation: string;
  evidence_reference: string;
}

export interface Relationship {
  facts: string[];
  observation: string;
  why_it_may_matter: string;
  uncertainty: string;
  evidence_references: string[];
}

export interface AreaToUnderstand {
  title: string;
  description: string;
  related_facts: string[];
  questions: string[];
  evidence_references: string[];
}

export interface InvestigationPath {
  question: string;
  related_facts: string[];
  evidence_references: string[];
}

export interface DocumentIntelligence {
  document_type: string;
  simple_summary: string;
  document_story?: string;
  key_facts: KeyFact[];
  financial_terms: FinancialTerm[];
  changes: MetricChange[];
  relationships: Relationship[];
  areas_to_understand: AreaToUnderstand[];
  investigation_paths: InvestigationPath[];
  important_sections: string[];
  uncertainty_notes: string[];
  source_references: string[];
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  page_number?: number;
  section_title?: string;
  content: string;
}

export interface DocumentSection {
  id: string;
  document_id: string;
  page_number: number;
  content: string;
  chunks: DocumentChunk[];
}

export interface ProcessedDocument {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: string;
  upload_timestamp: string;
  page_count?: number;
  metadata: Record<string, any>;
  sections: DocumentSection[];
  intelligence?: DocumentIntelligence;
}

export interface DocumentProcessResult {
  document: ProcessedDocument;
  message: string;
  error?: string;
}

export async function uploadDocument(file: File, language: string = "English"): Promise<DocumentProcessResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("language", language);

  const response = await fetch(`${API_URL}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Upload failed with status ${response.status}`);
  }

  return response.json();
}

export async function translateIntelligence(intelligence: DocumentIntelligence, language: string): Promise<DocumentIntelligence> {
  const response = await fetch(`${API_URL}/api/documents/translate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ intelligence, language }),
  });

  if (!response.ok) {
    throw new Error("Translation failed");
  }

  return response.json();
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  answer: string;
  intent_classified: 'DOCUMENT_QA' | 'FINANCIAL_EDUCATION' | 'SOURCE_LOOKUP' | 'UNSUPPORTED_OR_AMBIGUOUS' | 'PROHIBITED_INVESTMENT_ADVICE';
  answer_type: 'DOCUMENT_FACT' | 'EDUCATIONAL_EXPLANATION' | 'SOURCE_INFORMATION' | 'UNCERTAIN' | 'REFUSAL';
  evidence_snippet?: string;
  source_reference?: string;
  uncertainty_note?: string;
  language?: string;
  safety_state?: string;
}

export async function sendChatMessage(params: {
  message: string;
  history?: ChatMessage[];
  document_context?: string;
  language?: string;
}): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: params.message,
      history: params.history || [],
      document_context: params.document_context || "",
      language: params.language || "English"
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Chat failed with status ${response.status}`);
  }

  return response.json();
}
