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
  mode?: string;
  fallback_triggered?: boolean;
  fallback_reason?: string;
  fallback_message?: string;
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

export interface ConsentPreviewResponse {
  challenge_id: string;
  document_id: string;
  operation: string;
  recipient: string;
  purpose: string;
  payload_preview: string;
  payload_hash: string;
  expires_in_seconds: number;
  disclosure_statement: string;
}

export interface ConsentConfirmResponse {
  challenge_id: string;
  consent_token: string;
  expires_in_seconds: number;
  operation: string;
  document_id: string;
}

export interface AISessionPreviewResponse {
  activation_id: string;
  recipient: string;
  purpose: string;
  disclosure_items: string[];
  disclosure_statement: string;
  expires_in_seconds: number;
}

export interface AISessionActivateResponse {
  ai_session_id: string;
  ai_session_token: string;
  expires_in_seconds: number;
  active: boolean;
}

export interface AISessionStatusResponse {
  active: boolean;
  expires_in_seconds: number;
}

export interface AISessionCredentials {
  aiSessionId: string;
  aiSessionToken: string;
}

export async function getAiSessionPreview(): Promise<AISessionPreviewResponse> {
  const response = await fetch(`${API_URL}/api/documents/ai-session/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `AI activation preview failed: ${response.status}`);
  }
  return response.json();
}

export async function activateAiSession(activationId: string): Promise<AISessionActivateResponse> {
  const response = await fetch(`${API_URL}/api/documents/ai-session/activate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ activation_id: activationId }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `AI activation failed: ${response.status}`);
  }
  return response.json();
}

export async function disableAiSession(aiSessionId: string, aiSessionToken: string): Promise<AISessionStatusResponse> {
  const response = await fetch(`${API_URL}/api/documents/ai-session/disable`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ai_session_id: aiSessionId, ai_session_token: aiSessionToken }),
  });
  if (!response.ok) {
    return { active: false, expires_in_seconds: 0 };
  }
  return response.json();
}

export async function getAiSessionStatus(aiSessionId: string, aiSessionToken: string): Promise<AISessionStatusResponse> {
  const response = await fetch(`${API_URL}/api/documents/ai-session/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ai_session_id: aiSessionId, ai_session_token: aiSessionToken }),
  });
  if (!response.ok) {
    return { active: false, expires_in_seconds: 0 };
  }
  return response.json();
}

export async function uploadDocument(
  file: File,
  language: string = "English",
  mode: string = "local",
  aiSession?: AISessionCredentials | null
): Promise<DocumentProcessResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("language", language);
  formData.append("mode", mode);
  if (aiSession?.aiSessionId && aiSession?.aiSessionToken) {
    formData.append("ai_session_id", aiSession.aiSessionId);
    formData.append("ai_session_token", aiSession.aiSessionToken);
  }

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

export async function getConsentPreview(documentId: string, operation: string = "EXPLAIN"): Promise<ConsentPreviewResponse> {
  const response = await fetch(`${API_URL}/api/documents/consent/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: documentId, operation }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Consent preview failed: ${response.status}`);
  }
  return response.json();
}

export async function confirmConsent(challengeId: string, documentId: string, operation: string, payloadHash: string): Promise<ConsentConfirmResponse> {
  const response = await fetch(`${API_URL}/api/documents/consent/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ challenge_id: challengeId, document_id: documentId, operation, payload_hash: payloadHash }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Consent confirmation failed: ${response.status}`);
  }
  return response.json();
}

export async function requestAiAnalysis(
  documentId: string,
  challengeId?: string,
  consentToken?: string,
  language: string = "English",
  aiSession?: AISessionCredentials | null
): Promise<DocumentIntelligence> {
  const response = await fetch(`${API_URL}/api/documents/ai-analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_id: documentId,
      challenge_id: challengeId,
      consent_token: consentToken,
      ai_session_id: aiSession?.aiSessionId,
      ai_session_token: aiSession?.aiSessionToken,
      language,
    }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `AI Analysis failed: ${response.status}`);
  }
  return response.json();
}

export async function translateIntelligence(
  intelligence: DocumentIntelligence,
  language: string,
  mode: string = "local",
  documentId?: string,
  challengeId?: string,
  consentToken?: string,
  aiSession?: AISessionCredentials | null
): Promise<DocumentIntelligence> {
  const response = await fetch(`${API_URL}/api/documents/translate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      intelligence,
      language,
      mode,
      document_id: documentId,
      challenge_id: challengeId,
      consent_token: consentToken,
      ai_session_id: aiSession?.aiSessionId,
      ai_session_token: aiSession?.aiSessionToken,
    }),
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
  mode?: string;
  fallback_triggered?: boolean;
  fallback_message?: string;
}

export async function sendChatMessage(params: {
  message: string;
  history?: ChatMessage[];
  document_context?: string;
  language?: string;
  mode?: string;
  document_id?: string;
  challenge_id?: string;
  consent_token?: string;
  ai_session_id?: string;
  ai_session_token?: string;
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
      language: params.language || "English",
      mode: params.mode || "local",
      document_id: params.document_id,
      challenge_id: params.challenge_id,
      consent_token: params.consent_token,
      ai_session_id: params.ai_session_id,
      ai_session_token: params.ai_session_token,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Chat failed with status ${response.status}`);
  }

  return response.json();
}

