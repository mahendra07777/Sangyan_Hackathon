"""Deterministic, explainable compatibility matrix engine for Bharat Investor Copilot Compare Documents.
Evaluates multi-document comparisons against approved financial, assurance, currency, and period rules.
"""

from __future__ import annotations

import itertools
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from ..models.comparison import (
    AuditStatus,
    CompatibilityFinding,
    CompatibilityReport,
    CompatibilityStatus,
    DocumentMetadata,
    DocumentType,
    IssueSeverity,
    PairwiseCompatibility,
    ReportingPeriodType,
    ReportingScope,
)

logger = logging.getLogger(__name__)


class CompatibilityEngine:
    """Rules-based engine that evaluates comparative soundness across uploaded filings."""

    @classmethod
    def evaluate_session(
        cls,
        metadata_map: Dict[str, DocumentMetadata],
        session_id: Optional[str] = None,
    ) -> CompatibilityReport:
        """Run the comprehensive compatibility rules matrix across all session documents."""
        doc_ids = sorted(list(metadata_map.keys()))
        if len(doc_ids) < 2:
            return CompatibilityReport(
                session_id=session_id,
                is_comparable=True,
                overall_status=CompatibilityStatus.COMPATIBLE,
                blocker_count=0,
                warning_count=0,
                findings=[],
                pairwise_matrix=[],
                compatible_subsets=[doc_ids] if doc_ids else [],
            )

        # 1. Evaluate each document individually for completeness
        global_findings: List[CompatibilityFinding] = []
        for d_id in doc_ids:
            meta = metadata_map[d_id]
            missing_fields: List[str] = []
            if meta.company_name == "Unknown":
                missing_fields.append("company_name")
            if meta.financial_year == "Unknown":
                missing_fields.append("financial_year")
            if meta.reporting_period == ReportingPeriodType.UNKNOWN.value:
                missing_fields.append("reporting_period")
            if meta.currency == "Unknown":
                missing_fields.append("currency")

            if missing_fields:
                global_findings.append(
                    CompatibilityFinding(
                        finding_id=f"incomplete_{d_id}",
                        severity=IssueSeverity.WARNING,
                        code="METADATA_INCOMPLETE",
                        title=f"Incomplete Metadata for Document {d_id}",
                        description=(
                            f"Document '{d_id}' has unidentified or uncertain metadata fields: {', '.join(missing_fields)}. "
                            "Partial comparison is permitted where safe, but user review is recommended."
                        ),
                        affected_document_ids=[d_id],
                        relevant_fields=missing_fields,
                        observed_values={f: getattr(meta, f, "Unknown") for f in missing_fields},
                        remediation_hint="Review and verify identified metadata on the Metadata Review step to confirm missing details.",
                        can_user_override_resolve=True,
                    )
                )

        # 2. Evaluate all pairwise combinations
        pairwise_matrix: List[PairwiseCompatibility] = []
        all_pair_findings: List[CompatibilityFinding] = []
        blocked_pairs: Set[Tuple[str, str]] = set()

        for doc_a_id, doc_b_id in itertools.combinations(doc_ids, 2):
            meta_a = metadata_map[doc_a_id]
            meta_b = metadata_map[doc_b_id]

            pair_findings = cls._evaluate_pair(doc_a_id, meta_a, doc_b_id, meta_b)
            blockers = [f for f in pair_findings if f.severity == IssueSeverity.BLOCKER]
            warnings = [f for f in pair_findings if f.severity == IssueSeverity.WARNING]

            is_pair_comp = len(blockers) == 0
            if not is_pair_comp:
                blocked_pairs.add((doc_a_id, doc_b_id))
                blocked_pairs.add((doc_b_id, doc_a_id))

            if len(blockers) > 0:
                pair_status = CompatibilityStatus.BLOCKED
            elif len(warnings) > 0:
                pair_status = CompatibilityStatus.COMPATIBLE_WITH_WARNINGS
            else:
                pair_status = CompatibilityStatus.COMPATIBLE

            pairwise_matrix.append(
                PairwiseCompatibility(
                    doc_a_id=doc_a_id,
                    doc_b_id=doc_b_id,
                    is_comparable=is_pair_comp,
                    status=pair_status,
                    blocker_count=len(blockers),
                    warning_count=len(warnings),
                    findings=pair_findings,
                )
            )
            all_pair_findings.extend(pair_findings)

        # Deduplicate findings by code and affected documents
        unique_findings: List[CompatibilityFinding] = list(global_findings)
        seen_keys: Set[str] = {f"{f.code}_{'-'.join(sorted(f.affected_document_ids))}" for f in global_findings}

        for f in all_pair_findings:
            key = f"{f.code}_{'-'.join(sorted(f.affected_document_ids))}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_findings.append(f)

        total_blockers = sum(1 for f in unique_findings if f.severity == IssueSeverity.BLOCKER)
        total_warnings = sum(1 for f in unique_findings if f.severity == IssueSeverity.WARNING)

        # 3. Compute compatible subsets (cliques/subsets without blockers)
        compatible_subsets = cls._compute_compatible_subsets(doc_ids, blocked_pairs)

        # 4. Overall status determination
        if total_blockers == 0:
            if total_warnings == 0:
                overall_status = CompatibilityStatus.COMPATIBLE
            else:
                overall_status = CompatibilityStatus.COMPATIBLE_WITH_WARNINGS
            is_comparable = True
        else:
            # Check if any partial compatible subset of size >= 2 exists
            if any(len(subset) >= 2 for subset in compatible_subsets):
                overall_status = CompatibilityStatus.PARTIALLY_COMPATIBLE
                is_comparable = False
            else:
                overall_status = CompatibilityStatus.BLOCKED
                is_comparable = False

        return CompatibilityReport(
            session_id=session_id,
            is_comparable=is_comparable,
            overall_status=overall_status,
            blocker_count=total_blockers,
            warning_count=total_warnings,
            findings=unique_findings,
            pairwise_matrix=pairwise_matrix,
            compatible_subsets=compatible_subsets,
        )

    # -----------------------------------------------------------------------
    # Pairwise Rules Evaluation
    # -----------------------------------------------------------------------

    @classmethod
    def _evaluate_pair(
        cls,
        id_a: str,
        meta_a: DocumentMetadata,
        id_b: str,
        meta_b: DocumentMetadata,
    ) -> List[CompatibilityFinding]:
        """Evaluate two documents against the approved financial comparison rules."""
        findings: List[CompatibilityFinding] = []
        pair_ids = [id_a, id_b]

        # 1. Currency Mismatch Rule (BLOCKER)
        if meta_a.currency != "Unknown" and meta_b.currency != "Unknown" and meta_a.currency != meta_b.currency:
            findings.append(
                CompatibilityFinding(
                    finding_id=f"curr_mismatch_{id_a}_{id_b}",
                    severity=IssueSeverity.BLOCKER,
                    code="CURRENCY_MISMATCH",
                    title="Currency Mismatch Between Documents",
                    description=(
                        f"Direct numerical comparison between {id_a} ({meta_a.currency}) and "
                        f"{id_b} ({meta_b.currency}) is blocked. Silent currency conversion is prohibited."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["currency"],
                    observed_values={id_a: meta_a.currency, id_b: meta_b.currency},
                    remediation_hint="Ensure both documents are reported in matching currencies or override currency with manual conversion.",
                    can_user_override_resolve=True,
                )
            )

        # 2. Incompatible Document Types (BLOCKER)
        incompatible_combos = {
            (DocumentType.INVESTOR_PRESENTATION.value, DocumentType.IPO_PROSPECTUS.value),
            (DocumentType.IPO_PROSPECTUS.value, DocumentType.INVESTOR_PRESENTATION.value),
        }
        if (meta_a.document_type, meta_b.document_type) in incompatible_combos:
            findings.append(
                CompatibilityFinding(
                    finding_id=f"doctype_incompatible_{id_a}_{id_b}",
                    severity=IssueSeverity.BLOCKER,
                    code="INCOMPATIBLE_DOCUMENT_TYPE",
                    title="Incompatible Document Types",
                    description=(
                        f"Direct comparative analysis between '{meta_a.document_type}' ({id_a}) and "
                        f"'{meta_b.document_type}' ({id_b}) is blocked because their financial disclosures follow non-comparable structures."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["document_type"],
                    observed_values={id_a: meta_a.document_type, id_b: meta_b.document_type},
                    remediation_hint="Upload audited financial statements, annual reports, or quarterly results for comparative analysis.",
                    can_user_override_resolve=False,
                )
            )

        # 3. Reporting Period Duration Mismatch (WARNING)
        # e.g. Annual Report vs Quarterly Results
        period_a = meta_a.reporting_period
        period_b = meta_b.reporting_period
        if period_a != "Unknown" and period_b != "Unknown" and period_a != period_b:
            findings.append(
                CompatibilityFinding(
                    finding_id=f"period_duration_{id_a}_{id_b}",
                    severity=IssueSeverity.WARNING,
                    code="PERIOD_DURATION_MISMATCH",
                    title="Differing Reporting Period Durations",
                    description=(
                        f"Document {id_a} covers '{period_a}' while Document {id_b} covers '{period_b}'. "
                        "Comparing full-year cumulative metrics against quarterly results can lead to misleading growth calculations."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["reporting_period", "quarter"],
                    observed_values={id_a: period_a, id_b: period_b},
                    remediation_hint="Annualize figures or select matching period slices (e.g. Q3 vs Q3) for direct variance calculations.",
                    can_user_override_resolve=True,
                )
            )

        # 3b. Quarter Discrepancy Rule
        q_a = getattr(meta_a, "quarter", None)
        q_b = getattr(meta_b, "quarter", None)
        if q_a and q_b and q_a != q_b:
            q_num_a = int(q_a.replace("Q", "")) if q_a.startswith("Q") and q_a[1:].isdigit() else None
            q_num_b = int(q_b.replace("Q", "")) if q_b.startswith("Q") and q_b[1:].isdigit() else None
            if q_num_a is not None and q_num_b is not None and abs(q_num_a - q_num_b) > 1:
                findings.append(
                    CompatibilityFinding(
                        finding_id=f"quarter_mismatch_{id_a}_{id_b}",
                        severity=IssueSeverity.WARNING,
                        code="QUARTER_MISMATCH",
                        title="Seasonal Quarter Discrepancy",
                        description=(
                            f"Document {id_a} covers '{q_a}' while Document {id_b} covers '{q_b}'. "
                            "Comparing non-adjacent quarters introduces seasonal demand variations (e.g. festive retail in Q3 vs monsoon in Q1). "
                            "Year-over-Year same-quarter comparisons (e.g. Q3 vs Q3) are recommended."
                        ),
                        affected_document_ids=pair_ids,
                        relevant_fields=["quarter"],
                        observed_values={id_a: q_a, id_b: q_b},
                        remediation_hint="Select matching quarters for direct operational performance analysis.",
                        can_user_override_resolve=True,
                    )
                )
            elif q_num_a is not None and q_num_b is not None:
                findings.append(
                    CompatibilityFinding(
                        finding_id=f"quarter_seq_{id_a}_{id_b}",
                        severity=IssueSeverity.INFORMATION,
                        code="SEQUENTIAL_QUARTER_COMPARISON",
                        title=f"Sequential Quarter-over-Quarter Comparison ({q_a} vs {q_b})",
                        description=(
                            f"Sequential Quarter-over-Quarter (QoQ) comparison between Document {id_a} ({q_a}) and Document {id_b} ({q_b}). "
                            "Observe short-term operational momentum while accounting for sequential seasonality."
                        ),
                        affected_document_ids=pair_ids,
                        relevant_fields=["quarter"],
                        observed_values={id_a: q_a, id_b: q_b},
                        remediation_hint="Compare with YoY same-quarter data to distinguish cyclical trends from structural growth.",
                        can_user_override_resolve=False,
                    )
                )

        # 3c. Multi-Year Gap Rule (WARNING)
        fy_a = getattr(meta_a, "financial_year", "Unknown")
        fy_b = getattr(meta_b, "financial_year", "Unknown")
        if fy_a != "Unknown" and fy_b != "Unknown":
            def _extract_fy_year(fy_s: str) -> Optional[int]:
                m = re.search(r"\b20(\d{2})\b", fy_s)
                return int("20" + m.group(1)) if m else None

            y_a = _extract_fy_year(fy_a)
            y_b = _extract_fy_year(fy_b)
            if y_a is not None and y_b is not None:
                gap = abs(y_a - y_b)
                if gap > 1:
                    findings.append(
                        CompatibilityFinding(
                            finding_id=f"year_gap_{id_a}_{id_b}",
                            severity=IssueSeverity.WARNING,
                            code="YEAR_GAP_WARNING",
                            title=f"Multi-Year Temporal Distance ({gap}-Year Gap)",
                            description=(
                                f"Document {id_a} ({fy_a}) and Document {id_b} ({fy_b}) have a {gap}-year temporal distance. "
                                "Multi-year comparisons may be significantly affected by changes in corporate structure, acquisitions, divestments, "
                                "or accounting restatements across intervening years."
                            ),
                            affected_document_ids=pair_ids,
                            relevant_fields=["financial_year"],
                            observed_values={id_a: fy_a, id_b: fy_b},
                            remediation_hint="Evaluate intervening annual reports to understand structural business evolution.",
                            can_user_override_resolve=False,
                        )
                    )

        # 4. Scope Mismatch: Consolidated vs Standalone (WARNING / INFORMATION)
        scope_a = meta_a.reporting_scope
        scope_b = meta_b.reporting_scope
        scope_a_str = scope_a.value if hasattr(scope_a, "value") else str(scope_a)
        scope_b_str = scope_b.value if hasattr(scope_b, "value") else str(scope_b)
        if (scope_a_str == "BOTH" and scope_b_str in ("CONSOLIDATED", "STANDALONE")) or \
           (scope_b_str == "BOTH" and scope_a_str in ("CONSOLIDATED", "STANDALONE")):
            both_id = id_a if scope_a_str == "BOTH" else id_b
            single_id = id_b if scope_a_str == "BOTH" else id_a
            target_scope = scope_b_str if scope_a_str == "BOTH" else scope_a_str
            findings.append(
                CompatibilityFinding(
                    finding_id=f"scope_dual_{id_a}_{id_b}",
                    severity=IssueSeverity.INFORMATION,
                    code="DUAL_SCOPE_ALIGNMENT",
                    title=f"Multi-Scope Alignment with {target_scope}",
                    description=(
                        f"Document '{both_id}' contains both Consolidated and Standalone disclosures. "
                        f"Comparison automatically aligns with Document '{single_id}' on its {target_scope} perimeter."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["reporting_scope"],
                    observed_values={id_a: scope_a_str, id_b: scope_b_str},
                    remediation_hint=f"Verify that {target_scope} tables in '{both_id}' are referenced during analysis.",
                    can_user_override_resolve=False,
                )
            )
        elif scope_a_str not in ("UNKNOWN", "BOTH") and \
             scope_b_str not in ("UNKNOWN", "BOTH") and \
             scope_a_str != scope_b_str:
            findings.append(
                CompatibilityFinding(
                    finding_id=f"scope_mismatch_{id_a}_{id_b}",
                    severity=IssueSeverity.WARNING,
                    code="SCOPE_MISMATCH",
                    title="Reporting Scope Mismatch (Consolidated vs Standalone)",
                    description=(
                        f"Document {id_a} reports {scope_a_str} figures whereas Document {id_b} reports {scope_b_str} figures. "
                        "Neither reporting scope is ranked above the other; figures represent different institutional perimeters."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["reporting_scope"],
                    observed_values={id_a: scope_a_str, id_b: scope_b_str},
                    remediation_hint="Review company group perimeter or verify if matching standalone/consolidated tables exist in both documents.",
                    can_user_override_resolve=True,
                )
            )

        # 5. Assurance / Audit Status Mismatch (WARNING)
        audit_a = meta_a.audit_status
        audit_b = meta_b.audit_status
        audit_a_str = audit_a.value if hasattr(audit_a, "value") else str(audit_a)
        audit_b_str = audit_b.value if hasattr(audit_b, "value") else str(audit_b)
        if audit_a_str != "UNKNOWN" and audit_b_str != "UNKNOWN" and audit_a_str != audit_b_str:
            findings.append(
                CompatibilityFinding(
                    finding_id=f"audit_mismatch_{id_a}_{id_b}",
                    severity=IssueSeverity.WARNING,
                    code="ASSURANCE_MISMATCH",
                    title="Assurance Level Discrepancy",
                    description=(
                        f"Document {id_a} assurance is '{audit_a_str}' whereas Document {id_b} is '{audit_b_str}'. "
                        "Limited review figures are subject to narrower review procedures than full statutory audits."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["audit_status"],
                    observed_values={id_a: audit_a_str, id_b: audit_b_str},
                    remediation_hint="Treat unaudited or limited review variances as provisional until reconciled in annual audited accounts.",
                    can_user_override_resolve=True,
                )
            )

        # 6. Accounting Standard Mismatch (WARNING)
        std_a = meta_a.accounting_standard
        std_b = meta_b.accounting_standard
        if std_a != "Unknown" and std_b != "Unknown" and std_a != std_b:
            findings.append(
                CompatibilityFinding(
                    finding_id=f"acct_mismatch_{id_a}_{id_b}",
                    severity=IssueSeverity.WARNING,
                    code="ACCOUNTING_STANDARD_MISMATCH",
                    title="Accounting Standards Divergence",
                    description=(
                        f"Document {id_a} follows {std_a} while Document {id_b} follows {std_b}. "
                        "Accounting differences in lease capitalization, revenue recognition, or goodwill amortisation may affect line items."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["accounting_standard"],
                    observed_values={id_a: std_a, id_b: std_b},
                    remediation_hint="Consult the accounting policy reconciliation note for normalized comparisons.",
                    can_user_override_resolve=True,
                )
            )

        # 7. IPO Prospectus Stages (WARNING)
        # e.g. DRHP vs RHP vs Prospectus
        type_a = meta_a.document_type
        type_b = meta_b.document_type
        prospectus_types = {
            DocumentType.DRAFT_RED_HERRING_PROSPECTUS.value,
            DocumentType.RED_HERRING_PROSPECTUS.value,
            DocumentType.IPO_PROSPECTUS.value,
        }
        if type_a in prospectus_types and type_b in prospectus_types and type_a != type_b:
            findings.append(
                CompatibilityFinding(
                    finding_id=f"prospectus_stage_{id_a}_{id_b}",
                    severity=IssueSeverity.WARNING,
                    code="PROSPECTUS_VERSION_DIFFERENCE",
                    title="IPO Prospectus Stage Discrepancy",
                    description=(
                        f"Document {id_a} is a '{type_a}' whereas Document {id_b} is a '{type_b}'. "
                        "DRHP figures represent preliminary disclosures prior to SEBI review comments and price band finalization."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["document_type"],
                    observed_values={id_a: type_a, id_b: type_b},
                    remediation_hint="Review offer price band and final object allocations in the final prospectus.",
                    can_user_override_resolve=False,
                )
            )

        # 7b. Numerical Scale Difference (WARNING)
        scale_a = (getattr(meta_a, "reporting_scale", "CRORE") or "CRORE").upper()
        scale_b = (getattr(meta_b, "reporting_scale", "CRORE") or "CRORE").upper()
        if scale_a not in ("UNKNOWN", "UNITS") and scale_b not in ("UNKNOWN", "UNITS") and scale_a != scale_b:
            findings.append(
                CompatibilityFinding(
                    finding_id=f"scale_diff_{id_a}_{id_b}",
                    severity=IssueSeverity.WARNING,
                    code="SCALE_DIFFERENCE",
                    title="Reporting Scale Discrepancy",
                    description=(
                        f"Document {id_a} is reported in '{scale_a}' whereas Document {id_b} is reported in '{scale_b}'. "
                        "Figures are automatically normalized to Crores (e.g. 100 Lakhs = 1 Crore, 10 Million = 1 Crore) "
                        "for mathematical calculations, but original reported display units differ."
                    ),
                    affected_document_ids=pair_ids,
                    relevant_fields=["reporting_scale"],
                    observed_values={id_a: scale_a, id_b: scale_b},
                    remediation_hint="Review normalized calculations; variances reflect standardized Crore values.",
                    can_user_override_resolve=True,
                )
            )

        # 8. Same Company vs Cross-Company Identification (INFORMATION / WARNING)
        comp_a = meta_a.company_name
        comp_b = meta_b.company_name
        if comp_a != "Unknown" and comp_b != "Unknown":
            if comp_a.strip().lower() != comp_b.strip().lower():
                ind_a = (getattr(meta_a, "industry", None) or "UNKNOWN").strip()
                ind_b = (getattr(meta_b, "industry", None) or "UNKNOWN").strip()

                if ind_a.upper() != "UNKNOWN" and ind_b.upper() != "UNKNOWN" and ind_a.upper() == ind_b.upper():
                    findings.append(
                        CompatibilityFinding(
                            finding_id=f"peer_compare_{id_a}_{id_b}",
                            severity=IssueSeverity.INFORMATION,
                            code="SAME_INDUSTRY_PEER_COMPARISON",
                            title=f"Same-Industry Peer Comparison ({ind_a})",
                            description=(
                                f"Peer comparison between '{comp_a}' and '{comp_b}' operating in the same industry ('{ind_a}'). "
                                "While operational metrics are directly comparable, note differences in business model, product mix, and geographic concentration."
                            ),
                            affected_document_ids=pair_ids,
                            relevant_fields=["company_name", "industry"],
                            observed_values={id_a: f"{comp_a} ({ind_a})", id_b: f"{comp_b} ({ind_b})"},
                            remediation_hint="Compare relative margin and efficiency metrics rather than unscaled absolute amounts.",
                            can_user_override_resolve=False,
                        )
                    )
                else:
                    # Industry is UNKNOWN or disparate -> Return cross-company comparison with explicit limitations
                    ind_display_a = ind_a if ind_a.upper() != "UNKNOWN" else "UNKNOWN"
                    ind_display_b = ind_b if ind_b.upper() != "UNKNOWN" else "UNKNOWN"
                    findings.append(
                        CompatibilityFinding(
                            finding_id=f"cross_company_{id_a}_{id_b}",
                            severity=IssueSeverity.WARNING,
                            code="CROSS_COMPANY_COMPARISON",
                            title="Cross-Company Comparison (Industry Unverified)",
                            description=(
                                f"Cross-company comparison between '{comp_a}' and '{comp_b}'. "
                                f"Industry classification is unverified or disparate (Doc {id_a}: {ind_display_a}, Doc {id_b}: {ind_display_b}). "
                                "Cross-industry comparisons carry severe limitations: operating margins, capital intensity, working capital cycles, "
                                "and accounting ratios differ intrinsically across non-peer sectors and should not be compared directly."
                            ),
                            affected_document_ids=pair_ids,
                            relevant_fields=["company_name", "industry"],
                            observed_values={id_a: f"{comp_a} (Industry: {ind_display_a})", id_b: f"{comp_b} (Industry: {ind_display_b})"},
                            remediation_hint="Verify industry parity or set verified industry via metadata overrides before drawing comparative valuation conclusions.",
                            can_user_override_resolve=True,
                        )
                    )

        return findings

    @classmethod
    def _compute_compatible_subsets(
        cls,
        doc_ids: List[str],
        blocked_pairs: Set[Tuple[str, str]],
    ) -> List[List[str]]:
        """Identify compatible subsets of documents that share zero blockers."""
        if not blocked_pairs:
            return [doc_ids]

        # Greedy maximal clique search for compatible subsets
        subsets: List[List[str]] = []
        for r in range(len(doc_ids), 1, -1):
            for candidate in itertools.combinations(doc_ids, r):
                candidate_list = list(candidate)
                # Check if every pair in candidate_list is unblocked
                is_valid = True
                for a, b in itertools.combinations(candidate_list, 2):
                    if (a, b) in blocked_pairs or (b, a) in blocked_pairs:
                        is_valid = False
                        break
                if is_valid:
                    # Check if already a subset of an existing recorded subset
                    if not any(set(candidate_list).issubset(set(s)) for s in subsets):
                        subsets.append(candidate_list)

        return subsets
