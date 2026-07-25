from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from business_service_posture import (
    BusinessServicePosture,
    PostureAvailability,
    PostureDimension,
    PostureDimensionResult,
)
from data_fabric.foundation import TenantContext
from execution_outcome import (
    CompensationPlan,
    ExecutionPlan,
    ExecutionRecord,
    ExecutionState,
    OutcomeCriterion,
    OutcomeObservation,
    OutcomePlan,
    OutcomeState,
    OutcomeVerification,
)
from financial_decision_product import (
    AllocationResult,
    CostRecord,
    FinancialDecisionError,
    FinancialDecisionProduct,
    FinancialEvidenceReference,
    ForecastAvailability,
    ForecastRecord,
    ReconciliationState,
    RecordState,
    SavingsState,
)
from policy_approval import AuthorityScope
from recommendation_decision import (
    Actor,
    ActorType,
    Alternative,
    Decision,
    DecisionDisposition,
    Recommendation,
    RecommendationState,
)

NOW = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
BASE_START = NOW - timedelta(days=60)
BASE_END = NOW - timedelta(days=30)
ACTUAL_START = BASE_END
ACTUAL_END = NOW


def context(name="a"):
    return TenantContext(f"org-{name}", f"tenant-{name}")


def evidence(name, ctx=None):
    ctx = ctx or context()
    return FinancialEvidenceReference(
        f"ev-{name}",
        ctx.organization_id,
        ctx.tenant_id,
        "canonical-cost",
        name,
        f"hash-{name}",
        f"lineage-{name}",
        f"provenance-{name}",
    )


def cost(name, amount, *, ctx=None, actual=False, currency="USD", service="svc-1"):
    ctx = ctx or context()
    return CostRecord(
        f"cost-{name}",
        ctx.organization_id,
        ctx.tenant_id,
        service,
        "app-1",
        amount,
        currency,
        ACTUAL_START if actual else BASE_START,
        ACTUAL_END if actual else BASE_END,
        evidence(name, ctx),
    )


def allocation(baseline, amount=None, *, ctx=None, service="svc-1"):
    ctx = ctx or context()
    return AllocationResult(
        "allocation-1",
        ctx.organization_id,
        ctx.tenant_id,
        service,
        baseline.cost_id,
        baseline.amount if amount is None else amount,
        baseline.currency,
        baseline.period_start,
        baseline.period_end,
        "existing-enterprise-financial-model-v1",
        evidence("allocation", ctx),
    )


def forecast(
    baseline,
    amount=70,
    *,
    ctx=None,
    availability=ForecastAvailability.AVAILABLE,
    currency=None,
):
    ctx = ctx or context()
    return ForecastRecord(
        "forecast-1",
        ctx.organization_id,
        ctx.tenant_id,
        baseline.business_service_id,
        availability,
        None if availability is ForecastAvailability.MISSING else amount,
        currency or baseline.currency,
        baseline.period_start,
        baseline.period_end,
        ACTUAL_START,
        ACTUAL_END,
        "existing-deterministic-trend",
        "v1",
        NOW - timedelta(hours=1),
        0.91,
        {"quality": "certified", "source": "ForecastingService"},
        evidence("forecast", ctx),
    )


def posture(ctx=None, *, service="svc-1"):
    ctx = ctx or context()
    dimensions = {
        dimension: PostureDimensionResult(
            dimension,
            PostureAvailability.AVAILABLE,
            80,
            "wp-007",
            NOW,
            0,
            (),
            {"source": "business_service_posture"},
            1.0,
            "domain_input_available",
        )
        for dimension in PostureDimension
    }
    return BusinessServicePosture(
        ctx.organization_id,
        ctx.tenant_id,
        service,
        1,
        1,
        NOW,
        dimensions,
    )


def recommendation_and_decision(ctx=None):
    ctx = ctx or context()
    recommendation = Recommendation(
        "rec-1",
        ctx.organization_id,
        ctx.tenant_id,
        1,
        "cost posture",
        "remediate",
        "reduce cost",
        (
            Alternative("do-nothing", "No action", "No savings"),
            Alternative("right-size", "Right size", "Lower cost"),
        ),
        "pkg-1",
        "package-hash",
        Actor("proposer", ActorType.HUMAN),
        RecommendationState.APPROVED,
        NOW,
        assumptions=("stable workload",),
        lineage_refs=("lineage-rec",),
        provenance_refs=("provenance-rec",),
    )
    decision = Decision(
        "decision-1",
        ctx.organization_id,
        ctx.tenant_id,
        "rec-1",
        1,
        DecisionDisposition.APPROVE,
        Actor("approver", ActorType.HUMAN),
        "AUTHORIZED",
        "AVAILABLE",
        "approved",
        NOW,
    )
    return recommendation, decision


def execution_chain(ctx=None, *, verified=True, command_only=False):
    ctx = ctx or context()
    requester = Actor("requester", ActorType.HUMAN)
    executor = Actor("executor", ActorType.HUMAN)
    plan = ExecutionPlan(
        "plan-1",
        ctx.organization_id,
        ctx.tenant_id,
        "rec-1",
        1,
        "decision-1",
        1,
        "pkg-1",
        "package-hash",
        "evaluation-1",
        "approval",
        "approval-1",
        AuthorityScope("remediate", "application", "app-1"),
        "mock",
        "remediate",
        ("resource_id",),
        requester,
        executor,
        {"resource_id": "app-1"},
        OutcomePlan(
            {"cost": 100},
            (OutcomeCriterion("cost-lower", "cost", "<=", 100),),
            ("outcome-cost",),
            NOW + timedelta(days=1),
        ),
        CompensationPlan(("outcome_not_achieved",), ("restore",)),
        NOW,
        "plan-hash",
    )
    execution = ExecutionRecord(
        "execution-1",
        ctx.organization_id,
        ctx.tenant_id,
        "plan-1",
        "plan-hash",
        ExecutionState.AWAITING_VERIFICATION,
        "Completed",
        "mock",
        executor,
        NOW,
        NOW,
        {"external_calls": 0},
    )
    if command_only:
        return plan, execution, None
    observation = OutcomeObservation(
        ctx.organization_id,
        ctx.tenant_id,
        "cost",
        70,
        "outcome-cost",
        "outcome-hash",
        "mock",
        NOW,
        "outcome-lineage",
        "outcome-provenance",
    )
    verification = OutcomeVerification(
        "verification-1",
        ctx.organization_id,
        ctx.tenant_id,
        "execution-1",
        Actor("verifier", ActorType.HUMAN),
        NOW,
        OutcomeState.VERIFIED if verified else OutcomeState.NOT_VERIFIED,
        ("verified" if verified else "failed",),
        (observation,),
        "verification-hash",
    )
    return plan, execution, verification


def complete_product(*, actual_amount=70):
    ctx = context()
    product = FinancialDecisionProduct(ctx)
    rec, decision = recommendation_and_decision(ctx)
    baseline = cost("baseline", 100, ctx=ctx)
    actual = cost("actual", actual_amount, ctx=ctx, actual=True)
    allocated = allocation(baseline, ctx=ctx)
    predicted = forecast(baseline, ctx=ctx)
    alternative = product.create_alternative(
        alternative_id="alternative-1",
        recommendation=rec,
        decision=decision,
        posture=posture(ctx),
        resource_id="app-1",
        baseline=baseline,
        allocation=allocated,
        forecast=predicted,
        assumptions=("stable workload",),
    )
    reconciled = product.reconcile(
        reconciliation_id="reconciliation-1",
        business_service_id="svc-1",
        baseline=baseline,
        actual=actual,
        allocation=allocated,
    )
    plan, execution, verification = execution_chain(ctx)
    return (
        ctx,
        product,
        rec,
        decision,
        baseline,
        actual,
        allocated,
        predicted,
        alternative,
        reconciled,
        plan,
        execution,
        verification,
    )


def attribute(bundle, **overrides):
    (
        _,
        product,
        rec,
        decision,
        baseline,
        actual,
        _,
        _,
        alternative,
        reconciled,
        plan,
        execution,
        verification,
    ) = bundle
    values = {
        "savings_id": "savings-1",
        "recommendation": rec,
        "decision": decision,
        "alternative": alternative,
        "reconciliation": reconciled,
        "baseline": baseline,
        "actual": actual,
        "plan": plan,
        "execution": execution,
        "verification": verification,
        "recorded_at": NOW,
    }
    values.update(overrides)
    return product.attribute_realized_savings(**values)


def test_complete_financial_alternative_reuses_governed_inputs():
    bundle = complete_product()
    alternative = bundle[8]
    assert alternative.baseline_cost == 100
    assert alternative.projected_cost == 70
    assert alternative.projected_savings == 30
    assert alternative.forecast_availability is ForecastAvailability.AVAILABLE
    assert alternative.allocation_basis == "existing-enterprise-financial-model-v1"
    assert not alternative.missing_inputs


def test_missing_baseline_remains_explicit_and_does_not_fabricate_savings():
    ctx = context()
    product = FinancialDecisionProduct(ctx)
    rec, decision = recommendation_and_decision(ctx)
    result = product.create_alternative(
        alternative_id="missing-baseline",
        recommendation=rec,
        decision=decision,
        posture=posture(ctx),
        resource_id="app-1",
        baseline=None,
        allocation=None,
        forecast=None,
    )
    assert result.projected_savings is None
    assert {"baseline", "allocation", "forecast"} <= set(result.missing_inputs)


@pytest.mark.parametrize(
    ("availability", "expected"),
    [
        (ForecastAvailability.MISSING, ForecastAvailability.MISSING),
        (ForecastAvailability.STALE, ForecastAvailability.STALE),
    ],
)
def test_missing_and_stale_forecast_are_explicit(availability, expected):
    bundle = complete_product()
    ctx, product, rec, decision, baseline, _, allocated = bundle[:7]
    result = product.create_alternative(
        alternative_id=f"alternative-{availability.value}",
        recommendation=rec,
        decision=decision,
        posture=posture(ctx),
        resource_id="app-1",
        baseline=baseline,
        allocation=allocated,
        forecast=forecast(baseline, availability=availability),
    )
    assert result.forecast_availability is expected
    if availability is ForecastAvailability.MISSING:
        assert result.projected_cost is None


def test_valid_reconciliation_is_matched():
    assert complete_product()[9].state is ReconciliationState.MATCHED


def test_partial_reconciliation_surfaces_unmatched_cost():
    bundle = complete_product()
    ctx, product, _, _, baseline, actual = bundle[:6]
    result = product.reconcile(
        reconciliation_id="partial",
        business_service_id="svc-1",
        baseline=baseline,
        actual=actual,
        allocation=allocation(baseline, 60, ctx=ctx),
    )
    assert result.state is ReconciliationState.PARTIAL
    assert result.unmatched_amount == 40


def test_unreconciled_cost_is_never_discarded():
    bundle = complete_product()
    product, baseline, actual = bundle[1], bundle[4], bundle[5]
    result = product.reconcile(
        reconciliation_id="unreconciled",
        business_service_id="svc-1",
        baseline=baseline,
        actual=actual,
        allocation=None,
    )
    assert result.state is ReconciliationState.UNRECONCILED
    assert result.baseline_amount == 100
    assert "allocation_missing" in result.reasons


def test_forecast_savings_is_not_realized_savings():
    bundle = complete_product()
    assert bundle[8].projected_savings == 30
    assert bundle[1].realized_savings_by_decision("decision-1") == ()


def test_command_success_without_verified_outcome_is_indeterminate():
    bundle = complete_product()
    plan, execution, _ = execution_chain(command_only=True)
    result = attribute(bundle, plan=plan, execution=execution, verification=None)
    assert result.state is SavingsState.INDETERMINATE
    assert result.amount is None


def test_verified_outcome_with_insufficient_financial_evidence_is_indeterminate():
    bundle = complete_product()
    result = attribute(bundle, baseline=None)
    assert result.state is SavingsState.INDETERMINATE
    assert result.amount is None


def test_confirmed_realized_savings_requires_full_governed_chain():
    result = attribute(complete_product())
    assert result.state is SavingsState.REALIZED
    assert result.amount == 30


def test_not_realized_savings_is_explicit():
    result = attribute(complete_product(actual_amount=110))
    assert result.state is SavingsState.NOT_REALIZED
    assert result.amount == -10


def test_non_verified_outcome_is_indeterminate():
    bundle = complete_product()
    plan, execution, verification = execution_chain(verified=False)
    result = attribute(
        bundle, plan=plan, execution=execution, verification=verification
    )
    assert result.state is SavingsState.INDETERMINATE


def test_duplicate_decision_outcome_savings_is_rejected():
    bundle = complete_product()
    attribute(bundle)
    with pytest.raises(FinancialDecisionError, match="already exists"):
        attribute(bundle, savings_id="duplicate")


def test_overlapping_savings_window_is_rejected():
    bundle = complete_product()
    attribute(bundle)
    rec2, decision2 = recommendation_and_decision()
    decision2 = replace(decision2, decision_id="decision-2")
    alternative2 = replace(
        bundle[8],
        alternative_id="alternative-2",
        decision_id="decision-2",
        alternative_hash="alternative-hash-2",
    )
    bundle[1]._alternatives["alternative-2"] = alternative2
    verification2 = replace(bundle[12], verification_id="verification-2")
    with pytest.raises(FinancialDecisionError, match="overlapping"):
        bundle[1].attribute_realized_savings(
            savings_id="savings-2",
            recommendation=rec2,
            decision=decision2,
            alternative=alternative2,
            reconciliation=bundle[9],
            baseline=bundle[4],
            actual=bundle[5],
            plan=replace(bundle[10], decision_id="decision-2"),
            execution=bundle[11],
            verification=verification2,
            recorded_at=NOW,
        )


def test_supersession_preserves_history_and_excludes_old_current_value():
    bundle = complete_product()
    first = attribute(bundle)
    second = attribute(
        bundle,
        savings_id="savings-2",
        supersedes_savings_id="savings-1",
    )
    assert second.version == 2
    assert bundle[1].savings_version("savings-1", 1).record_state is RecordState.SUPERSEDED
    assert bundle[1].realized_savings_by_decision("decision-1") == (second,)
    assert first.savings_hash == bundle[1].savings_version("savings-1", 1).savings_hash


def test_incompatible_currency_is_unreconciled_and_indeterminate():
    bundle = complete_product()
    foreign_actual = replace(bundle[5], currency="EUR")
    reconciled = bundle[1].reconcile(
        reconciliation_id="currency",
        business_service_id="svc-1",
        baseline=bundle[4],
        actual=foreign_actual,
        allocation=bundle[6],
    )
    assert reconciled.state is ReconciliationState.UNRECONCILED
    result = attribute(bundle, reconciliation=reconciled, actual=foreign_actual)
    assert result.state is SavingsState.INDETERMINATE
    assert result.amount is None


def test_incompatible_period_is_unreconciled():
    bundle = complete_product()
    actual = replace(bundle[5], period_start=NOW - timedelta(days=20))
    result = bundle[1].reconcile(
        reconciliation_id="period",
        business_service_id="svc-1",
        baseline=bundle[4],
        actual=actual,
        allocation=bundle[6],
    )
    assert result.state is ReconciliationState.UNRECONCILED
    assert "incompatible_period" in result.reasons


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("baseline", "baseline cost"),
        ("allocation", "allocation"),
        ("forecast", "forecast"),
        ("posture", "business service posture"),
        ("recommendation", "recommendation"),
        ("decision", "decision"),
    ],
)
def test_cross_tenant_alternative_inputs_are_rejected(field, label):
    ctx = context()
    foreign = context("b")
    product = FinancialDecisionProduct(ctx)
    rec, decision = recommendation_and_decision(ctx)
    baseline = cost("baseline", 100, ctx=ctx)
    values = {
        "alternative_id": "cross-tenant",
        "recommendation": rec,
        "decision": decision,
        "posture": posture(ctx),
        "resource_id": "app-1",
        "baseline": baseline,
        "allocation": allocation(baseline, ctx=ctx),
        "forecast": forecast(baseline, ctx=ctx),
    }
    if field == "baseline":
        values[field] = cost("foreign", 100, ctx=foreign)
    elif field == "allocation":
        values[field] = allocation(baseline, ctx=foreign)
    elif field == "forecast":
        values[field] = forecast(baseline, ctx=foreign)
    elif field == "posture":
        values[field] = posture(foreign)
    elif field == "decision":
        values[field] = recommendation_and_decision(foreign)[1]
    else:
        values[field] = recommendation_and_decision(foreign)[0]
    with pytest.raises(FinancialDecisionError, match=f"{label} crosses tenant"):
        product.create_alternative(**values)


def test_cross_tenant_outcome_is_rejected():
    bundle = complete_product()
    foreign_verification = replace(
        bundle[12], organization_id="org-b", tenant_id="tenant-b"
    )
    with pytest.raises(FinancialDecisionError, match="outcome verification crosses tenant"):
        attribute(bundle, verification=foreign_verification)


def test_cross_tenant_savings_attribution_is_rejected():
    bundle = complete_product()
    foreign_alternative = replace(
        bundle[8], organization_id="org-b", tenant_id="tenant-b"
    )
    with pytest.raises(FinancialDecisionError, match="financial alternative crosses tenant"):
        attribute(bundle, alternative=foreign_alternative)


def test_cross_tenant_financial_evidence_is_rejected():
    bundle = complete_product()
    foreign_evidence = evidence("foreign", context("b"))
    own_record_with_foreign_evidence = replace(bundle[5], evidence=foreign_evidence)
    with pytest.raises(FinancialDecisionError, match="actual evidence crosses tenant"):
        attribute(bundle, actual=own_record_with_foreign_evidence)


def test_duplicate_cost_or_allocation_evidence_is_rejected():
    bundle = complete_product()
    duplicate = replace(bundle[6], evidence=bundle[4].evidence)
    with pytest.raises(FinancialDecisionError, match="duplicate financial evidence"):
        bundle[1].reconcile(
            reconciliation_id="duplicate-evidence",
            business_service_id="svc-1",
            baseline=bundle[4],
            actual=bundle[5],
            allocation=duplicate,
        )


def test_deterministic_reconstruction_contains_complete_attribution_chain():
    bundle = complete_product()
    savings = attribute(bundle)
    first = bundle[1].reconstruct(savings.savings_id)
    second = bundle[1].reconstruct(savings.savings_id)
    assert first == second
    assert first["business_service"] == "svc-1"
    assert first["recommendation"] == {"id": "rec-1", "version": 1}
    assert first["decision"] == {"id": "decision-1", "version": 1}
    assert first["financial_alternative"]["alternative_id"] == "alternative-1"
    assert first["baseline"]["cost_id"] == "cost-baseline"
    assert first["forecast"]["id"] == "forecast-1"
    assert first["policy_authorization"]["execution_id"] == "execution-1"
    assert first["policy_authorization"]["authority_id"] == "approval-1"
    assert first["policy_authorization"]["evaluation_id"] == "evaluation-1"
    assert first["policy_authorization"]["verification_hash"] == "verification-hash"
    assert first["verified_outcome"] == "verification-1"
    assert first["post_action_actual"]["cost_id"] == "cost-actual"
    assert first["reconciliation"]["state"] == "matched"
    assert first["realized_savings"]["state"] == "realized"
    assert len(first["reconstruction_hash"]) == 64


def test_same_inputs_produce_same_alternative_reconciliation_and_savings_hashes():
    first = complete_product()
    second = complete_product()
    first_savings = attribute(first)
    second_savings = attribute(second)
    assert first[8].alternative_hash == second[8].alternative_hash
    assert first[9].reconciliation_hash == second[9].reconciliation_hash
    assert first_savings.savings_hash == second_savings.savings_hash


def test_product_query_interface_is_bounded_and_tenant_scoped():
    bundle = complete_product()
    savings = attribute(bundle)
    assert bundle[1].alternatives_for_decision("decision-1") == (bundle[8],)
    assert bundle[1].realized_savings_by_decision("decision-1") == (savings,)
    assert bundle[1].realized_savings_by_service("svc-1") == (savings,)
    assert bundle[1].financial_posture_by_service("svc-1")["confirmed_total"] == 30
    comparison = bundle[1].forecast_versus_actual("alternative-1", bundle[5])
    assert comparison == {
        "alternative_id": "alternative-1",
        "forecast": 70,
        "actual": 70,
        "currency": "USD",
        "variance": 0,
        "compatible": True,
    }
