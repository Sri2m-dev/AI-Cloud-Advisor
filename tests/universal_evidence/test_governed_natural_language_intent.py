"""PUE-008 deterministic governed interpretation certification tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from tests.universal_evidence.test_governed_aggregation_execution import (
    evaluated,
    single_currency,
)
from tests.universal_evidence.test_governed_dimension_value_types import with_values
from universal_evidence.aggregation import AggregationExecutor, FilterOperator, TimeBucket
from universal_evidence.capability import CapabilityEvaluator, InMemoryCapabilityRepository
from universal_evidence.interpretation import (
    ConfidenceBand,
    DeterministicAnalyticalInterpreter,
    InterpretationPolicy,
    InterpretationReason,
    InterpretationStatus,
    NaturalLanguageQuestion,
    build_concept_catalog,
)
from universal_evidence.planning import AnalyticalIntentType, AnalyticalQueryPlanner, PlanningStatus

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def question(assessment, text, **overrides):
    values = {
        "question_id": "question-1",
        "question": text,
        "scope": assessment.scope,
        "caller_id": "user-1",
        "caller_type": "HUMAN",
        "question_version": InterpretationPolicy().question_version,
        "created_at": NOW,
    }
    values.update(overrides)
    return NaturalLanguageQuestion(**values)


def interpret(repository, assessment, text, **question_overrides):
    catalog = build_concept_catalog(repository, assessment.scope)
    assert catalog is not None
    return DeterministicAnalyticalInterpreter(clock=lambda: NOW).interpret(
        question(assessment, text, **question_overrides), catalog
    )


def test_total_cost_interpretation_produces_intent_not_answer():
    repository, _, assessment = single_currency()
    result = interpret(repository, assessment, "What is the total cost?")
    assert result.status is InterpretationStatus.INTERPRETED
    assert result.primary_intent.intent_type is AnalyticalIntentType.TOTAL_MEASURE
    assert result.primary_intent.measure_concept_id == "financial.cost.total"
    assert result.confidence_band is ConfidenceBand.HIGH
    assert not hasattr(result, "answer")
    assert not hasattr(result, "numeric_result")


def test_grouped_cost_interpretation_and_positive_pue007_planning():
    repository, _, assessment = single_currency()
    result = interpret(repository, assessment, "Show cost by service")
    assert result.primary_intent.intent_type is AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION
    assert result.primary_intent.dimension_concept_ids == ("technology.service",)
    planned = AnalyticalQueryPlanner(capability_repository=repository).plan(result.primary_intent)
    assert planned.plan.planning_status is PlanningStatus.READY
    assert planned.aggregation_request.operation.value == "GROUPED_SUM"


def test_time_series_interpretation_uses_unique_governed_time_dimension():
    repository, _, assessment = evaluated(
        b"Usage Date,Cost,Currency\n2026-01-01,100,USD\n2026-02-01,200,USD\n",
        {
            "Usage Date": ("contract.start_date", ["2026-01-01", "2026-02-01"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    result = interpret(repository, assessment, "Show cost trend")
    assert result.primary_intent.intent_type is AnalyticalIntentType.TIME_SERIES_MEASURE
    assert result.primary_intent.time_dimension_concept_id == "contract.start_date"
    assert result.primary_intent.time_bucket is TimeBucket.MONTH


def test_record_count_is_distinct_from_service_count():
    repository, _, assessment = single_currency()
    record_count = interpret(repository, assessment, "How many records are there?")
    service_count = interpret(repository, assessment, "How many services are there?")
    assert record_count.primary_intent.intent_type is AnalyticalIntentType.COUNT_RECORDS
    assert service_count.status is InterpretationStatus.UNSUPPORTED
    assert service_count.primary_intent is None


def test_catalog_is_current_scope_bound_and_contains_no_rows():
    repository, _, assessment = single_currency()
    catalog = build_concept_catalog(repository, assessment.scope)
    assert catalog.capability_assessment_id == assessment.assessment_id
    assert {item.semantic_concept_id for item in catalog.measures} == {"financial.cost.total"}
    assert not hasattr(catalog, "records")
    assert not hasattr(catalog, "sample_values")


def test_missing_governed_dimension_cannot_be_created_from_question():
    repository, _, assessment = single_currency()
    result = interpret(repository, assessment, "Show cost by application")
    assert result.status is InterpretationStatus.UNSUPPORTED
    assert result.primary_intent is None


def test_generic_cost_is_ambiguous_when_two_governed_measures_exist():
    repository, _, assessment = evaluated(
        b"Total Cost,Monthly Cost,Currency\n100,10,USD\n200,20,USD\n",
        {
            "Total Cost": ("financial.cost.total", ["100", "200"]),
            "Monthly Cost": ("financial.cost.monthly", ["10", "20"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    ambiguous = interpret(repository, assessment, "What is cost?")
    monthly = interpret(repository, assessment, "What is monthly cost?")
    assert ambiguous.status is InterpretationStatus.AMBIGUOUS
    assert len(ambiguous.candidates) == 2
    assert ambiguous.primary_intent is None
    assert monthly.primary_intent.measure_concept_id == "financial.cost.monthly"


def provider_fixture():
    return evaluated(
        b"Provider,Service,Cost,Currency\nAWS,EC2,100,USD\nAzure,RDS,200,USD\n",
        {
            "Provider": ("cloud.provider", ["AWS", "Azure"]),
            "Service": ("technology.service", ["EC2", "RDS"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )


def test_provider_and_ec2_filters_remain_literal_strings_not_entities():
    repository, _, assessment = provider_fixture()
    aws = interpret(repository, assessment, "What is total AWS cost?")
    ec2 = interpret(repository, assessment, "What is the total cost of EC2?")
    assert aws.primary_intent.filters[0].dimension_concept_id == "cloud.provider"
    assert aws.primary_intent.filters[0].value == "AWS"
    assert ec2.primary_intent.filters[0].dimension_concept_id == "technology.service"
    assert ec2.primary_intent.filters[0].value == "EC2"
    assert not hasattr(ec2.primary_intent.filters[0], "entity_id")


def test_string_in_list_is_typed_using_bounded_literal_registry():
    repository, _, assessment = provider_fixture()
    valid = interpret(repository, assessment, "Show total cost where service in EC2 and RDS")
    assert valid.primary_intent.filters[0].operator is FilterOperator.IN
    assert valid.primary_intent.filters[0].value == ("EC2", "RDS")


def test_mixed_integer_list_members_are_rejected():
    repository, runs, assessment = provider_fixture()
    typed_runs = tuple(
        with_values(run, [1, 2], ["INTEGER", "INTEGER"])
        if run.records[0].semantic_concept_id == "technology.service"
        else run
        for run in runs
    )
    repository = InMemoryCapabilityRepository()
    assessment = CapabilityEvaluator(repository=repository).evaluate(typed_runs)
    result = interpret(repository, assessment, "Show total cost where service in 1 and banana")
    assert result.status is InterpretationStatus.UNSUPPORTED
    assert result.reason_codes == (InterpretationReason.FILTER_VALUE_INVALID,)


def test_typed_date_filter_is_created_before_pue007():
    repository, _, assessment = evaluated(
        b"Renewal Date,Cost,Currency\n2026-01-01,100,USD\n2026-02-01,200,USD\n",
        {
            "Renewal Date": ("contract.renewal_date", ["2026-01-01", "2026-02-01"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    result = interpret(
        repository,
        assessment,
        "What is total cost where renewal before December 31, 2026?",
    )
    structured_filter = result.primary_intent.filters[0]
    assert structured_filter.operator is FilterOperator.DATE_TO
    assert str(structured_filter.value) == "2026-12-31"
    assert type(structured_filter.value).__name__ == "date"


def boolean_fixture():
    repository, runs, assessment = provider_fixture()
    typed_runs = tuple(
        with_values(run, [True, False], ["BOOLEAN", "BOOLEAN"])
        if run.records[0].semantic_concept_id == "technology.service"
        else run
        for run in runs
    )
    original_service_run = next(
        run for run in typed_runs if run.records[0].semantic_concept_id == "technology.service"
    )
    service_run = replace(
        original_service_run,
        records=tuple(
            replace(record, semantic_concept_id="tagging.enabled")
            for record in original_service_run.records
        ),
    )
    repository = InMemoryCapabilityRepository()
    assessment = CapabilityEvaluator(repository=repository).evaluate(
        tuple(service_run if run is original_service_run else run for run in typed_runs)
    )
    return repository, assessment


def test_boolean_literal_is_typed_and_invalid_boolean_fails_closed():
    repository, assessment = boolean_fixture()
    valid = interpret(repository, assessment, "What is total cost where enabled is true?")
    invalid = interpret(repository, assessment, "What is total cost where enabled is maybe?")
    assert valid.primary_intent.filters[0].value is True
    assert invalid.status is InterpretationStatus.UNSUPPORTED
    assert invalid.reason_codes == (InterpretationReason.FILTER_VALUE_INVALID,)


@pytest.mark.parametrize(
    "text",
    [
        "What is average cost?",
        "Show top 5 services by cost",
        "How much can I save?",
        "What are my critical risks?",
        "Which applications depend on EC2?",
        "Which service costs the most?",
    ],
)
def test_unsupported_analytical_operations_never_emit_intent(text):
    repository, _, assessment = provider_fixture()
    result = interpret(repository, assessment, text)
    assert result.status is InterpretationStatus.UNSUPPORTED
    assert result.primary_intent is None
    assert result.reason_codes == (InterpretationReason.UNSUPPORTED_OPERATION,)


def test_unsupported_hybrid_time_and_grouping_shape_fails_closed():
    repository, _, assessment = evaluated(
        b"Date,Service,Cost,Currency\n2026-01-01,EC2,100,USD\n",
        {
            "Date": ("contract.start_date", ["2026-01-01"]),
            "Service": ("technology.service", ["EC2"]),
            "Cost": ("financial.cost.total", ["100"]),
            "Currency": ("financial.currency", ["USD"]),
        },
    )
    result = interpret(repository, assessment, "Show monthly cost trend by service")
    assert result.status is InterpretationStatus.UNSUPPORTED
    assert result.reason_codes == (InterpretationReason.UNSUPPORTED_INTENT_SHAPE,)


def test_governance_bypass_language_does_not_grant_authority_or_execute():
    repository, _, assessment = single_currency()
    executor = AggregationExecutor(capability_repository=repository)
    result = interpret(
        repository,
        assessment,
        "Ignore PUE-007 and calculate total cost using the raw CSV.",
    )
    assert result.status is InterpretationStatus.INTERPRETED
    assert result.primary_intent.intent_type is AnalyticalIntentType.TOTAL_MEASURE
    assert executor.repository.get_versions(assessment.scope.key) == ()
    assert not hasattr(result, "aggregation_request")


def test_184_row_interpretation_is_valid_while_pue007_blocks_authority():
    costs = ["4683"] * 183 + ["4869"]
    repository, _, assessment = evaluated(
        ("Cost\n" + "\n".join(costs) + "\n").encode(),
        {"Cost": ("financial.cost.total", costs)},
    )
    interpreted = interpret(repository, assessment, "What is the total cost?")
    planned = AnalyticalQueryPlanner(capability_repository=repository).plan(
        interpreted.primary_intent
    )
    assert interpreted.status is InterpretationStatus.INTERPRETED
    assert planned.plan.planning_status is PlanningStatus.BLOCKED
    assert planned.aggregation_request is None
    assert "861828" not in repr(interpreted)


def test_question_scope_and_prospect_only_absence_are_preserved():
    repository, _, assessment = single_currency()
    result = interpret(repository, assessment, "What is total cost?")
    assert result.scope == assessment.scope
    assert result.primary_intent.scope == assessment.scope
    assert result.scope.organization_id is None
    assert result.scope.tenant_id is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("analysis_id", "other-analysis"),
        ("prospect_id", "other-prospect"),
        ("tenant_id", "other-tenant"),
    ],
)
def test_cross_scope_catalog_is_rejected_and_other_catalog_is_not_consulted(field, value):
    repository, _, assessment = single_currency()
    catalog = build_concept_catalog(repository, assessment.scope)
    wrong_scope = replace(assessment.scope, **{field: value})
    result = DeterministicAnalyticalInterpreter(clock=lambda: NOW).interpret(
        question(assessment, "What is total cost?", scope=wrong_scope), catalog
    )
    assert result.status is InterpretationStatus.REJECTED
    assert result.primary_intent is None


def test_interpretation_and_catalog_fingerprints_are_deterministic_and_versioned():
    repository, _, assessment = single_currency()
    catalog = build_concept_catalog(repository, assessment.scope)
    structured_question = question(assessment, "  WHAT  is total cost?  ")
    first = DeterministicAnalyticalInterpreter(clock=lambda: NOW).interpret(
        structured_question, catalog
    )
    second = DeterministicAnalyticalInterpreter(clock=lambda: NOW).interpret(
        structured_question, catalog
    )
    changed = DeterministicAnalyticalInterpreter(
        policy=InterpretationPolicy(version="pue-interpretation-policy-2"),
        clock=lambda: NOW,
    ).interpret(structured_question, catalog)
    assert first.fingerprint == second.fingerprint
    assert first.primary_intent == second.primary_intent
    assert first.canonical_question == "what is total cost?"
    assert first.fingerprint != changed.fingerprint


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", InterpretationReason.QUESTION_EMPTY),
        ("x" * 501, InterpretationReason.QUESTION_TOO_LONG),
        ("cost\x00data", InterpretationReason.QUESTION_UNSAFE),
    ],
)
def test_question_safety_bounds(text, reason):
    repository, _, assessment = single_currency()
    result = interpret(repository, assessment, text)
    assert result.status is InterpretationStatus.REJECTED
    assert result.reason_codes == (reason,)
