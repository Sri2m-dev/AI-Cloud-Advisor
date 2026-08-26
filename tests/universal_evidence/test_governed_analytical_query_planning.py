"""PUE-007 structured, non-executing analytical planning certification."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from tests.universal_evidence.test_governed_aggregation_execution import evaluated, single_currency
from universal_evidence.aggregation import (
    AggregationExecutor,
    AggregationResultStatus,
    FilterOperator,
    TimeBucket,
)
from universal_evidence.capability import CapabilityEvaluator, CapabilityPolicy
from universal_evidence.planning import (
    AnalyticalIntent,
    AnalyticalIntentType,
    AnalyticalPlanningPolicy,
    AnalyticalQueryPlanner,
    IntentFilter,
    PlanningReason,
    PlanningStatus,
)

NOW = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)


def intent(assessment, intent_type, **overrides):
    values = {
        "intent_id": "intent-1",
        "scope": assessment.scope,
        "intent_type": intent_type,
        "measure_concept_id": None,
        "dimension_concept_ids": (),
        "time_dimension_concept_id": None,
        "filters": (),
        "time_bucket": None,
        "requested_currency_behavior": None,
        "caller_id": "caller-1",
        "caller_type": "SERVICE",
        "capability_assessment_id": assessment.assessment_id,
        "execution_authorization_id": None,
        "intent_version": AnalyticalPlanningPolicy().intent_version,
        "created_at": NOW,
    }
    values.update(overrides)
    return AnalyticalIntent(**values)


def total_intent(assessment, **overrides):
    overrides.setdefault("measure_concept_id", "financial.cost.total")
    return intent(
        assessment,
        AnalyticalIntentType.TOTAL_MEASURE,
        **overrides,
    )


def test_count_intent_builds_request_but_does_not_execute():
    repository, runs, assessment = single_currency()
    executor = AggregationExecutor(capability_repository=repository)
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(
        intent(assessment, AnalyticalIntentType.COUNT_RECORDS)
    )
    assert result.plan.planning_status is PlanningStatus.READY
    assert result.aggregation_request.operation.value == "COUNT"
    assert result.aggregation_request.request_id == result.plan.plan_id
    assert executor.repository.get_versions(assessment.scope.key) == ()
    executed = executor.execute(result.aggregation_request, assessment, runs)
    assert executed.status is AggregationResultStatus.COMPLETED


def test_total_intent_resolves_exact_authorization_and_currency_run():
    repository, runs, assessment = single_currency()
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(total_intent(assessment))
    request = result.aggregation_request
    assert result.plan.planning_status is PlanningStatus.READY
    assert request.operation.value == "SUM"
    assert request.measure_id == result.plan.measure_id
    assert set(result.plan.normalization_run_ids) == {run.normalization_run_id for run in runs}
    assert result.plan.currency_requirement == "ROW_LEVEL_SINGLE_CURRENCY"


def test_grouped_intent_requires_alignment_and_resolves_filter():
    repository, _, assessment = single_currency()
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(
        intent(
            assessment,
            AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
            measure_concept_id="financial.cost.total",
            dimension_concept_ids=("technology.service",),
            filters=(IntentFilter("technology.service", FilterOperator.EQUALS, "EC2"),),
        )
    )
    assert result.plan.planning_status is PlanningStatus.READY
    assert result.plan.alignment_id is not None
    assert result.aggregation_request.filters[0].dimension_id == result.plan.dimension_ids[0]


def test_trend_intent_resolves_time_authorization_and_bucket():
    repository, _, assessment = evaluated(
        b"Usage Date,Cost,Currency\n2026-01-01,100,USD\n2026-02-01,200,USD\n",
        {
            "Usage Date": ("contract.start_date", ["2026-01-01", "2026-02-01"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(
        intent(
            assessment,
            AnalyticalIntentType.TIME_SERIES_MEASURE,
            measure_concept_id="financial.cost.total",
            time_dimension_concept_id="contract.start_date",
            time_bucket=TimeBucket.MONTH,
        )
    )
    assert result.plan.planning_status is PlanningStatus.READY
    assert result.aggregation_request.operation.value == "TIME_BUCKETED_SUM"


@pytest.mark.parametrize("concept", ["cost", "Cost", "spend", "EC2 Cost"])
def test_alias_header_and_shorthand_concepts_are_not_resolved(concept):
    repository, _, assessment = single_currency()
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(
        total_intent(assessment, measure_concept_id=concept)
    )
    assert result.plan.planning_status is PlanningStatus.REJECTED
    assert result.aggregation_request is None


@pytest.mark.parametrize(
    "question",
    ["What is EC2 cost?", "Show me spend by region.", "Where are we spending the most?"],
)
def test_free_form_questions_are_unsupported_input(question):
    repository, _, assessment = single_currency()
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(
        intent(assessment, question)
    )
    assert result.plan.reason_codes == (PlanningReason.INTENT_UNSUPPORTED,)
    assert result.aggregation_request is None


def test_184_rows_without_currency_block_total_without_arithmetic():
    costs = ["4683"] * 183 + ["4869"]
    repository, _, assessment = evaluated(
        ("Cost\n" + "\n".join(costs) + "\n").encode(),
        {"Cost": ("financial.cost.total", costs)},
    )
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(total_intent(assessment))
    assert result.plan.planning_status is PlanningStatus.BLOCKED
    assert result.plan.reason_codes == (PlanningReason.CAPABILITY_BLOCKED,)
    assert result.aggregation_request is None
    assert not hasattr(result.plan, "result_value")


def test_mixed_currency_total_is_blocked_not_reinterpreted():
    repository, _, assessment = evaluated(
        b"Cost,Currency\n100,USD\n200,INR\n",
        {
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "INR"]),
        },
    )
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(total_intent(assessment))
    assert result.plan.planning_status is PlanningStatus.BLOCKED
    assert result.aggregation_request is None


def test_multiple_dimensions_and_unsupported_average_are_rejected():
    repository, _, assessment = single_currency()
    planner = AnalyticalQueryPlanner(capability_repository=repository)
    dimensions = planner.plan(
        intent(
            assessment,
            AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
            measure_concept_id="financial.cost.total",
            dimension_concept_ids=("technology.service", "financial.currency"),
        )
    )
    average = planner.plan(intent(assessment, "AVERAGE"))
    assert dimensions.aggregation_request is None
    assert average.plan.reason_codes == (PlanningReason.INTENT_UNSUPPORTED,)


def test_ungoverned_dimension_and_unauthorized_filter_are_rejected():
    repository, _, assessment = single_currency()
    planner = AnalyticalQueryPlanner(capability_repository=repository)
    grouped = planner.plan(
        intent(
            assessment,
            AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
            measure_concept_id="financial.cost.total",
            dimension_concept_ids=("geography.region",),
        )
    )
    filtered = planner.plan(
        total_intent(
            assessment,
            filters=(IntentFilter("technology.service", FilterOperator.EQUALS, "EC2"),),
        )
    )
    assert grouped.plan.reason_codes == (PlanningReason.DIMENSION_NOT_GOVERNED,)
    assert filtered.plan.reason_codes == (PlanningReason.FILTER_NOT_AUTHORIZED,)


def test_forged_authorization_and_currency_behavior_are_rejected():
    repository, _, assessment = single_currency()
    planner = AnalyticalQueryPlanner(capability_repository=repository)
    forged = planner.plan(total_intent(assessment, execution_authorization_id="forged"))
    behavior = planner.plan(total_intent(assessment, requested_currency_behavior="FX_CONVERT"))
    assert forged.plan.reason_codes == (PlanningReason.AUTHORIZATION_NOT_FOUND,)
    assert behavior.plan.reason_codes == (PlanningReason.OPERATION_NOT_AUTHORIZED,)


def test_superseded_assessment_and_authorization_are_stale():
    repository, runs, assessment = single_currency()
    old_auth = next(
        item
        for item in assessment.execution_authorizations
        if item.measure_id is not None and item.authorized_operations[0].value == "SUM"
    )
    CapabilityEvaluator(
        repository=repository,
        capability_policy=CapabilityPolicy(version="pue-capability-policy-2"),
    ).evaluate(runs)
    planner = AnalyticalQueryPlanner(capability_repository=repository)
    stale_assessment = planner.plan(total_intent(assessment))
    current = repository.get_current_assessment(assessment.scope.key)
    stale_auth = planner.plan(
        total_intent(current, execution_authorization_id=old_auth.authorization_id)
    )
    assert stale_assessment.plan.reason_codes == (PlanningReason.CAPABILITY_STALE,)
    assert stale_auth.plan.reason_codes == (PlanningReason.AUTHORIZATION_STALE,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("analysis_id", "analysis-other"),
        ("prospect_id", "prospect-other"),
        ("organization_id", "org-other"),
        ("tenant_id", "tenant-other"),
    ],
)
def test_cross_scope_never_uses_another_scope_authorization(field, value):
    repository, _, assessment = single_currency()
    changed_scope = replace(assessment.scope, **{field: value})
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(
        total_intent(assessment, scope=changed_scope)
    )
    assert result.plan.planning_status is PlanningStatus.STALE
    assert result.aggregation_request is None


def test_injection_like_operator_fails_closed():
    repository, _, assessment = single_currency()
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(
        intent(
            assessment,
            AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
            measure_concept_id="financial.cost.total",
            dimension_concept_ids=("technology.service",),
            filters=(
                IntentFilter("technology.service", FilterOperator.EQUALS, "x; drop table y;--"),
            ),
        )
    )
    assert result.plan.reason_codes == (PlanningReason.FILTER_NOT_AUTHORIZED,)


def test_time_bucket_must_be_carried_by_exact_authorization():
    repository, _, assessment = evaluated(
        b"Usage Date,Cost,Currency\n2026-01-01,100,USD\n",
        {
            "Usage Date": ("contract.start_date", ["2026-01-01"]),
            "Cost": ("financial.cost.total", ["100"]),
            "Currency": ("financial.currency", ["USD"]),
        },
        capability_policy=CapabilityPolicy(allowed_time_buckets=("DAY", "MONTH")),
    )
    result = AnalyticalQueryPlanner(capability_repository=repository).plan(
        intent(
            assessment,
            AnalyticalIntentType.TIME_SERIES_MEASURE,
            measure_concept_id="financial.cost.total",
            time_dimension_concept_id="contract.start_date",
            time_bucket=TimeBucket.QUARTER,
        )
    )
    assert result.plan.reason_codes == (PlanningReason.TIME_BUCKET_NOT_AUTHORIZED,)
    assert result.aggregation_request is None


def test_same_inputs_produce_same_plan_and_request():
    repository, _, assessment = single_currency()
    planner = AnalyticalQueryPlanner(capability_repository=repository, clock=lambda: NOW)
    structured = total_intent(assessment)
    first = planner.plan(structured)
    second = planner.plan(structured)
    assert first.plan is second.plan
    assert first.plan.plan_fingerprint == second.plan.plan_fingerprint
    assert first.aggregation_request == second.aggregation_request
    assert planner.repository.get_versions(assessment.scope.key) == (first.plan,)
