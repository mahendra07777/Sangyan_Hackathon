# Bharat Investor Copilot — Compare Documents
## Data Schemas & Model Contracts (Slice 0)

**Project:** Bharat Investor Copilot (SANGYAN 2026 Hackathon — IIT BHU)  
**File:** `docs/compare_documents_data_schemas.md`  
**Status:** Approved Specification (Slice 0 Deliverable)  
**Author:** Senior Software Architect, Backend Architect, Frontend Architect & Security Reviewer  

---

## 1. Overview & Schema Architecture

This document defines the authoritative data contracts, Pydantic v2 models (backend), and TypeScript interfaces (frontend) for the **Compare Documents** feature.

### Design Principles:
1. **Decimal Precision:** All financial amounts and ratios use Python `decimal.Decimal` and string serializations over the wire to eliminate IEEE 754 floating-point drift.
2. **Immutable Provenance:** Every extracted value maintains an `EvidenceReference` linking it to an exact document, page/sheet, bounding box/cell, and verbatim quote.
3. **Strict Validation & No Magic Values:** Missing values are represented as `None` / `null` with explicit status tags (`NOT_DISCLOSED`), never imputed as `0` or empty strings.
4. **Trilingual Ready:** Text fields support English, Hindi (Devanagari), and Hinglish (Romanized Hindi).

---

## 2. Core Schemas & Pydantic / TypeScript Specifications

### 2.1 ComparisonSession & Session State

#### Purpose:
Represents the root ephemeral comparison container, tracking client capability tokens, document slots, processing stages, and timeout timestamps.

#### Pydantic Model (Python):
```python
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class SessionStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    FILES_UPLOADED = "FILES_UPLOADED"
    METADATA_EXTRACTED = "METADATA_EXTRACTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class ComparisonMode(str, Enum):
    QUICK_COMPARE = "QUICK_COMPARE"       # Exactly 2 documents
    MULTI_DOCUMENT = "MULTI_DOCUMENT"     # 3 to 5 documents

class ComparisonSession(BaseModel):
    session_id: str = Field(..., description="Internal random UUID for filesystem directory isolation")
    token_hash: str = Field(..., description="SHA-256 hash of the 256-bit client capability token")
    comparison_mode: ComparisonMode = Field(default=ComparisonMode.QUICK_COMPARE)
    status: SessionStatus = Field(default=SessionStatus.INITIALIZED)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="Hard absolute expiration ceiling (created_at + 4h)")
    idle_timeout_at: datetime = Field(..., description="Rolling inactivity timeout (last_accessed_at + 30m)")
    document_ids: List[str] = Field(default_factory=list, max_length=5)
    consent_granted: bool = Field(default=False, description="External AI cloud processing consent flag")
    error_message: Optional[str] = None
```

#### TypeScript Interface (Frontend):
```typescript
export type SessionStatus = 
  | 'INITIALIZED' 
  | 'FILES_UPLOADED' 
  | 'METADATA_EXTRACTED' 
  | 'PROCESSING' 
  | 'COMPLETED' 
  | 'FAILED' 
  | 'CANCELLED' 
  | 'EXPIRED';

export type ComparisonMode = 'QUICK_COMPARE' | 'MULTI_DOCUMENT';

export interface ComparisonSession {
  sessionId: string;
  comparisonMode: ComparisonMode;
  status: SessionStatus;
  createdAt: string;
  lastAccessedAt: string;
  expiresAt: string;
  idleTimeoutAt: string;
  documentIds: string[];
  consentGranted: boolean;
  errorMessage?: string | null;
}
```

---

### 2.2 ComparisonDocument & File Signatures

#### Purpose:
Tracks metadata and physical properties of each uploaded filing within a comparison session.

#### Pydantic Model (Python):
```python
class SupportedFileFormat(str, Enum):
    PDF_DIGITAL = "PDF_DIGITAL"
    PDF_SCANNED = "PDF_SCANNED"
    IMAGE_PNG = "IMAGE_PNG"
    IMAGE_JPEG = "IMAGE_JPEG"
    DOCX = "DOCX"
    XLSX = "XLSX"
    XLS = "XLS"

class DocumentSlot(str, Enum):
    DOC_A = "doc_a"
    DOC_B = "doc_b"
    DOC_C = "doc_c"
    DOC_D = "doc_d"
    DOC_E = "doc_e"

class ComparisonDocument(BaseModel):
    doc_id: str = Field(..., description="Unique document ID (doc_a .. doc_e)")
    slot: DocumentSlot
    original_filename: str = Field(..., min_length=1, max_length=255)
    file_format: SupportedFileFormat
    file_size_bytes: int = Field(..., gt=0, le=20 * 1024 * 1024, description="Max 20 MiB")
    page_count: Optional[int] = Field(default=None, le=200, description="Max 200 pages for PDFs")
    sheet_names: Optional[List[str]] = Field(default=None, description="Sheet names for spreadsheets")
    is_scanned: bool = Field(default=False)
    storage_rel_path: str = Field(..., description="Path relative to session directory")
```

#### TypeScript Interface (Frontend):
```typescript
export type SupportedFileFormat = 
  | 'PDF_DIGITAL' 
  | 'PDF_SCANNED' 
  | 'IMAGE_PNG' 
  | 'IMAGE_JPEG' 
  | 'DOCX' 
  | 'XLSX' 
  | 'XLS';

export interface ComparisonDocument {
  docId: string;
  slot: string;
  originalFilename: string;
  fileFormat: SupportedFileFormat;
  fileSizeBytes: number;
  pageCount?: number | null;
  sheetNames?: string[] | null;
  isScanned: boolean;
}
```

---

### 2.3 DocumentMetadata & User Overrides

#### Purpose:
Encapsulates extracted institutional identity, time horizon, reporting scope, currency, and accounting standards.

#### Pydantic Model (Python):
```python
class ReportingScope(str, Enum):
    CONSOLIDATED = "CONSOLIDATED"
    STANDALONE = "STANDALONE"
    UNKNOWN = "UNKNOWN"

class AuditStatus(str, Enum):
    AUDITED = "AUDITED"
    UNAUDITED = "UNAUDITED"
    PROVISIONAL = "PROVISIONAL"
    UNKNOWN = "UNKNOWN"

class DocumentMetadata(BaseModel):
    doc_id: str
    company_name: str = Field(..., min_length=1)
    company_identifier: Optional[str] = None
    industry: str = Field(default="UNKNOWN", description="e.g. Automobiles, IT Services, Banking, or UNKNOWN")
    document_type: str = Field(..., description="e.g. Annual Report, Q3 Financial Results, IPO Prospectus")
    financial_year: str = Field(..., description="e.g. FY 2023-24, FY 2022-23")
    reporting_period: str = Field(..., description="e.g. Q1, Q2, Q3, Q4, Full Year, 9 Months")
    quarter: Optional[str] = Field(default=None, description="e.g. Q1, Q2, Q3, Q4")
    currency: str = Field(default="INR", description="e.g. INR, USD, EUR")
    accounting_standard: str = Field(default="Ind AS", description="e.g. Ind AS, Indian GAAP, IFRS, US GAAP")
    reporting_scope: ReportingScope = Field(default=ReportingScope.CONSOLIDATED)
    audit_status: AuditStatus = Field(default=AuditStatus.AUDITED)
    is_user_overridden: bool = Field(default=False)
```

#### TypeScript Interface (Frontend):
```typescript
export type ReportingScope = 'CONSOLIDATED' | 'STANDALONE' | 'UNKNOWN';
export type AuditStatus = 'AUDITED' | 'UNAUDITED' | 'PROVISIONAL' | 'UNKNOWN';

export interface DocumentMetadata {
  docId: string;
  companyName: string;
  companyIdentifier?: string | null;
  industry: string;
  documentType: string;
  financialYear: string;
  reportingPeriod: string;
  quarter?: string | null;
  currency: string;
  accountingStandard: string;
  reportingScope: ReportingScope;
  auditStatus: AuditStatus;
  isUserOverridden: boolean;
}
```

---

### 2.4 CompatibilityReport, Finding & Severity

#### Purpose:
Validates comparative soundness across uploaded documents, identifying hard blockers, contextual warnings, and information notices.

#### Pydantic Model (Python):
```python
class IssueSeverity(str, Enum):
    BLOCKER = "BLOCKER"         # Halts comparative calculation
    WARNING = "WARNING"         # Explains contextual discrepancy to user
    INFORMATION = "INFORMATION" # Non-blocking contextual disclosure

class CompatibilityStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    COMPATIBLE_WITH_WARNINGS = "COMPATIBLE_WITH_WARNINGS"
    PARTIALLY_COMPATIBLE = "PARTIALLY_COMPATIBLE"
    BLOCKED = "BLOCKED"

class CompatibilityFinding(BaseModel):
    finding_id: str
    severity: IssueSeverity
    code: str = Field(..., description="e.g. CURRENCY_MISMATCH, SCOPE_MISMATCH, DURATION_MISMATCH")
    title: str
    description: str
    affected_document_ids: List[str]
    remediation_hint: Optional[str] = None

class CompatibilityReport(BaseModel):
    is_comparable: bool = Field(..., description="False if any BLOCKER severity finding exists")
    overall_status: CompatibilityStatus = Field(default=CompatibilityStatus.COMPATIBLE)
    blocker_count: int = 0
    warning_count: int = 0
    findings: List[CompatibilityFinding] = Field(default_factory=list)
```

#### TypeScript Interface (Frontend):
```typescript
export type IssueSeverity = 'BLOCKER' | 'WARNING' | 'INFORMATION';
export type CompatibilityStatus = 'COMPATIBLE' | 'COMPATIBLE_WITH_WARNINGS' | 'PARTIALLY_COMPATIBLE' | 'BLOCKED';

export interface CompatibilityFinding {
  findingId: string;
  severity: IssueSeverity;
  code: string;
  title: string;
  description: string;
  affectedDocumentIds: string[];
  remediationHint?: string | null;
}

export interface CompatibilityReport {
  isComparable: boolean;
  overallStatus: CompatibilityStatus;
  blockerCount: number;
  warningCount: number;
  findings: CompatibilityFinding[];
}
```

---

### 2.5 EvidenceReference & Physical Coordinates

#### Purpose:
Guarantees source provenance for every extracted line item, variance, and narrative fact.

#### Pydantic Model (Python):
```python
class EvidenceReference(BaseModel):
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
```

#### TypeScript Interface (Frontend):
```typescript
export interface EvidenceReference {
  evidenceId: string;
  docId: string;
  documentName: string;
  pageNumber?: number | null;
  boundingBox?: number[] | null;
  sheetName?: string | null;
  cellRange?: string | null;
  structuralRef?: string | null;
  verbatimSnippet: string;
  tableContext?: string | null;
}
```

---

### 2.6 FinancialMetric, ValueCandidate & ConflictResolution

#### Purpose:
Tracks candidates extracted across multiple tables/footnotes, applies the 8-factor context-aware priority rules, and records the resolution explanation.

#### Pydantic Model (Python):
```python
from decimal import Decimal

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
    candidate_id: str
    doc_id: str
    metric_key: str
    raw_text_value: str
    normalized_amount: Decimal = Field(..., description="Standardized in Crore/Lakh with Decimal precision")
    unit: str = Field(default="INR_CRORE")
    statement_type: StatementType
    is_audited: bool = True
    is_restated: bool = False
    evidence: EvidenceReference

class ConflictResolution(BaseModel):
    conflict_id: str
    metric_key: str
    status: ConflictStatus
    selected_candidate: Optional[ValueCandidate] = None
    all_candidates: List[ValueCandidate]
    resolution_reason: str = Field(..., description="Human-readable explanation of priority rule applied")
    difference_absolute: Optional[Decimal] = None

class FinancialValue(BaseModel):
    doc_id: str
    metric_key: str
    label: str
    amount: Optional[Decimal] = None
    unit: str = "INR_CRORE"
    status: str = Field(default="REPORTED", description="REPORTED | NOT_DISCLOSED | UNCERTAIN")
    evidence: Optional[EvidenceReference] = None
    conflict_info: Optional[ConflictResolution] = None
```

#### TypeScript Interface (Frontend):
```typescript
export type StatementType = 
  | 'BALANCE_SHEET' 
  | 'PROFIT_AND_LOSS' 
  | 'CASH_FLOW' 
  | 'NOTES_TO_ACCOUNTS' 
  | 'MDA_NARRATIVE' 
  | 'OTHER';

export type ConflictStatus = 
  | 'NO_CONFLICT' 
  | 'RESOLVED_AUTOMATIC' 
  | 'UNCERTAIN' 
  | 'USER_RESOLVED';

export interface ValueCandidate {
  candidateId: string;
  docId: string;
  metricKey: string;
  rawTextValue: string;
  normalizedAmount: string; // Serialized Decimal string
  unit: string;
  statementType: StatementType;
  isAudited: boolean;
  isRestated: boolean;
  evidence: EvidenceReference;
}

export interface ConflictResolution {
  conflictId: string;
  metricKey: string;
  status: ConflictStatus;
  selectedCandidate?: ValueCandidate | null;
  allCandidates: ValueCandidate[];
  resolutionReason: string;
  differenceAbsolute?: string | null;
}

export interface FinancialValue {
  docId: string;
  metricKey: string;
  label: string;
  amount?: string | null;
  unit: string;
  status: 'REPORTED' | 'NOT_DISCLOSED' | 'UNCERTAIN';
  evidence?: EvidenceReference | null;
  conflictInfo?: ConflictResolution | null;
}
```

---

### 2.7 CalculationResult & Negative-Base Math Rules

#### Purpose:
Stores deterministic absolute variance and percentage changes with explicit loss-to-profit directional handling.

#### Pydantic Model (Python):
```python
class VarianceStatus(str, Enum):
    CALCULATED = "CALCULATED"
    DIV_BY_ZERO = "DIV_BY_ZERO"
    NON_POSITIVE_BASE = "NON_POSITIVE_BASE"
    NOT_DISCLOSED = "NOT_DISCLOSED"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"

class CalculationResult(BaseModel):
    metric_key: str
    label: str
    base_doc_id: str
    comparison_doc_id: str
    base_value: Optional[Decimal] = None
    comparison_value: Optional[Decimal] = None
    absolute_variance: Optional[Decimal] = None
    percentage_change: Optional[Decimal] = None
    status: VarianceStatus
    directional_explanation: Optional[str] = Field(
        default=None, 
        description="Mandatory narrative for non-positive base transitions (e.g. Loss to Profit)"
    )
```

#### TypeScript Interface (Frontend):
```typescript
export type VarianceStatus = 
  | 'CALCULATED' 
  | 'DIV_BY_ZERO' 
  | 'NON_POSITIVE_BASE' 
  | 'NOT_DISCLOSED' 
  | 'CURRENCY_MISMATCH';

export interface CalculationResult {
  metricKey: string;
  label: string;
  baseDocId: string;
  comparisonDocId: string;
  baseValue?: string | null;
  comparisonValue?: string | null;
  absoluteVariance?: string | null;
  percentageChange?: string | null;
  status: VarianceStatus;
  directionalExplanation?: string | null;
}
```

---

### 2.8 ExecutiveSummary, RiskDisclosure, AccountingDifference & Fact Classifications

#### Purpose:
Encapsulates 8 canonical comparative narrative sections, risk alerts, and policy shifts.

#### Pydantic Model (Python):
```python
class ChangeClassification(str, Enum):
    POSITIVE_IMPROVEMENT = "POSITIVE_IMPROVEMENT"
    NEGATIVE_PRESSURE = "NEGATIVE_PRESSURE"
    NEUTRAL_STRUCTURAL = "NEUTRAL_STRUCTURAL"
    UNCERTAIN = "UNCERTAIN"

class RiskDisclosure(BaseModel):
    risk_id: str
    title: str
    category: str = Field(..., description="Operational, Financial, Regulatory, Market, Governance")
    doc_id: str
    severity: str = Field(default="MEDIUM", description="HIGH, MEDIUM, LOW")
    disclosure_text: str
    evidence: EvidenceReference

class AccountingDifference(BaseModel):
    difference_id: str
    topic: str = Field(..., description="Revenue Recognition, Depreciation, Leases, Financial Instruments")
    doc_a_policy: str
    doc_b_policy: str
    impact_summary: str
    evidence_a: EvidenceReference
    evidence_b: EvidenceReference

class ExecutiveSummary(BaseModel):
    overview_story: str
    core_positive_changes: List[str] = Field(default_factory=list)
    core_negative_changes: List[str] = Field(default_factory=list)
    neutral_observations: List[str] = Field(default_factory=list)
    uncertain_findings: List[str] = Field(default_factory=list)
    critical_disclosures: List[str] = Field(default_factory=list)
```

#### TypeScript Interface (Frontend):
```typescript
export type ChangeClassification = 
  | 'POSITIVE_IMPROVEMENT' 
  | 'NEGATIVE_PRESSURE' 
  | 'NEUTRAL_STRUCTURAL' 
  | 'UNCERTAIN';

export interface RiskDisclosure {
  riskId: string;
  title: string;
  category: string;
  docId: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  disclosureText: string;
  evidence: EvidenceReference;
}

export interface AccountingDifference {
  differenceId: string;
  topic: string;
  docAPolicy: string;
  docBPolicy: string;
  impactSummary: string;
  evidenceA: EvidenceReference;
  evidenceB: EvidenceReference;
}

export interface ExecutiveSummary {
  overviewStory: string;
  corePositiveChanges: string[];
  coreNegativeChanges: string[];
  neutralObservations: string[];
  uncertainFindings: string[];
  criticalDisclosures: string[];
}
```

---

### 2.9 VerificationResult (Official Sources)

#### Purpose:
Tracks verification lookups against official regulatory registries (SEBI, NSE, BSE).

#### Pydantic Model (Python):
```python
class VerificationSourceType(str, Enum):
    SEBI_FILING = "SEBI_FILING"
    NSE_ANNOUNCEMENT = "NSE_ANNOUNCEMENT"
    BSE_ANNOUNCEMENT = "BSE_ANNOUNCEMENT"
    COMPANY_IR = "COMPANY_IR"

class VerificationStatus(str, Enum):
    VERIFIED_MATCH = "VERIFIED_MATCH"
    DISCREPANCY_DETECTED = "DISCREPANCY_DETECTED"
    REGISTRY_UNAVAILABLE = "REGISTRY_UNAVAILABLE"
    SKIPPED_LOCAL_MODE = "SKIPPED_LOCAL_MODE"

class VerificationResult(BaseModel):
    source_type: VerificationSourceType
    source_url: Optional[str] = None
    status: VerificationStatus
    verified_item: str
    details: str
    retrieved_at: Optional[datetime] = None
```

---

### 2.10 ProcessingStatus & Cancellation State

#### Purpose:
Delivers live status updates for the 9 backend stages, surviving frontend refresh and tracking cancellation.

#### Pydantic Model (Python):
```python
class PipelineStage(str, Enum):
    UPLOADING = "UPLOADING"
    EXTRACTING_TEXT_TABLES = "EXTRACTING_TEXT_TABLES"
    IDENTIFYING_METADATA = "IDENTIFYING_METADATA"
    VALIDATING_COMPATIBILITY = "VALIDATING_COMPATIBILITY"
    EXTRACTING_FINANCIAL_DATA = "EXTRACTING_FINANCIAL_DATA"
    RESOLVING_CONFLICTS = "RESOLVING_CONFLICTS"
    CALCULATING_METRICS = "CALCULATING_METRICS"
    VERIFYING_OFFICIAL_SOURCES = "VERIFYING_OFFICIAL_SOURCES"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class ProcessingStatus(BaseModel):
    session_id: str
    current_stage: PipelineStage
    completed_stages: List[PipelineStage] = Field(default_factory=list)
    stage_message: str
    is_cancelled: bool = False
    is_completed: bool = False
    error: Optional[str] = None
```

---

### 2.11 ComparisonResult, ComparisonChatMessage & ExportJob

#### Pydantic Model (Python):
```python
class ComparisonResult(BaseModel):
    session_id: str
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

class ComparisonChatMessage(BaseModel):
    message_id: str
    role: str = Field(..., description="'user' | 'assistant'")
    content: str
    cited_evidence: List[EvidenceReference] = Field(default_factory=list)
    safety_disclaimer: str = Field(
        default="This is an educational comparison grounded in the uploaded documents and does not constitute investment advice."
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ExportJob(BaseModel):
    job_id: str
    export_format: str = Field(..., description="'PDF' | 'XLSX'")
    status: str = Field(default="PENDING")
    download_url: Optional[str] = None
```
