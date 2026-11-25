"""Deterministic financial calculations engine using decimal.Decimal.

Implements:
- Absolute variance: New - Old
- Percentage variance: ((New - Old) / abs(Old)) * 100
- Rounding: ROUND_HALF_UP with 4 decimal places internal, 2 decimal places display.
- Negative-base transition handling: Turnaround (loss to profit), Downturn (profit to loss),
  loss reduction, loss expansion, zero-denominator.
- Compatibility integration: Respects COMPATIBLE, COMPATIBLE_WITH_WARNINGS, PARTIALLY_COMPATIBLE, BLOCKED.
- No LLM participation in mathematical calculation.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Set, Tuple

from ..models.comparison import (
    CalculationResult,
    CompatibilityReport,
    CompatibilityStatus,
    DocumentMetadata,
    FinancialValue,
    PairwiseCompatibility,
    VarianceStatus,
)
from .financial_extractor import METRIC_REGISTRY
from .financial_normalizer import FOUR_PLACES, TWO_PLACES, FinancialNormalizer


class FinancialCalculator:
    """Computes deterministic variances and directional explanations across document pairs."""

    @classmethod
    def compute_all_variances(
        cls,
        financial_values: Dict[str, Dict[str, FinancialValue]],  # metric_key -> doc_id -> FinancialValue
        doc_ids: List[str],
        compatibility_report: Optional[CompatibilityReport] = None,
        metadata_map: Optional[Dict[str, DocumentMetadata]] = None,
    ) -> List[CalculationResult]:
        """Compute all pairwise mathematical variances for eligible document pairs."""
        variances: List[CalculationResult] = []

        if len(doc_ids) < 2:
            return variances

        # Build blocked pairs lookup from pairwise matrix if available
        blocked_pairs: Set[Tuple[str, str]] = set()
        if compatibility_report:
            for pair in compatibility_report.pairwise_matrix:
                if pair.status == CompatibilityStatus.BLOCKED or not pair.is_comparable:
                    blocked_pairs.add((pair.doc_a_id, pair.doc_b_id))
                    blocked_pairs.add((pair.doc_b_id, pair.doc_a_id))

        # Collect metrics: standard registered metrics plus any valid additional metrics
        metrics_to_compute: List[Tuple[str, str]] = [(m["key"], m["label"]) for m in METRIC_REGISTRY]
        seen_keys = {m["key"] for m in METRIC_REGISTRY}

        for extra_key in sorted(financial_values.keys()):
            if extra_key.startswith("ADDITIONAL_") and extra_key not in seen_keys:
                seen_keys.add(extra_key)
                doc_map = financial_values.get(extra_key, {})
                first_fv = next((fv for fv in doc_map.values() if fv and fv.label), None)
                extra_label = first_fv.label if first_fv else extra_key.replace("ADDITIONAL_", "").replace("_", " ").title()
                metrics_to_compute.append((extra_key, extra_label))

        # Generate pairwise comparisons: doc_ids[i] as base (earlier), doc_ids[j] as comparison (later)
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                base_id = doc_ids[i]
                comp_id = doc_ids[j]
                pair_is_blocked = (base_id, comp_id) in blocked_pairs
                base_meta = metadata_map.get(base_id) if metadata_map else None
                comp_meta = metadata_map.get(comp_id) if metadata_map else None

                for m_key, m_label in metrics_to_compute:
                    metric_docs = financial_values.get(m_key, {})
                    base_fv = metric_docs.get(base_id)
                    comp_fv = metric_docs.get(comp_id)

                    calc = cls.compute_pairwise_metric_variance(
                        metric_key=m_key,
                        label=m_label,
                        base_doc_id=base_id,
                        comp_doc_id=comp_id,
                        base_fv=base_fv,
                        comp_fv=comp_fv,
                        pair_is_blocked=pair_is_blocked,
                        base_meta=base_meta,
                        comp_meta=comp_meta,
                    )
                    variances.append(calc)

        return variances

    @classmethod
    def compute_pairwise_metric_variance(
        cls,
        metric_key: str,
        label: str,
        base_doc_id: str,
        comp_doc_id: str,
        base_fv: Optional[FinancialValue],
        comp_fv: Optional[FinancialValue],
        pair_is_blocked: bool = False,
        base_meta: Optional[DocumentMetadata] = None,
        comp_meta: Optional[DocumentMetadata] = None,
    ) -> CalculationResult:
        """Compute variance between two specific document values for a single metric."""
        # 1. Blocked Pair Handling
        if pair_is_blocked:
            return CalculationResult(
                metric_key=metric_key,
                label=label,
                base_doc_id=base_doc_id,
                comparison_doc_id=comp_doc_id,
                base_value=base_fv.amount if base_fv else None,
                comparison_value=comp_fv.amount if comp_fv else None,
                base_candidate_id=base_fv.selected_candidate_id if base_fv else None,
                comparison_candidate_id=comp_fv.selected_candidate_id if comp_fv else None,
                formula="(comparison - base)",
                absolute_variance=None,
                percentage_change=None,
                display_absolute_variance="Blocked",
                display_percentage_change="Blocked",
                unit=base_fv.unit if base_fv else "INR_CRORE",
                rounding_method="ROUND_HALF_UP",
                status=VarianceStatus.BLOCKED,
                directional_explanation="Mathematical variance calculation blocked due to pairwise incompatibility (e.g. currency mismatch).",
            )

        # 2. Currency Mismatch or Unknown Currency Guard
        if base_fv and comp_fv:
            base_curr = (base_fv.currency or "UNKNOWN").upper()
            comp_curr = (comp_fv.currency or "UNKNOWN").upper()
            if base_curr != comp_curr or base_curr == "UNKNOWN" or comp_curr == "UNKNOWN":
                curr_desc = (
                    f"Currencies differ ({base_curr} vs {comp_curr}). Silent conversion is prohibited under non-advisory principles without approved FX conversion methodology."
                    if base_curr != comp_curr
                    else f"Currency is unknown (Doc {base_doc_id}: {base_curr}, Doc {comp_doc_id}: {comp_curr}). Mathematical variance calculation prohibited."
                )
                return CalculationResult(
                    metric_key=metric_key,
                    label=label,
                    base_doc_id=base_doc_id,
                    comparison_doc_id=comp_doc_id,
                    base_value=base_fv.amount,
                    comparison_value=comp_fv.amount,
                    base_candidate_id=base_fv.selected_candidate_id,
                    comparison_candidate_id=comp_fv.selected_candidate_id,
                    formula="(comparison - base)",
                    absolute_variance=None,
                    percentage_change=None,
                    display_absolute_variance="Currency Mismatch",
                    display_percentage_change="N/A",
                    unit=base_fv.unit,
                    rounding_method="ROUND_HALF_UP",
                    status=VarianceStatus.CURRENCY_MISMATCH,
                    directional_explanation=curr_desc,
                )

            # Incompatible Units / Scale Guard
            if base_fv.unit != comp_fv.unit:
                return CalculationResult(
                    metric_key=metric_key,
                    label=label,
                    base_doc_id=base_doc_id,
                    comparison_doc_id=comp_doc_id,
                    base_value=base_fv.amount,
                    comparison_value=comp_fv.amount,
                    base_candidate_id=base_fv.selected_candidate_id,
                    comparison_candidate_id=comp_fv.selected_candidate_id,
                    formula="(comparison - base)",
                    absolute_variance=None,
                    percentage_change=None,
                    display_absolute_variance="Unit Mismatch",
                    display_percentage_change="N/A",
                    unit=base_fv.unit,
                    rounding_method="ROUND_HALF_UP",
                    status=VarianceStatus.INCOMPATIBLE_UNITS,
                    directional_explanation=f"Reporting units/scales differ ({base_fv.unit} vs {comp_fv.unit}). Incompatible units cannot be subtracted directly.",
                )

        # 3. Missing or Uncertain Data Guard (missing values must never silently become zero)
        if (
            not base_fv
            or not comp_fv
            or base_fv.amount is None
            or comp_fv.amount is None
            or base_fv.status != "REPORTED"
            or comp_fv.status != "REPORTED"
        ):
            def _human_status(st: Optional[str]) -> str:
                if not st or st == "NOT_DISCLOSED":
                    return "Not disclosed in filing"
                if st == "UNCERTAIN":
                    return "Uncertain / Unverified"
                if st == "AMBIGUOUS":
                    return "Multiple conflicting values"
                if st == "EXTRACTION_UNAVAILABLE":
                    return "Manual verification required"
                return st.replace("_", " ").title()

            if not base_fv or base_fv.amount is None:
                missing_detail = f"Base document (Doc {base_doc_id}) does not disclose an authoritative numeric value ({_human_status(base_fv.status if base_fv else 'NOT_DISCLOSED')})."
            elif not comp_fv or comp_fv.amount is None:
                missing_detail = f"Comparison document (Doc {comp_doc_id}) does not disclose an authoritative numeric value ({_human_status(comp_fv.status if comp_fv else 'NOT_DISCLOSED')})."
            else:
                missing_detail = f"Metric is not consistently reported with authoritative certainty (Doc {base_doc_id}: {_human_status(base_fv.status)}, Doc {comp_doc_id}: {_human_status(comp_fv.status)})."

            return CalculationResult(
                metric_key=metric_key,
                label=label,
                base_doc_id=base_doc_id,
                comparison_doc_id=comp_doc_id,
                base_value=base_fv.amount if base_fv else None,
                comparison_value=comp_fv.amount if comp_fv else None,
                base_candidate_id=base_fv.selected_candidate_id if base_fv else None,
                comparison_candidate_id=comp_fv.selected_candidate_id if comp_fv else None,
                formula="(comparison - base)",
                absolute_variance=None,
                percentage_change=None,
                display_absolute_variance="N/A",
                display_percentage_change="N/A",
                unit=base_fv.unit if base_fv else (comp_fv.unit if comp_fv else "INR_CRORE"),
                rounding_method="ROUND_HALF_UP",
                status=VarianceStatus.NOT_DISCLOSED,
                directional_explanation=missing_detail,
            )

        # 4. Deterministic Decimal Math
        base_num: Decimal = base_fv.amount
        comp_num: Decimal = comp_fv.amount
        unit = base_fv.unit

        # Absolute variance is always mathematically valid: New - Old
        abs_var = (comp_num - base_num).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        disp_abs_var = FinancialNormalizer.format_display_amount(abs_var, unit)

        # Context Discrepancy Warnings (Scope Mismatch & Period Duration Discrepancy)
        context_warnings: List[str] = []

        base_scope = (base_fv.reporting_scope if base_fv and base_fv.reporting_scope else (base_meta.reporting_scope if base_meta else None))
        comp_scope = (comp_fv.reporting_scope if comp_fv and comp_fv.reporting_scope else (comp_meta.reporting_scope if comp_meta else None))
        base_scope_str = str(base_scope.value if hasattr(base_scope, "value") else base_scope).upper() if base_scope else "UNKNOWN"
        comp_scope_str = str(comp_scope.value if hasattr(comp_scope, "value") else comp_scope).upper() if comp_scope else "UNKNOWN"

        if base_scope_str not in ("UNKNOWN", "BOTH") and comp_scope_str not in ("UNKNOWN", "BOTH") and base_scope_str != comp_scope_str:
            context_warnings.append(
                f"Scope discrepancy: Compares {base_scope_str} (Doc {base_doc_id}) vs {comp_scope_str} (Doc {comp_doc_id}) perimeters. Variance reflects organizational boundary differences rather than identical operational growth."
            )

        if base_meta and comp_meta:
            bp = (base_meta.reporting_period or "").strip().lower()
            cp = (comp_meta.reporting_period or "").strip().lower()
            if bp and cp and bp not in ("unknown", "") and cp not in ("unknown", "") and bp != cp:
                context_warnings.append(
                    f"Period duration discrepancy: Compares {base_meta.reporting_period} (Doc {base_doc_id}) vs {comp_meta.reporting_period} (Doc {comp_doc_id}). Differing duration disclosures cannot be directly compared as like-for-like operational growth."
                )

        warning_suffix = f" [{' | '.join(context_warnings)}]" if context_warnings else ""

        # 5. Percentage Variance & Negative-Base Directional Logic
        # Case A: Base is Zero -> Division by Zero
        if base_num == Decimal("0"):
            explanation = (
                "Zero in both periods (no change)."
                if comp_num == Decimal("0")
                else f"Base value was zero; expanded to {FinancialNormalizer.format_display_amount(comp_num, unit)} (percentage undefined)."
            )
            return CalculationResult(
                metric_key=metric_key,
                label=label,
                base_doc_id=base_doc_id,
                comparison_doc_id=comp_doc_id,
                base_value=base_num,
                comparison_value=comp_num,
                base_candidate_id=base_fv.selected_candidate_id,
                comparison_candidate_id=comp_fv.selected_candidate_id,
                formula="(comparison - base)",
                absolute_variance=abs_var,
                percentage_change=None,
                display_absolute_variance=disp_abs_var,
                display_percentage_change="N/A (Base Zero)",
                unit=unit,
                rounding_method="ROUND_HALF_UP",
                status=VarianceStatus.DIV_BY_ZERO,
                directional_explanation=f"{explanation}{warning_suffix}",
            )

        # Case B: Negative Base (Loss) -> Misleading percentage change avoided
        if base_num < Decimal("0"):
            disp_abs_base = FinancialNormalizer.format_display_amount(abs(base_num), unit)
            disp_abs_comp = FinancialNormalizer.format_display_amount(abs(comp_num), unit)

            if comp_num > Decimal("0"):
                explanation = (
                    f"Turnaround: shifted from net loss of {disp_abs_base} to net profit of "
                    f"{FinancialNormalizer.format_display_amount(comp_num, unit)} (+{disp_abs_var} absolute improvement)."
                )
            elif comp_num < Decimal("0"):
                if comp_num > base_num:
                    explanation = f"Loss reduction: net loss narrowed by {FinancialNormalizer.format_display_amount(abs_var, unit)} (from -{disp_abs_base} to -{disp_abs_comp})."
                elif comp_num < base_num:
                    explanation = f"Loss expansion: net loss widened by {FinancialNormalizer.format_display_amount(abs(abs_var), unit)} (from -{disp_abs_base} to -{disp_abs_comp})."
                else:
                    explanation = f"Loss unchanged at -{disp_abs_base}."
            else:
                explanation = f"Loss eliminated: shifted from net loss of {disp_abs_base} to break-even (zero)."

            return CalculationResult(
                metric_key=metric_key,
                label=label,
                base_doc_id=base_doc_id,
                comparison_doc_id=comp_doc_id,
                base_value=base_num,
                comparison_value=comp_num,
                base_candidate_id=base_fv.selected_candidate_id,
                comparison_candidate_id=comp_fv.selected_candidate_id,
                formula="(comparison - base)",
                absolute_variance=abs_var,
                percentage_change=None,
                display_absolute_variance=disp_abs_var,
                display_percentage_change="N/A (Loss Base)",
                unit=unit,
                rounding_method="ROUND_HALF_UP",
                status=VarianceStatus.NON_POSITIVE_BASE,
                directional_explanation=f"{explanation}{warning_suffix}",
            )

        # Case C: Positive Base shifting to Negative Comparison (Profit to Loss)
        if base_num > Decimal("0") and comp_num < Decimal("0"):
            disp_abs_base = FinancialNormalizer.format_display_amount(base_num, unit)
            disp_abs_comp = FinancialNormalizer.format_display_amount(abs(comp_num), unit)
            explanation = (
                f"Downturn: shifted from net profit of {disp_abs_base} to net loss of {disp_abs_comp} "
                f"({disp_abs_var} absolute decline)."
            )
            return CalculationResult(
                metric_key=metric_key,
                label=label,
                base_doc_id=base_doc_id,
                comparison_doc_id=comp_doc_id,
                base_value=base_num,
                comparison_value=comp_num,
                base_candidate_id=base_fv.selected_candidate_id,
                comparison_candidate_id=comp_fv.selected_candidate_id,
                formula="(comparison - base)",
                absolute_variance=abs_var,
                percentage_change=None,
                display_absolute_variance=disp_abs_var,
                display_percentage_change="N/A (Downturn to Loss)",
                unit=unit,
                rounding_method="ROUND_HALF_UP",
                status=VarianceStatus.NON_POSITIVE_BASE,
                directional_explanation=f"{explanation}{warning_suffix}",
            )

        # Case D: Standard Positive Base -> Valid Percentage Calculation
        pct = ((comp_num - base_num) / base_num) * Decimal("100.0")
        pct_quant = pct.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        disp_pct = f"{pct_quant.quantize(TWO_PLACES, rounding=ROUND_HALF_UP):+.2f}%"

        return CalculationResult(
            metric_key=metric_key,
            label=label,
            base_doc_id=base_doc_id,
            comparison_doc_id=comp_doc_id,
            base_value=base_num,
            comparison_value=comp_num,
            base_candidate_id=base_fv.selected_candidate_id,
            comparison_candidate_id=comp_fv.selected_candidate_id,
            formula="((comparison - base) / base) * 100",
            absolute_variance=abs_var,
            percentage_change=pct_quant,
            display_absolute_variance=disp_abs_var,
            display_percentage_change=disp_pct,
            unit=unit,
            rounding_method="ROUND_HALF_UP",
            status=VarianceStatus.CALCULATED,
            directional_explanation="; ".join(context_warnings) if context_warnings else None,
        )
