"""Comprehensive automated test suite for Compare Documents Slice 4:
Financial Metric Extraction, Normalization, Conflict Arbitration & Deterministic Calculations.
"""

from __future__ import annotations

import io
from decimal import Decimal
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.models.comparison import (
    AuditStatus,
    CalculationResult,
    CompatibilityReport,
    CompatibilityStatus,
    ComparisonDocument,
    ComparisonResult,
    ComparisonSession,
    ConflictResolution,
    ConflictStatus,
    DocumentExtractionResult,
    DocumentMetadata,
    DocumentSlot,
    EvidenceReference,
    ExtractedTable,
    ExtractedTextBlock,
    FactClassification,
    FinancialCorrectionRecord,
    FinancialCorrectionRequest,
    FinancialCorrectionResponse,
    FinancialUndoResponse,
    FinancialValue,
    PairwiseCompatibility,
    ProcessingStage,
    ReportingScope,
    SessionCorrectionsResponse,
    SessionStatus,
    StatementType,
    SupportedFileFormat,
    ValueCandidate,
    VarianceStatus,
)
from app.services.comparison_session_store import session_store
from app.services.conflict_arbitrator import ConflictArbitrator
from app.services.financial_calculator import FinancialCalculator
from app.services.financial_extractor import FinancialExtractor, METRIC_REGISTRY
from app.services.financial_normalizer import FinancialNormalizer
from main import app

client = TestClient(app)


def create_sample_table(
    table_id: str = "t1",
    sheet_name: str = "Statement of P&L",
    headers: list[str] = None,
    rows: list[list[str]] = None,
) -> ExtractedTable:
    """Helper to build an ExtractedTable fixture."""
    h = headers or ["Particulars", "31-Dec-2023 (Q3)", "30-Sep-2023 (Q2)"]
    r = rows or []
    return ExtractedTable(
        table_id=table_id,
        sheet_name=sheet_name,
        headers=h,
        rows=r,
        num_rows=len(r),
        num_cols=len(h),
        structural_ref=f"Sheet: {sheet_name}",
    )


class TestSlice4FinancialEngine(unittest.TestCase):
    """Slice 4 unit and integration test suite."""

    # -----------------------------------------------------------------------
    # 1. Financial Normalizer Tests
    # -----------------------------------------------------------------------

    def test_parse_raw_number_positive_and_indian_commas(self) -> None:
        """Verify standard numbers and Indian numbering comma placements."""
        self.assertEqual(FinancialNormalizer.parse_raw_number("10500.50"), Decimal("10500.5000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("10,500.50"), Decimal("10500.5000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("1,23,456.78"), Decimal("123456.7800"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("₹ 9,800.00"), Decimal("9800.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("$ 1,500.25"), Decimal("1500.2500"))

    def test_parse_raw_number_parentheses_and_negative_notations(self) -> None:
        """Verify accounting parentheses '(50.25)' and minus signs parse as negative Decimal."""
        self.assertEqual(FinancialNormalizer.parse_raw_number("(50.25)"), Decimal("-50.2500"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("( 1,200.50 )"), Decimal("-1200.5000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("-50.25"), Decimal("-50.2500"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("— 50.25"), Decimal("-50.2500"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("50.25-"), Decimal("-50.2500"))

    def test_parse_raw_number_zero_and_nil_tokens(self) -> None:
        """Verify explicit numeric zero parses as zero, while nil/N/A/dash without convention do not."""
        # Explicit numeric zero
        self.assertEqual(FinancialNormalizer.parse_raw_number("0"), Decimal("0.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("0.00"), Decimal("0.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("Zero"), Decimal("0.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("₹ 0"), Decimal("0.0000"))

        # Missing / unavailable tokens must never silently become zero
        self.assertIsNone(FinancialNormalizer.parse_raw_number("Nil"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("NIL"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("N/A"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("n.a."))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("None"))

        # Dash without convention: must be None (missing/uncertain, not zero)
        self.assertIsNone(FinancialNormalizer.parse_raw_number("-"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("—"))

        # Dash with explicit convention: parses as zero
        self.assertEqual(FinancialNormalizer.parse_raw_number("-", allow_dash_as_zero=True), Decimal("0.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("—", allow_dash_as_zero=True), Decimal("0.0000"))

        # Blank or invalid text
        self.assertIsNone(FinancialNormalizer.parse_raw_number(""))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("   "))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("NonNumericText"))

    # -----------------------------------------------------------------------
    # Correction 1: Missing Values Must Never Silently Become Zero Tests
    # -----------------------------------------------------------------------

    def test_missing_values_explicit_numeric_zero(self) -> None:
        """Explicit numeric zero must parse as Decimal zero and be retained."""
        self.assertEqual(FinancialNormalizer.parse_raw_number("0"), Decimal("0.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("0.0000"), Decimal("0.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("₹ 0.00"), Decimal("0.0000"))

    def test_missing_values_blank_cell(self) -> None:
        """Blank cell must parse as None (missing/unavailable)."""
        self.assertIsNone(FinancialNormalizer.parse_raw_number(""))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("  "))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("\t\n"))

    def test_missing_values_nil(self) -> None:
        """nil and NIL must parse as None (missing/unavailable), never zero."""
        self.assertIsNone(FinancialNormalizer.parse_raw_number("nil"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("NIL"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number(" Nil "))

    def test_missing_values_na(self) -> None:
        """N/A and NA must parse as None (unavailable), never zero."""
        self.assertIsNone(FinancialNormalizer.parse_raw_number("N/A"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("n/a"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("NA"))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("n.a."))

    def test_missing_values_dash_with_no_supporting_convention(self) -> None:
        """Dash without supporting convention must be None, never zero."""
        self.assertIsNone(FinancialNormalizer.parse_raw_number("-", allow_dash_as_zero=False))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("—", allow_dash_as_zero=False))
        self.assertIsNone(FinancialNormalizer.parse_raw_number("–", allow_dash_as_zero=False))

    def test_missing_values_dash_with_explicit_zero_convention(self) -> None:
        """Dash with explicitly documented zero convention parses as zero."""
        self.assertEqual(FinancialNormalizer.parse_raw_number("-", allow_dash_as_zero=True), Decimal("0.0000"))
        self.assertEqual(FinancialNormalizer.parse_raw_number("—", allow_dash_as_zero=True), Decimal("0.0000"))

    def test_calculation_missing_old_value(self) -> None:
        """Missing base (old) value must yield NOT_DISCLOSED status and prevent zero arithmetic."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="PAT", label="PAT", amount=None, status="NOT_DISCLOSED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="PAT", label="PAT", amount=Decimal("100.0000"), status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("PAT", "PAT", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.NOT_DISCLOSED)
        self.assertIsNone(res.absolute_variance)
        self.assertIsNone(res.percentage_change)
        self.assertIn("Base document (Doc doc_a) does not disclose", res.directional_explanation)

    def test_calculation_missing_new_value(self) -> None:
        """Missing comparison (new) value must yield NOT_DISCLOSED status and prevent zero arithmetic."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="PAT", label="PAT", amount=Decimal("100.0000"), status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="PAT", label="PAT", amount=None, status="NOT_DISCLOSED")

        res = FinancialCalculator.compute_pairwise_metric_variance("PAT", "PAT", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.NOT_DISCLOSED)
        self.assertIsNone(res.absolute_variance)
        self.assertIsNone(res.percentage_change)
        self.assertIn("Comparison document (Doc doc_b) does not disclose", res.directional_explanation)

    # -----------------------------------------------------------------------
    # Correction 2: Currency and Scale Normalization Tests
    # -----------------------------------------------------------------------

    def test_normalization_inr_crore_scale_known(self) -> None:
        """INR value with known scale (Lakh) normalizes correctly to INR_CRORE."""
        amt, curr, scale, unit = FinancialNormalizer.normalize_value(
            raw_number=Decimal("500.00"),
            currency="INR",
            scale="LAKH",
            metric_key="REVENUE",
        )
        self.assertEqual(amt, Decimal("5.0000"))
        self.assertEqual(curr, "INR")
        self.assertEqual(scale, "CRORE")
        self.assertEqual(unit, "INR_CRORE")

    def test_normalization_foreign_currency_preserved(self) -> None:
        """Foreign currency (USD) must not be relabeled as INR and must not be converted without approved FX."""
        amt, curr, scale, unit = FinancialNormalizer.normalize_value(
            raw_number=Decimal("150.00"),
            currency="USD",
            scale="MILLION",
            metric_key="REVENUE",
        )
        self.assertEqual(amt, Decimal("150.0000"))
        self.assertEqual(curr, "USD")
        self.assertEqual(scale, "MILLION")
        self.assertEqual(unit, "USD_MILLION")
        self.assertNotEqual(curr, "INR")

    def test_normalization_unknown_currency(self) -> None:
        """Unknown currency must remain UNKNOWN and not defaulted to INR."""
        amt, curr, scale, unit = FinancialNormalizer.normalize_value(
            raw_number=Decimal("100.00"),
            currency="UNKNOWN",
            scale="CRORE",
            metric_key="REVENUE",
        )
        self.assertEqual(curr, "UNKNOWN")
        self.assertEqual(unit, "UNKNOWN_CRORE")
        self.assertNotEqual(curr, "INR")

    def test_normalization_unknown_scale(self) -> None:
        """Unknown scale must remain UNKNOWN without assuming Crore or Thousand."""
        amt, curr, scale, unit = FinancialNormalizer.normalize_value(
            raw_number=Decimal("1000.00"),
            currency="INR",
            scale="UNKNOWN",
            metric_key="REVENUE",
        )
        self.assertEqual(amt, Decimal("1000.0000"))  # Unscaled raw amount
        self.assertEqual(scale, "UNKNOWN")
        self.assertEqual(unit, "INR_UNKNOWN_SCALE")

    def test_normalization_eps_retains_unit(self) -> None:
        """EPS must retain per-share denomination for both INR and foreign currencies."""
        amt_inr, curr_inr, scale_inr, unit_inr = FinancialNormalizer.normalize_value(
            raw_number=Decimal("15.50"),
            currency="INR",
            scale="CRORE",
            metric_key="EPS",
        )
        self.assertEqual(amt_inr, Decimal("15.5000"))
        self.assertEqual(unit_inr, "INR/share")

        amt_usd, curr_usd, scale_usd, unit_usd = FinancialNormalizer.normalize_value(
            raw_number=Decimal("2.25"),
            currency="USD",
            scale="MILLION",
            metric_key="EPS",
        )
        self.assertEqual(amt_usd, Decimal("2.2500"))
        self.assertEqual(unit_usd, "USD/share")

    def test_calculation_incompatible_currencies_blocked(self) -> None:
        """Incompatible currencies (USD vs INR) must block calculation with CURRENCY_MISMATCH."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="REVENUE", label="Revenue", amount=Decimal("100.0000"), currency="INR", unit="INR_CRORE", status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="REVENUE", label="Revenue", amount=Decimal("100.0000"), currency="USD", unit="USD_MILLION", status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("REVENUE", "Revenue", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.CURRENCY_MISMATCH)
        self.assertIsNone(res.absolute_variance)
        self.assertIn("Currencies differ (INR vs USD)", res.directional_explanation)

    # -----------------------------------------------------------------------
    # Correction 3: Conflict Arbitration Hierarchy Tests
    # -----------------------------------------------------------------------

    def test_arbitration_restatement_same_period(self) -> None:
        """Restatement of the SAME reporting period and scope supersedes original with explanation."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            financial_year="FY 2023-24",
            quarter="Q3",
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
        )

        cand_orig = ValueCandidate(
            candidate_id="c_orig",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="Profit After Tax",
            raw_text_value="800.00",
            parsed_number=Decimal("800.00"),
            normalized_amount=Decimal("800.0000"),
            financial_year="FY 2023-24",
            quarter="Q3",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Original PAT 800"),
        )

        cand_restated = ValueCandidate(
            candidate_id="c_rest",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="Restated Profit After Tax",
            raw_text_value="825.00",
            parsed_number=Decimal("825.00"),
            normalized_amount=Decimal("825.0000"),
            financial_year="FY 2023-24",
            quarter="Q3",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=True,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Restated PAT 825"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_orig, cand_restated], meta)
        pat = fvs["PAT"]
        self.assertEqual(pat.amount, Decimal("825.0000"))
        self.assertEqual(pat.selected_candidate_id, "c_rest")
        self.assertEqual(confs["PAT"].status, ConflictStatus.RESOLVED_AUTOMATIC)
        self.assertIn("restated statutory disclosure supersedes original", confs["PAT"].resolution_reason)

    def test_arbitration_restatement_different_period_does_not_override_current(self) -> None:
        """Restatement of a DIFFERENT reporting period (e.g. prior FY) must NOT override current period original."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            financial_year="FY 2023-24",
            quarter="Q3",
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
        )

        cand_current_orig = ValueCandidate(
            candidate_id="c_curr",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Revenue from Operations (Q3 FY24)",
            raw_text_value="10,500.00",
            parsed_number=Decimal("10500.00"),
            normalized_amount=Decimal("10500.0000"),
            financial_year="FY 2023-24",
            quarter="Q3",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Current Q3 FY24 10500"),
        )

        cand_prior_restated = ValueCandidate(
            candidate_id="c_prior_rest",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Restated Revenue (Q3 FY23)",
            raw_text_value="9,200.00",
            parsed_number=Decimal("9200.00"),
            normalized_amount=Decimal("9200.0000"),
            financial_year="FY 2022-23",  # Different period!
            quarter="Q3",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=True,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Restated Prior Q3 FY23 9200"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_current_orig, cand_prior_restated], meta)
        rev = fvs["REVENUE"]
        self.assertEqual(rev.amount, Decimal("10500.0000"))
        self.assertEqual(rev.selected_candidate_id, "c_curr")
        self.assertIn("current period primary disclosure supersedes prior period comparative column", confs["REVENUE"].resolution_reason)

    def test_arbitration_restatement_different_scope_does_not_override_target_scope(self) -> None:
        """Restatement in Standalone scope must NOT override Consolidated candidate when target is Consolidated."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            financial_year="FY 2023-24",
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
        )

        cand_con_orig = ValueCandidate(
            candidate_id="c_con_orig",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="Consolidated PAT",
            raw_text_value="1,200.00",
            parsed_number=Decimal("1200.00"),
            normalized_amount=Decimal("1200.0000"),
            financial_year="FY 2023-24",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Consolidated PAT 1200"),
        )

        cand_std_rest = ValueCandidate(
            candidate_id="c_std_rest",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="Restated Standalone PAT",
            raw_text_value="750.00",
            parsed_number=Decimal("750.00"),
            normalized_amount=Decimal("750.0000"),
            financial_year="FY 2023-24",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,  # Different scope!
            audit_status=AuditStatus.AUDITED,
            is_restated=True,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Restated Standalone PAT 750"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_con_orig, cand_std_rest], meta)
        pat = fvs["PAT"]
        self.assertEqual(pat.amount, Decimal("1200.0000"))
        self.assertEqual(pat.selected_candidate_id, "c_con_orig")
        self.assertIn("scope matches target filing", confs["PAT"].resolution_reason)

    def test_arbitration_conflicting_metric_definitions_marks_uncertain(self) -> None:
        """Conflicting metric definitions (e.g. EBITDA before vs after Ind AS 116) must return UNCERTAIN."""
        meta = DocumentMetadata(doc_id="doc_a", reporting_scope=ReportingScope.CONSOLIDATED)

        cand_pre = ValueCandidate(
            candidate_id="c_pre",
            doc_id="doc_a",
            metric_key="EBITDA",
            raw_label="EBITDA (Pre-Ind AS 116)",
            metric_definition="EBITDA_PRE_IND_AS_116",
            raw_text_value="1,500.00",
            parsed_number=Decimal("1500.00"),
            normalized_amount=Decimal("1500.0000"),
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Pre 1500"),
        )

        cand_post = ValueCandidate(
            candidate_id="c_post",
            doc_id="doc_a",
            metric_key="EBITDA",
            raw_label="EBITDA (Post-Ind AS 116)",
            metric_definition="EBITDA_POST_IND_AS_116",
            raw_text_value="1,650.00",
            parsed_number=Decimal("1650.00"),
            normalized_amount=Decimal("1650.0000"),
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Post 1650"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_pre, cand_post], meta)
        ebitda = fvs["EBITDA"]
        self.assertEqual(ebitda.status, "UNCERTAIN")
        self.assertIsNone(ebitda.amount)
        self.assertEqual(confs["EBITDA"].status, ConflictStatus.UNCERTAIN)
        self.assertIn("Conflicting metric definitions", confs["EBITDA"].resolution_reason)

    def test_arbitration_equal_authority_unresolved_marks_uncertain(self) -> None:
        """Equal authority candidates with divergent numbers must return UNCERTAIN without automated guessing."""
        meta = DocumentMetadata(doc_id="doc_a", reporting_scope=ReportingScope.CONSOLIDATED)

        cand1 = ValueCandidate(
            candidate_id="c1",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Revenue Disclosure A",
            raw_text_value="10,000.00",
            parsed_number=Decimal("10000.00"),
            normalized_amount=Decimal("10000.0000"),
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Rev 10000"),
        )

        cand2 = ValueCandidate(
            candidate_id="c2",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Revenue Disclosure B",
            raw_text_value="10,200.00",
            parsed_number=Decimal("10200.00"),
            normalized_amount=Decimal("10200.0000"),
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Rev 10200"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand1, cand2], meta)
        rev = fvs["REVENUE"]
        self.assertEqual(rev.status, "UNCERTAIN")
        self.assertIsNone(rev.amount)
        self.assertEqual(confs["REVENUE"].status, ConflictStatus.UNCERTAIN)

    def test_arbitration_preservation_of_all_candidates_and_evidence(self) -> None:
        """Verify that all competing candidates and evidence references are completely preserved in conflict resolution."""
        meta = DocumentMetadata(doc_id="doc_a", reporting_scope=ReportingScope.CONSOLIDATED)

        cand1 = ValueCandidate(
            candidate_id="c1",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="PAT Table",
            raw_text_value="500.00",
            parsed_number=Decimal("500.00"),
            normalized_amount=Decimal("500.0000"),
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Table PAT 500"),
        )

        cand2 = ValueCandidate(
            candidate_id="c2",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="PAT Text",
            raw_text_value="520.00",
            parsed_number=Decimal("520.00"),
            normalized_amount=Decimal("520.0000"),
            statement_type=StatementType.MDA_NARRATIVE,
            reporting_scope=ReportingScope.CONSOLIDATED,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Text PAT 520"),
        )

        _, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand1, cand2], meta)
        conf = confs["PAT"]
        self.assertEqual(len(conf.all_candidates), 2)
        candidate_ids = {c.candidate_id for c in conf.all_candidates}
        self.assertEqual(candidate_ids, {"c1", "c2"})
        for c in conf.all_candidates:
            self.assertIsNotNone(c.evidence)
            self.assertIsNotNone(c.evidence.verbatim_snippet)

    def test_scale_conversions_to_crore(self) -> None:
        """Verify deterministic conversion of Lakh, Thousand, Units, Million, Billion to Crore."""
        # Lakh to Crore: 100 Lakh = 1 Crore
        amt_lakh, unit = FinancialNormalizer.normalize_to_crore(Decimal("500.00"), "LAKH", "REVENUE")
        self.assertEqual(amt_lakh, Decimal("5.0000"))
        self.assertEqual(unit, "INR_CRORE")

        # Thousand to Crore: 10,000 Thousand = 1 Crore
        amt_th, _ = FinancialNormalizer.normalize_to_crore(Decimal("10000.00"), "THOUSAND", "REVENUE")
        self.assertEqual(amt_th, Decimal("1.0000"))

        # Million to Crore: 10 Million = 1 Crore
        amt_mn, _ = FinancialNormalizer.normalize_to_crore(Decimal("50.00"), "MILLION", "REVENUE")
        self.assertEqual(amt_mn, Decimal("5.0000"))

        # Billion to Crore: 1 Billion = 100 Crores
        amt_bn, _ = FinancialNormalizer.normalize_to_crore(Decimal("2.50"), "BILLION", "REVENUE")
        self.assertEqual(amt_bn, Decimal("250.0000"))

        # Crore to Crore: 1:1
        amt_cr, _ = FinancialNormalizer.normalize_to_crore(Decimal("123.45"), "CRORE", "REVENUE")
        self.assertEqual(amt_cr, Decimal("123.4500"))

    def test_eps_per_share_remains_in_inr_not_crores(self) -> None:
        """Verify EPS is recognized as a per-share metric and stays in INR rather than Crores."""
        amt_eps, unit_eps = FinancialNormalizer.normalize_to_crore(Decimal("25.50"), "CRORE", "EPS")
        self.assertEqual(amt_eps, Decimal("25.5000"))
        self.assertEqual(unit_eps, "INR/share")

    # -----------------------------------------------------------------------
    # 2. Metric Extraction Tests
    # -----------------------------------------------------------------------

    def test_extract_core_financial_metrics_from_table(self) -> None:
        """Verify extraction of all core metrics from standard tabular P&L and Balance Sheet."""
        pnl_table = create_sample_table(
            table_id="pnl_1",
            sheet_name="Profit and Loss Statement",
            headers=["Particulars", "Quarter ended 31-Dec-2023", "Quarter ended 30-Sep-2023"],
            rows=[
                ["I. Revenue from Operations", "10,500.50", "9,800.00"],
                ["II. Total Income", "10,650.00", "9,920.00"],
                ["III. Total Expenses", "9,200.00", "8,700.00"],
                ["IV. Operating EBITDA", "1,850.00", "1,600.00"],
                ["V. Finance Costs", "250.00", "240.00"],
                ["VI. Depreciation and Amortisation", "350.00", "340.00"],
                ["VII. Exceptional Items", "(15.00)", "0.00"],
                ["VIII. Profit Before Tax", "1,050.00", "880.00"],
                ["IX. Profit After Tax for the Period", "820.00", "690.00"],
                ["X. Basic Earnings Per Share (Rs.)", "5.45", "4.60"],
            ],
        )

        bs_table = create_sample_table(
            table_id="bs_1",
            sheet_name="Balance Sheet",
            headers=["Particulars", "As at 31-Dec-2023", "As at 31-Mar-2023"],
            rows=[
                ["Total Assets", "55,000.00", "52,000.00"],
                ["Current Assets", "18,500.00", "16,000.00"],
                ["Total Liabilities", "32,000.00", "31,000.00"],
                ["Current Liabilities", "12,000.00", "11,500.00"],
                ["Total Borrowings", "15,000.00", "14,500.00"],
                ["Total Equity (Net Worth)", "23,000.00", "21,000.00"],
                ["Cash and Cash Equivalents", "3,500.00", "2,800.00"],
            ],
        )

        cf_table = create_sample_table(
            table_id="cf_1",
            sheet_name="Cash Flow Statement",
            headers=["Particulars", "9 Months ended 31-Dec-2023", "9 Months ended 31-Dec-2022"],
            rows=[
                ["Net Cash generated from Operating Activities", "4,200.00", "3,800.00"],
                ["Net Cash used in Investing Activities", "(2,100.00)", "(1,900.00)"],
                ["Net Cash flow from Financing Activities", "(1,000.00)", "(800.00)"],
            ],
        )

        extraction = DocumentExtractionResult(
            doc_id="doc_a",
            slot=DocumentSlot.DOC_A,
            file_format=SupportedFileFormat.PDF_DIGITAL,
            tables=[pnl_table, bs_table, cf_table],
            text_blocks=[],
            extraction_status="SUCCESS",
        )

        cdoc = ComparisonDocument(
            doc_id="doc_a",
            slot=DocumentSlot.DOC_A,
            original_filename="TataMotors_Q3.pdf",
            file_format=SupportedFileFormat.PDF_DIGITAL,
            file_size_bytes=1024,
            storage_rel_path="documents/doc_a.pdf",
        )

        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Tata Motors Limited",
            document_type="Quarterly Financial Results",
            reporting_scale="CRORE",
            currency="INR",
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
        )

        candidates = FinancialExtractor.extract_candidates(cdoc, extraction, meta)
        keys_extracted = {c.metric_key for c in candidates}

        # Verify Core Metrics
        self.assertIn("REVENUE", keys_extracted)
        self.assertIn("PAT", keys_extracted)
        self.assertIn("PBT", keys_extracted)
        self.assertIn("EBITDA", keys_extracted)
        self.assertIn("TOTAL_ASSETS", keys_extracted)
        self.assertIn("TOTAL_LIABILITIES", keys_extracted)
        self.assertIn("TOTAL_DEBT", keys_extracted)
        self.assertIn("CASH_EQUIVALENTS", keys_extracted)
        self.assertIn("EPS", keys_extracted)
        self.assertIn("OPERATING_CASH_FLOW", keys_extracted)

        # Verify Additional Metrics
        self.assertIn("TOTAL_INCOME", keys_extracted)
        self.assertIn("OPERATING_EXPENSES", keys_extracted)
        self.assertIn("FINANCE_COSTS", keys_extracted)
        self.assertIn("DEPRECIATION", keys_extracted)
        self.assertIn("EXCEPTIONAL_ITEMS", keys_extracted)
        self.assertIn("CURRENT_ASSETS", keys_extracted)
        self.assertIn("CURRENT_LIABILITIES", keys_extracted)
        self.assertIn("NET_WORTH", keys_extracted)
        self.assertIn("INVESTING_CASH_FLOW", keys_extracted)
        self.assertIn("FINANCING_CASH_FLOW", keys_extracted)

        # Verify evidence reference is attached to every candidate
        for c in candidates:
            self.assertIsNotNone(c.evidence)
            self.assertEqual(c.evidence.doc_id, "doc_a")
            self.assertTrue(len(c.evidence.verbatim_snippet) > 0)

    def test_scanned_pdf_and_images_yield_zero_fabricated_candidates(self) -> None:
        """Local mode: Scanned PDFs and images must yield zero fabricated candidates."""
        cdoc = ComparisonDocument(
            doc_id="doc_a",
            slot=DocumentSlot.DOC_A,
            original_filename="Scanned.pdf",
            file_format=SupportedFileFormat.PDF_SCANNED,
            file_size_bytes=1024,
            storage_rel_path="documents/doc_a.pdf",
            extraction_status="OCR_UNAVAILABLE_LOCAL_MODE",
        )
        extraction = DocumentExtractionResult(
            doc_id="doc_a",
            slot=DocumentSlot.DOC_A,
            file_format=SupportedFileFormat.PDF_SCANNED,
            is_scanned=True,
            extraction_status="OCR_UNAVAILABLE_LOCAL_MODE",
        )
        meta = DocumentMetadata(doc_id="doc_a", company_name="Unknown")
        candidates = FinancialExtractor.extract_candidates(cdoc, extraction, meta)
        self.assertEqual(len(candidates), 0)

    # -----------------------------------------------------------------------
    # 3. Conflict Arbitration Tests
    # -----------------------------------------------------------------------

    def test_arbitration_primary_table_over_notes_and_mda(self) -> None:
        """Verify Statement Tier Authority: Primary P&L table supersedes Notes and MD&A snippet."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Tata Motors",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
        )

        cand_primary = ValueCandidate(
            candidate_id="c_primary",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Revenue from Operations",
            raw_text_value="10,500.00",
            parsed_number=Decimal("10500.00"),
            normalized_amount=Decimal("10500.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="P&L 10500"),
        )

        cand_notes = ValueCandidate(
            candidate_id="c_notes",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Segment Revenue",
            raw_text_value="10,480.00",
            parsed_number=Decimal("10480.00"),
            normalized_amount=Decimal("10480.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.NOTES_TO_ACCOUNTS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Notes 10480"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_primary, cand_notes], meta)
        rev = fvs["REVENUE"]
        self.assertEqual(rev.status, "REPORTED")
        self.assertEqual(rev.amount, Decimal("10500.0000"))
        self.assertEqual(rev.selected_candidate_id, "c_primary")
        self.assertEqual(confs["REVENUE"].status, ConflictStatus.RESOLVED_AUTOMATIC)
        self.assertIn("primary financial statement tier", confs["REVENUE"].resolution_reason)

    def test_arbitration_ambiguity_triggers_uncertain(self) -> None:
        """Verify that conflicting candidates with equal authority are flagged UNCERTAIN without guessing."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Tata Motors",
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
        )

        cand1 = ValueCandidate(
            candidate_id="c1",
            doc_id="doc_a",
            metric_key="EBITDA",
            raw_label="Operating EBITDA",
            raw_text_value="1,800.00",
            parsed_number=Decimal("1800.00"),
            normalized_amount=Decimal("1800.0000"),
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="EBITDA 1800"),
        )

        cand2 = ValueCandidate(
            candidate_id="c2",
            doc_id="doc_a",
            metric_key="EBITDA",
            raw_label="Adjusted EBITDA",
            raw_text_value="1,950.00",
            parsed_number=Decimal("1950.00"),
            normalized_amount=Decimal("1950.0000"),
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="EBITDA 1950"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand1, cand2], meta)
        ebitda = fvs["EBITDA"]
        self.assertEqual(ebitda.status, "UNCERTAIN")
        self.assertIsNone(ebitda.amount)
        self.assertEqual(confs["EBITDA"].status, ConflictStatus.UNCERTAIN)
        self.assertEqual(ebitda.fact_classification, "UNCERTAIN")

    def test_arbitration_standalone_scope_preserved_not_overwritten_by_consolidated(self) -> None:
        """Verify Standalone filing prioritizes Standalone candidate without false consolidated subordination."""
        meta_standalone = DocumentMetadata(
            doc_id="doc_a",
            company_name="Tata Motors (Standalone)",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
        )

        cand_standalone = ValueCandidate(
            candidate_id="c_std",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Standalone Revenue",
            raw_text_value="6,500.00",
            parsed_number=Decimal("6500.00"),
            normalized_amount=Decimal("6500.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Standalone 6500"),
        )

        cand_consolidated = ValueCandidate(
            candidate_id="c_con",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Consolidated Group Revenue",
            raw_text_value="10,500.00",
            parsed_number=Decimal("10500.00"),
            normalized_amount=Decimal("10500.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Consolidated 10500"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_standalone, cand_consolidated], meta_standalone)
        rev = fvs["REVENUE"]
        self.assertEqual(rev.status, "REPORTED")
        self.assertEqual(rev.amount, Decimal("6500.0000"))
        self.assertEqual(rev.selected_candidate_id, "c_std")
        self.assertEqual(confs["REVENUE"].status, ConflictStatus.RESOLVED_AUTOMATIC)
        self.assertIn("scope matches target filing (STANDALONE prioritized over CONSOLIDATED)", confs["REVENUE"].resolution_reason)

    def test_arbitration_audited_over_unaudited(self) -> None:
        """Verify Audited figure is prioritized over Unaudited/Limited Review figure."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Tata Motors",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            reporting_scope=ReportingScope.CONSOLIDATED,
        )

        cand_audited = ValueCandidate(
            candidate_id="c_aud",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="Profit for the Year",
            raw_text_value="820.00",
            parsed_number=Decimal("820.00"),
            normalized_amount=Decimal("820.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Audited 820"),
        )

        cand_unaudited = ValueCandidate(
            candidate_id="c_unaud",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="Provisional Profit",
            raw_text_value="850.00",
            parsed_number=Decimal("850.00"),
            normalized_amount=Decimal("850.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.CONSOLIDATED,
            audit_status=AuditStatus.UNAUDITED,
            is_restated=False,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Unaudited 850"),
        )

        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_audited, cand_unaudited], meta)
        self.assertEqual(fvs["PAT"].amount, Decimal("820.0000"))
        self.assertEqual(fvs["PAT"].selected_candidate_id, "c_aud")
        self.assertIn("higher assurance authority", confs["PAT"].resolution_reason)

    def test_calculation_loss_expansion(self) -> None:
        """Loss to Wider Loss: Old PAT -40 Cr, New PAT -100 Cr -> Loss expansion explanation."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="PAT", label="PAT", amount=Decimal("-40.0000"), status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="PAT", label="PAT", amount=Decimal("-100.0000"), status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("PAT", "PAT", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.NON_POSITIVE_BASE)
        self.assertEqual(res.absolute_variance, Decimal("-60.0000"))
        self.assertIsNone(res.percentage_change)
        self.assertIn("Loss expansion", res.directional_explanation)

    def test_calculation_positive_to_zero(self) -> None:
        """Positive base to zero: Old Revenue 100 Cr, New 0 Cr -> -100% variance."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="REVENUE", label="Revenue", amount=Decimal("100.0000"), status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="REVENUE", label="Revenue", amount=Decimal("0.0000"), status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("REVENUE", "Revenue", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.CALCULATED)
        self.assertEqual(res.absolute_variance, Decimal("-100.0000"))
        self.assertEqual(res.percentage_change, Decimal("-100.0000"))
        self.assertEqual(res.display_percentage_change, "-100.00%")

    def test_missing_metric_marked_not_disclosed_never_zero(self) -> None:
        """Verify undisclosed metrics are marked NOT_DISCLOSED and never fabricated as zero."""
        meta = DocumentMetadata(doc_id="doc_a", company_name="Tata Motors")
        fvs, _ = ConflictArbitrator.arbitrate_document_metrics("doc_a", [], meta)
        pat = fvs["PAT"]
        self.assertEqual(pat.status, "NOT_DISCLOSED")
        self.assertIsNone(pat.amount)
        self.assertNotEqual(pat.amount, Decimal("0.0000"))

    # -----------------------------------------------------------------------
    # 4. Deterministic Calculation Tests
    # -----------------------------------------------------------------------

    def test_calculation_positive_to_positive(self) -> None:
        """Verify standard growth: Old 100, New 150 -> Absolute +50, Pct +50.00%."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="REVENUE", label="Revenue", amount=Decimal("100.0000"), status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="REVENUE", label="Revenue", amount=Decimal("150.0000"), status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("REVENUE", "Revenue", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.CALCULATED)
        self.assertEqual(res.absolute_variance, Decimal("50.0000"))
        self.assertEqual(res.percentage_change, Decimal("50.0000"))
        self.assertEqual(res.display_percentage_change, "+50.00%")

    def test_negative_base_turnaround_loss_to_profit(self) -> None:
        """Negative Base: Old PAT -50 Cr, New PAT +20 Cr -> Turnaround explanation, percentage omitted."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="PAT", label="PAT", amount=Decimal("-50.0000"), status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="PAT", label="PAT", amount=Decimal("20.0000"), status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("PAT", "PAT", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.NON_POSITIVE_BASE)
        self.assertEqual(res.absolute_variance, Decimal("70.0000"))
        self.assertIsNone(res.percentage_change)
        self.assertIn("Turnaround", res.directional_explanation)
        self.assertIn("loss", res.directional_explanation.lower())
        self.assertIn("profit", res.directional_explanation.lower())

    def test_positive_to_negative_downturn_profit_to_loss(self) -> None:
        """Profit to Loss: Old PAT +50 Cr, New PAT -20 Cr -> Downturn explanation."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="PAT", label="PAT", amount=Decimal("50.0000"), status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="PAT", label="PAT", amount=Decimal("-20.0000"), status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("PAT", "PAT", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.NON_POSITIVE_BASE)
        self.assertEqual(res.absolute_variance, Decimal("-70.0000"))
        self.assertIsNone(res.percentage_change)
        self.assertIn("Downturn", res.directional_explanation)

    def test_negative_to_negative_loss_reduction(self) -> None:
        """Loss to Smaller Loss: Old PAT -100 Cr, New PAT -40 Cr -> Loss reduction explanation."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="PAT", label="PAT", amount=Decimal("-100.0000"), status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="PAT", label="PAT", amount=Decimal("-40.0000"), status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("PAT", "PAT", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.NON_POSITIVE_BASE)
        self.assertEqual(res.absolute_variance, Decimal("60.0000"))
        self.assertIsNone(res.percentage_change)
        self.assertIn("Loss reduction", res.directional_explanation)

    def test_zero_denominator_division_by_zero_safeguard(self) -> None:
        """Base is zero: Old 0, New 50 -> DIV_BY_ZERO status, percentage undefined narrative."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="REVENUE", label="Revenue", amount=Decimal("0.0000"), status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="REVENUE", label="Revenue", amount=Decimal("50.0000"), status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("REVENUE", "Revenue", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.DIV_BY_ZERO)
        self.assertIsNone(res.percentage_change)
        self.assertEqual(res.absolute_variance, Decimal("50.0000"))
        self.assertIn("percentage undefined", res.directional_explanation)

    def test_currency_mismatch_blocks_calculation(self) -> None:
        """Currency mismatch: Doc A (INR) vs Doc B (USD) -> CURRENCY_MISMATCH status, no variance calculated."""
        fv_base = FinancialValue(doc_id="doc_a", metric_key="REVENUE", label="Revenue", amount=Decimal("100.0000"), currency="INR", status="REPORTED")
        fv_comp = FinancialValue(doc_id="doc_b", metric_key="REVENUE", label="Revenue", amount=Decimal("100.0000"), currency="USD", status="REPORTED")

        res = FinancialCalculator.compute_pairwise_metric_variance("REVENUE", "Revenue", "doc_a", "doc_b", fv_base, fv_comp)
        self.assertEqual(res.status, VarianceStatus.CURRENCY_MISMATCH)
        self.assertIsNone(res.absolute_variance)
        self.assertIsNone(res.percentage_change)

    # -----------------------------------------------------------------------
    # 5. Full Pipeline & REST API Integration Tests
    # -----------------------------------------------------------------------

    def test_api_process_financial_comparison_pipeline(self) -> None:
        """Integration test: Create session, upload filings, POST /process, verify financials and calculations."""
        # 1. Initialize session
        create_res = client.post("/api/compare/session", json={"comparison_mode": "QUICK_COMPARE"})
        self.assertEqual(create_res.status_code, 201)
        session_id = create_res.json()["session_id"]
        token = create_res.json()["session_token"]

        try:
            # 2. Upload synthetic filings
            # Build mini PDFs with financial numbers
            import pymupdf
            doc1 = pymupdf.open()
            page1 = doc1.new_page()
            page1.insert_text((50, 50), "Tata Motors Limited - Unaudited Financial Results for Q3 FY 2023-24 (Quarter ended December 31, 2023). Prepared under Indian Accounting Standards Ind AS.")
            page1.insert_text((50, 70), "Statement of Standalone and Consolidated Financial Results approved by Board of Directors at meeting held in Mumbai Maharashtra India.")
            page1.insert_text((50, 90), "All monetary figures and amounts reported in Rupees in Crores unless specifically stated otherwise.")
            page1.insert_text((50, 110), "Revenue from Operations: 10,500.50")
            page1.insert_text((50, 130), "Profit After Tax: 820.00")
            page1.insert_text((50, 150), "Basic EPS (Rs.): 5.45")
            page1.insert_textbox(pymupdf.Rect(50, 180, 550, 300), "The accompanying notes are an integral part of these financial results and should be read in conjunction with the statutory disclosures. " * 3, fontsize=9)
            pdf1_bytes = doc1.tobytes()
            doc1.close()

            doc2 = pymupdf.open()
            page2 = doc2.new_page()
            page2.insert_text((50, 50), "Maruti Suzuki India Limited - Unaudited Financial Results for Q3 FY 2023-24 (Quarter ended December 31, 2023). Prepared under Indian Accounting Standards Ind AS.")
            page2.insert_text((50, 70), "Statement of Standalone and Consolidated Financial Results approved by Board of Directors at meeting held in New Delhi India.")
            page2.insert_text((50, 90), "All monetary figures and amounts reported in Rupees in Crores unless specifically stated otherwise.")
            page2.insert_text((50, 110), "Revenue from Operations: 12,000.00")
            page2.insert_text((50, 130), "Profit After Tax: 950.00")
            page2.insert_text((50, 150), "Basic EPS (Rs.): 6.20")
            page2.insert_textbox(pymupdf.Rect(50, 180, 550, 300), "The accompanying notes are an integral part of these financial results and should be read in conjunction with the statutory disclosures. " * 3, fontsize=9)
            pdf2_bytes = doc2.tobytes()
            doc2.close()

            upload_res = client.post(
                f"/api/compare/session/{session_id}/upload",
                headers={"X-Session-Token": token},
                files=[
                    ("files", ("DocA.pdf", pdf1_bytes, "application/pdf")),
                    ("files", ("DocB.pdf", pdf2_bytes, "application/pdf")),
                ],
            )
            self.assertEqual(upload_res.status_code, 200)

            # 3. POST /process pipeline
            proc_res = client.post(
                f"/api/compare/session/{session_id}/process",
                headers={"X-Session-Token": token},
            )
            self.assertEqual(proc_res.status_code, 200)
            proc_data = proc_res.json()
            self.assertEqual(proc_data["current_stage"], "COMPLETED")
            self.assertTrue(proc_data["is_completed"])
            self.assertIn("EXTRACTING_FINANCIAL_DATA", proc_data["completed_stages"])
            self.assertIn("RESOLVING_CONFLICTS", proc_data["completed_stages"])
            self.assertIn("COMPUTING_CALCULATIONS", proc_data["completed_stages"])

            # 4. GET /financials
            fin_res = client.get(
                f"/api/compare/session/{session_id}/financials",
                headers={"X-Session-Token": token},
            )
            self.assertEqual(fin_res.status_code, 200)
            fin_data = fin_res.json()
            self.assertIn("REVENUE", fin_data["financial_values"])
            self.assertIn("PAT", fin_data["financial_values"])
            self.assertIn("doc_a", fin_data["financial_values"]["REVENUE"])
            self.assertIn("doc_b", fin_data["financial_values"]["REVENUE"])

            # 5. GET /calculations
            calc_res = client.get(
                f"/api/compare/session/{session_id}/calculations",
                headers={"X-Session-Token": token},
            )
            self.assertEqual(calc_res.status_code, 200)
            calc_data = calc_res.json()
            self.assertGreaterEqual(len(calc_data["variances"]), 1)

            # Verify math on REVENUE (10500.50 vs 12000.00)
            rev_calcs = [c for c in calc_data["variances"] if c["metric_key"] == "REVENUE"]
            self.assertTrue(len(rev_calcs) >= 1)
            rev_c = rev_calcs[0]
            self.assertEqual(rev_c["status"], "CALCULATED")
            self.assertAlmostEqual(float(rev_c["absolute_variance"]), 1499.50, places=2)

            # 6. GET /status recovery
            stat_res = client.get(
                f"/api/compare/session/{session_id}/status",
                headers={"X-Session-Token": token},
            )
            self.assertEqual(stat_res.status_code, 200)
            self.assertTrue(stat_res.json()["is_completed"])

        finally:
            # 7. Cleanup
            client.delete(f"/api/compare/session/{session_id}", headers={"X-Session-Token": token})

    def test_arbitration_unknown_period_candidate_alone_is_uncertain(self) -> None:
        """Phase 2: Single candidate with unverified period must be marked UNCERTAIN."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Bharat Alpha Engineering Limited",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            reporting_scope=ReportingScope.STANDALONE,
        )
        cand_unknown = ValueCandidate(
            candidate_id="c_unverified",
            doc_id="doc_a",
            metric_key="TOTAL_DEBT",
            raw_label="Borrowings",
            raw_text_value="450.00",
            parsed_number=Decimal("450.00"),
            normalized_amount=Decimal("450.0000"),
            financial_year=None,  # Blank header, unverified period
            statement_type=StatementType.BALANCE_SHEET,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            extraction_confidence="LOW",
            evidence=EvidenceReference(evidence_id="ev_u1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Borrowings 450.00"),
        )
        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_unknown], meta)
        debt = fvs["TOTAL_DEBT"]
        self.assertEqual(debt.status, "UNCERTAIN")
        self.assertEqual(debt.fact_classification, "UNCERTAIN")
        self.assertIsNone(debt.amount, "Unverified period candidate must have amount=None to prevent deceptive calculations")
        self.assertEqual(debt.display_amount, "Uncertain (Unverified Period)")
        self.assertIsNotNone(debt.evidence, "Source evidence must be preserved for user inspection")

    def test_arbitration_unknown_period_competing_with_verified_current_period(self) -> None:
        """Phase 2: Verified current-period candidate wins over unverified blank-header candidate."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Bharat Alpha Engineering Limited",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            reporting_scope=ReportingScope.STANDALONE,
        )
        cand_verified = ValueCandidate(
            candidate_id="c_verified",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Revenue from operations",
            raw_text_value="12,500.00",
            parsed_number=Decimal("12500.00"),
            normalized_amount=Decimal("12500.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev_v", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Revenue 12500"),
        )
        cand_unverified = ValueCandidate(
            candidate_id="c_unverified",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Gross Turnover",
            raw_text_value="12,480.00",
            parsed_number=Decimal("12480.00"),
            normalized_amount=Decimal("12480.0000"),
            financial_year=None,
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev_u", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Gross Turnover 12480"),
        )
        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_verified, cand_unverified], meta)
        rev = fvs["REVENUE"]
        self.assertEqual(rev.status, "REPORTED")
        self.assertEqual(rev.amount, Decimal("12500.0000"))
        self.assertEqual(rev.selected_candidate_id, "c_verified")

    def test_arbitration_unknown_period_candidate_with_higher_raw_score_is_uncertain(self) -> None:
        """Phase 2: High score cannot override missing essential period identity."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Bharat Alpha Engineering Limited",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            reporting_scope=ReportingScope.STANDALONE,
        )
        # Candidate A: Primary Table Cell, Audited, Standalone -> Score = 100 + 10 + 40 + 50 + 20 = 220
        # But financial_year is None (unverified)
        cand_high_tier_unverified = ValueCandidate(
            candidate_id="c_table_unverified",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="Net Profit",
            raw_text_value="1,200.00",
            parsed_number=Decimal("1200.00"),
            normalized_amount=Decimal("1200.0000"),
            financial_year=None,
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev_t", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Table Net Profit 1200"),
        )
        # Candidate B: Narrative Text, Unaudited, Standalone -> Score = 100 + 70 + 15 + 10 + 5 = 200
        # Has verified financial_year = "FY 2024-25"
        cand_low_tier_verified = ValueCandidate(
            candidate_id="c_text_verified",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="Reported Net Profit",
            raw_text_value="1,150.00",
            parsed_number=Decimal("1150.00"),
            normalized_amount=Decimal("1150.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.MDA_NARRATIVE,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.UNAUDITED,
            extraction_method="TEXT_PATTERN",
            evidence=EvidenceReference(evidence_id="ev_n", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Text Net Profit 1150"),
        )
        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_high_tier_unverified, cand_low_tier_verified], meta)
        pat = fvs["PAT"]
        self.assertEqual(pat.status, "UNCERTAIN")
        self.assertEqual(pat.fact_classification, "UNCERTAIN")
        self.assertIsNone(pat.amount, "Unverified period candidate must NOT become DOCUMENT_FACT through high score")
        self.assertEqual(pat.display_amount, "Uncertain (Period Identity Conflict)")
        self.assertIn("lacks verified period match", confs["PAT"].resolution_reason)

    def test_arbitration_multiple_unknown_period_candidates_differing_amounts(self) -> None:
        """Phase 2: Multiple candidates with unidentified periods and different amounts -> UNCERTAIN."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Bharat Alpha Engineering Limited",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            reporting_scope=ReportingScope.STANDALONE,
        )
        cand1 = ValueCandidate(
            candidate_id="c_u1",
            doc_id="doc_a",
            metric_key="EBITDA",
            raw_label="EBITDA Col 1",
            raw_text_value="2,500.00",
            parsed_number=Decimal("2500.00"),
            normalized_amount=Decimal("2500.0000"),
            financial_year=None,
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="EBITDA 2500"),
        )
        cand2 = ValueCandidate(
            candidate_id="c_u2",
            doc_id="doc_a",
            metric_key="EBITDA",
            raw_label="EBITDA Col 2",
            raw_text_value="2,200.00",
            parsed_number=Decimal("2200.00"),
            normalized_amount=Decimal("2200.0000"),
            financial_year=None,
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="EBITDA 2200"),
        )
        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand1, cand2], meta)
        ebitda = fvs["EBITDA"]
        self.assertEqual(ebitda.status, "UNCERTAIN")
        self.assertIsNone(ebitda.amount)
        self.assertEqual(ebitda.display_amount, "Uncertain (Unverified Period)")

    def test_arbitration_verified_current_period_versus_verified_prior_period(self) -> None:
        """Phase 2: Verified current-period candidate decisively beats verified prior-period comparative."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Bharat Alpha Engineering Limited",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            reporting_scope=ReportingScope.STANDALONE,
        )
        cand_curr = ValueCandidate(
            candidate_id="c_curr",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Revenue from operations",
            raw_text_value="12,500.00",
            parsed_number=Decimal("12500.00"),
            normalized_amount=Decimal("12500.0000"),
            financial_year="FY 2024-25",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Revenue 12500"),
        )
        cand_prior = ValueCandidate(
            candidate_id="c_prior",
            doc_id="doc_a",
            metric_key="REVENUE",
            raw_label="Revenue from operations",
            raw_text_value="10,200.00",
            parsed_number=Decimal("10200.00"),
            normalized_amount=Decimal("10200.0000"),
            financial_year="FY 2023-24",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            is_restated=False,
            extraction_method="TABLE_CELL",
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Revenue 10200"),
        )
        fvs, confs = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand_curr, cand_prior], meta)
        rev = fvs["REVENUE"]
        self.assertEqual(rev.status, "REPORTED")
        self.assertEqual(rev.amount, Decimal("12500.0000"))
        self.assertEqual(rev.selected_candidate_id, "c_curr")

    def test_arbitration_unknown_financial_year_on_both_candidate_and_metadata(self) -> None:
        """Phase 2: Both candidate and metadata financial year UNKNOWN must never match."""
        meta = DocumentMetadata(
            doc_id="doc_a",
            company_name="Unknown Entity",
            financial_year="Unknown",
            reporting_scope=ReportingScope.STANDALONE,
        )
        cand = ValueCandidate(
            candidate_id="c1",
            doc_id="doc_a",
            metric_key="EPS",
            raw_label="Earnings Per Share",
            raw_text_value="15.50",
            parsed_number=Decimal("15.50"),
            normalized_amount=Decimal("15.5000"),
            financial_year="Unknown",
            statement_type=StatementType.PROFIT_AND_LOSS,
            reporting_scope=ReportingScope.STANDALONE,
            audit_status=AuditStatus.AUDITED,
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="EPS 15.50"),
        )
        self.assertFalse(
            ConflictArbitrator._is_period_affirmatively_matched(cand, meta),
            "Two Unknown financial years must never affirmatively match"
        )
        fvs, _ = ConflictArbitrator.arbitrate_document_metrics("doc_a", [cand], meta)
        self.assertEqual(fvs["EPS"].status, "UNCERTAIN")

    def test_arbitration_annual_vs_quarterly_mismatch(self) -> None:
        """Phase 2: Annual vs Quarterly granularity mismatch must fail period matching."""
        meta_annual = DocumentMetadata(
            doc_id="doc_a",
            company_name="Bharat Alpha",
            financial_year="FY 2024-25",
            reporting_period="Annual",
            quarter=None,
        )
        cand_quarterly = ValueCandidate(
            candidate_id="c_q",
            doc_id="doc_a",
            metric_key="PAT",
            raw_label="PAT",
            raw_text_value="350.00",
            financial_year="FY 2024-25",
            quarter="Q3",
            evidence=EvidenceReference(evidence_id="ev1", doc_id="doc_a", document_name="doc.pdf", verbatim_snippet="Q3 PAT 350"),
        )
        self.assertFalse(
            ConflictArbitrator._is_period_affirmatively_matched(cand_quarterly, meta_annual),
            "Quarterly candidate must not match Annual report metadata"
        )

        meta_quarterly = DocumentMetadata(
            doc_id="doc_b",
            company_name="Bharat Alpha",
            financial_year="FY 2024-25",
            reporting_period="Quarterly",
            quarter="Q2",
        )
        cand_annual = ValueCandidate(
            candidate_id="c_ann",
            doc_id="doc_b",
            metric_key="PAT",
            raw_label="PAT",
            raw_text_value="1400.00",
            financial_year="FY 2024-25",
            quarter=None,
            evidence=EvidenceReference(evidence_id="ev2", doc_id="doc_b", document_name="doc.pdf", verbatim_snippet="Annual PAT 1400"),
        )
        self.assertFalse(
            ConflictArbitrator._is_period_affirmatively_matched(cand_annual, meta_quarterly),
            "Annual candidate must not match Quarterly Q2 metadata"
        )


class TestSlice4FinancialCorrections(unittest.TestCase):
    """Phase 6: Comprehensive unit & integration tests for Manual Financial Corrections,
    Deterministic Recalculation, and LIFO Undo stack.
    """

    def setUp(self) -> None:
        self.created_sessions: list[str] = []
        self.session_tokens: dict[str, str] = {}

    def tearDown(self) -> None:
        for sid in self.created_sessions:
            try:
                session_store.terminate_session(sid)
            except Exception:
                pass

    def _create_fixture_session(self, num_docs: int = 2) -> tuple[ComparisonSession, str]:
        """Helper to create a fully initialized session fixture with comparison result."""
        session, raw_token = session_store.create_session()
        sid = session.session_id
        self.created_sessions.append(sid)
        self.session_tokens[sid] = raw_token
        session_store.grant_consent(sid)

        docs = []
        meta = {}
        letters = ["a", "b", "c"]
        companies = ["Tata Motors Limited", "Maruti Suzuki Limited", "Mahindra & Mahindra"]
        for i in range(num_docs):
            doc_id = f"doc_{letters[i]}"
            docs.append(ComparisonDocument(
                doc_id=doc_id,
                slot=f"doc_{letters[i]}",
                original_filename=f"Report_{letters[i].upper()}.pdf",
                file_format=SupportedFileFormat.PDF_DIGITAL,
                file_size_bytes=1024,
                storage_rel_path=f"documents/{doc_id}.pdf",
            ))
            meta[doc_id] = DocumentMetadata(
                doc_id=doc_id,
                company_name=companies[i % len(companies)],
                company_identifier=f"CIN00{i+1}",
                financial_year="FY 2023-24",
                currency="INR",
                reporting_scale="CRORE",
                reporting_scope=ReportingScope.CONSOLIDATED,
                audit_status=AuditStatus.AUDITED,
            )

        fvs: dict[str, dict[str, FinancialValue]] = {
            "REVENUE": {
                "doc_a": FinancialValue(
                    doc_id="doc_a",
                    metric_key="REVENUE",
                    label="Revenue from operations",
                    amount=Decimal("1000.00"),
                    original_amount=Decimal("1000.00"),
                    reported_amount=Decimal("1000.00"),
                    unit="INR_CRORE",
                    currency="INR",
                    statement_type=StatementType.PROFIT_AND_LOSS,
                    fact_classification="DOCUMENT_FACT",
                    status="REPORTED",
                    evidence=EvidenceReference(
                        evidence_id="ev_rev_a",
                        doc_id="doc_a",
                        document_name="Report_A.pdf",
                        page_number=5,
                        verbatim_snippet="Revenue from operations: 1,000.00 Cr",
                    ),
                ),
                "doc_b": FinancialValue(
                    doc_id="doc_b",
                    metric_key="REVENUE",
                    label="Revenue from operations",
                    amount=Decimal("1500.00"),
                    original_amount=Decimal("1500.00"),
                    reported_amount=Decimal("1500.00"),
                    unit="INR_CRORE",
                    currency="INR",
                    statement_type=StatementType.PROFIT_AND_LOSS,
                    fact_classification="DOCUMENT_FACT",
                    status="REPORTED",
                    evidence=EvidenceReference(
                        evidence_id="ev_rev_b",
                        doc_id="doc_b",
                        document_name="Report_B.pdf",
                        page_number=4,
                        verbatim_snippet="Revenue: 1,500.00 Cr",
                    ),
                ),
            },
            "PAT": {
                "doc_a": FinancialValue(
                    doc_id="doc_a",
                    metric_key="PAT",
                    label="Profit after tax",
                    amount=Decimal("100.00"),
                    original_amount=Decimal("100.00"),
                    reported_amount=Decimal("100.00"),
                    unit="INR_CRORE",
                    currency="INR",
                    statement_type=StatementType.PROFIT_AND_LOSS,
                    fact_classification="DOCUMENT_FACT",
                    status="REPORTED",
                ),
                "doc_b": FinancialValue(
                    doc_id="doc_b",
                    metric_key="PAT",
                    label="Profit after tax",
                    amount=Decimal("200.00"),
                    original_amount=Decimal("200.00"),
                    reported_amount=Decimal("200.00"),
                    unit="INR_CRORE",
                    currency="INR",
                    statement_type=StatementType.PROFIT_AND_LOSS,
                    fact_classification="DOCUMENT_FACT",
                    status="REPORTED",
                ),
            },
            "TOTAL_ASSETS": {
                "doc_a": FinancialValue(
                    doc_id="doc_a",
                    metric_key="TOTAL_ASSETS",
                    label="Total Assets",
                    amount=Decimal("5000.00"),
                    original_amount=Decimal("5000.00"),
                    reported_amount=Decimal("5000.00"),
                    unit="INR_CRORE",
                    currency="INR",
                    statement_type=StatementType.BALANCE_SHEET,
                    fact_classification="DOCUMENT_FACT",
                    status="REPORTED",
                ),
                "doc_b": FinancialValue(
                    doc_id="doc_b",
                    metric_key="TOTAL_ASSETS",
                    label="Total Assets",
                    amount=Decimal("6000.00"),
                    original_amount=Decimal("6000.00"),
                    reported_amount=Decimal("6000.00"),
                    unit="INR_CRORE",
                    currency="INR",
                    statement_type=StatementType.BALANCE_SHEET,
                    fact_classification="DOCUMENT_FACT",
                    status="REPORTED",
                ),
            },
            "EPS": {
                "doc_a": FinancialValue(
                    doc_id="doc_a",
                    metric_key="EPS",
                    label="Earnings Per Share",
                    amount=Decimal("10.00"),
                    original_amount=Decimal("10.00"),
                    reported_amount=Decimal("10.00"),
                    unit="INR",
                    currency="INR",
                    statement_type=StatementType.PROFIT_AND_LOSS,
                    fact_classification="DOCUMENT_FACT",
                    status="REPORTED",
                ),
                "doc_b": FinancialValue(
                    doc_id="doc_b",
                    metric_key="EPS",
                    label="Earnings Per Share",
                    amount=Decimal("15.00"),
                    original_amount=Decimal("15.00"),
                    reported_amount=Decimal("15.00"),
                    unit="INR",
                    currency="INR",
                    statement_type=StatementType.PROFIT_AND_LOSS,
                    fact_classification="DOCUMENT_FACT",
                    status="REPORTED",
                ),
            },
        }

        if num_docs >= 3:
            fvs["REVENUE"]["doc_c"] = FinancialValue(
                doc_id="doc_c",
                metric_key="REVENUE",
                label="Revenue from operations",
                amount=Decimal("2000.00"),
                original_amount=Decimal("2000.00"),
                reported_amount=Decimal("2000.00"),
                unit="INR_CRORE",
                currency="INR",
                statement_type=StatementType.PROFIT_AND_LOSS,
                fact_classification="DOCUMENT_FACT",
                status="REPORTED",
            )

        doc_ids = [d.doc_id for d in docs]
        variances = FinancialCalculator.compute_all_variances(fvs, doc_ids)

        compat = CompatibilityReport(
            session_id=sid,
            is_comparable=True,
            overall_status=CompatibilityStatus.COMPATIBLE,
            blocker_count=0,
            warning_count=0,
            findings=[],
        )

        comp_result = ComparisonResult(
            session_id=sid,
            mode="LOCAL_MODE",
            documents=docs,
            metadata=meta,
            compatibility=compat,
            financial_values=fvs,
            variances=variances,
        )

        session_store.save_session_documents(sid, docs)
        session_store.save_session_metadata(sid, meta)
        session_store.save_session_compatibility(sid, compat)
        session_store.save_session_comparison_result(sid, comp_result)
        session_store.save_session_financials(sid, fvs, {}, {})
        session_store.save_session_calculations(sid, variances)

        return session, raw_token

    def test_apply_financial_correction_valid(self) -> None:
        """Phase 6: Valid correction updates amount, sets USER_ENTERED, and stores metadata."""
        session, _ = self._create_fixture_session()
        sid = session.session_id

        res, record, _ = session_store.apply_financial_correction(
            sid,
            "doc_a",
            "REVENUE",
            Decimal("1200.00"),
            reason="Audited restatement footnote 4",
        )

        val_a = res.financial_values["REVENUE"]["doc_a"]
        self.assertEqual(val_a.amount, Decimal("1200.00"))
        self.assertTrue(val_a.is_user_corrected)
        self.assertEqual(val_a.fact_classification, "USER_ENTERED")
        self.assertEqual(val_a.user_entered_amount, Decimal("1200.00"))
        self.assertEqual(val_a.correction_reason, "Audited restatement footnote 4")
        self.assertIsNotNone(val_a.correction_timestamp)

        self.assertEqual(record.doc_id, "doc_a")
        self.assertEqual(record.metric_key, "REVENUE")
        self.assertEqual(record.previous_effective_amount, Decimal("1000.00"))
        self.assertEqual(record.new_user_entered_amount, Decimal("1200.00"))
        self.assertEqual(record.original_extracted_amount, Decimal("1000.00"))

    def test_original_amount_and_reported_amount_preserved(self) -> None:
        """Phase 6: Original extracted amount, reported amount, and source evidence must be preserved."""
        session, _ = self._create_fixture_session()
        sid = session.session_id

        res, _, _ = session_store.apply_financial_correction(
            sid,
            "doc_a",
            "REVENUE",
            Decimal("1350.50"),
            reason="OCR missed digit",
        )

        val_a = res.financial_values["REVENUE"]["doc_a"]
        self.assertEqual(val_a.original_amount, Decimal("1000.00"))
        self.assertEqual(val_a.reported_amount, Decimal("1000.00"))
        self.assertIsNotNone(val_a.evidence)
        self.assertEqual(val_a.evidence.verbatim_snippet, "Revenue from operations: 1,000.00 Cr")

    def test_negative_amounts_allowed_and_total_assets_blocked(self) -> None:
        """Phase 6: Negative amounts permitted for PAT/EBITDA/OCF/EPS, but blocked for TOTAL_ASSETS."""
        session, token = self._create_fixture_session()
        sid = session.session_id

        # PAT net loss is permitted
        res_pat, _, _ = session_store.apply_financial_correction(
            sid, "doc_a", "PAT", Decimal("-50.00"), reason="Net loss reported"
        )
        self.assertEqual(res_pat.financial_values["PAT"]["doc_a"].amount, Decimal("-50.00"))

        # EPS loss is permitted
        res_eps, _, _ = session_store.apply_financial_correction(
            sid, "doc_a", "EPS", Decimal("-2.50"), reason="Negative EPS"
        )
        self.assertEqual(res_eps.financial_values["EPS"]["doc_a"].amount, Decimal("-2.50"))

        # TOTAL_ASSETS negative must be blocked at store level
        with self.assertRaises(ValueError):
            session_store.apply_financial_correction(
                sid, "doc_a", "TOTAL_ASSETS", Decimal("-100.00")
            )

        # TOTAL_ASSETS negative must be blocked at API level with 400
        resp = client.post(
            f"/api/compare/session/{sid}/financials/correct",
            headers={"x-session-token": token},
            json={
                "doc_id": "doc_a",
                "metric_key": "TOTAL_ASSETS",
                "corrected_amount": -100.0,
                "reason": "Invalid test",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Total Assets cannot be negative", resp.json()["detail"])

    def test_finite_decimal_validation(self) -> None:
        """Phase 6: Validation rejects non-finite decimals (NaN, Infinity)."""
        # Finite decimal succeeds
        req = FinancialCorrectionRequest(
            doc_id="doc_a",
            metric_key="REVENUE",
            corrected_amount=Decimal("123.45"),
        )
        self.assertEqual(req.corrected_amount, Decimal("123.45"))

        # Non-finite raises ValueError
        with self.assertRaises(ValueError):
            FinancialCorrectionRequest(
                doc_id="doc_a",
                metric_key="REVENUE",
                corrected_amount=Decimal("NaN"),
            )

        with self.assertRaises(ValueError):
            FinancialCorrectionRequest(
                doc_id="doc_a",
                metric_key="REVENUE",
                corrected_amount=Decimal("Infinity"),
            )

        with self.assertRaises(ValueError):
            FinancialCorrectionRequest(
                doc_id="doc_a",
                metric_key="REVENUE",
                corrected_amount=Decimal("-Infinity"),
            )

    def test_deterministic_recalculation_pairwise_variances(self) -> None:
        """Phase 6: Recalculates pairwise variance and percentage change with Decimal precision."""
        session, _ = self._create_fixture_session()
        sid = session.session_id

        # Initial: doc_a=1000, doc_b=1500 -> diff = +500 (+50.0%)
        # Correct doc_a to 1200: doc_a=1200, doc_b=1500 -> diff = +300 (+25.0%)
        res, _, _ = session_store.apply_financial_correction(
            sid, "doc_a", "REVENUE", Decimal("1200.00")
        )

        var_ab = next(
            (v for v in res.variances if v.metric_key == "REVENUE" and v.base_doc_id == "doc_a" and v.comparison_doc_id == "doc_b"),
            None,
        )
        self.assertIsNotNone(var_ab)
        self.assertEqual(var_ab.base_value, Decimal("1200.00"))
        self.assertEqual(var_ab.comparison_value, Decimal("1500.00"))
        self.assertEqual(var_ab.absolute_variance, Decimal("300.00"))
        self.assertEqual(var_ab.percentage_change, Decimal("25.00"))
        self.assertEqual(var_ab.display_absolute_variance, "₹300.00 Cr")
        self.assertEqual(var_ab.display_percentage_change, "+25.00%")
        self.assertIsNone(var_ab.directional_explanation)

    def test_unrelated_metrics_untouched(self) -> None:
        """Phase 6: Correcting one metric must leave other metrics and unaffected documents untouched."""
        session, _ = self._create_fixture_session()
        sid = session.session_id

        res, _, _ = session_store.apply_financial_correction(
            sid, "doc_a", "REVENUE", Decimal("1250.00")
        )

        # doc_b REVENUE untouched
        val_b_rev = res.financial_values["REVENUE"]["doc_b"]
        self.assertEqual(val_b_rev.amount, Decimal("1500.00"))
        self.assertFalse(val_b_rev.is_user_corrected)
        self.assertEqual(val_b_rev.fact_classification, "DOCUMENT_FACT")

        # PAT untouched
        val_a_pat = res.financial_values["PAT"]["doc_a"]
        self.assertEqual(val_a_pat.amount, Decimal("100.00"))
        self.assertFalse(val_a_pat.is_user_corrected)

        # TOTAL_ASSETS untouched
        val_a_ta = res.financial_values["TOTAL_ASSETS"]["doc_a"]
        self.assertEqual(val_a_ta.amount, Decimal("5000.00"))
        self.assertFalse(val_a_ta.is_user_corrected)

    def test_multi_document_pairwise_updates(self) -> None:
        """Phase 6: Correcting a document in 3-doc comparison updates all pairs involving that document."""
        session, _ = self._create_fixture_session(num_docs=3)
        sid = session.session_id

        # doc_a: 1000, doc_b: 1500, doc_c: 2000
        # Correct doc_a to 1200
        res, _, _ = session_store.apply_financial_correction(
            sid, "doc_a", "REVENUE", Decimal("1200.00")
        )

        # Pair a -> b: 1500 - 1200 = +300 (+25.0%)
        var_ab = next(v for v in res.variances if v.metric_key == "REVENUE" and v.base_doc_id == "doc_a" and v.comparison_doc_id == "doc_b")
        self.assertEqual(var_ab.absolute_variance, Decimal("300.00"))
        self.assertEqual(var_ab.percentage_change, Decimal("25.00"))

        # Pair a -> c: 2000 - 1200 = +800 (+66.67%)
        var_ac = next(v for v in res.variances if v.metric_key == "REVENUE" and v.base_doc_id == "doc_a" and v.comparison_doc_id == "doc_c")
        self.assertEqual(var_ac.absolute_variance, Decimal("800.00"))

        # Pair b -> c: untouched (2000 - 1500 = +500)
        var_bc = next(v for v in res.variances if v.metric_key == "REVENUE" and v.base_doc_id == "doc_b" and v.comparison_doc_id == "doc_c")
        self.assertEqual(var_bc.base_value, Decimal("1500.00"))
        self.assertEqual(var_bc.comparison_value, Decimal("2000.00"))
        self.assertEqual(var_bc.absolute_variance, Decimal("500.00"))

    def test_undo_latest_correction_lifo(self) -> None:
        """Phase 6: LIFO undo restores previous value, resets flags, and recomputes variances."""
        session, _ = self._create_fixture_session()
        sid = session.session_id

        # Apply correction: 1000 -> 1200
        session_store.apply_financial_correction(sid, "doc_a", "REVENUE", Decimal("1200.00"))

        # Undo correction
        res, undone_rec, remaining, _ = session_store.undo_latest_correction(sid)
        self.assertEqual(remaining, 0)
        self.assertEqual(undone_rec.doc_id, "doc_a")
        self.assertEqual(undone_rec.metric_key, "REVENUE")

        val_a = res.financial_values["REVENUE"]["doc_a"]
        self.assertEqual(val_a.amount, Decimal("1000.00"))
        self.assertFalse(val_a.is_user_corrected)
        self.assertEqual(val_a.fact_classification, "DOCUMENT_FACT")
        self.assertIsNone(val_a.user_entered_amount)

        # Variance restored: 1500 - 1000 = +500 (+50.0%)
        var_ab = next(v for v in res.variances if v.metric_key == "REVENUE" and v.base_doc_id == "doc_a" and v.comparison_doc_id == "doc_b")
        self.assertEqual(var_ab.absolute_variance, Decimal("500.00"))
        self.assertEqual(var_ab.percentage_change, Decimal("50.00"))

    def test_repeated_corrections_same_metric(self) -> None:
        """Phase 6: Repeated corrections to same metric undo in strict reverse order."""
        session, _ = self._create_fixture_session()
        sid = session.session_id

        # Original: 100
        # Correction 1: 150
        session_store.apply_financial_correction(sid, "doc_a", "PAT", Decimal("150.00"))
        # Correction 2: 200
        session_store.apply_financial_correction(sid, "doc_a", "PAT", Decimal("200.00"))

        # Undo 1 -> should revert to 150 (still user-corrected)
        res1, rec1, rem1, _ = session_store.undo_latest_correction(sid)
        self.assertEqual(rem1, 1)
        self.assertEqual(rec1.new_user_entered_amount, Decimal("200.00"))
        val1 = res1.financial_values["PAT"]["doc_a"]
        self.assertEqual(val1.amount, Decimal("150.00"))
        self.assertTrue(val1.is_user_corrected)
        self.assertEqual(val1.user_entered_amount, Decimal("150.00"))

        # Undo 2 -> should revert to 100 (original extracted DOCUMENT_FACT)
        res2, rec2, rem2, _ = session_store.undo_latest_correction(sid)
        self.assertEqual(rem2, 0)
        self.assertEqual(rec2.new_user_entered_amount, Decimal("150.00"))
        val2 = res2.financial_values["PAT"]["doc_a"]
        self.assertEqual(val2.amount, Decimal("100.00"))
        self.assertFalse(val2.is_user_corrected)
        self.assertEqual(val2.fact_classification, "DOCUMENT_FACT")

    def test_empty_undo_stack_error(self) -> None:
        """Phase 6: Attempting undo on empty stack raises ValueError and API returns 400."""
        session, token = self._create_fixture_session()
        sid = session.session_id

        with self.assertRaises(ValueError):
            session_store.undo_latest_correction(sid)

        resp = client.post(
            f"/api/compare/session/{sid}/financials/undo",
            headers={"x-session-token": token},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("remain to undo", resp.json()["detail"])

    def test_session_isolation_corrections(self) -> None:
        """Phase 6: Corrections in session A must have zero side-effects on session B."""
        session_a, _ = self._create_fixture_session()
        session_b, _ = self._create_fixture_session()
        sid_a = session_a.session_id
        sid_b = session_b.session_id

        # Correct session A
        session_store.apply_financial_correction(sid_a, "doc_a", "REVENUE", Decimal("9999.00"))

        # Session B must be completely unaffected
        res_b = session_store.get_session_comparison_result(sid_b)
        self.assertIsNotNone(res_b)
        val_b_a = res_b.financial_values["REVENUE"]["doc_a"]
        self.assertEqual(val_b_a.amount, Decimal("1000.00"))
        self.assertFalse(val_b_a.is_user_corrected)
        self.assertEqual(val_b_a.fact_classification, "DOCUMENT_FACT")

    def test_api_endpoints_correct_undo_and_get(self) -> None:
        """Phase 6: Full round-trip testing of Endpoints 10.1, 10.2, and 10.3."""
        session, token = self._create_fixture_session()
        sid = session.session_id
        headers = {"x-session-token": token}

        # 1. GET corrections -> empty list
        resp_get_empty = client.get(f"/api/compare/session/{sid}/financials/corrections", headers=headers)
        self.assertEqual(resp_get_empty.status_code, 200)
        self.assertEqual(resp_get_empty.json()["corrections_count"], 0)

        # 2. POST correct -> updates value
        resp_corr = client.post(
            f"/api/compare/session/{sid}/financials/correct",
            headers=headers,
            json={
                "doc_id": "doc_a",
                "metric_key": "REVENUE",
                "corrected_amount": 1250.0,
                "reason": "Test restatement",
            },
        )
        self.assertEqual(resp_corr.status_code, 200)
        data_corr = resp_corr.json()
        self.assertEqual(data_corr["status"], "CORRECTED")
        self.assertEqual(Decimal(str(data_corr["correction"]["new_user_entered_amount"])), Decimal("1250.0000"))
        self.assertEqual(
            Decimal(str(data_corr["comparison_result"]["financial_values"]["REVENUE"]["doc_a"]["amount"])),
            Decimal("1250.0000"),
        )
        self.assertTrue(
            data_corr["comparison_result"]["financial_values"]["REVENUE"]["doc_a"]["is_user_corrected"]
        )

        # 3. GET corrections -> 1 record
        resp_get_1 = client.get(f"/api/compare/session/{sid}/financials/corrections", headers=headers)
        self.assertEqual(resp_get_1.status_code, 200)
        self.assertEqual(resp_get_1.json()["corrections_count"], 1)

        # 4. POST undo -> reverts value
        resp_undo = client.post(f"/api/compare/session/{sid}/financials/undo", headers=headers)
        self.assertEqual(resp_undo.status_code, 200)
        data_undo = resp_undo.json()
        self.assertEqual(data_undo["status"], "UNDONE")
        self.assertEqual(data_undo["remaining_corrections_count"], 0)
        self.assertEqual(
            Decimal(str(data_undo["comparison_result"]["financial_values"]["REVENUE"]["doc_a"]["amount"])),
            Decimal("1000.00"),
        )
        self.assertFalse(
            data_undo["comparison_result"]["financial_values"]["REVENUE"]["doc_a"]["is_user_corrected"]
        )

    def test_gap_a_original_financial_values_integrity(self) -> None:
        """Gap A: reported_amount remains unchanged, amount reflects effective value,
        USER_ENTERED retained, evidence intact, and original extracted amount restored on undo."""
        session, _ = self._create_fixture_session()
        sid = session.session_id

        # Initial check
        fvs, _, _ = session_store.get_session_financials(sid)
        orig_rev = fvs["REVENUE"]["doc_a"]
        self.assertEqual(orig_rev.reported_amount, Decimal("1000.00"))
        self.assertEqual(orig_rev.amount, Decimal("1000.00"))
        self.assertEqual(orig_rev.fact_classification, "DOCUMENT_FACT")
        self.assertFalse(orig_rev.is_user_corrected)
        self.assertIsNotNone(orig_rev.evidence)
        ev_snippet = orig_rev.evidence.verbatim_snippet

        # Apply correction
        res, record, _ = session_store.apply_financial_correction(
            sid, "doc_a", "REVENUE", Decimal("1450.75"), reason="Footnote 8 adjustment"
        )
        corrected_rev = res.financial_values["REVENUE"]["doc_a"]
        # 1. reported_amount remains unchanged
        self.assertEqual(corrected_rev.reported_amount, Decimal("1000.00"))
        # 2. amount reflects current effective value
        self.assertEqual(corrected_rev.amount, Decimal("1450.7500"))
        # 3. USER_ENTERED classification is retained
        self.assertEqual(corrected_rev.fact_classification, "USER_ENTERED")
        self.assertTrue(corrected_rev.is_user_corrected)
        # 4. Original evidence references remain intact
        self.assertIsNotNone(corrected_rev.evidence)
        self.assertEqual(corrected_rev.evidence.verbatim_snippet, ev_snippet)

        # 5. Original extracted amount can be restored
        res_undo, _, remaining, _ = session_store.undo_latest_correction(sid)
        self.assertEqual(remaining, 0)
        restored_rev = res_undo.financial_values["REVENUE"]["doc_a"]
        self.assertEqual(restored_rev.amount, Decimal("1000.00"))
        self.assertEqual(restored_rev.reported_amount, Decimal("1000.00"))
        self.assertEqual(restored_rev.fact_classification, "DOCUMENT_FACT")
        self.assertFalse(restored_rev.is_user_corrected)
        self.assertIsNone(restored_rev.user_entered_amount)
        self.assertEqual(restored_rev.evidence.verbatim_snippet, ev_snippet)

    def test_gap_b_units_scale_and_precision_preservation(self) -> None:
        """Gap B: Correcting EPS preserves INR/share, Crore metrics preserve scale,
        currency is not silently converted, and Decimal precision/rounding is exact."""
        session, _ = self._create_fixture_session()
        sid = session.session_id

        # 1. Correct EPS -> preserves unit and currency
        res_eps, _, _ = session_store.apply_financial_correction(
            sid, "doc_a", "EPS", Decimal("18.45678"), reason="Restated EPS"
        )
        eps_val = res_eps.financial_values["EPS"]["doc_a"]
        self.assertEqual(eps_val.unit, "INR")
        self.assertEqual(eps_val.currency, "INR")
        # 4-place rounding with ROUND_HALF_UP: 18.45678 -> 18.4568
        self.assertEqual(eps_val.amount, Decimal("18.4568"))

        # 2. Correct REVENUE -> preserves INR_CRORE scale
        res_rev, _, _ = session_store.apply_financial_correction(
            sid, "doc_a", "REVENUE", Decimal("2500.12345"), reason="Crore scale test"
        )
        rev_val = res_rev.financial_values["REVENUE"]["doc_a"]
        self.assertEqual(rev_val.unit, "INR_CRORE")
        self.assertEqual(rev_val.currency, "INR")
        self.assertEqual(rev_val.amount, Decimal("2500.1235"))

    def test_gap_c_numerical_validation_strict_rejections_and_valid_values(self) -> None:
        """Gap C: API rejects NaN, Infinity, -Infinity, empty, null, and malformed inputs;
        accepts valid zero and metric-appropriate negative values while blocking negative Total Assets."""
        session, token = self._create_fixture_session()
        sid = session.session_id
        headers = {"x-session-token": token}

        # Null / None input -> 422
        r_null = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": None
        })
        self.assertEqual(r_null.status_code, 422)

        # Empty string input -> 422
        r_empty = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": ""
        })
        self.assertEqual(r_empty.status_code, 422)

        # Malformed string input -> 422
        r_malformed = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": "invalid_num"
        })
        self.assertEqual(r_malformed.status_code, 422)

        # NaN string -> 422
        r_nan = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": "NaN"
        })
        self.assertEqual(r_nan.status_code, 422)

        # Infinity string -> 422
        r_inf = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": "Infinity"
        })
        self.assertEqual(r_inf.status_code, 422)

        # Negative infinity string -> 422
        r_ninf = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": "-Infinity"
        })
        self.assertEqual(r_ninf.status_code, 422)

        # Valid zero -> 200 (e.g. Total Debt = 0 for debt-free company)
        r_zero = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "TOTAL_DEBT", "corrected_amount": 0.0
        })
        self.assertEqual(r_zero.status_code, 200)
        self.assertEqual(Decimal(str(r_zero.json()["comparison_result"]["financial_values"]["TOTAL_DEBT"]["doc_a"]["amount"])), Decimal("0.0000"))

        # Valid metric-appropriate negative value -> 200 (PAT net loss)
        r_loss = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "PAT", "corrected_amount": -75.5
        })
        self.assertEqual(r_loss.status_code, 200)
        self.assertEqual(Decimal(str(r_loss.json()["comparison_result"]["financial_values"]["PAT"]["doc_a"]["amount"])), Decimal("-75.5000"))

        # Negative TOTAL_ASSETS -> 400
        r_neg_assets = client.post(f"/api/compare/session/{sid}/financials/correct", headers=headers, json={
            "doc_id": "doc_a", "metric_key": "TOTAL_ASSETS", "corrected_amount": -10.0
        })
        self.assertEqual(r_neg_assets.status_code, 400)
        self.assertIn("Total Assets cannot be negative", r_neg_assets.json()["detail"])

    def test_gap_d_atomicity_and_simulated_persistence_failure(self) -> None:
        """Gap D: Simulated disk/persistence failure rolls back cleanly without leaving orphan journals,
        stale calculations, or partial undo state."""
        from unittest.mock import patch
        session, _ = self._create_fixture_session()
        sid = session.session_id

        # Verify initial state
        initial_corrections = session_store.get_session_corrections(sid)
        self.assertEqual(len(initial_corrections), 0)

        # 1. Simulate failure during correction save
        with patch.object(session_store, "save_session_calculations", side_effect=IOError("Simulated disk error")):
            with self.assertRaises(IOError):
                session_store.apply_financial_correction(sid, "doc_a", "REVENUE", Decimal("9999.00"))

        # Check clean rollback: no orphan correction record, revenue remains original
        corrs_after_fail = session_store.get_session_corrections(sid)
        self.assertEqual(len(corrs_after_fail), 0)
        fvs_after_fail, _, _ = session_store.get_session_financials(sid)
        self.assertEqual(fvs_after_fail["REVENUE"]["doc_a"].amount, Decimal("1000.00"))
        self.assertFalse(fvs_after_fail["REVENUE"]["doc_a"].is_user_corrected)

        # Apply a successful correction first
        session_store.apply_financial_correction(sid, "doc_a", "REVENUE", Decimal("1200.00"))
        self.assertEqual(len(session_store.get_session_corrections(sid)), 1)

        # 2. Simulate failure during undo save
        with patch.object(session_store, "save_session_calculations", side_effect=IOError("Simulated disk error on undo")):
            with self.assertRaises(IOError):
                session_store.undo_latest_correction(sid)

        # Check clean rollback on failed undo: journal is NOT lost, revenue remains user-corrected
        corrs_after_undo_fail = session_store.get_session_corrections(sid)
        self.assertEqual(len(corrs_after_undo_fail), 1)
        fvs_after_undo_fail, _, _ = session_store.get_session_financials(sid)
        self.assertEqual(fvs_after_undo_fail["REVENUE"]["doc_a"].amount, Decimal("1200.0000"))
        self.assertTrue(fvs_after_undo_fail["REVENUE"]["doc_a"].is_user_corrected)

    def test_gap_e_session_isolation_authentication_and_cleanup(self) -> None:
        """Gap E: Invalid tokens are rejected (401), expired sessions rejected,
        and terminating a session purges the correction journal from disk."""
        session, token = self._create_fixture_session()
        sid = session.session_id

        # Invalid token rejected
        resp_invalid = client.post(
            f"/api/compare/session/{sid}/financials/correct",
            headers={"x-session-token": "invalid_token_123"},
            json={"doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": 1100.0},
        )
        self.assertEqual(resp_invalid.status_code, 401)

        # Missing token rejected
        resp_missing = client.post(
            f"/api/compare/session/{sid}/financials/correct",
            json={"doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": 1100.0},
        )
        self.assertEqual(resp_missing.status_code, 401)

        # Apply a correction
        session_store.apply_financial_correction(sid, "doc_a", "REVENUE", Decimal("1100.00"))
        corr_path = session_store.resolve_session_path(sid) / "extracted" / "corrections.json"
        self.assertTrue(corr_path.exists())

        # Terminate session -> verify corrections journal disappears
        session_store.terminate_session(sid)
        self.assertFalse(corr_path.exists())

        # Terminated session cannot be corrected or undone
        with self.assertRaises(ValueError):
            session_store.apply_financial_correction(sid, "doc_a", "REVENUE", Decimal("1200.00"))
        with self.assertRaises(ValueError):
            session_store.undo_latest_correction(sid)

    def test_gap_f_executive_summary_narrative_and_ai_consent(self) -> None:
        """Gap F: Executive summary updates deterministically, discloses user adjustments,
        triggers no automatic AI dispatch, and invalidates stale consent hashes."""
        from app.services.compare_synthesis_service import CompareSynthesisService
        session, token = self._create_fixture_session()
        sid = session.session_id
        headers = {"x-session-token": token}

        # Generate initial local synthesis
        documents = session_store.get_session_documents(sid)
        meta_map = session_store.get_session_metadata(sid)
        comp_report = session_store.get_session_compatibility(sid)
        fvs, _, _ = session_store.get_session_financials(sid)
        variances = session_store.get_session_calculations(sid)
        summary, _, _ = CompareSynthesisService._generate_local_synthesis(
            documents=documents,
            metadata_map=meta_map,
            compatibility=comp_report,
            financial_values=fvs,
            variances=variances,
        )
        comp_res = session_store.get_session_comparison_result(sid)
        comp_res.executive_summary = summary
        session_store.save_session_comparison_result(sid, comp_res)

        # Get initial consent preview payload hash via API
        resp_prev1 = client.get(f"/api/compare/session/{sid}/transmission-preview", headers=headers)
        self.assertEqual(resp_prev1.status_code, 200)
        hash_before = resp_prev1.json()["payload_hash"]

        # Apply correction via API
        resp_corr = client.post(
            f"/api/compare/session/{sid}/financials/correct",
            headers=headers,
            json={"doc_id": "doc_a", "metric_key": "REVENUE", "corrected_amount": 1200.0},
        )
        self.assertEqual(resp_corr.status_code, 200)
        updated_res = session_store.get_session_comparison_result(sid)

        # 1. Executive summary observations refreshed
        self.assertIsNotNone(updated_res.executive_summary)
        self.assertIn("user-entered adjustments", updated_res.executive_summary.overview_story)
        # Check that core changes reflect 1500 - 1200 = 300 (+25.00%)
        self.assertTrue(any("25.00%" in s for s in updated_res.executive_summary.core_positive_changes))

        # 2. Consent payload hash changes after correction -> invalidating prior consent
        resp_prev2 = client.get(f"/api/compare/session/{sid}/transmission-preview", headers=headers)
        self.assertEqual(resp_prev2.status_code, 200)
        hash_after = resp_prev2.json()["payload_hash"]
        self.assertNotEqual(hash_before, hash_after)

    def test_gap_g_pdf_and_excel_export_verification(self) -> None:
        """Gap G: PDF exports corrected values with asterisk and disclaimer footnote;
        Excel exports mark USER_ENTERED in Column 11 and preserve raw value in Column 7."""
        import openpyxl
        import pymupdf
        from app.services.export_pdf_service import ExportPdfService
        from app.services.export_excel_service import ExportExcelService

        session, _ = self._create_fixture_session()
        sid = session.session_id

        # Correct REVENUE to 1250.00
        res, _, _ = session_store.apply_financial_correction(
            sid, "doc_a", "REVENUE", Decimal("1250.00"), reason="Audited 10-K adjustment"
        )

        # 1. Test PDF Export
        pdf_bytes = ExportPdfService.generate_comparison_pdf(res)
        self.assertGreater(len(pdf_bytes), 1000)
        doc_pdf = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pdf_text = ""
        for p in doc_pdf:
            pdf_text += p.get_text()

        norm_pdf_text = pdf_text.replace("\xa0", " ").replace("\u2010", "-")
        # PDF contains corrected figure with asterisk
        self.assertIn("₹1,250.00 Cr *", norm_pdf_text)
        # PDF contains explanatory footnote
        self.assertIn("user-entered manual adjustments", norm_pdf_text)

        # 2. Test Excel Export
        xlsx_bytes = ExportExcelService.generate_comparison_workbook(res)
        self.assertGreater(len(xlsx_bytes), 1000)
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        ws_matrix = wb["Financial Metrics"]

        # Find row for REVENUE doc_a
        found_corrected_row = False
        for row in range(2, ws_matrix.max_row + 1):
            m_key = ws_matrix.cell(row=row, column=1).value
            slot_str = str(ws_matrix.cell(row=row, column=3).value or "")
            if m_key == "REVENUE" and "A" in slot_str:
                found_corrected_row = True
                orig_val = ws_matrix.cell(row=row, column=7).value
                norm_val = ws_matrix.cell(row=row, column=10).value
                status_val = ws_matrix.cell(row=row, column=11).value
                self.assertEqual(float(orig_val), 1000.0)
                self.assertEqual(float(norm_val), 1250.0)
                self.assertEqual(status_val, "USER_ENTERED")
                break
        self.assertTrue(found_corrected_row, "Did not find REVENUE doc_a in Excel Financial Metrics sheet")


if __name__ == "__main__":
    unittest.main()
