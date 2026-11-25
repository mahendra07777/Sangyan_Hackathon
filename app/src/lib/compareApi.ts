/**
 * Client API and TypeScript types for Bharat Investor Copilot - Compare Documents (Slice 6).
 * Fully aligned with backend models in backend/app/models/comparison.py.
 */

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type ComparisonMode = "QUICK_COMPARE" | "MULTI_DOCUMENT";

export type SupportedFileFormat =
  | "PDF_DIGITAL"
  | "PDF_SCANNED"
  | "IMAGE_PNG"
  | "IMAGE_JPG"
  | "IMAGE_JPEG"
  | "DOCX"
  | "XLSX"
  | "XLS";

export type DocumentSlot = "doc_a" | "doc_b" | "doc_c" | "doc_d" | "doc_e";

export interface SessionCreatedResponse {
  session_id: string;
  session_token: string;
  comparison_mode: ComparisonMode;
  idle_timeout_seconds: number;
  absolute_timeout_seconds: number;
  max_documents: number;
}

export interface ComparisonDocument {
  doc_id: string;
  slot: DocumentSlot;
  original_filename: string;
  file_format: SupportedFileFormat;
  file_size_bytes: number;
  page_count?: number;
  sheet_names?: string[];
  is_scanned: boolean;
  storage_rel_path: string;
  extraction_status: string; // SUCCESS | VISION_EXTRACTION_REQUIRED | OCR_UNAVAILABLE_LOCAL_MODE | FAILED
  extraction_error?: string;
}

export interface EvidenceReference {
  evidence_id: string;
  doc_id: string;
  document_name: string;
  page_number?: number;
  bounding_box?: number[];
  sheet_name?: string;
  cell_range?: string;
  structural_ref?: string;
  verbatim_snippet: string;
  table_context?: string;
}

export interface ExtractedTableCell {
  row_index: number;
  col_index: number;
  value?: string | null;
  raw_value?: any;
  data_type: string;
  is_header: boolean;
  cell_range?: string | null;
  formula?: string | null;
}

export interface ExtractedTable {
  table_id: string;
  page_number?: number | null;
  sheet_name?: string | null;
  structural_ref?: string | null;
  title?: string | null;
  num_rows: number;
  num_cols: number;
  headers: string[];
  rows: (string | null)[][];
  cells: ExtractedTableCell[];
}

export interface ExtractedTextBlock {
  block_id: string;
  page_number?: number | null;
  sheet_name?: string | null;
  structural_ref?: string | null;
  text: string;
  bounding_box?: number[] | null;
  heading_level?: number | null;
  block_type: string;
}

export interface DocumentExtractionResult {
  doc_id: string;
  slot: DocumentSlot;
  file_format: SupportedFileFormat;
  page_count?: number | null;
  sheet_names?: string[] | null;
  is_scanned: boolean;
  extraction_status: string;
  tables: ExtractedTable[];
  text_blocks: ExtractedTextBlock[];
  raw_word_count: number;
  notes: string[];
  extraction_error?: string | null;
}

export interface DocumentMetadata {
  doc_id: string;
  company_name: string;
  company_identifier?: string;
  alternative_names?: string[];
  industry: string;
  document_type: string;
  financial_year: string;
  fy_start?: string;
  fy_end?: string;
  is_inferred_year?: boolean;
  reporting_period: string;
  reporting_period_display?: string;
  quarter?: string;
  period_start_date?: string;
  period_end_date?: string;
  currency: string;
  currency_symbol?: string;
  reporting_scale: string;
  accounting_standard: string;
  accounting_standard_disclosure?: string;
  reporting_scope: "CONSOLIDATED" | "STANDALONE" | "BOTH" | "NOT_APPLICABLE" | "UNKNOWN";
  audit_status: "AUDITED" | "UNAUDITED" | "LIMITED_REVIEW" | "PROVISIONAL" | "NOT_APPLICABLE" | "UNKNOWN";
  is_user_overridden?: boolean;
  confidence_category?: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
  extraction_notes?: string[];
}

export interface MetadataUpdateRequest {
  company_name?: string;
  company_identifier?: string;
  industry?: string;
  document_type?: string;
  financial_year?: string;
  reporting_period?: string;
  quarter?: string;
  currency?: string;
  reporting_scale?: string;
  accounting_standard?: string;
  reporting_scope?: "CONSOLIDATED" | "STANDALONE" | "BOTH" | "NOT_APPLICABLE" | "UNKNOWN";
  audit_status?: "AUDITED" | "UNAUDITED" | "LIMITED_REVIEW" | "PROVISIONAL" | "NOT_APPLICABLE" | "UNKNOWN";
}

export type IssueSeverity = "BLOCKER" | "WARNING" | "INFORMATION";
export type CompatibilityStatus = "COMPATIBLE" | "COMPATIBLE_WITH_WARNINGS" | "PARTIALLY_COMPATIBLE" | "BLOCKED";

export interface CompatibilityFinding {
  finding_id: string;
  severity: IssueSeverity;
  code: string;
  title: string;
  description: string;
  affected_document_ids: string[];
  relevant_fields?: string[];
  observed_values?: Record<string, string>;
  remediation_hint?: string;
  can_user_override_resolve?: boolean;
}

export interface PairwiseCompatibility {
  doc_a_id: string;
  doc_b_id: string;
  is_comparable: boolean;
  status: CompatibilityStatus;
  blocker_count: number;
  warning_count: number;
  findings: CompatibilityFinding[];
}

export interface CompatibilityReport {
  session_id?: string;
  is_comparable: boolean;
  overall_status: CompatibilityStatus;
  blocker_count: number;
  warning_count: number;
  findings: CompatibilityFinding[];
  pairwise_matrix: PairwiseCompatibility[];
  compatible_subsets: string[][];
}

export interface FinancialValue {
  doc_id: string;
  metric_key: string;
  label: string;
  amount?: number | null;
  reported_amount?: number | null;
  display_amount?: string | null;
  unit: string;
  currency: string;
  reported_currency?: string;
  reported_scale?: string;
  status: "REPORTED" | "NOT_DISCLOSED" | "UNCERTAIN" | "AMBIGUOUS" | "EXTRACTION_UNAVAILABLE";
  reporting_scope: string;
  evidence?: EvidenceReference;
  selected_candidate_id?: string | null;
  conflict_info?: any;
  fact_classification?: "DOCUMENT_FACT" | "EDUCATIONAL_EXPLANATION" | "SOURCE_INFORMATION" | "UNCERTAIN" | "USER_ENTERED";
  is_user_corrected?: boolean;
  original_amount?: number | null;
  user_entered_amount?: number | null;
  correction_reason?: string | null;
  correction_timestamp?: string | null;
}

export interface FinancialCorrectionRecord {
  correction_id: string;
  session_id: string;
  doc_id: string;
  metric_key: string;
  previous_effective_amount?: number | null;
  original_extracted_amount?: number | null;
  previous_status: string;
  previous_fact_classification: string;
  previous_display_amount?: string | null;
  new_user_entered_amount: number;
  corrected_display_amount: string;
  reason?: string | null;
  timestamp: string;
  unit: string;
  currency: string;
}

export interface FinancialCorrectionResponse {
  session_id: string;
  status: string;
  correction: FinancialCorrectionRecord;
  comparison_result: ComparisonResult;
  recalculated_metrics: string[];
}

export interface FinancialUndoResponse {
  session_id: string;
  status: string;
  undone_correction: FinancialCorrectionRecord;
  remaining_corrections_count: number;
  comparison_result: ComparisonResult;
  recalculated_metrics: string[];
}

export interface SessionCorrectionsResponse {
  session_id: string;
  corrections_count: number;
  corrections: FinancialCorrectionRecord[];
}

export type VarianceStatus =
  | "CALCULATED"
  | "DIV_BY_ZERO"
  | "NON_POSITIVE_BASE"
  | "NOT_DISCLOSED"
  | "CURRENCY_MISMATCH"
  | "INCOMPATIBLE_UNITS"
  | "PERIOD_MISMATCH"
  | "BLOCKED";

export interface CalculationResult {
  metric_key: string;
  label: string;
  base_doc_id: string;
  comparison_doc_id: string;
  base_value?: number | null;
  comparison_value?: number | null;
  formula: string;
  absolute_variance?: number | null;
  percentage_change?: number | null;
  display_absolute_variance?: string | null;
  display_percentage_change?: string | null;
  unit: string;
  status: VarianceStatus;
  directional_explanation?: string | null;
}

export type ProcessingStage =
  | "INITIALIZED"
  | "IDENTIFYING_METADATA"
  | "VALIDATING_COMPATIBILITY"
  | "EXTRACTING_FINANCIAL_DATA"
  | "RESOLVING_CONFLICTS"
  | "COMPUTING_CALCULATIONS"
  | "SYNTHESIZING_REPORT"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface ProcessingStatusResponse {
  session_id: string;
  current_stage: ProcessingStage;
  completed_stages: string[];
  stage_message: string;
  is_cancelled: boolean;
  is_completed: boolean;
  error?: string | null;
}

export interface PiiDetectionSummary {
  entity_type: string;
  count: number;
  placeholder: string;
}

export interface TransmissionSectionPreview {
  doc_id: string;
  document_name: string;
  page_number?: number | null;
  section_title: string;
  excerpt_snippet: string;
}

export interface TransmissionPreview {
  session_id: string;
  document_names: string[];
  selected_sections_and_pages: TransmissionSectionPreview[];
  purpose_of_processing: string;
  ai_service_provider: string;
  redacted_pii_summary: PiiDetectionSummary[];
  total_pii_redacted_count: number;
  redaction_disclaimer: string;
  payload_hash: string;
  sanitized_payload_preview: string;
  structured_financial_summary: Array<Record<string, any>>;
  requires_fresh_consent: boolean;
}

export interface ConsentResponse {
  consent_granted: boolean;
  message: string;
  updated_at: string;
  terms_disclosure?: string | null;
  withdrawal_limitations?: string | null;
  payload_hash?: string | null;
  transmission_preview?: TransmissionPreview | null;
}

export interface RiskDisclosure {
  risk_id: string;
  title: string;
  category: string;
  doc_id: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  disclosure_text: string;
  evidence: EvidenceReference;
  fact_classification: "DOCUMENT_FACT" | "EDUCATIONAL_EXPLANATION" | "SOURCE_INFORMATION" | "UNCERTAIN";
  audit_status?: string | null;
}

export interface AccountingDifference {
  difference_id: string;
  topic: string;
  doc_a_policy: string;
  doc_b_policy: string;
  impact_summary: string;
  evidence_a: EvidenceReference;
  evidence_b: EvidenceReference;
  fact_classification: "DOCUMENT_FACT" | "EDUCATIONAL_EXPLANATION" | "SOURCE_INFORMATION" | "UNCERTAIN";
  audit_status_a?: string | null;
  audit_status_b?: string | null;
}

export interface ExecutiveSummary {
  overview_story: string;
  core_positive_changes: string[];
  core_negative_changes: string[];
  neutral_observations: string[];
  uncertain_findings: string[];
  critical_disclosures: string[];
  mode: "LOCAL_MODE" | "AI_ASSISTED" | "LOCAL_MODE_FALLBACK";
  fallback_triggered: boolean;
  fallback_reason?: string | null;
  fallback_message?: string | null;
  fact_classification: "DOCUMENT_FACT" | "EDUCATIONAL_EXPLANATION" | "SOURCE_INFORMATION" | "UNCERTAIN";
}

export interface ComparisonResult {
  session_id: string;
  mode: "LOCAL_MODE" | "AI_ASSISTED" | "LOCAL_MODE_FALLBACK";
  fallback_triggered: boolean;
  fallback_reason?: string | null;
  fallback_message?: string | null;
  documents: ComparisonDocument[];
  metadata: Record<string, DocumentMetadata>;
  compatibility: CompatibilityReport;
  financial_values: Record<string, Record<string, FinancialValue>>; // metric_key -> doc_id -> value
  variances: CalculationResult[];
  executive_summary?: ExecutiveSummary | null;
  risks: RiskDisclosure[];
  accounting_differences: AccountingDifference[];
  verifications?: any[];
  language: string;
  safety_disclaimer: string;
}

export interface SessionFinancialsResponse {
  session_id: string;
  financial_values: Record<string, Record<string, FinancialValue>>;
  all_candidates?: Record<string, any[]>;
  conflicts?: Record<string, Record<string, any>>;
}

export interface SessionCalculationsResponse {
  session_id: string;
  variances: CalculationResult[];
  pairwise_matrix_summary?: Record<string, string>;
}

export interface ComparisonChatMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  cited_evidence: EvidenceReference[];
  safety_disclaimer: string;
  timestamp: string;
}

/* ==========================================================================
 * Client Methods
 * ========================================================================== */

function getHeaders(token?: string, extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (token) {
    headers["X-Session-Token"] = token;
  }
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errMsg = `Request failed (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson?.error?.message) {
        errMsg = errJson.error.message;
      } else if (errJson?.detail) {
        errMsg = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }
  return res.json();
}

/**
 * 1. Initialize a comparison session (QUICK_COMPARE: 2 docs, MULTI_DOCUMENT: 2-5 docs).
 */
export async function createCompareSession(
  mode: ComparisonMode = "QUICK_COMPARE"
): Promise<SessionCreatedResponse> {
  const res = await fetch(`${API_URL}/api/compare/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comparison_mode: mode }),
  });
  return handleResponse<SessionCreatedResponse>(res);
}

/**
 * 2. Delete and wipe a comparison session cleanly.
 */
export async function deleteCompareSession(sessionId: string, token: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}`, {
    method: "DELETE",
    headers: getHeaders(token),
  });
  await handleResponse(res);
}

/**
 * 3. Upload 2 to 5 documents to the active session.
 */
export async function uploadCompareDocuments(
  sessionId: string,
  token: string,
  files: File[]
): Promise<ComparisonDocument[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/upload`, {
    method: "POST",
    headers: getHeaders(token),
    body: formData,
  });

  const data = await handleResponse<{ uploaded_documents: ComparisonDocument[] }>(res);
  return data.uploaded_documents;
}

/**
 * 4. Retrieve identified metadata for all session documents.
 */
export async function getCompareMetadata(
  sessionId: string,
  token: string
): Promise<Record<string, DocumentMetadata>> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/metadata`, {
    method: "GET",
    headers: getHeaders(token),
  });
  const data = await handleResponse<{ session_id: string; metadata: Record<string, DocumentMetadata> }>(res);
  return data.metadata;
}

/**
 * 5. Update metadata for a single document slot (manual review/correction).
 */
export async function updateCompareMetadata(
  sessionId: string,
  token: string,
  docId: string,
  payload: MetadataUpdateRequest
): Promise<DocumentMetadata> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/metadata/${docId}`, {
    method: "PUT",
    headers: getHeaders(token, { "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  return handleResponse<DocumentMetadata>(res);
}

/**
 * 6. Get compatibility matrix and findings.
 */
export async function getCompareCompatibility(
  sessionId: string,
  token: string
): Promise<CompatibilityReport> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/compatibility`, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<CompatibilityReport>(res);
}

/**
 * 7. Retrieve pre-consent disclosure terms.
 */
export async function getConsentTerms(
  sessionId: string,
  token: string
): Promise<ConsentResponse> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/consent`, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<ConsentResponse>(res);
}

/**
 * 8. Grant affirmative consent for AI-assisted processing with optional payload hash binding.
 */
export async function grantConsent(
  sessionId: string,
  token: string,
  payloadHash?: string | null
): Promise<ConsentResponse> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/consent`, {
    method: "POST",
    headers: getHeaders(token, { "Content-Type": "application/json" }),
    body: JSON.stringify({
      consent_granted: true,
      payload_hash: payloadHash || null,
    }),
  });
  return handleResponse<ConsentResponse>(res);
}

/**
 * 8.1. Retrieve exact pre-transmission preview and sanitized payload fingerprint.
 */
export async function getTransmissionPreview(
  sessionId: string,
  token: string
): Promise<TransmissionPreview> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/transmission-preview`, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<TransmissionPreview>(res);
}

/**
 * 9. Withdraw external AI consent.
 */
export async function withdrawConsent(
  sessionId: string,
  token: string
): Promise<ConsentResponse> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/consent`, {
    method: "DELETE",
    headers: getHeaders(token),
  });
  return handleResponse<ConsentResponse>(res);
}

/**
 * 10. Start processing pipeline.
 */
export async function startCompareProcessing(
  sessionId: string,
  token: string,
  language: string = "English"
): Promise<ProcessingStatusResponse> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/process`, {
    method: "POST",
    headers: getHeaders(token, { "Content-Type": "application/json" }),
    body: JSON.stringify({ language }),
  });
  return handleResponse<ProcessingStatusResponse>(res);
}

/**
 * 11. Poll processing status.
 */
export async function getCompareStatus(
  sessionId: string,
  token: string
): Promise<ProcessingStatusResponse> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/status`, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<ProcessingStatusResponse>(res);
}

/**
 * 12. Cancel in-flight processing.
 */
export async function cancelCompareProcessing(sessionId: string, token: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/cancel`, {
    method: "POST",
    headers: getHeaders(token),
  });
  await handleResponse(res);
}

/**
 * 13. Get final comparison results.
 */
export async function getCompareResults(
  sessionId: string,
  token: string
): Promise<ComparisonResult> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/results`, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<ComparisonResult>(res);
}

/**
 * 14. Get standalone financial values (Slice 4).
 */
export async function getCompareFinancials(
  sessionId: string,
  token: string
): Promise<SessionFinancialsResponse> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/financials`, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<SessionFinancialsResponse>(res);
}

/**
 * 15. Get standalone calculation results & variances (Slice 4).
 */
export async function getCompareCalculations(
  sessionId: string,
  token: string
): Promise<SessionCalculationsResponse> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/calculations`, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<SessionCalculationsResponse>(res);
}

/**
 * 16. Send comparative grounded chat query.
 */
export async function sendCompareChat(
  sessionId: string,
  token: string,
  message: string,
  language: string = "English"
): Promise<ComparisonChatMessage> {
  const res = await fetch(`${API_URL}/api/compare/session/${sessionId}/chat`, {
    method: "POST",
    headers: getHeaders(token, { "Content-Type": "application/json" }),
    body: JSON.stringify({ message, language }),
  });
  return handleResponse<ComparisonChatMessage>(res);
}

/**
 * 17. Fetch binary PNG blob of rendered page (Endpoint 13).
 */
export async function fetchEvidencePageBlob(
  sessionId: string,
  token: string,
  docId: string,
  pageNum: number
): Promise<Blob> {
  const res = await fetch(
    `${API_URL}/api/compare/session/${sessionId}/evidence/${docId}/page/${pageNum}`,
    {
      method: "GET",
      headers: getHeaders(token),
    }
  );
  if (!res.ok) {
    let errMsg = `Failed to fetch page image (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson?.detail) errMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }
  return res.blob();
}

/**
 * 18. Get structured extraction context for document (Endpoint 13.1).
 */
export async function getEvidenceContext(
  sessionId: string,
  token: string,
  docId: string
): Promise<DocumentExtractionResult> {
  const res = await fetch(
    `${API_URL}/api/compare/session/${sessionId}/evidence/${docId}/context`,
    {
      method: "GET",
      headers: getHeaders(token),
    }
  );
  return handleResponse<DocumentExtractionResult>(res);
}

/**
 * 19. Export High-Fidelity Comparative PDF Report (Endpoint 15).
 */
export async function exportComparePdf(
  sessionId: string,
  token: string
): Promise<Blob> {
  const res = await fetch(
    `${API_URL}/api/compare/session/${sessionId}/export/pdf`,
    {
      method: "POST",
      headers: getHeaders(token),
    }
  );
  if (!res.ok) {
    let errMsg = `Failed to generate PDF report (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson?.detail) errMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }
  return res.blob();
}

/**
 * 20. Export 7-Tab Institutional Excel Comparison Workbook (Endpoint 16).
 */
export async function exportCompareXlsx(
  sessionId: string,
  token: string
): Promise<Blob> {
  const res = await fetch(
    `${API_URL}/api/compare/session/${sessionId}/export/xlsx`,
    {
      method: "POST",
      headers: getHeaders(token),
    }
  );
  if (!res.ok) {
    let errMsg = `Failed to generate Excel workbook (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson?.detail) errMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }
  return res.blob();
}

/**
 * 21. Manually correct an extracted financial figure (Endpoint 10.1).
 */
export async function correctFinancialValue(
  sessionId: string,
  token: string,
  docId: string,
  metricKey: string,
  correctedAmount: number,
  reason?: string
): Promise<FinancialCorrectionResponse> {
  const res = await fetch(
    `${API_URL}/api/compare/session/${sessionId}/financials/correct`,
    {
      method: "POST",
      headers: {
        ...getHeaders(token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        doc_id: docId,
        metric_key: metricKey,
        corrected_amount: correctedAmount,
        reason: reason || undefined,
      }),
    }
  );
  if (!res.ok) {
    let errMsg = `Failed to apply financial correction (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson?.detail) errMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }
  return res.json();
}

/**
 * 22. Undo the latest financial correction in LIFO order (Endpoint 10.2).
 */
export async function undoFinancialCorrection(
  sessionId: string,
  token: string
): Promise<FinancialUndoResponse> {
  const res = await fetch(
    `${API_URL}/api/compare/session/${sessionId}/financials/undo`,
    {
      method: "POST",
      headers: getHeaders(token),
    }
  );
  if (!res.ok) {
    let errMsg = `Failed to undo correction (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson?.detail) errMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }
  return res.json();
}

/**
 * 23. Retrieve active correction journal for session (Endpoint 10.3).
 */
export async function getFinancialCorrections(
  sessionId: string,
  token: string
): Promise<SessionCorrectionsResponse> {
  const res = await fetch(
    `${API_URL}/api/compare/session/${sessionId}/financials/corrections`,
    {
      method: "GET",
      headers: getHeaders(token),
    }
  );
  if (!res.ok) {
    let errMsg = `Failed to fetch corrections history (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson?.detail) errMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }
  return res.json();
}

/**
 * Utility: Triggers client download of binary Blob and immediately revokes temporary Object URL.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}
