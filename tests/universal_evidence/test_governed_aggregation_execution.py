"""PUE-006 governed aggregation execution certification tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from tests.universal_evidence.test_governed_evidence_capability import normalized_runs
from universal_evidence.aggregation import (
    AggregationExecutionPolicy,
    AggregationExecutor,
    AggregationFilter,
    AggregationRequest,
    AggregationResultStatus,
    AggregationWarning,
    FilterOperator,
    TimeBucket,
)
from universal_evidence.capability import (
    AuthorizedOperation,
    CapabilityEvaluator,
    CapabilityPolicy,
    InMemoryCapabilityRepository,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def evaluated(content, mappings, *, repository=None, capability_policy=None):
    repository = repository or InMemoryCapabilityRepository()
    runs = normalized_runs(content, mappings)
    assessment = CapabilityEvaluator(
        repository=repository, capability_policy=capability_policy
    ).evaluate(runs)
    return repository, runs, assessment


def authorization(assessment, operation, concept=None):
    dimensions = {item.dimension_id: item for item in assessment.dimensions}
    return next(
        item
        for item in assessment.execution_authorizations
        if operation in item.authorized_operations
        and (
            concept is None
            or any(
                dimensions[dimension_id].semantic_concept_id == concept
                for dimension_id in item.dimension_ids
            )
            or (
                item.time_dimension_id is not None
                and dimensions[item.time_dimension_id].semantic_concept_id == concept
            )
        )
    )


def request(assessment, auth, **overrides):
    values = {
        "request_id": "request-1",
        "scope": assessment.scope,
        "capability_assessment_id": assessment.assessment_id,
        "authorization_id": auth.authorization_id if auth else "missing",
        "operation": auth.authorized_operations[0] if auth else AuthorizedOperation.SUM,
        "measure_id": auth.measure_id if auth else None,
        "dimension_ids": auth.dimension_ids if auth else (),
        "time_dimension_id": auth.time_dimension_id if auth else None,
        "filters": (),
        "time_bucket": None,
        "execution_policy_version": AggregationExecutionPolicy().version,
        "requested_at": NOW,
    }
    values.update(overrides)
    return AggregationRequest(**values)


def single_currency():
    return evaluated(
        b"Service,Cost,Currency\nEC2,100.10,USD\nEC2,200.20,USD\nRDS,49.70,USD\n",
        {
            "Service": ("technology.service", ["EC2", "EC2", "RDS"]),
            "Cost": ("financial.cost.total", ["100.10", "200.20", "49.70"]),
            "Currency": ("financial.currency", ["USD", "USD", "USD"]),
        },
    )


def test_single_currency_sum_uses_exact_authorized_runs_and_decimal():
    repository, runs, assessment = single_currency()
    auth = authorization(assessment, AuthorizedOperation.SUM)
    assert set(auth.normalization_run_ids) == {run.normalization_run_id for run in runs}
    result = AggregationExecutor(capability_repository=repository).execute(
        request(assessment, auth), assessment, runs
    )
    assert result.status is AggregationResultStatus.COMPLETED
    assert result.scalar_value == Decimal("350.00")
    assert result.currency_or_unit == "USD"
    assert result.statistics.included_records == 3
    assert result.provenance.authorization_id == auth.authorization_id


def test_grouped_sum_and_governed_filter_do_not_run_ad_hoc_queries():
    repository, runs, assessment = single_currency()
    auth = authorization(assessment, AuthorizedOperation.GROUPED_SUM, "technology.service")
    result = AggregationExecutor(capability_repository=repository).execute(
        request(
            assessment,
            auth,
            filters=(
                AggregationFilter(
                    auth.dimension_ids[0], FilterOperator.EQUALS, "EC2"
                ),
            ),
        ),
        assessment,
        runs,
    )
    assert result.status is AggregationResultStatus.COMPLETED
    assert [(group.dimension_values, group.value, group.unit) for group in result.groups] == [
        ((('technology.service', 'EC2'),), Decimal("300.30"), "USD")
    ]
    assert result.statistics.excluded_filter_records == 1


def test_time_bucketed_sum_uses_authorized_time_dimension():
    repository, runs, assessment = evaluated(
        b"Usage Date,Cost,Currency\n2026-01-01,100,USD\n2026-01-20,200,USD\n2026-02-01,50,USD\n",
        {
            "Usage Date": (
                "contract.start_date",
                ["2026-01-01", "2026-01-20", "2026-02-01"],
            ),
            "Cost": ("financial.cost.total", ["100", "200", "50"]),
            "Currency": ("financial.currency", ["USD", "USD", "USD"]),
        },
    )
    auth = authorization(assessment, AuthorizedOperation.TIME_BUCKETED_SUM)
    result = AggregationExecutor(capability_repository=repository).execute(
        request(assessment, auth, time_bucket=TimeBucket.MONTH), assessment, runs
    )
    assert [(group.dimension_values, group.value) for group in result.groups] == [
        ((('contract.start_date', '2026-01'),), Decimal("300")),
        ((('contract.start_date', '2026-02'),), Decimal("50")),
    ]


def test_mixed_currency_has_no_single_total_and_groups_without_fx():
    repository, runs, assessment = evaluated(
        b"Cost,Currency\n100,USD\n200,INR\n",
        {
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "INR"]),
        },
    )
    assert not any(
        AuthorizedOperation.SUM in item.authorized_operations
        for item in assessment.execution_authorizations
    )
    auth = authorization(assessment, AuthorizedOperation.GROUPED_SUM, "financial.currency")
    result = AggregationExecutor(capability_repository=repository).execute(
        request(assessment, auth), assessment, runs
    )
    assert {(group.unit, group.value) for group in result.groups} == {
        ("USD", Decimal("100")),
        ("INR", Decimal("200")),
    }


def test_count_uses_distinct_source_rows_not_normalized_field_count():
    repository, runs, assessment = single_currency()
    auth = authorization(assessment, AuthorizedOperation.COUNT)
    result = AggregationExecutor(capability_repository=repository).execute(
        request(assessment, auth), assessment, runs
    )
    assert result.scalar_value == 3
    assert sum(len(run.records) for run in runs) == 9


def test_184_cost_rows_without_currency_are_blocked_before_calculation():
    costs = ["4683"] * 183 + ["4869"]
    repository, runs, assessment = evaluated(
        ("Cost\n" + "\n".join(costs) + "\n").encode(),
        {"Cost": ("financial.cost.total", costs)},
    )
    result = AggregationExecutor(capability_repository=repository).execute(
        request(assessment, None), assessment, runs
    )
    assert result.status is AggregationResultStatus.BLOCKED
    assert result.scalar_value is None
    assert result.groups == ()
    assert result.statistics.included_records == 0
    assert result.warnings == (AggregationWarning.UPSTREAM_CAPABILITY_NOT_SUPPORTED,)


@pytest.mark.parametrize(
    ("change", "warning"),
    [
        ({"authorization_id": "forged"}, AggregationWarning.AUTHORIZATION_MISMATCH),
        ({"measure_id": "forged"}, AggregationWarning.MEASURE_MISMATCH),
        ({"dimension_ids": ("forged",)}, AggregationWarning.DIMENSION_MISMATCH),
        ({"execution_policy_version": "stale"}, AggregationWarning.STALE_CAPABILITY),
    ],
)
def test_forged_or_mismatched_requests_are_rejected_before_execution(change, warning):
    repository, runs, assessment = single_currency()
    auth = authorization(assessment, AuthorizedOperation.SUM)
    result = AggregationExecutor(capability_repository=repository).execute(
        request(assessment, auth, **change), assessment, runs
    )
    assert result.status is AggregationResultStatus.REJECTED
    assert result.scalar_value is None
    assert result.statistics.eligible_records == 0
    assert result.warnings == (warning,)


def test_stale_authorization_and_normalization_drift_are_rejected():
    repository, runs, assessment = single_currency()
    auth = authorization(assessment, AuthorizedOperation.SUM)
    CapabilityEvaluator(
        repository=repository,
        capability_policy=CapabilityPolicy(version="pue-capability-policy-new"),
    ).evaluate(runs)
    stale = AggregationExecutor(capability_repository=repository).execute(
        request(assessment, auth), assessment, runs
    )
    assert stale.status is AggregationResultStatus.REJECTED
    assert stale.warnings == (AggregationWarning.STALE_CAPABILITY,)


def test_cross_scope_and_extra_runs_are_rejected_before_execution():
    repository, runs, assessment = single_currency()
    auth = authorization(assessment, AuthorizedOperation.SUM)
    wrong_scope = replace(assessment.scope, analysis_id="other-analysis")
    executor = AggregationExecutor(capability_repository=repository)
    scoped = executor.execute(
        request(assessment, auth, scope=wrong_scope), assessment, runs
    )
    assert scoped.warnings == (AggregationWarning.SCOPE_MISMATCH,)
    extra = executor.execute(request(assessment, auth), assessment, runs + (runs[0],))
    assert extra.warnings == (AggregationWarning.NORMALIZATION_RUN_MISMATCH,)


def test_unauthorized_filter_and_injection_like_values_are_rejected():
    repository, runs, assessment = single_currency()
    sum_auth = authorization(assessment, AuthorizedOperation.SUM)
    service = next(
        item for item in assessment.dimensions if item.semantic_concept_id == "technology.service"
    )
    executor = AggregationExecutor(capability_repository=repository)
    unauthorized = executor.execute(
        request(
            assessment,
            sum_auth,
            filters=(AggregationFilter(service.dimension_id, FilterOperator.EQUALS, "EC2"),),
        ),
        assessment,
        runs,
    )
    assert unauthorized.warnings == (AggregationWarning.UNSUPPORTED_FILTER,)
    grouped = authorization(assessment, AuthorizedOperation.GROUPED_SUM, "technology.service")
    injection = executor.execute(
        request(
            assessment,
            grouped,
            filters=(
                AggregationFilter(
                    grouped.dimension_ids[0], FilterOperator.EQUALS, "x'; drop table y;--"
                ),
            ),
        ),
        assessment,
        runs,
    )
    assert injection.warnings == (AggregationWarning.UNSUPPORTED_FILTER,)


def test_replay_is_deterministic_and_repository_history_is_immutable():
    repository, runs, assessment = single_currency()
    auth = authorization(assessment, AuthorizedOperation.SUM)
    executor = AggregationExecutor(capability_repository=repository, clock=lambda: NOW)
    first = executor.execute(request(assessment, auth), assessment, runs)
    second = executor.execute(request(assessment, auth), assessment, runs)
    assert first is second
    assert first.result_fingerprint == second.result_fingerprint
    assert executor.repository.get_versions(assessment.scope.key) == (first,)
