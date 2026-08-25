"""PUE-C5A execution authorization metadata without execution."""

from __future__ import annotations

from dataclasses import fields

import pytest

from tests.universal_evidence.test_governed_evidence_capability import (
    normalized_runs,
    source,
)
from universal_evidence.capability import (
    AlignmentStatus,
    AssessmentState,
    AuthorizedOperation,
    CapabilityEvaluator,
    CapabilityPolicy,
    InMemoryCapabilityRepository,
    RecordBasisType,
)


def authorizations(assessment, operation):
    return tuple(
        item
        for item in assessment.execution_authorizations
        if operation in item.authorized_operations
    )


def single_currency_assessment():
    runs = normalized_runs(
        b"Service,Cost,Currency\nEC2,100,USD\nRDS,50,USD\n",
        {
            "Service": ("technology.service", ["EC2", "RDS"]),
            "Cost": ("financial.cost.total", ["100", "50"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    return CapabilityEvaluator().evaluate(runs), runs


def test_monetary_total_explicitly_authorizes_sum_only():
    assessment, _ = single_currency_assessment()
    sum_authorizations = authorizations(assessment, AuthorizedOperation.SUM)
    assert len(sum_authorizations) == 1
    assert sum_authorizations[0].measure_id is not None
    all_operations = {
        operation
        for item in assessment.execution_authorizations
        for operation in item.authorized_operations
    }
    assert "AVERAGE" not in all_operations
    assert "MIN" not in all_operations
    assert "MAX" not in all_operations


def test_grouped_sum_requires_explicit_aligned_dimension_reference():
    assessment, _ = single_currency_assessment()
    grouped = tuple(
        item
        for item in authorizations(assessment, AuthorizedOperation.GROUPED_SUM)
        if item.dimension_ids
    )
    service_dimension = next(
        item for item in assessment.dimensions if item.semantic_concept_id == "technology.service"
    )
    authorization = next(
        item for item in grouped if service_dimension.dimension_id in item.dimension_ids
    )
    alignment = next(
        item for item in assessment.alignments if item.alignment_id == authorization.alignment_id
    )
    assert alignment.alignment_status is AlignmentStatus.ALIGNED
    assert alignment.aligned_row_count == 2


def test_misaligned_dimension_has_no_grouped_execution_authorization():
    runs = normalized_runs(
        b"Service,Cost,Currency\nEC2,100,USD\n,200,USD\n",
        {
            "Service": ("technology.service", ["EC2", ""]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    service_dimension = next(
        item for item in assessment.dimensions if item.semantic_concept_id == "technology.service"
    )
    assert not any(
        service_dimension.dimension_id in item.dimension_ids
        for item in assessment.execution_authorizations
    )


def test_monetary_trend_is_separate_and_authorizes_time_buckets_only_when_aligned():
    runs = normalized_runs(
        b"Usage Date,Cost,Currency\n2026-01-01,100,USD\n2026-02-01,200,USD\n",
        {
            "Usage Date": ("contract.start_date", ["2026-01-01", "2026-02-01"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    time_range = next(
        item for item in assessment.capabilities if item.capability_name == "TIME_RANGE_ANALYSIS"
    )
    trend = next(
        item for item in assessment.capabilities if item.capability_name == "MONETARY_TREND"
    )
    authorization = authorizations(assessment, AuthorizedOperation.TIME_BUCKETED_SUM)[0]
    assert time_range.capability_id != trend.capability_id
    assert authorization.capability_id == trend.capability_id
    assert authorization.time_dimension_id is not None
    assert authorization.allowed_time_buckets == ("DAY", "MONTH", "QUARTER", "YEAR")


def test_source_row_count_basis_prevents_normalized_field_inflation():
    values = [f"S{index}" for index in range(10)]
    rows = "".join(f"{value},{index},USD,A{index}\n" for index, value in enumerate(values))
    runs = normalized_runs(
        ("Service,Cost,Currency,Application\n" + rows).encode(),
        {
            "Service": ("technology.service", values),
            "Cost": ("financial.cost.total", [str(index) for index in range(10)]),
            "Currency": ("financial.currency", ["USD"] * 10),
            "Application": ("application.name", [f"A{index}" for index in range(10)]),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    basis = assessment.record_count_basis
    assert sum(len(run.records) for run in runs) == 40
    assert basis.basis_type is RecordBasisType.SOURCE_ROW
    assert basis.distinct_source_row_count == 10
    count_auth = authorizations(assessment, AuthorizedOperation.COUNT)[0]
    assert count_auth.record_basis_id == basis.record_basis_id


def test_current_assessment_supersedes_history_and_stales_authorization():
    repository = InMemoryCapabilityRepository()
    runs = normalized_runs(
        b"Service\nEC2\n",
        {"Service": ("technology.service", ["EC2"])},
    )
    first = CapabilityEvaluator(repository=repository).evaluate(runs)
    first_count = authorizations(first, AuthorizedOperation.COUNT)[0]
    second = CapabilityEvaluator(
        repository=repository,
        capability_policy=CapabilityPolicy(version="pue-capability-policy-2"),
    ).evaluate(runs)
    assert repository.get_assessment_state(first.assessment_id) is AssessmentState.SUPERSEDED
    assert repository.get_assessment_state(second.assessment_id) is AssessmentState.CURRENT
    assert repository.get_current_assessment(second.scope.key) is second
    assert not repository.is_authorization_current(first_count)
    assert repository.is_authorization_current(authorizations(second, AuthorizedOperation.COUNT)[0])


def test_normalization_drift_creates_new_current_assessment():
    repository = InMemoryCapabilityRepository()
    first_runs = normalized_runs(
        b"Service\nEC2\n",
        {"Service": ("technology.service", ["EC2"])},
    )
    second_runs = normalized_runs(
        b"Service\nRDS\n",
        {"Service": ("technology.service", ["RDS"])},
    )
    first = CapabilityEvaluator(repository=repository).evaluate(first_runs)
    second = CapabilityEvaluator(repository=repository).evaluate(second_runs)
    assert first.fingerprint != second.fingerprint
    assert repository.get_assessment_state(first.assessment_id) is AssessmentState.SUPERSEDED
    assert repository.get_current_assessment(second.scope.key) is second


@pytest.mark.parametrize(
    ("scope_field", "first_value", "second_value"),
    [
        ("analysis_id", "analysis-a", "analysis-b"),
        ("prospect_id", "prospect-a", "prospect-b"),
        ("organization_id", "org-a", "org-b"),
        ("tenant_id", "tenant-a", "tenant-b"),
    ],
)
def test_alignment_and_authorization_identity_is_scope_isolated(
    scope_field, first_value, second_value
):
    identities = []
    for value in (first_value, second_value):
        kwargs = {
            "analysis_id": "analysis",
            "prospect_id": "prospect",
            "organization_id": "org",
            "tenant_id": "tenant",
            scope_field: value,
        }
        runs = normalized_runs(
            b"Service,Cost,Currency\nEC2,10,USD\n",
            {
                "Service": ("technology.service", ["EC2"]),
                "Cost": ("financial.cost.total", ["10"]),
                "Currency": ("financial.currency", ["USD"]),
            },
            evidence_source=source(**kwargs),
        )
        assessment = CapabilityEvaluator().evaluate(runs)
        identities.append(
            (
                assessment.alignments[0].fingerprint,
                assessment.execution_authorizations[0].authorization_fingerprint,
            )
        )
    assert identities[0] != identities[1]


def test_mixed_currency_authorizes_currency_grouping_but_not_single_sum_or_fx():
    runs = normalized_runs(
        b"Cost,Currency\n100,USD\n200,INR\n",
        {
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "INR"]),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    assert authorizations(assessment, AuthorizedOperation.SUM) == ()
    grouped = authorizations(assessment, AuthorizedOperation.GROUPED_SUM)
    assert len(grouped) == 1
    assert grouped[0].dimension_ids
    assert all(
        "FX" not in operation.value for item in grouped for operation in item.authorized_operations
    )


def test_184_rows_authorize_count_but_not_monetary_sum():
    costs = ["1"] * 183 + [str(861_828 - 183)]
    runs = normalized_runs(
        ("Cost\n" + "\n".join(costs) + "\n").encode(),
        {"Cost": ("financial.cost.total", costs)},
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    assert assessment.record_count_basis.distinct_source_row_count == 184
    assert len(authorizations(assessment, AuthorizedOperation.COUNT)) == 1
    assert authorizations(assessment, AuthorizedOperation.SUM) == ()
    assert not hasattr(assessment, "aggregation_result")
    assert "861828" not in repr(assessment)


def test_c5a_contracts_contain_authorization_metadata_not_execution_results():
    assessment, _ = single_currency_assessment()
    contract_fields = {
        field.name
        for contract in (
            type(assessment.record_count_basis),
            type(assessment.alignments[0]),
            type(assessment.execution_authorizations[0]),
        )
        for field in fields(contract)
    }
    assert {"authorized_operations", "alignment_id", "record_basis_id"} <= contract_fields
    assert {"scalar_result", "grouped_result", "executed_at"}.isdisjoint(contract_fields)
