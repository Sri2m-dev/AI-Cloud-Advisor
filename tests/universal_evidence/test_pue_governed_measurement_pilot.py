"""ACT-005 governed measurement orchestration tests."""

from decimal import Decimal
from pathlib import Path

import pytest

from tests.universal_evidence.test_pue_governed_normalization_pilot import (
    _admission,
    _confirm,
    _content,
    _runtime,
)
from universal_evidence.activation import ActivationStage, InMemoryActivationAuditSink
from universal_evidence.aggregation import AggregationResultStatus
from universal_evidence.pilot.measurement_service import PilotGovernedMeasurementService
from universal_evidence.planning import AnalyticalIntentType, PlanningStatus


def _measurement(admission, stage=ActivationStage.CAPABILITY_VISIBLE):
    normalization, semantic, activation, admin, scope, actor = _runtime(admission, stage)
    audit = InMemoryActivationAuditSink()
    service = PilotGovernedMeasurementService(
        activation_resolver=normalization.activation_resolver,
        normalization_service=normalization,
        telemetry=normalization.telemetry,
        audit_sink=audit,
        clock=normalization.normalization.clock,
    )
    return service, normalization, semantic, activation, admin, scope, actor, audit


def _govern_financial(semantic, admission, actor):
    _confirm(semantic, admission, actor, "Amount", "financial.cost.total")
    _confirm(semantic, admission, actor, "Currency", "financial.currency")


def test_candidate_only_and_shadow_block_measurement_without_a_number():
    admission = _admission()
    service, *_items, actor, _audit = _measurement(admission)
    readiness = service.readiness(admission, actor=actor)
    assert readiness.state == "BLOCKED"
    with pytest.raises(PermissionError, match="normalization"):
        service.execute(admission, actor=actor, intent_type=AnalyticalIntentType.COUNT_RECORDS)
    shadow, *_items, shadow_actor, _audit = _measurement(admission, ActivationStage.SHADOW_ONLY)
    assert shadow.readiness(admission, actor=shadow_actor) is None
    with pytest.raises(PermissionError, match="ACT-C1"):
        shadow.execute(
            admission,
            actor=shadow_actor,
            intent_type=AnalyticalIntentType.COUNT_RECORDS,
        )


def test_count_executes_only_over_governed_normalized_source_rows():
    admission = _admission()
    service, _, semantic, *_items, actor, audit = _measurement(admission)
    _confirm(semantic, admission, actor, "Service", "technology.service")
    planning, result = service.execute(
        admission, actor=actor, intent_type=AnalyticalIntentType.COUNT_RECORDS
    )
    assert planning.plan.planning_status is PlanningStatus.READY
    assert result.status is AggregationResultStatus.COMPLETED
    assert result.scalar_value == 2
    assert result.provenance and result.provenance.normalization_run_ids
    assert result.statistics.included_records == 2
    assert any(item.event_type == "PUE_AGGREGATION_EXECUTED" for item in audit.events)


def test_governed_amount_and_currency_authorize_sum_with_complete_provenance():
    admission = _admission(
        content=_content(rows=(("Compute", "12.50", "USD"), ("Storage", "2.50", "USD")))
    )
    service, _, semantic, *_items, actor, _audit = _measurement(admission)
    _govern_financial(semantic, admission, actor)
    readiness = service.readiness(admission, actor=actor)
    assert readiness.currency_ready and "SUM" in readiness.available_operations
    planning, result = service.execute(
        admission,
        actor=actor,
        intent_type=AnalyticalIntentType.TOTAL_MEASURE,
        measure_concept_id="financial.cost.total",
    )
    assert planning.plan.planning_status is PlanningStatus.READY
    assert result.scalar_value == Decimal("15.00")
    assert result.currency_or_unit == "USD"
    assert result.statistics.excluded_null_records == 0
    assert result.provenance.mapping_decision_ids
    assert result.plan_id and result.result_fingerprint


def test_missing_currency_and_mixed_currency_block_cross_currency_sum():
    missing = _admission(content=_content(headers=("Service", "Amount"), rows=(("A", 1),)))
    service, _, semantic, *_items, actor, _audit = _measurement(missing)
    _confirm(semantic, missing, actor, "Amount", "financial.cost.total")
    planning, result = service.execute(
        missing,
        actor=actor,
        intent_type=AnalyticalIntentType.TOTAL_MEASURE,
        measure_concept_id="financial.cost.total",
    )
    assert planning.plan.planning_status in {PlanningStatus.BLOCKED, PlanningStatus.REJECTED}
    assert result is None

    mixed = _admission(
        name="mixed",
        content=_content(rows=(("A", 1, "USD"), ("B", 2, "INR"))),
    )
    mixed_service, _, mixed_semantic, *_items, mixed_actor, _audit = _measurement(mixed)
    _govern_financial(mixed_semantic, mixed, mixed_actor)
    mixed_plan, mixed_result = mixed_service.execute(
        mixed,
        actor=mixed_actor,
        intent_type=AnalyticalIntentType.TOTAL_MEASURE,
        measure_concept_id="financial.cost.total",
    )
    assert mixed_plan.plan.planning_status is PlanningStatus.BLOCKED
    assert mixed_result is None


def test_grouped_sum_uses_only_governed_dimension_and_is_deterministic():
    admission = _admission(
        content=_content(
            rows=(("Compute", 10, "USD"), ("Storage", 3, "USD"), ("Compute", 2, "USD"))
        )
    )
    service, _, semantic, *_items, actor, _audit = _measurement(admission)
    _govern_financial(semantic, admission, actor)
    _confirm(semantic, admission, actor, "Service", "technology.service")
    args = dict(
        actor=actor,
        intent_type=AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
        measure_concept_id="financial.cost.total",
        dimension_concept_ids=("technology.service",),
    )
    first_plan, first = service.execute(admission, **args)
    second_plan, second = service.execute(admission, **args)
    assert first_plan.plan.plan_fingerprint == second_plan.plan.plan_fingerprint
    assert first.result_fingerprint == second.result_fingerprint
    assert [(group.dimension_values[0][1], group.value) for group in first.groups] == [
        ("Compute", Decimal("12")),
        ("Storage", Decimal("3")),
    ]
    assert service.result_is_current(admission, first_plan, first, actor=actor)
    amount = next(
        item
        for item in semantic.experience(admission, actor=actor).mappings
        if item.source_column_name == "Amount"
    )
    semantic.override(
        admission,
        amount.column_reference,
        "financial.price",
        actor=actor,
        reason="ACT-005 stale-result test",
    )
    assert not service.result_is_current(admission, first_plan, first, actor=actor)


def test_unit_price_never_substitutes_for_total_cost():
    admission = _admission(content=_content(headers=("Unit Price", "Currency"), rows=((5, "USD"),)))
    service, _, semantic, *_items, actor, _audit = _measurement(admission)
    _confirm(semantic, admission, actor, "Unit Price", "financial.cost.unit")
    _confirm(semantic, admission, actor, "Currency", "financial.currency")
    planning, result = service.execute(
        admission,
        actor=actor,
        intent_type=AnalyticalIntentType.TOTAL_MEASURE,
        measure_concept_id="financial.cost.total",
    )
    assert planning.plan.planning_status in {PlanningStatus.REJECTED, PlanningStatus.BLOCKED}
    assert result is None


def test_kill_switch_suppresses_prior_result_but_preserves_governance_and_runs():
    admission = _admission()
    service, normalization, semantic, activation, admin, _scope, actor, _audit = _measurement(
        admission
    )
    _confirm(semantic, admission, actor, "Service", "technology.service")
    _, result = service.execute(
        admission, actor=actor, intent_type=AnalyticalIntentType.COUNT_RECORDS
    )
    assert result.scalar_value == 2
    activation.set_kill_switch(enabled=True, actor=admin, reason="ACT-005 test")
    assert service.readiness(admission, actor=actor) is None
    assert normalization.normalization.repository.get_by_analysis(admission.scope.analysis_id)
    column = next(
        item for item in semantic.discovery(admission).columns if item.original_header == "Service"
    )
    assert semantic.confirmation_service.get_effective_mapping(column, actor=actor)


def test_synthetic_workbook_cost_stays_blocked_without_currency_authority():
    path = Path("tests/fixtures/cmp_p1/fixture_a_cloud_cost.xlsx")
    if not path.exists():
        pytest.skip("certified local workbook is not present")
    admission = _admission(name="real-act005", content=path.read_bytes())
    service, _, semantic, *_items, actor, _audit = _measurement(admission)
    _confirm(semantic, admission, actor, "Extended Amount (USD)", "financial.cost.total")
    primary = next(item for item in admission.regions if item.region_kind == "PRIMARY_DETAIL")
    planning, result = service.execute(
        admission,
        actor=actor,
        intent_type=AnalyticalIntentType.TOTAL_MEASURE,
        measure_concept_id="financial.cost.total",
    )
    assert primary.detail_record_count == 3 and primary.end_row < 10
    assert planning.plan.planning_status in {PlanningStatus.BLOCKED, PlanningStatus.REJECTED}
    assert result is None
    assert "861830" not in repr(planning)
