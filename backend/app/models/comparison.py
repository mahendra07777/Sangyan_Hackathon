"""Data models and schemas for Bharat Investor Copilot Compare Documents."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionStatus(str, Enum):
    """Explicit lifecycle state machine for comparison sessions."""

    INITIALIZED = "INITIALIZED"
    ACTIVE = "ACTIVE"
    FILES_UPLOADED = "FILES_UPLOADED"
    METADATA_EXTRACTED = "METADATA_EXTRACTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"


TERMINAL_SESSION_STATES = frozenset({
    SessionStatus.EXPIRED.value,
    SessionStatus.TERMINATED.value,
    SessionStatus.CANCELLED.value,
})

LEGAL_STATE_TRANSITIONS: Dict[str, Set[str]] = {
    SessionStatus.INITIALIZED.value: {
        SessionStatus.ACTIVE.value,
        SessionStatus.FILES_UPLOADED.value,
        SessionStatus.CANCELLED.value,
        SessionStatus.EXPIRED.value,
        SessionStatus.TERMINATED.value,
    },
    SessionStatus.ACTIVE.value: {
        SessionStatus.FILES_UPLOADED.value,
        SessionStatus.METADATA_EXTRACTED.value,
        SessionStatus.PROCESSING.value,
        SessionStatus.COMPLETED.value,
        SessionStatus.FAILED.value,
        SessionStatus.CANCELLED.value,
        SessionStatus.EXPIRED.value,
        SessionStatus.TERMINATED.value,
    },
    SessionStatus.FILES_UPLOADED.value: {
        SessionStatus.FILES_UPLOADED.value,
        SessionStatus.METADATA_EXTRACTED.value,
        SessionStatus.PROCESSING.value,
        SessionStatus.FAILED.value,
        SessionStatus.CANCELLED.value,
        SessionStatus.EXPIRED.value,
        SessionStatus.TERMINATED.value,
    },
    SessionStatus.METADATA_EXTRACTED.value: {
        SessionStatus.FILES_UPLOADED.value,
        SessionStatus.METADATA_EXTRACTED.value,
        SessionStatus.PROCESSING.value,
        SessionStatus.FAILED.value,
        SessionStatus.CANCELLED.value,
        SessionStatus.EXPIRED.value,
        SessionStatus.TERMINATED.value,
    },
    SessionStatus.PROCESSING.value: {
        SessionStatus.COMPLETED.value,
        SessionStatus.FAILED.value,
        SessionStatus.CANCELLED.value,
        SessionStatus.EXPIRED.value,
        SessionStatus.TERMINATED.value,
    },
    SessionStatus.COMPLETED.value: {
        SessionStatus.CANCELLED.value,
        SessionStatus.EXPIRED.value,
        SessionStatus.TERMINATED.value,
    },
    SessionStatus.FAILED.value: {
        SessionStatus.INITIALIZED.value,
        SessionStatus.CANCELLED.value,
        SessionStatus.EXPIRED.value,
        SessionStatus.TERMINATED.value,
    },
    SessionStatus.CANCELLED.value: set(),
    SessionStatus.EXPIRED.value: set(),
    SessionStatus.TERMINATED.value: set(),
}


class ComparisonMode(str, Enum):
    """Supported comparison modes."""

    QUICK_COMPARE = "QUICK_COMPARE"       # Exactly 2 documents
    MULTI_DOCUMENT = "MULTI_DOCUMENT"     # 3 to 5 documents


class SupportedFileFormat(str, Enum):
    """All eight approved document and spreadsheet formats."""

    PDF_DIGITAL = "PDF_DIGITAL"
    PDF_SCANNED = "PDF_SCANNED"
    IMAGE_PNG = "IMAGE_PNG"
    IMAGE_JPG = "IMAGE_JPG"
    IMAGE_JPEG = "IMAGE_JPEG"
    DOCX = "DOCX"
    XLSX = "XLSX"
    XLS = "XLS"


class DocumentSlot(str, Enum):
    """Pre-allocated document slots for multi-document comparisons (up to 5)."""

    DOC_A = "doc_a"
    DOC_B = "doc_b"
    DOC_C = "doc_c"
    DOC_D = "doc_d"
    DOC_E = "doc_e"


# ---------------------------------------------------------------------------
# Session & Lifecycle Models
# ---------------------------------------------------------------------------

class ComparisonSession(BaseModel):
    """Authoritative ephemeral comparison session state."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: str = Field(..., description="Internal UUID for directory isolation")
    token_hash: str = Field(..., description="SHA-256 hash of capability token")
    comparison_mode: ComparisonMode = Field(default=ComparisonMode.QUICK_COMPARE)
    status: SessionStatus = Field(default=SessionStatus.INITIALIZED)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(..., description="Hard absolute ceiling: created_at + 4h")
    idle_timeout_at: datetime = Field(..., description="Rolling idle timeout: last_accessed_at + 30m")
    document_ids: List[str] = Field(default_factory=list, max_length=5)
    consent_granted: bool = Field(default=False, description="Future-compatible external AI consent flag")
    approved_payload_hash: Optional[str] = Field(default=None, description="SHA-256 hash of approved transmission payload")
    storage_rel_path: str = Field(..., description="Relative storage path inside storage root")
    error_message: Optional[str] = None

    def can_transition_to(self, target: SessionStatus | str) -> bool:
        """Check if transition to target status is legal under the state machine."""
        target_val = target.value if isinstance(target, SessionStatus) else str(target)
        current_val = self.status.value if isinstance(self.status, SessionStatus) else str(self.status)
        if current_val in TERMINAL_SESSION_STATES:
            return False
        allowed = LEGAL_STATE_TRANSITIONS.get(current_val, set())
        return target_val in allowed

    def transition_to(self, target: SessionStatus | str) -> None:
        """Atomically transition session to target status, rejecting illegal transitions."""
        target_val = target.value if isinstance(target, SessionStatus) else str(target)
        current_val = self.status.value if isinstance(self.status, SessionStatus) else str(self.status)
        if not self.can_transition_to(target_val):
            raise ValueError(
                f"Illegal state transition from {current_val} to {target_val}."
            )
        self.status = SessionStatus(target_val)

    @field_validator("session_id")
    @classmethod
    def validate_uuid_format(cls, v: str) -> str:
        pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(pattern, v, re.IGNORECASE):
            raise ValueError("session_id must be a valid UUID4 string")
        return v.lower()


class SessionCreateRequest(BaseModel):
    """Payload for initializing a comparison session."""

    comparison_mode: ComparisonMode = Field(
        default=ComparisonMode.QUICK_COMPARE,
        description="QUICK_COMPARE (2 docs) or MULTI_DOCUMENT (up to 5 docs)",
    )


class SessionCreatedResponse(BaseModel):
    """Initial response returned upon session creation. The raw token is returned ONLY once."""

    session_id: str = Field(..., description="Internal session UUID")
    session_token: str = Field(..., description="256-bit cryptographically secure capability token")
    comparison_mode: ComparisonMode
    idle_timeout_seconds: int = Field(default=1800, description="30 minutes")
    absolute_timeout_seconds: int = Field(default=14400, description="4 hours")
    max_documents: int = Field(default=5)


class SessionDeleteResponse(BaseModel):
    """Response returned when a session is explicitly terminated."""

    status: str = "DELETED"
    message: str = "Session storage wiped cleanly and terminated."
    session_id: str


class SessionManifest(BaseModel):
    """Minimal on-disk session manifest. Strictly zero secrets or raw tokens."""

    schema_version: str = "1.0.0"
    session_id: str
    comparison_mode: str
    status: str
    created_at: str
    last_accessed_at: str
    expires_at: str
    idle_timeout_at: str
    document_ids: List[str] = Field(default_factory=list)
    consent_granted: bool = False
    approved_payload_hash: Optional[str] = None


# ---------------------------------------------------------------------------
# Error Envelope
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Slice 2: Multi-Document Ingestion & Extraction Models
# ---------------------------------------------------------------------------

class ComparisonDocument(BaseModel):
    """Tracks metadata and physical properties of each uploaded filing."""

    model_config = ConfigDict(use_enum_values=True)

    doc_id: str = Field(..., description="Unique document ID (doc_a .. doc_e)")
    slot: DocumentSlot
    original_filename: str = Field(..., min_length=1, max_length=255)
    file_format: SupportedFileFormat
    file_size_bytes: int = Field(..., gt=0, le=20 * 1024 * 1024, description="Max 20 MiB")
    page_count: Optional[int] = Field(default=None, le=200, description="Max 200 pages for PDFs")
    sheet_names: Optional[List[str]] = Field(default=None, description="Sheet names for spreadsheets")
    is_scanned: bool = Field(default=False)
    storage_rel_path: str = Field(..., description="Path relative to session directory")
    extraction_status: str = Field(
        default="SUCCESS",
        description="SUCCESS | VISION_EXTRACTION_REQUIRED | OCR_UNAVAILABLE_LOCAL_MODE | FAILED",
    )
    extraction_error: Optional[str] = None


class EvidenceReference(BaseModel):
    """Guarantees source provenance for every extracted line item, variance, and narrative fact."""

    evidence_id: str
    doc_id: str
    document_name: str
    page_number: Optional[int] = Field(default=None, description="1-based page index for PDF/images")
    bounding_box: Optional[List[float]] = Field(default=None, description="[x0, y0, x1, y1] normalized (0.0 to 1.0)")
    sheet_name: Optional[str] = Field(default=None, description="Sheet name for spreadsheets")
    cell_range: Optional[str] = Field(default=None, description="e.g. B14, C10:E22 for spreadsheets")
    structural_ref: Optional[str] = Field(default=None, description="Heading, Section or Paragraph for DOCX")
    verbatim_snippet: str = Field(..., description="Verbatim text quote from source document")
    table_context: Optional[str] = Field(default=None, description="Table header or line item label context")


class ExtractedTableCell(BaseModel):
    """Individual cell representation inside extracted tabular structures."""

    row_index: int
    col_index: int
    value: Optional[str] = None
    raw_value: Optional[Any] = None
    data_type: str = "string"  # string, number, date, boolean, empty
    is_header: bool = False
    cell_range: Optional[str] = None
    formula: Optional[str] = None
    bounding_box: Optional[List[float]] = Field(
        default=None,
        description="[x0, y0, x1, y1] normalized (0.0 to 1.0)",
    )


class ExtractedTable(BaseModel):
    """Tabular structure extracted from PDF, DOCX, XLSX, or XLS."""

    table_id: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    structural_ref: Optional[str] = None
    title: Optional[str] = None
    num_rows: int = 0
    num_cols: int = 0
    headers: List[str] = Field(default_factory=list)
    rows: List[List[Optional[str]]] = Field(default_factory=list)
    cells: List[ExtractedTableCell] = Field(default_factory=list)
    bounding_box: Optional[List[float]] = Field(
        default=None,
        description="[x0, y0, x1, y1] normalized (0.0 to 1.0)",
    )


class ExtractedTextBlock(BaseModel):
    """Extracted paragraph or heading block with location coordinates."""

    block_id: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    structural_ref: Optional[str] = None
    text: str
    bounding_box: Optional[List[float]] = None
    heading_level: Optional[int] = None
    block_type: str = "paragraph"  # paragraph, heading, list_item, note


class DocumentExtractionResult(BaseModel):
    """Complete localized extraction outcome stored as structured JSON on disk."""

    model_config = ConfigDict(use_enum_values=True)

    doc_id: str
    slot: DocumentSlot
    file_format: SupportedFileFormat
    page_count: Optional[int] = None
    sheet_names: Optional[List[str]] = None
    is_scanned: bool = False
    extraction_status: str = "SUCCESS"  # SUCCESS | VISION_EXTRACTION_REQUIRED | OCR_UNAVAILABLE_LOCAL_MODE | FAILED
    tables: List[ExtractedTable] = Field(default_factory=list)
    text_blocks: List[ExtractedTextBlock] = Field(default_factory=list)
    raw_word_count: int = 0
    notes: List[str] = Field(default_factory=list)
    extraction_error: Optional[str] = None


class UploadSuccessResponse(BaseModel):
    """Response returned when documents are successfully ingested and parsed."""

    session_id: str
    uploaded_documents: List[ComparisonDocument]
    consent_granted: bool = False


# ---------------------------------------------------------------------------
# Slice 3: Metadata Extraction & Compatibility Models
# ---------------------------------------------------------------------------

class ReportingScope(str, Enum):
    CONSOLIDATED = "CONSOLIDATED"
    STANDALONE = "STANDALONE"
    BOTH = "BOTH"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class AuditStatus(str, Enum):
    AUDITED = "AUDITED"
    UNAUDITED = "UNAUDITED"
    LIMITED_REVIEW = "LIMITED_REVIEW"
    PROVISIONAL = "PROVISIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class DocumentType(str, Enum):
    ANNUAL_REPORT = "Annual Report"
    QUARTERLY_RESULTS = "Quarterly Financial Results"
    HALF_YEARLY_RESULTS = "Half-Yearly Financial Results"
    IPO_PROSPECTUS = "IPO Prospectus"
    RED_HERRING_PROSPECTUS = "Red Herring Prospectus (RHP)"
    DRAFT_RED_HERRING_PROSPECTUS = "Draft Red Herring Prospectus (DRHP)"
    FINANCIAL_STATEMENTS = "Financial Statements"
    INVESTOR_PRESENTATION = "Investor Presentation"
    OTHER = "Other Financial Document"
    UNKNOWN = "Unknown"


class ReportingPeriodType(str, Enum):
    ANNUAL = "Annual"
    QUARTERLY = "Quarterly"
    HALF_YEARLY = "Half-Yearly"
    NINE_MONTHS = "Nine-Month"
    MONTHLY = "Monthly"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class DocumentMetadata(BaseModel):
    """Authoritative institutional metadata with detection provenance and override tracking."""

    model_config = ConfigDict(use_enum_values=True)

    doc_id: str
    company_name: str = Field(default="Unknown")
    company_identifier: Optional[str] = None  # Explicit CIN / registration ID found; never invented
    alternative_names: List[str] = Field(default_factory=list)
    industry: str = Field(default="UNKNOWN", description="e.g. Automobiles, IT Services, Banking, or UNKNOWN")
    document_type: str = Field(default=DocumentType.UNKNOWN.value)
    financial_year: str = Field(default="Unknown", description="e.g. FY 2023-24, FY 2024-25")
    fy_start: Optional[str] = None
    fy_end: Optional[str] = None
    is_inferred_year: bool = False
    reporting_period: str = Field(default=ReportingPeriodType.UNKNOWN.value)
    reporting_period_display: Optional[str] = None
    quarter: Optional[str] = Field(default=None, description="Q1, Q2, Q3, Q4, or None")
    period_start_date: Optional[str] = None
    period_end_date: Optional[str] = None
    currency: str = Field(default="INR")
    currency_symbol: Optional[str] = "₹"
    reporting_scale: str = Field(default="CRORE", description="CRORE, LAKH, MILLION, BILLION, THOUSAND, UNITS, UNKNOWN")
    accounting_standard: str = Field(default="Ind AS")
    accounting_standard_disclosure: Optional[str] = None
    reporting_scope: ReportingScope = Field(default=ReportingScope.CONSOLIDATED)
    audit_status: AuditStatus = Field(default=AuditStatus.AUDITED)
    is_user_overridden: bool = False
    confidence_category: str = Field(default="MEDIUM", description="HIGH | MEDIUM | LOW | UNKNOWN")
    evidence_sources: Dict[str, EvidenceReference] = Field(default_factory=dict)
    conflicting_candidates: Dict[str, List[str]] = Field(default_factory=dict)
    user_overrides: Dict[str, Any] = Field(default_factory=dict)
    original_detected_values: Dict[str, Any] = Field(default_factory=dict)
    extraction_notes: List[str] = Field(default_factory=list)


class MetadataUpdateRequest(BaseModel):
    """User correction payload for identified metadata fields."""

    company_name: Optional[str] = None
    company_identifier: Optional[str] = None
    industry: Optional[str] = None
    document_type: Optional[str] = None
    financial_year: Optional[str] = None
    reporting_period: Optional[str] = None
    quarter: Optional[str] = None
    currency: Optional[str] = None
    reporting_scale: Optional[str] = None
    accounting_standard: Optional[str] = None
    reporting_scope: Optional[ReportingScope] = None
    audit_status: Optional[AuditStatus] = None


class SessionMetadataResponse(BaseModel):
    """Encapsulates identified metadata for all session documents."""

    session_id: str
    metadata: Dict[str, DocumentMetadata]


# ---------------------------------------------------------------------------
# Compatibility Matrix Models
# ---------------------------------------------------------------------------

class IssueSeverity(str, Enum):
    BLOCKER = "BLOCKER"     # Halts comparative calculation
    WARNING = "WARNING"     # Explains contextual discrepancy to user
    INFORMATION = "INFORMATION"


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    COMPATIBLE_WITH_WARNINGS = "COMPATIBLE_WITH_WARNINGS"
    PARTIALLY_COMPATIBLE = "PARTIALLY_COMPATIBLE"
    BLOCKED = "BLOCKED"


class CompatibilityFinding(BaseModel):
    """Specific contextual discrepancy, warning, or comparative blocker."""

    finding_id: str
    severity: IssueSeverity
    code: str = Field(..., description="e.g. CURRENCY_MISMATCH, SCOPE_MISMATCH, PERIOD_DURATION_MISMATCH, SCALE_DIFFERENCE, QUARTER_MISMATCH, YEAR_GAP_WARNING")
    title: str
    description: str
    affected_document_ids: List[str]
    relevant_fields: List[str] = Field(default_factory=list)
    observed_values: Dict[str, str] = Field(default_factory=dict)
    remediation_hint: Optional[str] = None
    can_user_override_resolve: bool = False


class PairwiseCompatibility(BaseModel):
    """Granular directional or bilateral compatibility between two specific documents."""

    doc_a_id: str
    doc_b_id: str
    is_comparable: bool
    status: CompatibilityStatus
    blocker_count: int = 0
    warning_count: int = 0
    findings: List[CompatibilityFinding] = Field(default_factory=list)


class CompatibilityReport(BaseModel):
    """Comprehensive multi-document compatibility matrix evaluation."""

    session_id: Optional[str] = None
    is_comparable: bool = Field(..., description="False if any blocker severity finding exists")
    overall_status: CompatibilityStatus = Field(default=CompatibilityStatus.COMPATIBLE)
    blocker_count: int = 0
    warning_count: int = 0
    findings: List[CompatibilityFinding] = Field(default_factory=list)
    pairwise_matrix: List[PairwiseCompatibility] = Field(default_factory=list)
    compatible_subsets: List[List[str]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Slice 4: Financial Metric Candidates, Normalization & Calculations
# ---------------------------------------------------------------------------

class StatementType(str, Enum):
    BALANCE_SHEET = "BALANCE_SHEET"
    PROFIT_AND_LOSS = "PROFIT_AND_LOSS"
    CASH_FLOW = "CASH_FLOW"
    NOTES_TO_ACCOUNTS = "NOTES_TO_ACCOUNTS"
    MDA_NARRATIVE = "MDA_NARRATIVE"
    OTHER = "OTHER"


class ConflictStatus(str, Enum):
    NO_CONFLICT = "NO_CONFLICT"
    RESOLVED_AUTOMATIC = "RESOLVED_AUTOMATIC"
    UNCERTAIN = "UNCERTAIN"
    USER_RESOLVED = "USER_RESOLVED"


class ValueCandidate(BaseModel):
    """Traceable financial metric candidate extracted from tables or text."""

    model_config = ConfigDict(use_enum_values=True)

    candidate_id: str
    doc_id: str
    metric_key: str
    raw_label: str
    raw_text_value: str
    parsed_number: Optional[Decimal] = None
    normalized_amount: Optional[Decimal] = Field(
        default=None,
        description="Standardized in Crore with Decimal precision (or INR per-share for EPS)",
    )
    original_currency: str = "INR"
    normalized_currency: str = "INR"
    original_scale: str = "CRORE"
    normalized_unit: str = "INR_CRORE"
    statement_type: StatementType = StatementType.OTHER
    reporting_scope: ReportingScope = ReportingScope.CONSOLIDATED
    audit_status: AuditStatus = AuditStatus.AUDITED
    accounting_standard: str = "Ind AS"
    period_start_date: Optional[str] = None
    period_end_date: Optional[str] = None
    financial_year: Optional[str] = None
    quarter: Optional[str] = None
    period_duration: Optional[str] = None
    is_restated: bool = False
    is_derived: bool = False
    metric_definition: Optional[str] = None
    dash_convention_applied: bool = False
    evidence: EvidenceReference
    extraction_method: str = "TABLE_CELL"  # TABLE_CELL | TEXT_PATTERN
    extraction_confidence: str = "HIGH"    # HIGH | MEDIUM | LOW | UNKNOWN
    resolution_status: ConflictStatus = ConflictStatus.NO_CONFLICT
    warnings: List[str] = Field(default_factory=list)


class ConflictResolution(BaseModel):
    """Explainable conflict arbitration outcome for a specific metric across candidates."""

    model_config = ConfigDict(use_enum_values=True)

    conflict_id: str
    metric_key: str
    status: ConflictStatus
    selected_candidate: Optional[ValueCandidate] = None
    all_candidates: List[ValueCandidate] = Field(default_factory=list)
    resolution_reason: str = Field(..., description="Human-readable explanation of priority rule applied")
    difference_absolute: Optional[Decimal] = None
    remaining_warnings: List[str] = Field(default_factory=list)


class FinancialValue(BaseModel):
    """Final resolved or unresolvable institutional financial value for comparison."""

    model_config = ConfigDict(use_enum_values=True)

    doc_id: str
    metric_key: str
    label: str
    amount: Optional[Decimal] = None
    reported_amount: Optional[Decimal] = None
    display_amount: Optional[str] = None
    unit: str = "INR_CRORE"
    currency: str = "INR"
    reported_currency: Optional[str] = None
    reported_scale: Optional[str] = None
    status: str = Field(
        default="REPORTED",
        description="REPORTED | NOT_DISCLOSED | UNCERTAIN | AMBIGUOUS | EXTRACTION_UNAVAILABLE",
    )
    reporting_scope: ReportingScope = ReportingScope.CONSOLIDATED
    evidence: Optional[EvidenceReference] = None
    selected_candidate_id: Optional[str] = None
    conflict_info: Optional[ConflictResolution] = None
    fact_classification: str = "DOCUMENT_FACT"  # DOCUMENT_FACT | EDUCATIONAL_EXPLANATION | SOURCE_INFORMATION | UNCERTAIN | USER_ENTERED
    is_user_corrected: bool = Field(default=False, description="True if value was manually adjusted by user")
    original_amount: Optional[Decimal] = Field(default=None, description="Preserves original machine-extracted normalized amount")
    user_entered_amount: Optional[Decimal] = Field(default=None, description="Exact amount entered by user")
    correction_reason: Optional[str] = Field(default=None, description="Optional user explanation for manual adjustment")
    correction_timestamp: Optional[datetime] = Field(default=None, description="ISO timestamp of manual adjustment")


class VarianceStatus(str, Enum):
    CALCULATED = "CALCULATED"
    DIV_BY_ZERO = "DIV_BY_ZERO"
    NON_POSITIVE_BASE = "NON_POSITIVE_BASE"
    NOT_DISCLOSED = "NOT_DISCLOSED"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    INCOMPATIBLE_UNITS = "INCOMPATIBLE_UNITS"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    BLOCKED = "BLOCKED"


class CalculationResult(BaseModel):
    """Deterministic mathematical variance with negative-base directional explanation."""

    model_config = ConfigDict(use_enum_values=True)

    metric_key: str
    label: str
    base_doc_id: str
    comparison_doc_id: str
    base_value: Optional[Decimal] = None
    comparison_value: Optional[Decimal] = None
    base_candidate_id: Optional[str] = None
    comparison_candidate_id: Optional[str] = None
    formula: str = "(comparison - base)"
    absolute_variance: Optional[Decimal] = None
    percentage_change: Optional[Decimal] = None
    display_absolute_variance: Optional[str] = None
    display_percentage_change: Optional[str] = None
    unit: str = "INR_CRORE"
    rounding_method: str = "ROUND_HALF_UP"
    status: VarianceStatus
    directional_explanation: Optional[str] = Field(
        default=None,
        description="Mandatory narrative for non-positive base transitions (Loss to Profit, etc.) or reason percentage was omitted",
    )


class ProcessingStage(str, Enum):
    INITIALIZED = "INITIALIZED"
    IDENTIFYING_METADATA = "IDENTIFYING_METADATA"
    VALIDATING_COMPATIBILITY = "VALIDATING_COMPATIBILITY"
    EXTRACTING_FINANCIAL_DATA = "EXTRACTING_FINANCIAL_DATA"
    RESOLVING_CONFLICTS = "RESOLVING_CONFLICTS"
    COMPUTING_CALCULATIONS = "COMPUTING_CALCULATIONS"
    SYNTHESIZING_REPORT = "SYNTHESIZING_REPORT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ProcessingStatusResponse(BaseModel):
    session_id: str
    current_stage: ProcessingStage
    completed_stages: List[str] = Field(default_factory=list)
    stage_message: str = ""
    is_cancelled: bool = False
    is_completed: bool = False
    error: Optional[str] = None


class SessionFinancialsResponse(BaseModel):
    session_id: str
    financial_values: Dict[str, Dict[str, FinancialValue]]  # metric_key -> doc_id -> value
    all_candidates: Dict[str, List[ValueCandidate]] = Field(default_factory=dict)  # doc_id -> candidates
    conflicts: Dict[str, Dict[str, ConflictResolution]] = Field(default_factory=dict)  # doc_id -> metric_key -> conflict


class SessionCalculationsResponse(BaseModel):
    session_id: str
    variances: List[CalculationResult] = Field(default_factory=list)
    pairwise_matrix_summary: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Slice 5: Evidence-Grounded AI Synthesis, Translation & Consent Models
# ---------------------------------------------------------------------------

class ChangeClassification(str, Enum):
    POSITIVE_IMPROVEMENT = "POSITIVE_IMPROVEMENT"
    NEGATIVE_PRESSURE = "NEGATIVE_PRESSURE"
    NEUTRAL_STRUCTURAL = "NEUTRAL_STRUCTURAL"
    UNCERTAIN = "UNCERTAIN"


class FactClassification(str, Enum):
    DOCUMENT_FACT = "DOCUMENT_FACT"
    EDUCATIONAL_EXPLANATION = "EDUCATIONAL_EXPLANATION"
    SOURCE_INFORMATION = "SOURCE_INFORMATION"
    UNCERTAIN = "UNCERTAIN"


class RiskDisclosure(BaseModel):
    """Institutional disclosed risk with evidence grounding. Direct disclosure classified as DOCUMENT_FACT; audit status preserved separately."""

    model_config = ConfigDict(use_enum_values=True)

    risk_id: str
    title: str
    category: str = Field(..., description="Operational, Financial, Regulatory, Market, Governance")
    doc_id: str
    severity: str = Field(default="MEDIUM", description="HIGH | MEDIUM | LOW")
    disclosure_text: str
    evidence: EvidenceReference
    fact_classification: FactClassification = FactClassification.DOCUMENT_FACT
    audit_status: Optional[str] = Field(default=None, description="AUDITED, UNAUDITED, LIMITED_REVIEW, etc.")


class AccountingDifference(BaseModel):
    """Identified accounting standard or disclosure policy divergence. Direct disclosures classified as DOCUMENT_FACT; audit status preserved separately."""

    model_config = ConfigDict(use_enum_values=True)

    difference_id: str
    topic: str = Field(..., description="Revenue Recognition, Depreciation, Leases, Financial Instruments")
    doc_a_policy: str
    doc_b_policy: str
    impact_summary: str
    evidence_a: EvidenceReference
    evidence_b: EvidenceReference
    fact_classification: FactClassification = FactClassification.DOCUMENT_FACT
    audit_status_a: Optional[str] = None
    audit_status_b: Optional[str] = None


class ExecutiveSummary(BaseModel):
    """Evidence-grounded comparative narrative structured across approved sections."""

    model_config = ConfigDict(use_enum_values=True)

    overview_story: str
    core_positive_changes: List[str] = Field(default_factory=list)
    core_negative_changes: List[str] = Field(default_factory=list)
    neutral_observations: List[str] = Field(default_factory=list)
    uncertain_findings: List[str] = Field(default_factory=list)
    critical_disclosures: List[str] = Field(default_factory=list)
    mode: str = "LOCAL_MODE"  # "LOCAL_MODE" | "AI_ASSISTED" | "LOCAL_MODE_FALLBACK"
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    fallback_message: Optional[str] = None
    fact_classification: FactClassification = FactClassification.EDUCATIONAL_EXPLANATION


class VerificationSourceType(str, Enum):
    SEBI_FILING = "SEBI_FILING"
    NSE_ANNOUNCEMENT = "NSE_ANNOUNCEMENT"
    BSE_ANNOUNCEMENT = "BSE_ANNOUNCEMENT"
    COMPANY_IR = "COMPANY_IR"


class VerificationStatus(str, Enum):
    VERIFIED_MATCH = "VERIFIED_MATCH"
    SIMULATED = "SIMULATED"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    DISCREPANCY_DETECTED = "DISCREPANCY_DETECTED"
    REGISTRY_UNAVAILABLE = "REGISTRY_UNAVAILABLE"
    SKIPPED_LOCAL_MODE = "SKIPPED_LOCAL_MODE"


class VerificationResult(BaseModel):
    """Official regulatory or stock exchange verification record."""

    model_config = ConfigDict(use_enum_values=True)

    source_type: VerificationSourceType
    source_url: Optional[str] = None
    status: VerificationStatus
    verified_item: str
    details: str
    retrieved_at: Optional[datetime] = None


class ComparisonResult(BaseModel):
    """Comprehensive comparative output model (Endpoint 12)."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: str
    mode: str = "LOCAL_MODE"  # "LOCAL_MODE" | "AI_ASSISTED" | "LOCAL_MODE_FALLBACK"
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    fallback_message: Optional[str] = None
    documents: List[ComparisonDocument]
    metadata: Dict[str, DocumentMetadata]
    compatibility: CompatibilityReport
    financial_values: Dict[str, Dict[str, FinancialValue]]  # metric_key -> doc_id -> value
    variances: List[CalculationResult]                      # Pairwise calculations
    executive_summary: Optional[ExecutiveSummary] = None
    risks: List[RiskDisclosure] = Field(default_factory=list)
    accounting_differences: List[AccountingDifference] = Field(default_factory=list)
    verifications: List[VerificationResult] = Field(default_factory=list)
    language: str = "English"
    safety_disclaimer: str = (
        "This is an educational financial-document understanding assistant grounded strictly in the provided "
        "documents and does not constitute SEBI-registered investment advice, stock tips, or buy/sell recommendations."
    )


class ComparisonChatMessage(BaseModel):
    """Comparative Q&A chat message grounded in extracted evidence (Endpoint 14)."""

    model_config = ConfigDict(use_enum_values=True)

    message_id: str
    role: str = Field(..., description="'user' | 'assistant'")
    content: str
    cited_evidence: List[EvidenceReference] = Field(default_factory=list)
    safety_disclaimer: str = (
        "This is an educational comparison grounded in the uploaded documents and does not constitute investment advice."
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FallbackReasonCode(str, Enum):
    """Granular failure and fallback classification codes."""

    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    PROVIDER_UNAVAILABLE_503 = "PROVIDER_UNAVAILABLE_503"
    PROVIDER_SERVER_ERROR_5XX = "PROVIDER_SERVER_ERROR_5XX"
    PROVIDER_QUOTA_EXCEEDED_429 = "PROVIDER_QUOTA_EXCEEDED_429"
    PROVIDER_CREDENTIALS_MISSING = "PROVIDER_CREDENTIALS_MISSING"
    CONSENT_WITHDRAWN = "CONSENT_WITHDRAWN"
    STALE_CONSENT_HASH_MISMATCH = "STALE_CONSENT_HASH_MISMATCH"


class TransmissionSectionPreview(BaseModel):
    """Selective page and section preview for external transmission."""

    model_config = ConfigDict(use_enum_values=True)

    doc_id: str
    document_name: str
    page_number: Optional[int] = None
    section_title: str
    excerpt_snippet: str


class TransmissionPreview(BaseModel):
    """Exact preview of sanitized data payload scheduled for external AI processing."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: str
    document_names: List[str]
    selected_sections_and_pages: List[TransmissionSectionPreview] = Field(default_factory=list)
    purpose_of_processing: str = (
        "Synthesizing educational comparative narrative and explaining financial variances for retail investors."
    )
    ai_service_provider: str = "Google Gemini 2.5 Flash via Google Standard Free Tier"
    redacted_pii_summary: List[Any] = Field(default_factory=list)
    total_pii_redacted_count: int = 0
    redaction_disclaimer: str = (
        "Automatic PII redaction uses automated heuristic pattern matching and may be imperfect. "
        "Do not submit unredacted confidential or sensitive personal financial data."
    )
    payload_hash: str = Field(..., description="SHA-256 fingerprint of the exact sanitized prompt")
    sanitized_payload_preview: str = Field(..., description="Actual sanitized prompt content to be transmitted")
    structured_financial_summary: List[Dict[str, Any]] = Field(default_factory=list)
    requires_fresh_consent: bool = True


class ConsentRequest(BaseModel):
    """Payload strictly requiring affirmative acceptance to record external AI consent."""

    model_config = ConfigDict(use_enum_values=True)

    consent_granted: bool = Field(
        ...,
        description="Affirmative acceptance flag. Must be explicitly True to record consent.",
    )
    payload_hash: Optional[str] = Field(
        default=None,
        description="Optional SHA-256 hash of the reviewed transmission preview payload to bind consent.",
    )


class ConsentResponse(BaseModel):
    """External AI processing consent status with mandatory disclosures and withdrawal limitations."""

    model_config = ConfigDict(use_enum_values=True)

    consent_granted: bool
    message: str
    updated_at: str
    terms_disclosure: Optional[str] = None
    withdrawal_limitations: Optional[str] = None
    payload_hash: Optional[str] = None
    transmission_preview: Optional[TransmissionPreview] = None


class ProcessPayload(BaseModel):
    """Request payload for POST /api/compare/session/{id}/process."""

    model_config = ConfigDict(use_enum_values=True)

    language: str = "English"
    payload_hash: Optional[str] = None


# ---------------------------------------------------------------------------
# Slice 6: Manual Financial Correction & Undo Models
# ---------------------------------------------------------------------------

class FinancialCorrectionRequest(BaseModel):
    """Payload for manually correcting an extracted financial metric."""

    model_config = ConfigDict(use_enum_values=True)

    doc_id: str = Field(..., description="Target document ID (e.g. doc_a)")
    metric_key: str = Field(..., description="Canonical metric key (e.g. REVENUE, PAT)")
    corrected_amount: Decimal = Field(..., description="New numeric amount in the metric's normalized scale")
    reason: Optional[str] = Field(default=None, max_length=500, description="Optional user note explaining reason for correction")

    @field_validator("corrected_amount")
    @classmethod
    def validate_finite_decimal(cls, v: Decimal) -> Decimal:
        if v.is_nan() or v.is_infinite():
            raise ValueError("Corrected amount must be a finite numerical value")
        if abs(v) > Decimal("1e14"):
            raise ValueError("Corrected amount exceeds maximum supported magnitude (10^14)")
        return v


class FinancialCorrectionRecord(BaseModel):
    """Journal record tracking previous and user-entered states for LIFO undo stack."""

    model_config = ConfigDict(use_enum_values=True)

    correction_id: str = Field(..., description="Unique ID for this correction entry")
    session_id: str
    doc_id: str
    metric_key: str
    previous_effective_amount: Optional[Decimal] = None
    original_extracted_amount: Optional[Decimal] = None
    previous_status: str = "REPORTED"
    previous_fact_classification: str = "DOCUMENT_FACT"
    previous_display_amount: Optional[str] = None
    new_user_entered_amount: Decimal
    corrected_display_amount: str
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    unit: str = "INR_CRORE"
    currency: str = "INR"


class FinancialCorrectionResponse(BaseModel):
    """Response returned after successfully applying a financial correction."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: str
    status: str = "CORRECTED"
    correction: FinancialCorrectionRecord
    comparison_result: ComparisonResult
    recalculated_metrics: List[str] = Field(default_factory=list)


class FinancialUndoResponse(BaseModel):
    """Response returned after successfully undoing the latest correction."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: str
    status: str = "UNDONE"
    undone_correction: FinancialCorrectionRecord
    remaining_corrections_count: int
    comparison_result: ComparisonResult
    recalculated_metrics: List[str] = Field(default_factory=list)


class SessionCorrectionsResponse(BaseModel):
    """Summary of all active corrections for a comparison session."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: str
    corrections_count: int
    corrections: List[FinancialCorrectionRecord] = Field(default_factory=list)






