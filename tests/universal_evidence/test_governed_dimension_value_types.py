"""PUE-007A governed dimension value-type and filter certification."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from tests.universal_evidence.test_governed_aggregation_execution import evaluated
from tests.universal_evidence.test_governed_analytical_query_planning import intent
from tests.universal_evidence.test_governed_evidence_capability import normalized_runs
from universal_evidence.aggregation import FilterOperator, TimeBucket
from universal_evidence.capability import (
    AuthorizedOperation,
    CapabilityEvaluator,
    CapabilityPolicy,
    CapabilityState,
    DimensionValueType,
    InMemoryCapabilityRepository,
    ReasonCode,
)
from universal_evidence.planning import (
    AnalyticalIntentType,
    AnalyticalQueryPlanner,
    IntentFilter,
    PlanningReason,
    PlanningStatus,
)


def with_values(run, values, types):
    records = tuple(
        replace(record, normalized_value=value, normalized_type=value_type)
        for record, value, value_type in zip(run.records, values, types, strict=True)
    )
    return replace(run, records=records)


def typed_assessment(value_type, values, *, repository=None, policy=None):
    strings = [str(value) for value in values]
    runs = normalized_runs(
        ("Service\n" + "\n".join(strings) + "\n").encode(),
        {"Service": ("technology.service", strings)},
    )
    typed = (with_values(runs[0], values, [value_type] * len(values)),)
    repository = repository or InMemoryCapabilityRepository()
    assessment = CapabilityEvaluator(repository=repository, capability_policy=policy).evaluate(
        typed
    )
    dimension = next(
        item for item in assessment.dimensions if item.semantic_concept_id == "technology.service"
    )
    return repository, typed, assessment, dimension


@pytest.mark.parametrize(
    ("normalized_type", "values", "expected_type", "operators"),
    [
        ("STRING", ["EC2", "RDS"], DimensionValueType.STRING, ("EQUALS", "NOT_EQUALS", "IN")),
        ("INTEGER", [1, 2], DimensionValueType.INTEGER, ("EQUALS", "NOT_EQUALS", "IN")),
        (
            "DECIMAL",
            [Decimal("1.5"), Decimal("2.5")],
            DimensionValueType.DECIMAL,
            ("EQUALS", "NOT_EQUALS", "IN"),
        ),
        ("BOOLEAN", [True, False], DimensionValueType.BOOLEAN, ("EQUALS",)),
        (
            "DATE",
            [date(2026, 1, 1), date(2026, 1, 2)],
            DimensionValueType.DATE,
            ("EQUALS", "DATE_FROM", "DATE_TO"),
        ),
        (
            "DATETIME",
            [
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc),
            ],
            DimensionValueType.DATETIME,
            ("EQUALS", "DATE_FROM", "DATE_TO"),
        ),
    ],
)
def test_dimension_type_and_operator_policy_are_certified(
    normalized_type, values, expected_type, operators
):
    _, _, _, dimension = typed_assessment(normalized_type, values)
    assert dimension.state is CapabilityState.SUPPORTED
    assert dimension.normalized_value_type is expected_type
    assert dimension.allowed_filter_operators == operators
    assert dimension.filterable
    assert ReasonCode.DIMENSION_VALUE_TYPE_CERTIFIED in dimension.reason_codes


def test_mixed_normalized_types_block_dimension_instead_of_selecting_one():
    _, runs, assessment, _ = typed_assessment("STRING", ["prod", "uat", "dev"])
    mixed = (with_values(runs[0], ["prod", "uat", 123], ["STRING", "STRING", "INTEGER"]),)
    conflicted = CapabilityEvaluator().evaluate(mixed)
    dimension = next(
        item for item in conflicted.dimensions if item.semantic_concept_id == "technology.service"
    )
    assert assessment.scope == conflicted.scope
    assert dimension.state is CapabilityState.BLOCKED
    assert dimension.normalized_value_type is None
    assert dimension.allowed_filter_operators == ()
    assert not dimension.filterable
    assert dimension.reason_codes == (ReasonCode.DIMENSION_VALUE_TYPE_CONFLICT,)


def grouped_fixture(value_type="STRING", dimension_values=None):
    dimension_values = dimension_values or ["EC2", "RDS"]
    repository, runs, assessment = evaluated(
        b"Service,Cost,Currency\nEC2,100,USD\nRDS,200,USD\n",
        {
            "Service": ("technology.service", ["EC2", "RDS"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    typed_runs = tuple(
        with_values(
            run,
            dimension_values,
            [value_type] * len(dimension_values),
        )
        if run.records[0].semantic_concept_id == "technology.service"
        else run
        for run in runs
    )
    repository = InMemoryCapabilityRepository()
    assessment = CapabilityEvaluator(repository=repository).evaluate(typed_runs)
    return repository, typed_runs, assessment


def grouped_intent(assessment, filter_value, operator=FilterOperator.EQUALS):
    return intent(
        assessment,
        AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
        measure_concept_id="financial.cost.total",
        dimension_concept_ids=("technology.service",),
        filters=(IntentFilter("technology.service", operator, filter_value),),
    )


def test_string_equals_and_in_are_valid_but_mixed_in_members_are_rejected():
    repository, _, assessment = grouped_fixture()
    planner = AnalyticalQueryPlanner(capability_repository=repository)
    equals = planner.plan(grouped_intent(assessment, "EC2"))
    in_filter = planner.plan(grouped_intent(assessment, ("EC2", "RDS"), FilterOperator.IN))
    mixed = planner.plan(grouped_intent(assessment, ("EC2", 123), FilterOperator.IN))
    assert equals.plan.planning_status is PlanningStatus.READY
    assert in_filter.plan.planning_status is PlanningStatus.READY
    assert mixed.plan.reason_codes == (PlanningReason.FILTER_LIST_MEMBER_TYPE_MISMATCH,)


def test_boolean_equals_is_valid_but_in_and_string_coercion_are_rejected():
    repository, _, assessment = grouped_fixture("BOOLEAN", [True, False])
    planner = AnalyticalQueryPlanner(capability_repository=repository)
    valid = planner.plan(grouped_intent(assessment, True))
    no_in = planner.plan(grouped_intent(assessment, (True, False), FilterOperator.IN))
    no_coercion = planner.plan(grouped_intent(assessment, "true"))
    assert valid.plan.planning_status is PlanningStatus.READY
    assert no_in.plan.reason_codes == (PlanningReason.FILTER_OPERATOR_NOT_ALLOWED,)
    assert no_coercion.plan.reason_codes == (PlanningReason.FILTER_VALUE_TYPE_MISMATCH,)


def date_fixture():
    return evaluated(
        b"Renewal Date,Cost,Currency\n2026-01-01,100,USD\n2026-02-01,200,USD\n",
        {
            "Renewal Date": ("contract.renewal_date", ["2026-01-01", "2026-02-01"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )


def trend_intent(assessment, operator, value):
    return intent(
        assessment,
        AnalyticalIntentType.TIME_SERIES_MEASURE,
        measure_concept_id="financial.cost.total",
        time_dimension_concept_id="contract.renewal_date",
        filters=(IntentFilter("contract.renewal_date", operator, value),),
        time_bucket=TimeBucket.MONTH,
    )


def test_date_range_values_are_valid_and_string_date_is_not_coerced():
    repository, _, assessment = date_fixture()
    planner = AnalyticalQueryPlanner(capability_repository=repository)
    date_from = planner.plan(trend_intent(assessment, FilterOperator.DATE_FROM, date(2026, 1, 1)))
    date_to = planner.plan(trend_intent(assessment, FilterOperator.DATE_TO, date(2026, 12, 1)))
    string_date = planner.plan(trend_intent(assessment, FilterOperator.DATE_FROM, "2026-01-01"))
    assert date_from.plan.planning_status is PlanningStatus.READY
    assert date_to.plan.planning_status is PlanningStatus.READY
    assert string_date.plan.reason_codes == (PlanningReason.FILTER_VALUE_TYPE_MISMATCH,)


def test_type_and_operator_policy_versions_change_all_downstream_identity():
    repository = InMemoryCapabilityRepository()
    _, runs, first, first_dimension = typed_assessment(
        "STRING", ["EC2", "RDS"], repository=repository
    )
    second = CapabilityEvaluator(
        repository=repository,
        capability_policy=CapabilityPolicy(
            dimension_value_policy_version="pue-dimension-value-policy-2"
        ),
    ).evaluate(runs)
    second_dimension = next(
        item for item in second.dimensions if item.semantic_concept_id == "technology.service"
    )
    assert first_dimension.fingerprint != second_dimension.fingerprint
    assert first.fingerprint != second.fingerprint
    assert repository.get_current_assessment(first.scope.key) is second


def test_type_drift_stales_old_authorization_and_ready_plan():
    repository, runs, first = grouped_fixture()
    planner = AnalyticalQueryPlanner(capability_repository=repository)
    old_plan = planner.plan(grouped_intent(first, "EC2"))
    old_authorization = next(
        item
        for item in first.execution_authorizations
        if AuthorizedOperation.GROUPED_SUM in item.authorized_operations
        and item.dimension_ids == old_plan.plan.dimension_ids
    )
    typed_runs = tuple(
        with_values(run, [1, 2], ["INTEGER", "INTEGER"])
        if run.records[0].semantic_concept_id == "technology.service"
        else run
        for run in runs
    )
    second = CapabilityEvaluator(repository=repository).evaluate(typed_runs)
    stale = planner.plan(grouped_intent(first, "EC2"))
    assert old_plan.plan.planning_status is PlanningStatus.READY
    assert second.assessment_id != first.assessment_id
    assert not repository.is_authorization_current(old_authorization)
    assert stale.plan.planning_status is PlanningStatus.STALE


@pytest.mark.parametrize(
    ("scope_field", "first_value", "second_value"),
    [
        ("analysis_id", "analysis-a", "analysis-b"),
        ("tenant_id", "tenant-a", "tenant-b"),
    ],
)
def test_dimension_type_identity_is_scope_isolated(scope_field, first_value, second_value):
    fingerprints = []
    for value in (first_value, second_value):
        from tests.universal_evidence.test_governed_evidence_capability import source

        kwargs = {scope_field: value}
        runs = normalized_runs(
            b"Service\nEC2\n",
            {"Service": ("technology.service", ["EC2"])},
            evidence_source=source(**kwargs),
        )
        assessment = CapabilityEvaluator().evaluate(runs)
        fingerprints.append(assessment.dimensions[0].fingerprint)
    assert fingerprints[0] != fingerprints[1]


def test_same_evidence_and_policy_produce_deterministic_type_metadata():
    _, runs, first, first_dimension = typed_assessment("DECIMAL", [Decimal("1.0")])
    second = CapabilityEvaluator().evaluate(runs)
    second_dimension = next(
        item for item in second.dimensions if item.semantic_concept_id == "technology.service"
    )
    assert first_dimension == second_dimension
    assert first.fingerprint == second.fingerprint
