"""Comprehensive Unit and Regression Tests for Repair Group 4: Comparison Accuracy & Compatibility.

Covers:
1. Reversed percentage calculation (never negating percentage; ₹100 Cr -> ₹200 Cr is +100%, reversed is -50%).
2. Chronological ordering independent of upload order based on financial year / period end.
3. Additional disclosed metrics variance calculations (ADDITIONAL_*).
4. Reporting-scope mismatch metric-level warnings (Standalone vs Consolidated).
5. Period-duration mismatch metric-level warnings (Annual vs Quarterly).
6. Currency mismatch remains blocked with zero silent conversion.
7. Negative-base turnaround and downturn handling.
8. Zero-base division guard.
9. Missing and uncertain values never converted to zero.
10. Manual correction and evidence provenance separation.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from app.models.comparison import (
    AuditStatus,
    CalculationResult,
    CompatibilityReport,
    CompatibilityStatus,
    DocumentMetadata,
    EvidenceReference,
    FinancialCorrectionRecord,
    FinancialValue,
    IssueSeverity,
    PairwiseCompatibility,
    ReportingPeriodType,
    ReportingScope,
    VarianceStatus,
)
from app.services.financial_calculator import FinancialCalculator
from app.services.financial_normalizer import FOUR_PLACES


def make_fv(
    doc_id: str,
    metric_key: str,
    amount: Decimal | None,
    unit: str = "INR_CRORE",
    currency: str = "INR",
    status: str = "REPORTED",
    scope: str = "CONSOLIDATED",
    period_type: str = "Annual",
) -> FinancialValue:
    return FinancialValue(
        doc_id=doc_id,
        metric_key=metric_key,
        label=metric_key.replace("_", " ").title(),
        amount=amount,
        reported_amount=amount,
        display_amount=f"₹{amount} Cr" if amount is not None else "Not Disclosed",
        unit=unit,
        currency=currency,
        status=status,
        reporting_scope=scope,
        fact_classification="DOCUMENT_FACT",
    )


class TestSlice14ComparisonAccuracy(unittest.TestCase):
    """Test suite for Group 4 comparison accuracy, calculations, and compatibility."""

    # -----------------------------------------------------------------------
    # 1. Reversed Percentage Calculation
    # -----------------------------------------------------------------------

    def test_01_percentage_calculation_when_reversing_baseline(self):
        """Reversing baseline recalculates using actual new base denominator: 100->200 is +100%, 200->100 is -50%."""
        fv_100 = make_fv("doc_a", "REVENUE", Decimal("100.0000"))
        fv_200 = make_fv("doc_b", "REVENUE", Decimal("200.0000"))

        # Base = doc_a (100), Comp = doc_b (200)
        res_forward = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="REVENUE",
            label="Revenue from Operations",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=fv_100,
            comp_fv=fv_200,
        )
        self.assertEqual(res_forward.status, VarianceStatus.CALCULATED)
        self.assertEqual(res_forward.absolute_variance, Decimal("100.0000"))
        self.assertEqual(res_forward.percentage_change, Decimal("100.0000"))
        self.assertEqual(res_forward.display_percentage_change, "+100.00%")

        # Base = doc_b (200), Comp = doc_a (100) -> Must be -50%, NEVER -100%
        res_reversed = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="REVENUE",
            label="Revenue from Operations",
            base_doc_id="doc_b",
            comp_doc_id="doc_a",
            base_fv=fv_200,
            comp_fv=fv_100,
        )
        self.assertEqual(res_reversed.status, VarianceStatus.CALCULATED)
        self.assertEqual(res_reversed.absolute_variance, Decimal("-100.0000"))
        self.assertEqual(res_reversed.percentage_change, Decimal("-50.0000"))
        self.assertEqual(res_reversed.display_percentage_change, "-50.00%")

    # -----------------------------------------------------------------------
    # 2. Chronological Ordering of Documents
    # -----------------------------------------------------------------------

    def test_02_chronological_ordering_independent_of_upload_order(self):
        """Documents uploaded in reverse chronological order (FY25 before FY24) must order FY24 as base."""
        from app.api.compare_routes import order_documents_chronologically

        meta_fy25 = DocumentMetadata(
            doc_id="doc_1",
            financial_year="FY 2024-25",
            period_end_date="2025-03-31",
            reporting_period="annual",
        )
        meta_fy24 = DocumentMetadata(
            doc_id="doc_2",
            financial_year="FY 2023-24",
            period_end_date="2024-03-31",
            reporting_period="annual",
        )

        metadata_map = {"doc_1": meta_fy25, "doc_2": meta_fy24}
        # Upload order was doc_1 (FY25) then doc_2 (FY24)
        ordered_ids = order_documents_chronologically(["doc_1", "doc_2"], metadata_map)
        self.assertEqual(ordered_ids, ["doc_2", "doc_1"], "Earlier filing FY24 must be baseline (first)")

    # -----------------------------------------------------------------------
    # 3. Additional Disclosed Metrics Variance Calculations
    # -----------------------------------------------------------------------

    def test_03_additional_metrics_variance_calculation(self):
        """Variances are computed for valid ADDITIONAL_* metrics present in financial_values."""
        fv_mat_a = make_fv("doc_a", "ADDITIONAL_COST_OF_MATERIALS_CONSUMED", Decimal("4200.0000"))
        fv_mat_b = make_fv("doc_b", "ADDITIONAL_COST_OF_MATERIALS_CONSUMED", Decimal("4800.0000"))

        financial_values = {
            "ADDITIONAL_COST_OF_MATERIALS_CONSUMED": {
                "doc_a": fv_mat_a,
                "doc_b": fv_mat_b,
            }
        }

        variances = FinancialCalculator.compute_all_variances(
            financial_values=financial_values,
            doc_ids=["doc_a", "doc_b"],
        )

        mat_var = next((v for v in variances if "COST_OF_MATERIALS" in v.metric_key), None)
        self.assertIsNotNone(mat_var, "Variance for ADDITIONAL_COST_OF_MATERIALS_CONSUMED must be computed")
        self.assertEqual(mat_var.absolute_variance, Decimal("600.0000"))
        self.assertEqual(mat_var.status, VarianceStatus.CALCULATED)

    # -----------------------------------------------------------------------
    # 4. Reporting Scope Mismatch Warnings
    # -----------------------------------------------------------------------

    def test_04_scope_mismatch_warning_in_calculation(self):
        """Comparing Standalone vs Consolidated annotates directional explanation with perimeter warning."""
        fv_stand = make_fv("doc_a", "REVENUE", Decimal("25000.0000"), scope="STANDALONE")
        fv_cons = make_fv("doc_b", "REVENUE", Decimal("100000.0000"), scope="CONSOLIDATED")

        res = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="REVENUE",
            label="Revenue from Operations",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=fv_stand,
            comp_fv=fv_cons,
        )
        self.assertIsNotNone(res.directional_explanation)
        self.assertTrue(
            "scope" in res.directional_explanation.lower() or "perimeter" in res.directional_explanation.lower(),
            f"Expected scope perimeter warning in explanation: {res.directional_explanation}",
        )

    # -----------------------------------------------------------------------
    # 5. Period Duration Mismatch Warnings
    # -----------------------------------------------------------------------

    def test_05_period_duration_mismatch_warning_in_calculation(self):
        """Comparing Annual vs Quarterly annotates calculation with period duration discrepancy warning."""
        fv_ann = make_fv("doc_a", "REVENUE", Decimal("40000.0000"))
        fv_qtr = make_fv("doc_b", "REVENUE", Decimal("11000.0000"))

        meta_a = DocumentMetadata(doc_id="doc_a", reporting_period="Annual", financial_year="FY 2023-24")
        meta_b = DocumentMetadata(doc_id="doc_b", reporting_period="Quarterly", quarter="Q1", financial_year="FY 2024-25")

        res = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="REVENUE",
            label="Revenue from Operations",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=fv_ann,
            comp_fv=fv_qtr,
            base_meta=meta_a,
            comp_meta=meta_b,
        )
        self.assertIsNotNone(res.directional_explanation)
        self.assertTrue(
            "period" in res.directional_explanation.lower() or "duration" in res.directional_explanation.lower() or "annual" in res.directional_explanation.lower(),
            f"Expected period duration warning in explanation: {res.directional_explanation}",
        )

    # -----------------------------------------------------------------------
    # 6. Currency Mismatch Remains Blocked
    # -----------------------------------------------------------------------

    def test_06_currency_mismatch_remains_blocked(self):
        """Incompatible currencies (USD vs INR) are strictly blocked with zero silent conversion."""
        fv_inr = make_fv("doc_a", "REVENUE", Decimal("5000.0000"), currency="INR")
        fv_usd = make_fv("doc_b", "REVENUE", Decimal("600.0000"), currency="USD", unit="USD_MILLION")

        res = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="REVENUE",
            label="Revenue from Operations",
            base_doc_id="doc_a",
            comp_doc_id="doc_b",
            base_fv=fv_inr,
            comp_fv=fv_usd,
        )
        self.assertEqual(res.status, VarianceStatus.CURRENCY_MISMATCH)
        self.assertIsNone(res.absolute_variance)
        self.assertIsNone(res.percentage_change)
        self.assertIn("Currencies differ", res.directional_explanation)

    # -----------------------------------------------------------------------
    # 7. Negative-Base Turnaround and Downturn
    # -----------------------------------------------------------------------

    def test_07_negative_base_turnaround_and_downturn(self):
        """Negative bases avoid misleading percentage math and explain directionality factually."""
        # Turnaround: loss to profit
        fv_loss = make_fv("doc_a", "PAT", Decimal("-500.0000"))
        fv_profit = make_fv("doc_b", "PAT", Decimal("200.0000"))
        res_turn = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="PAT", label="Profit After Tax",
            base_doc_id="doc_a", comp_doc_id="doc_b",
            base_fv=fv_loss, comp_fv=fv_profit,
        )
        self.assertEqual(res_turn.status, VarianceStatus.NON_POSITIVE_BASE)
        self.assertIsNone(res_turn.percentage_change)
        self.assertIn("Turnaround", res_turn.directional_explanation)

        # Downturn: profit to loss
        res_down = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="PAT", label="Profit After Tax",
            base_doc_id="doc_b", comp_doc_id="doc_a",
            base_fv=fv_profit, comp_fv=fv_loss,
        )
        self.assertEqual(res_down.status, VarianceStatus.NON_POSITIVE_BASE)
        self.assertIsNone(res_down.percentage_change)
        self.assertIn("Downturn", res_down.directional_explanation)

    # -----------------------------------------------------------------------
    # 8. Zero-Base Division Guard
    # -----------------------------------------------------------------------

    def test_08_zero_base_division_guard(self):
        """Zero denominator produces DIV_BY_ZERO status and N/A (Base Zero) without division error."""
        fv_zero = make_fv("doc_a", "TOTAL_DEBT", Decimal("0.0000"))
        fv_pos = make_fv("doc_b", "TOTAL_DEBT", Decimal("150.0000"))
        res = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="TOTAL_DEBT", label="Total Debt",
            base_doc_id="doc_a", comp_doc_id="doc_b",
            base_fv=fv_zero, comp_fv=fv_pos,
        )
        self.assertEqual(res.status, VarianceStatus.DIV_BY_ZERO)
        self.assertEqual(res.display_percentage_change, "N/A (Base Zero)")

    # -----------------------------------------------------------------------
    # 9. Missing and Uncertain Values Never Become Zero
    # -----------------------------------------------------------------------

    def test_09_missing_and_uncertain_values_never_become_zero(self):
        """Missing or UNCERTAIN values are never converted to Decimal(0) for mathematical subtraction."""
        fv_reported = make_fv("doc_a", "EBITDA", Decimal("1200.0000"))
        fv_missing = make_fv("doc_b", "EBITDA", None, status="NOT_DISCLOSED")
        fv_uncertain = make_fv("doc_c", "EBITDA", Decimal("1100.0000"), status="UNCERTAIN")

        res_miss = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="EBITDA", label="EBITDA",
            base_doc_id="doc_a", comp_doc_id="doc_b",
            base_fv=fv_reported, comp_fv=fv_missing,
        )
        self.assertEqual(res_miss.status, VarianceStatus.NOT_DISCLOSED)
        self.assertIsNone(res_miss.absolute_variance)

        res_unc = FinancialCalculator.compute_pairwise_metric_variance(
            metric_key="EBITDA", label="EBITDA",
            base_doc_id="doc_a", comp_doc_id="doc_c",
            base_fv=fv_reported, comp_fv=fv_uncertain,
        )
        self.assertEqual(res_unc.status, VarianceStatus.NOT_DISCLOSED)
        self.assertIsNone(res_unc.absolute_variance)

    # -----------------------------------------------------------------------
    # 10. Manual Correction and Provenance Isolation
    # -----------------------------------------------------------------------

    def test_10_manual_correction_and_evidence_provenance_isolation(self):
        """User-entered manual corrections are distinguished from extracted facts and preserve original amounts."""
        ev = EvidenceReference(
            evidence_id="ev_rev_1",
            doc_id="doc_a",
            document_name="doc_a.pdf",
            page_number=1,
            bounding_box=[0.1, 0.1, 0.5, 0.2],
            verbatim_snippet="Revenue from operations 10,000",
        )
        fv_doc = FinancialValue(
            doc_id="doc_a",
            metric_key="REVENUE",
            label="Revenue from operations",
            amount=Decimal("10000.0000"),
            unit="INR_CRORE",
            currency="INR",
            status="REPORTED",
            reporting_scope="CONSOLIDATED",
            evidence=ev,
            fact_classification="DOCUMENT_FACT",
        )
        self.assertEqual(fv_doc.fact_classification, "DOCUMENT_FACT")
        self.assertFalse(fv_doc.is_user_corrected)
        self.assertIsNotNone(fv_doc.evidence)

        # Simulate user correction
        fv_corrected = fv_doc.model_copy()
        fv_corrected.original_amount = fv_doc.amount
        fv_corrected.amount = Decimal("10500.0000")
        fv_corrected.user_entered_amount = Decimal("10500.0000")
        fv_corrected.is_user_corrected = True
        fv_corrected.fact_classification = "USER_ENTERED"
        fv_corrected.correction_reason = "Typo in OCR"

        self.assertEqual(fv_corrected.fact_classification, "USER_ENTERED")
        self.assertTrue(fv_corrected.is_user_corrected)
        self.assertEqual(fv_corrected.original_amount, Decimal("10000.0000"))
        self.assertEqual(fv_corrected.amount, Decimal("10500.0000"))


if __name__ == "__main__":
    unittest.main()
