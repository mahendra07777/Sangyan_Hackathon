"""Explainable Context-Aware Conflict Arbitration Engine for Compare Documents.

Applies the approved 8-Factor Context-Aware Priority Matrix:
1. Reporting Entity / Scope Alignment (Consolidated vs Standalone; never universally ranked).
2. Reporting Period Alignment (Current period disclosure > Prior period comparative column).
3. Audit Status Authority (Audited > Limited Review > Unaudited > Provisional > Unknown).
4. Restatement Supersession (Explains restated comparative columns).
5. Metric Definition Precedence (Statutory line item > Custom definitions).
6. Statement Tier Authority (Primary Statements > Notes to Accounts > MD&A Narrative).
7. Evidence Format Quality (Digital table cell > Text snippet).
8. Ambiguity & UNCERTAIN Rule (Equal-authority conflicts marked UNCERTAIN; zero LLM guesswork).
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from ..models.comparison import (
    AuditStatus,
    ConflictResolution,
    ConflictStatus,
    DocumentMetadata,
    FinancialValue,
    ReportingPeriodType,
    ReportingScope,
    StatementType,
    ValueCandidate,
)
from .financial_extractor import METRIC_REGISTRY
from .financial_normalizer import FinancialNormalizer


class ConflictArbitrator:
    """Arbitrates conflicting financial metric candidates using explainable contextual rules."""

    @classmethod
    def _normalize_fy_token(cls, fy_str: Optional[str]) -> Optional[str]:
        """Standardize various financial year representations to canonical 'FY YYYY-YY' format."""
        if not fy_str:
            return None
        clean = fy_str.strip().upper()
        if clean in ("UNKNOWN", "NONE", ""):
            return None
        m = re.search(r"(?:FY\s*)?(\d{4})[-\/](\d{2,4})", clean)
        if m:
            start_y = int(m.group(1))
            end_raw = m.group(2)
            end_y = int(end_raw) if len(end_raw) == 4 else (start_y // 100 * 100 + int(end_raw))
            return f"FY {start_y}-{str(end_y)[-2:]}"
        m_single = re.search(r"FY\s*(\d{2,4})", clean)
        if m_single:
            val = int(m_single.group(1))
            end_y = (2000 + val) if val < 100 else val
            start_y = end_y - 1
            return f"FY {start_y}-{str(end_y)[-2:]}"
        return clean

    @classmethod
    def _is_period_affirmatively_matched(
        cls,
        cand: ValueCandidate,
        metadata: DocumentMetadata,
    ) -> bool:
        """Affirmatively determine if candidate period strictly matches target document period.

        Zero guesswork: missing metadata on either side is never treated as a match.
        Both financial year and reporting granularity (annual vs quarter) must be verified.
        """
        # 1. Reject invalid or missing metadata financial year
        meta_fy = (metadata.financial_year or "").strip()
        if not meta_fy or meta_fy.lower() in ("unknown", "none"):
            return False

        # 2. Reject invalid or missing candidate financial year
        cand_fy = (cand.financial_year or "").strip()
        if not cand_fy or cand_fy.lower() in ("unknown", "none"):
            return False

        # 3. Standardize and compare financial years
        norm_meta_fy = cls._normalize_fy_token(meta_fy)
        norm_cand_fy = cls._normalize_fy_token(cand_fy)
        if not norm_meta_fy or not norm_cand_fy or norm_meta_fy != norm_cand_fy:
            return False

        # 4. Evaluate Reporting Granularity (Annual vs Quarterly vs Interim)
        meta_period = (metadata.reporting_period or "").strip().lower()
        meta_quarter = (metadata.quarter or "").strip().upper() if metadata.quarter else None
        cand_quarter = (cand.quarter or "").strip().upper() if cand.quarter else None

        # Case 1: Target metadata is Quarterly
        if meta_quarter in ("Q1", "Q2", "Q3", "Q4") or meta_period == "quarterly":
            if not cand_quarter or not meta_quarter or cand_quarter != meta_quarter:
                return False
            return True

        # Case 2: Target metadata is Annual / Full Year
        if meta_period in ("annual", "full year") or (meta_quarter is None and meta_period != "quarterly"):
            if cand_quarter in ("Q1", "Q2", "Q3", "Q4"):
                return False
            if getattr(cand, "period_duration", None) in ("3M", "6M", "9M"):
                return False
            return True

        # Case 3: Target metadata is Half-Yearly or Nine-Months
        if meta_period in ("half-yearly", "nine-month"):
            cand_dur = getattr(cand, "period_duration", None)
            expected_dur = "6M" if meta_period == "half-yearly" else "9M"
            return cand_dur == expected_dur

        return False

    @classmethod
    def arbitrate_document_metrics(
        cls,
        doc_id: str,
        candidates: List[ValueCandidate],
        metadata: DocumentMetadata,
    ) -> Tuple[Dict[str, FinancialValue], Dict[str, ConflictResolution]]:
        """Arbitrate all metric candidates for a single document.
        
        Returns:
            financial_values: metric_key -> FinancialValue
            conflicts: metric_key -> ConflictResolution
        """
        financial_values: Dict[str, FinancialValue] = {}
        conflicts: Dict[str, ConflictResolution] = {}

        # Group candidates by metric_key
        grouped: Dict[str, List[ValueCandidate]] = {}
        for c in candidates:
            grouped.setdefault(c.metric_key, []).append(c)

        # Process each registered metric
        for metric in METRIC_REGISTRY:
            m_key = metric["key"]
            m_label = metric["label"]
            m_candidates = grouped.get(m_key, [])

            # Case 1: Metric not disclosed in document
            if not m_candidates:
                financial_values[m_key] = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key,
                    label=m_label,
                    amount=None,
                    display_amount="Not Disclosed",
                    unit="INR_CRORE",
                    currency=metadata.currency or "INR",
                    status="NOT_DISCLOSED",
                    reporting_scope=metadata.reporting_scope,
                    evidence=None,
                    selected_candidate_id=None,
                    conflict_info=None,
                    fact_classification="DOCUMENT_FACT",
                )
                continue

            # Case 2: Exactly one candidate extracted
            if len(m_candidates) == 1:
                cand = m_candidates[0]
                is_period_verified = cls._is_period_affirmatively_matched(cand, metadata)

                if is_period_verified and cand.parsed_number is not None:
                    # Affirmative current-period match with valid numeric figure
                    conf = ConflictResolution(
                        conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                        metric_key=m_key,
                        status=ConflictStatus.NO_CONFLICT,
                        selected_candidate=cand,
                        all_candidates=m_candidates,
                        resolution_reason=f"Single authoritative disclosure identified in {cand.statement_type}.",
                        difference_absolute=Decimal("0.0000"),
                    )
                    conflicts[m_key] = conf

                    disp_amt = FinancialNormalizer.format_display_amount(cand.normalized_amount, cand.normalized_unit)
                    financial_values[m_key] = FinancialValue(
                        doc_id=doc_id,
                        metric_key=m_key,
                        label=m_label,
                        amount=cand.normalized_amount,
                        reported_amount=cand.parsed_number,
                        display_amount=disp_amt,
                        unit=cand.normalized_unit,
                        currency=cand.normalized_currency,
                        reported_currency=cand.original_currency,
                        reported_scale=cand.original_scale,
                        status="REPORTED",
                        reporting_scope=cand.reporting_scope,
                        evidence=cand.evidence,
                        selected_candidate_id=cand.candidate_id,
                        conflict_info=conf,
                        fact_classification="DOCUMENT_FACT",
                    )
                else:
                    # Period unverified or non-numeric: Preserve candidate and evidence, but mark UNCERTAIN
                    is_numeric = cand.parsed_number is not None
                    disp_amt = "Uncertain (Unverified Period)" if is_numeric else "Not Disclosed"
                    c_status = ConflictStatus.UNCERTAIN if is_numeric else ConflictStatus.NO_CONFLICT
                    fv_status = "UNCERTAIN" if is_numeric else "NOT_DISCLOSED"
                    fact_class = "UNCERTAIN" if is_numeric else "DOCUMENT_FACT"

                    conf = ConflictResolution(
                        conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                        metric_key=m_key,
                        status=c_status,
                        selected_candidate=None,
                        all_candidates=m_candidates,
                        resolution_reason=(
                            f"Single candidate identified in {cand.statement_type}, but reporting period cannot be affirmatively verified against target filing metadata. Marked UNCERTAIN without automated guesswork."
                            if is_numeric
                            else f"Single disclosure identified as non-numeric/missing ('{cand.raw_text_value}'); retained as missing."
                        ),
                        difference_absolute=Decimal("0.0000"),
                    )
                    conflicts[m_key] = conf
                    financial_values[m_key] = FinancialValue(
                        doc_id=doc_id,
                        metric_key=m_key,
                        label=m_label,
                        amount=None,
                        reported_amount=cand.parsed_number,
                        display_amount=disp_amt,
                        unit=cand.normalized_unit,
                        currency=cand.normalized_currency,
                        reported_currency=cand.original_currency,
                        reported_scale=cand.original_scale,
                        status=fv_status,
                        reporting_scope=cand.reporting_scope,
                        evidence=cand.evidence,
                        selected_candidate_id=None,
                        conflict_info=conf,
                        fact_classification=fact_class,
                    )
                continue

            # Check for conflicting metric definitions (e.g. EBITDA before vs after Ind AS 116)
            explicit_definitions = {c.metric_definition for c in m_candidates if c.metric_definition}
            if len(explicit_definitions) > 1:
                # Conflicting metric definitions cannot be automatically merged
                valid_amounts = [c.normalized_amount for c in m_candidates if c.normalized_amount is not None]
                max_diff = max(valid_amounts) - min(valid_amounts) if valid_amounts else Decimal("0.0000")
                conf = ConflictResolution(
                    conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                    metric_key=m_key,
                    status=ConflictStatus.UNCERTAIN,
                    selected_candidate=None,
                    all_candidates=m_candidates,
                    resolution_reason=(
                        f"Conflicting metric definitions / accounting treatments disclosed across candidates: "
                        f"{', '.join(sorted(str(d) for d in explicit_definitions))}. "
                        "Marked UNCERTAIN without automated guesswork."
                    ),
                    difference_absolute=max_diff,
                    remaining_warnings=["Conflicting accounting treatments identified; user review required."],
                )
                conflicts[m_key] = conf
                financial_values[m_key] = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key,
                    label=m_label,
                    amount=None,
                    reported_amount=None,
                    display_amount="Uncertain (Conflicting Metric Definitions)",
                    unit=m_candidates[0].normalized_unit,
                    currency=m_candidates[0].normalized_currency,
                    reported_currency=m_candidates[0].original_currency,
                    reported_scale=m_candidates[0].original_scale,
                    status="UNCERTAIN",
                    reporting_scope=metadata.reporting_scope,
                    evidence=m_candidates[0].evidence,
                    selected_candidate_id=None,
                    conflict_info=conf,
                    fact_classification="UNCERTAIN",
                )
                continue

            # Case 3: Multiple candidates extracted -> Evaluate agreement and apply 8-factor arbitration
            # Check if all candidates have identical normalized amount
            distinct_amounts = {c.normalized_amount for c in m_candidates if c.normalized_amount is not None}

            if len(distinct_amounts) <= 1:
                # Verify that at least one candidate has an affirmatively verified reporting period
                period_matched_cands = [c for c in m_candidates if cls._is_period_affirmatively_matched(c, metadata)]

                if period_matched_cands:
                    # Candidates agree on amount and period is verified -> Select highest tier disclosure
                    ranked = sorted(period_matched_cands, key=lambda c: cls._score_candidate(c, metadata), reverse=True)
                    best_cand = ranked[0]
                    conf = ConflictResolution(
                        conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                        metric_key=m_key,
                        status=ConflictStatus.NO_CONFLICT,
                        selected_candidate=best_cand if best_cand.parsed_number is not None else None,
                        all_candidates=m_candidates,
                        resolution_reason=(
                            f"Multiple disclosures ({len(m_candidates)}) agree on identical amount ({best_cand.normalized_amount}) with verified reporting period."
                            if best_cand.parsed_number is not None
                            else f"Multiple disclosures ({len(m_candidates)}) all reported as non-numeric/missing."
                        ),
                        difference_absolute=Decimal("0.0000"),
                    )
                    conflicts[m_key] = conf
                    disp_amt = FinancialNormalizer.format_display_amount(best_cand.normalized_amount, best_cand.normalized_unit)
                    fv_status = "REPORTED" if best_cand.parsed_number is not None else "NOT_DISCLOSED"
                    financial_values[m_key] = FinancialValue(
                        doc_id=doc_id,
                        metric_key=m_key,
                        label=m_label,
                        amount=best_cand.normalized_amount,
                        reported_amount=best_cand.parsed_number,
                        display_amount=disp_amt,
                        unit=best_cand.normalized_unit,
                        currency=best_cand.normalized_currency,
                        reported_currency=best_cand.original_currency,
                        reported_scale=best_cand.original_scale,
                        status=fv_status,
                        reporting_scope=best_cand.reporting_scope,
                        evidence=best_cand.evidence,
                        selected_candidate_id=best_cand.candidate_id if best_cand.parsed_number is not None else None,
                        conflict_info=conf,
                        fact_classification="DOCUMENT_FACT",
                    )
                else:
                    # Disclosures agree on amount, but NONE have an affirmatively verified period
                    best_cand = m_candidates[0]
                    conf = ConflictResolution(
                        conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                        metric_key=m_key,
                        status=ConflictStatus.UNCERTAIN,
                        selected_candidate=None,
                        all_candidates=m_candidates,
                        resolution_reason=(
                            f"Multiple disclosures ({len(m_candidates)}) agree on identical amount ({best_cand.normalized_amount}), but no candidate has an affirmatively verified reporting period matching target filing."
                        ),
                        difference_absolute=Decimal("0.0000"),
                    )
                    conflicts[m_key] = conf
                    financial_values[m_key] = FinancialValue(
                        doc_id=doc_id,
                        metric_key=m_key,
                        label=m_label,
                        amount=None,
                        reported_amount=best_cand.parsed_number,
                        display_amount="Uncertain (Unverified Period)",
                        unit=best_cand.normalized_unit,
                        currency=best_cand.normalized_currency,
                        reported_currency=best_cand.original_currency,
                        reported_scale=best_cand.original_scale,
                        status="UNCERTAIN",
                        reporting_scope=metadata.reporting_scope,
                        evidence=best_cand.evidence,
                        selected_candidate_id=None,
                        conflict_info=conf,
                        fact_classification="UNCERTAIN",
                    )
                continue

            # Case 4: Conflicting amounts -> Apply 8-Factor Context-Aware Priority Matrix
            scored_candidates = [
                (cls._score_candidate(c, metadata), c) for c in m_candidates
            ]
            scored_candidates.sort(key=lambda sc: sc[0], reverse=True)

            top_score, top_cand = scored_candidates[0]
            second_score, second_cand = scored_candidates[1]

            # Compute maximum variance between candidates
            valid_amounts = [c.normalized_amount for c in m_candidates if c.normalized_amount is not None]
            max_diff = max(valid_amounts) - min(valid_amounts) if valid_amounts else Decimal("0.0000")

            is_top_period_verified = cls._is_period_affirmatively_matched(top_cand, metadata)

            if not is_top_period_verified:
                # Essential Period Identity Gate: An unverified period candidate can NEVER become DOCUMENT_FACT through scoring
                any_period_verified = any(cls._is_period_affirmatively_matched(c, metadata) for c in m_candidates)
                if any_period_verified:
                    disp_reason = f"Top-scoring candidate '{top_cand.candidate_id}' lacks verified period match, while lower-scoring candidate has verified period. Flagged UNCERTAIN without automated guesswork."
                    disp_text = "Uncertain (Period Identity Conflict)"
                else:
                    disp_reason = "No candidate has an affirmatively verified reporting period matching target filing. Flagged UNCERTAIN without automated guesswork."
                    disp_text = "Uncertain (Unverified Period)"

                conf = ConflictResolution(
                    conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                    metric_key=m_key,
                    status=ConflictStatus.UNCERTAIN,
                    selected_candidate=None,
                    all_candidates=m_candidates,
                    resolution_reason=disp_reason,
                    difference_absolute=max_diff,
                    remaining_warnings=["Unverified reporting period precludes automated selection."],
                )
                conflicts[m_key] = conf
                financial_values[m_key] = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key,
                    label=m_label,
                    amount=None,
                    reported_amount=None,
                    display_amount=disp_text,
                    unit=top_cand.normalized_unit,
                    currency=top_cand.normalized_currency,
                    reported_currency=top_cand.original_currency,
                    reported_scale=top_cand.original_scale,
                    status="UNCERTAIN",
                    reporting_scope=metadata.reporting_scope,
                    evidence=top_cand.evidence,
                    selected_candidate_id=None,
                    conflict_info=conf,
                    fact_classification="UNCERTAIN",
                )
            elif top_score > second_score and top_cand.parsed_number is not None:
                # Clear priority winner with valid numeric value and verified period
                rules_applied = cls._explain_priority_rules(top_cand, second_cand, metadata)
                conf = ConflictResolution(
                    conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                    metric_key=m_key,
                    status=ConflictStatus.RESOLVED_AUTOMATIC,
                    selected_candidate=top_cand,
                    all_candidates=m_candidates,
                    resolution_reason=f"Resolved automatically: {rules_applied}",
                    difference_absolute=max_diff,
                )
                conflicts[m_key] = conf
                disp_amt = FinancialNormalizer.format_display_amount(top_cand.normalized_amount, top_cand.normalized_unit)
                financial_values[m_key] = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key,
                    label=m_label,
                    amount=top_cand.normalized_amount,
                    reported_amount=top_cand.parsed_number,
                    display_amount=disp_amt,
                    unit=top_cand.normalized_unit,
                    currency=top_cand.normalized_currency,
                    reported_currency=top_cand.original_currency,
                    reported_scale=top_cand.original_scale,
                    status="REPORTED",
                    reporting_scope=top_cand.reporting_scope,
                    evidence=top_cand.evidence,
                    selected_candidate_id=top_cand.candidate_id,
                    conflict_info=conf,
                    fact_classification="DOCUMENT_FACT",
                )
            else:
                # Ambiguous: Equal authority candidates with distinct amounts -> Mark UNCERTAIN (Factor 8)
                conf = ConflictResolution(
                    conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                    metric_key=m_key,
                    status=ConflictStatus.UNCERTAIN,
                    selected_candidate=None,
                    all_candidates=m_candidates,
                    resolution_reason=(
                        f"Unresolved conflict: {len(m_candidates)} candidates disclosed with differing amounts "
                        f"({', '.join(str(c.normalized_amount) for c in m_candidates if c.normalized_amount is not None)}) "
                        f"and equal disclosure authority (Score {top_score}). Flagged UNCERTAIN without automated guesswork."
                    ),
                    difference_absolute=max_diff,
                    remaining_warnings=["Conflicting disclosures require user review before comparative calculations."],
                )
                conflicts[m_key] = conf
                financial_values[m_key] = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key,
                    label=m_label,
                    amount=None,
                    reported_amount=None,
                    display_amount="Uncertain (Conflicting Disclosures)",
                    unit=top_cand.normalized_unit,
                    currency=top_cand.normalized_currency,
                    reported_currency=top_cand.original_currency,
                    reported_scale=top_cand.original_scale,
                    status="UNCERTAIN",
                    reporting_scope=metadata.reporting_scope,
                    evidence=top_cand.evidence,
                    selected_candidate_id=None,
                    conflict_info=conf,
                    fact_classification="UNCERTAIN",
                )

        # Process any additional disclosed metrics (e.g. ADDITIONAL_*)
        for m_key, m_candidates in grouped.items():
            if m_key in financial_values:
                continue
            if not m_candidates:
                continue

            # Derive display label from the first candidate's raw_label or fallback to m_key
            m_label = m_candidates[0].raw_label or m_key.replace("ADDITIONAL_", "").replace("_", " ").title()

            if len(m_candidates) == 1:
                cand = m_candidates[0]
                is_period_verified = cls._is_period_affirmatively_matched(cand, metadata)

                if is_period_verified and cand.parsed_number is not None:
                    conf = ConflictResolution(
                        conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                        metric_key=m_key,
                        status=ConflictStatus.NO_CONFLICT,
                        selected_candidate=cand,
                        all_candidates=m_candidates,
                        resolution_reason=f"Single authoritative disclosure identified in {cand.statement_type}.",
                        difference_absolute=Decimal("0.0000"),
                    )
                    conflicts[m_key] = conf
                    disp_amt = FinancialNormalizer.format_display_amount(cand.normalized_amount, cand.normalized_unit)
                    financial_values[m_key] = FinancialValue(
                        doc_id=doc_id,
                        metric_key=m_key,
                        label=m_label,
                        amount=cand.normalized_amount,
                        reported_amount=cand.parsed_number,
                        display_amount=disp_amt,
                        unit=cand.normalized_unit,
                        currency=cand.normalized_currency,
                        reported_currency=cand.original_currency,
                        reported_scale=cand.original_scale,
                        status="REPORTED",
                        reporting_scope=cand.reporting_scope,
                        evidence=cand.evidence,
                        selected_candidate_id=cand.candidate_id,
                        conflict_info=conf,
                        fact_classification="DOCUMENT_FACT",
                    )
                else:
                    is_numeric = cand.parsed_number is not None
                    disp_amt = "Uncertain (Unverified Period)" if is_numeric else "Not Disclosed"
                    c_status = ConflictStatus.UNCERTAIN if is_numeric else ConflictStatus.NO_CONFLICT
                    fv_status = "UNCERTAIN" if is_numeric else "NOT_DISCLOSED"
                    fact_class = "UNCERTAIN" if is_numeric else "DOCUMENT_FACT"

                    conf = ConflictResolution(
                        conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                        metric_key=m_key,
                        status=c_status,
                        selected_candidate=None,
                        all_candidates=m_candidates,
                        resolution_reason=(
                            f"Single candidate identified in {cand.statement_type}, but reporting period cannot be affirmatively verified against target filing metadata. Marked UNCERTAIN without automated guesswork."
                            if is_numeric
                            else f"Single disclosure identified as non-numeric/missing ('{cand.raw_text_value}'); retained as missing."
                        ),
                        difference_absolute=Decimal("0.0000"),
                    )
                    conflicts[m_key] = conf
                    financial_values[m_key] = FinancialValue(
                        doc_id=doc_id,
                        metric_key=m_key,
                        label=m_label,
                        amount=None,
                        reported_amount=cand.parsed_number,
                        display_amount=disp_amt,
                        unit=cand.normalized_unit,
                        currency=cand.normalized_currency,
                        reported_currency=cand.original_currency,
                        reported_scale=cand.original_scale,
                        status=fv_status,
                        reporting_scope=cand.reporting_scope,
                        evidence=cand.evidence,
                        selected_candidate_id=None,
                        conflict_info=conf,
                        fact_classification=fact_class,
                    )
                continue

            # Check identical amounts across candidates
            valid_amounts = [c.normalized_amount for c in m_candidates if c.normalized_amount is not None]
            unique_amounts = set(valid_amounts)
            if len(unique_amounts) == 1:
                period_matched_cands = [c for c in m_candidates if cls._is_period_affirmatively_matched(c, metadata)]
                if period_matched_cands:
                    best_cand = period_matched_cands[0]
                    conf = ConflictResolution(
                        conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                        metric_key=m_key,
                        status=ConflictStatus.RESOLVED_AUTOMATIC,
                        selected_candidate=best_cand,
                        all_candidates=m_candidates,
                        resolution_reason=f"Multiple disclosures ({len(m_candidates)}) agree on identical amount ({best_cand.normalized_amount}).",
                        difference_absolute=Decimal("0.0000"),
                    )
                    conflicts[m_key] = conf
                    disp_amt = FinancialNormalizer.format_display_amount(best_cand.normalized_amount, best_cand.normalized_unit)
                    financial_values[m_key] = FinancialValue(
                        doc_id=doc_id,
                        metric_key=m_key,
                        label=m_label,
                        amount=best_cand.normalized_amount,
                        reported_amount=best_cand.parsed_number,
                        display_amount=disp_amt,
                        unit=best_cand.normalized_unit,
                        currency=best_cand.normalized_currency,
                        reported_currency=best_cand.original_currency,
                        reported_scale=best_cand.original_scale,
                        status="REPORTED",
                        reporting_scope=best_cand.reporting_scope,
                        evidence=best_cand.evidence,
                        selected_candidate_id=best_cand.candidate_id if best_cand.parsed_number is not None else None,
                        conflict_info=conf,
                        fact_classification="DOCUMENT_FACT",
                    )
                else:
                    best_cand = m_candidates[0]
                    conf = ConflictResolution(
                        conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                        metric_key=m_key,
                        status=ConflictStatus.UNCERTAIN,
                        selected_candidate=None,
                        all_candidates=m_candidates,
                        resolution_reason=(
                            f"Multiple disclosures ({len(m_candidates)}) agree on identical amount ({best_cand.normalized_amount}), but no candidate has an affirmatively verified reporting period matching target filing."
                        ),
                        difference_absolute=Decimal("0.0000"),
                    )
                    conflicts[m_key] = conf
                    financial_values[m_key] = FinancialValue(
                        doc_id=doc_id,
                        metric_key=m_key,
                        label=m_label,
                        amount=None,
                        reported_amount=best_cand.parsed_number,
                        display_amount="Uncertain (Unverified Period)",
                        unit=best_cand.normalized_unit,
                        currency=best_cand.normalized_currency,
                        reported_currency=best_cand.original_currency,
                        reported_scale=best_cand.original_scale,
                        status="UNCERTAIN",
                        reporting_scope=metadata.reporting_scope,
                        evidence=best_cand.evidence,
                        selected_candidate_id=None,
                        conflict_info=conf,
                        fact_classification="UNCERTAIN",
                    )
                continue

            # Conflicting amounts -> Score candidates
            scored_candidates = [
                (cls._score_candidate(c, metadata), c) for c in m_candidates
            ]
            scored_candidates.sort(key=lambda sc: sc[0], reverse=True)

            top_score, top_cand = scored_candidates[0]
            second_score, second_cand = scored_candidates[1]
            max_diff = max(valid_amounts) - min(valid_amounts) if valid_amounts else Decimal("0.0000")
            is_top_period_verified = cls._is_period_affirmatively_matched(top_cand, metadata)

            if not is_top_period_verified:
                conf = ConflictResolution(
                    conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                    metric_key=m_key,
                    status=ConflictStatus.UNCERTAIN,
                    selected_candidate=None,
                    all_candidates=m_candidates,
                    resolution_reason="Top candidate lacks verified period match matching target filing.",
                    difference_absolute=max_diff,
                )
                conflicts[m_key] = conf
                financial_values[m_key] = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key,
                    label=m_label,
                    amount=None,
                    reported_amount=None,
                    display_amount="Uncertain (Unverified Period)",
                    unit=top_cand.normalized_unit,
                    currency=top_cand.normalized_currency,
                    reported_currency=top_cand.original_currency,
                    reported_scale=top_cand.original_scale,
                    status="UNCERTAIN",
                    reporting_scope=metadata.reporting_scope,
                    evidence=top_cand.evidence,
                    selected_candidate_id=None,
                    conflict_info=conf,
                    fact_classification="UNCERTAIN",
                )
            elif top_score > second_score and top_cand.parsed_number is not None:
                rules_applied = cls._explain_priority_rules(top_cand, second_cand, metadata)
                conf = ConflictResolution(
                    conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                    metric_key=m_key,
                    status=ConflictStatus.RESOLVED_AUTOMATIC,
                    selected_candidate=top_cand,
                    all_candidates=m_candidates,
                    resolution_reason=f"Resolved automatically: {rules_applied}",
                    difference_absolute=max_diff,
                )
                conflicts[m_key] = conf
                disp_amt = FinancialNormalizer.format_display_amount(top_cand.normalized_amount, top_cand.normalized_unit)
                financial_values[m_key] = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key,
                    label=m_label,
                    amount=top_cand.normalized_amount,
                    reported_amount=top_cand.parsed_number,
                    display_amount=disp_amt,
                    unit=top_cand.normalized_unit,
                    currency=top_cand.normalized_currency,
                    reported_currency=top_cand.original_currency,
                    reported_scale=top_cand.original_scale,
                    status="REPORTED",
                    reporting_scope=top_cand.reporting_scope,
                    evidence=top_cand.evidence,
                    selected_candidate_id=top_cand.candidate_id,
                    conflict_info=conf,
                    fact_classification="DOCUMENT_FACT",
                )
            else:
                conf = ConflictResolution(
                    conflict_id=f"conf_{doc_id}_{m_key}_{uuid.uuid4().hex[:6]}",
                    metric_key=m_key,
                    status=ConflictStatus.UNCERTAIN,
                    selected_candidate=None,
                    all_candidates=m_candidates,
                    resolution_reason="Unresolved conflict: differing amounts and equal authority.",
                    difference_absolute=max_diff,
                )
                conflicts[m_key] = conf
                financial_values[m_key] = FinancialValue(
                    doc_id=doc_id,
                    metric_key=m_key,
                    label=m_label,
                    amount=None,
                    reported_amount=None,
                    display_amount="Uncertain (Conflicting Disclosures)",
                    unit=top_cand.normalized_unit,
                    currency=top_cand.normalized_currency,
                    reported_currency=top_cand.original_currency,
                    reported_scale=top_cand.original_scale,
                    status="UNCERTAIN",
                    reporting_scope=metadata.reporting_scope,
                    evidence=top_cand.evidence,
                    selected_candidate_id=None,
                    conflict_info=conf,
                    fact_classification="UNCERTAIN",
                )

        return financial_values, conflicts

    @classmethod
    def _score_candidate(cls, cand: ValueCandidate, metadata: DocumentMetadata) -> int:
        """Compute authoritative score based on the approved 8-Factor Priority Rules.
        
        Hierarchy:
        1. Reporting entity and reporting scope (Consolidated vs Standalone; never universally ranked).
        2. Reporting period alignment.
        3. Audit status (Audited > Limited Review > Unaudited).
        4. Restatement footnotes & revised disclosures (Takes precedence ONLY when correcting same period/scope).
        5. Metric definition and accounting treatment.
        6. Statement tier authority (Primary Statements > Notes > MD&A).
        7. Evidence format quality (Table cell > Text pattern).
        8. Equal authority -> UNCERTAIN.
        """
        score = 0

        # Unparseable / missing candidate penalty
        if cand.parsed_number is None:
            return -200

        # Factor 1: Scope alignment (Target document scope match; never blanket priority to Consolidated)
        if cand.reporting_scope == metadata.reporting_scope:
            score += 100
        else:
            score += 0

        # Factor 2 & 4: Period alignment and conditional restatement authority
        cand_period_matches = cls._is_period_affirmatively_matched(cand, metadata)

        if cand_period_matches:
            if cand.is_restated:
                # Restated candidate specifically correcting the target period and scope
                if cand.reporting_scope == metadata.reporting_scope:
                    score += 85  # Restatement correcting same period & scope takes precedence
                else:
                    score += 35  # Different scope restatement does not take precedence
            else:
                score += 70  # Original current-period disclosure
        else:
            # Comparative prior period column or different period disclosure
            score += 10

        # Factor 3: Statement Tier Authority
        if cand.statement_type in (StatementType.BALANCE_SHEET, StatementType.PROFIT_AND_LOSS, StatementType.CASH_FLOW):
            score += 50
        elif cand.statement_type == StatementType.NOTES_TO_ACCOUNTS:
            score += 25
        elif cand.statement_type == StatementType.MDA_NARRATIVE:
            score += 10
        else:
            score += 5

        # Factor 4: Audit Status Authority
        if cand.audit_status == AuditStatus.AUDITED:
            score += 40
        elif cand.audit_status == AuditStatus.LIMITED_REVIEW:
            score += 25
        elif cand.audit_status == AuditStatus.UNAUDITED:
            score += 15
        elif cand.audit_status == AuditStatus.PROVISIONAL:
            score += 10

        # Factor 7: Evidence Format Quality
        if cand.extraction_method == "TABLE_CELL":
            score += 20
        elif cand.extraction_method == "TEXT_PATTERN":
            score += 5

        return score

    @classmethod
    def _explain_priority_rules(cls, winner: ValueCandidate, runner_up: ValueCandidate, metadata: DocumentMetadata) -> str:
        """Generate human-readable audit trail explanation for the winning candidate."""
        reasons = []

        winner_scope = winner.reporting_scope.value if hasattr(winner.reporting_scope, "value") else str(winner.reporting_scope)
        runner_scope = runner_up.reporting_scope.value if hasattr(runner_up.reporting_scope, "value") else str(runner_up.reporting_scope)
        if winner_scope != runner_scope:
            reasons.append(f"scope matches target filing ({winner_scope} prioritized over {runner_scope})")

        # Restatement explanation
        if winner.is_restated and not runner_up.is_restated:
            reasons.append("restated statutory disclosure supersedes original figure for the same period and scope")
        elif not winner.is_restated and runner_up.is_restated:
            reasons.append("current period primary disclosure supersedes prior period comparative column")

        winner_stmt = winner.statement_type.value if hasattr(winner.statement_type, "value") else str(winner.statement_type)
        runner_stmt = runner_up.statement_type.value if hasattr(runner_up.statement_type, "value") else str(runner_up.statement_type)
        if winner_stmt != runner_stmt:
            reasons.append(f"primary financial statement tier ({winner_stmt}) supersedes lower-tier schedule ({runner_stmt})")

        winner_audit = winner.audit_status.value if hasattr(winner.audit_status, "value") else str(winner.audit_status)
        runner_audit = runner_up.audit_status.value if hasattr(runner_up.audit_status, "value") else str(runner_up.audit_status)
        if winner_audit != runner_audit:
            reasons.append(f"higher assurance authority ({winner_audit} vs {runner_audit})")

        if winner.extraction_method != runner_up.extraction_method:
            reasons.append(f"structured table cell evidence ({winner.extraction_method}) prioritized over narrative text ({runner_up.extraction_method})")

        if not reasons:
            reasons.append("overall higher contextual authority score under approved 8-factor hierarchy")

        return f"Candidate '{winner.candidate_id}' selected because " + "; ".join(reasons) + "."
