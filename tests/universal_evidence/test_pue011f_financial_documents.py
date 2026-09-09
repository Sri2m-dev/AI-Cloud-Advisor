from decimal import Decimal

import pytest

from universal_evidence.documents import SemanticDecisionState
from universal_evidence.financial import (
    AggregationEligibility,
    ConceptRole,
    FinancialDocumentInput,
    FinancialLineEvidence,
    FinancialValueEvidence,
    ReconciliationState,
    assert_financial_scope,
    normalize_financial_document,
)
from universal_evidence.financial.models import FinancialConcept


def evidence(*, lines=(), values=(), tenant="tenant-a", set_id="set-1"):
    return FinancialDocumentInput(
        set_id,
        "org",
        tenant,
        "prospect",
        "analysis",
        0.81,
        tuple({item.region_id for item in (*lines, *values)}),
        tuple(lines),
        tuple(values),
    )


def line(row, quantity=None, unit_price=None, amount=None, currency="USD", **kwargs):
    return FinancialLineEvidence(
        "line-region",
        f"row:{row}",
        quantity=quantity,
        unit_price=unit_price,
        amount=amount,
        currency_candidate=currency,
        **kwargs,
    )


def value(label, amount, *, region="summary-region", currency="USD", **kwargs):
    return FinancialValueEvidence(
        region,
        f"cell:{label}",
        label,
        amount,
        currency_candidate=currency,
        currency_source="metadata",
        **kwargs,
    )


def concepts(result, concept):
    return [item for item in result.concept_observations if item.concept is concept]


def reconciliation(result, relationship):
    return next(item for item in result.reconciliations if item.relationship == relationship)


def test_line_item_decimal_normalization_and_arithmetic_reconciliation():
    result = normalize_financial_document(
        evidence(lines=(line(1, "2", "5.25", "10.50"),))
    )
    amount = concepts(result, FinancialConcept.LINE_ITEM_AMOUNT)[0]
    assert amount.normalized_amount == Decimal("10.50")
    assert amount.aggregation_eligibility is AggregationEligibility.ELIGIBLE_DETAIL
    assert reconciliation(
        result, "QUANTITY_X_UNIT_PRICE_TO_LINE_AMOUNT"
    ).state is ReconciliationState.RECONCILED


def test_amount_only_line_is_valid_detail_with_insufficient_arithmetic_evidence():
    result = normalize_financial_document(evidence(lines=(line(1, amount="12.00"),)))
    assert result.eligible_detail_total == Decimal("12.00")
    assert reconciliation(
        result, "QUANTITY_X_UNIT_PRICE_TO_LINE_AMOUNT"
    ).state is ReconciliationState.INSUFFICIENT_EVIDENCE


def test_subtotal_is_control_only_and_never_double_counted():
    result = normalize_financial_document(
        evidence(
            lines=(line(1, 2, 5, 10), line(2, 1, 7, 7)),
            values=(value("Subtotal", 17),),
        )
    )
    subtotal = concepts(result, FinancialConcept.SUBTOTAL)[0]
    assert subtotal.role is ConceptRole.CONTROL
    assert subtotal.aggregation_eligibility is AggregationEligibility.CONTROL_ONLY
    assert result.eligible_detail_total == Decimal("17")
    assert reconciliation(result, "LINE_ITEMS_TO_SUBTOTAL").state is ReconciliationState.RECONCILED


def test_subtotal_mismatch_is_preserved_and_blocks_aggregation():
    result = normalize_financial_document(
        evidence(lines=(line(1, 2, 5, 10),), values=(value("Subtotal", 12),))
    )
    check = reconciliation(result, "LINE_ITEMS_TO_SUBTOTAL")
    assert check.state is ReconciliationState.MISMATCH
    assert check.expected == Decimal("10")
    assert check.observed == Decimal("12")
    assert not result.aggregation_authorized


def test_tax_discount_credit_fee_and_total_due_reconcile_separately():
    result = normalize_financial_document(
        evidence(
            lines=(line(1, 2, 50, 100),),
            values=(
                value("Subtotal", 100),
                value("Tax", 10),
                value("Service Fee", 5),
                value("Discount", 3),
                value("Credit", 2),
                value("Total Due", 110),
            ),
        )
    )
    assert result.tax_total == Decimal("10")
    assert concepts(result, FinancialConcept.DISCOUNT)[0].signed_effect == Decimal("-3")
    assert concepts(result, FinancialConcept.CREDIT)[0].signed_effect == Decimal("-2")
    assert concepts(result, FinancialConcept.FEE)[0].signed_effect == Decimal("5")
    assert result.gross_payable == Decimal("110")
    assert reconciliation(result, "COMPONENTS_TO_TOTAL_DUE").state is ReconciliationState.RECONCILED


def test_multiple_tax_components_remain_independent():
    result = normalize_financial_document(
        evidence(
            lines=(line(1, amount=100),),
            values=(value("Tax", 5), value("VAT", 7), value("Total Due", 112)),
        )
    )
    assert [item.normalized_amount for item in concepts(result, FinancialConcept.TAX)] == [
        Decimal("5"),
        Decimal("7"),
    ]


def test_balance_total_due_monthly_annual_and_period_dates_are_distinct():
    result = normalize_financial_document(
        evidence(
            values=(
                value("Total Due", 100),
                value("Balance", 40),
                value("Monthly Equivalent", 10),
                value("Annual Amount", 120),
                value("Billing Period", "2026-01"),
                value("Invoice Date", "2026-02-01"),
                value("Due Date", "2026-03-01"),
            )
        )
    )
    assert concepts(result, FinancialConcept.BALANCE)[0].role is ConceptRole.STATE
    assert concepts(result, FinancialConcept.TOTAL_DUE)[0].role is ConceptRole.CONTROL
    assert concepts(result, FinancialConcept.MONTHLY_EQUIVALENT)[0].role is ConceptRole.DERIVED
    assert concepts(result, FinancialConcept.ANNUAL_AMOUNT)[0].role is ConceptRole.DERIVED
    assert concepts(result, FinancialConcept.BILLING_PERIOD)
    assert concepts(result, FinancialConcept.INVOICE_DATE)
    assert concepts(result, FinancialConcept.DUE_DATE)


def test_currency_reuses_p1_authority_contract_and_blocks_ambiguous_or_mixed():
    governed = normalize_financial_document(evidence(lines=(line(1, amount=10),)))
    ambiguous = normalize_financial_document(
        evidence(lines=(line(1, amount=10, currency="$"),))
    )
    mixed = normalize_financial_document(
        evidence(lines=(line(1, amount=10, currency="USD"), line(2, amount=5, currency="EUR")))
    )
    formatted = normalize_financial_document(
        evidence(
            lines=(line(1, amount=10, currency=None),),
            values=(value("Subtotal", 10, currency=None, number_format="$#,##0.00"),),
        )
    )
    assert governed.currency.governed
    assert not ambiguous.aggregation_authorized
    assert mixed.currency.conflicted
    assert not mixed.aggregation_authorized
    assert not formatted.aggregation_authorized
    assert "number_format" in formatted.currency.evidence


def test_formula_cache_uncertainty_blocks_without_changing_source_value():
    result = normalize_financial_document(
        evidence(
            values=(value("Subtotal", 10, formula="=SUM(A1:A2)"),),
            lines=(line(1, amount=10),),
        )
    )
    observed = concepts(result, FinancialConcept.SUBTOTAL)[0]
    assert observed.formula_uncertain
    assert observed.source_value == 10
    assert not result.aggregation_authorized


def test_unknown_and_false_positive_controls_are_not_forced():
    result = normalize_financial_document(
        evidence(
            values=(
                value("Metric Total", 99),
                value("Department Amount", 50),
                value("Country Tax Rate", "10%"),
            )
        )
    )
    assert not concepts(result, FinancialConcept.TOTAL_DUE)
    assert len(concepts(result, FinancialConcept.MONETARY_AMOUNT)) == 2
    assert concepts(result, FinancialConcept.TAX_RATE)
    assert result.eligible_detail_total is None


def test_rounding_tolerance_and_determinism():
    source = evidence(lines=(line(1, "3", "3.333", "10.00"),))
    first = normalize_financial_document(source, tolerance=Decimal("0.01"))
    replay = normalize_financial_document(source, tolerance=Decimal("0.01"))
    assert reconciliation(
        first, "QUANTITY_X_UNIT_PRICE_TO_LINE_AMOUNT"
    ).state is ReconciliationState.RECONCILED
    assert first.fingerprint == replay.fingerprint


def test_financial_sets_remain_independent_and_nonfinancial_regions_are_excluded():
    first = normalize_financial_document(
        evidence(lines=(line(1, amount=10),), set_id="invoice-set-a")
    )
    second = normalize_financial_document(
        evidence(lines=(line(1, amount=20),), set_id="invoice-set-b")
    )
    assignment = evidence(set_id="assignment-set")
    assert first.eligible_detail_total == Decimal("10")
    assert second.eligible_detail_total == Decimal("20")
    assert first.fingerprint != second.fingerprint
    assert not assignment.lines and not assignment.values


def test_scope_isolation_and_no_business_dedup_or_publication():
    left = evidence(lines=(line(1, amount=10),), tenant="tenant-a")
    right = evidence(lines=(line(1, amount=10),), tenant="tenant-b")
    with pytest.raises(PermissionError):
        assert_financial_scope(left, right)
    result = normalize_financial_document(left)
    assert result.business_document_fingerprint is None
    assert all(
        item.decision_state is SemanticDecisionState.CANDIDATE
        for item in result.concept_observations
    )
    assert not hasattr(result, "source_facts")
    assert not hasattr(result, "optimization_opportunities")
    assert not hasattr(result, "published_observations")
