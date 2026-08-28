"""ACT-009C integrated durable lifecycle and startup certification."""

from __future__ import annotations

import gc
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from services.universal_evidence_runtime_service import initialize_universal_evidence_runtime
from tests.universal_evidence.test_pue_governed_intelligence import SCOPE, _graph_fixture
from tests.universal_evidence.test_pue_governed_measurement_pilot import (
    _admission,
    _confirm,
    _content,
)
from universal_evidence.activation import (
    ActivationActor,
    ActivationPermission,
    ActivationScope,
    ActivationStage,
    InMemoryActivationAuditSink,
    ScopeLevel,
)
from universal_evidence.durable_runtime import DurableRuntimeComposition
from universal_evidence.governance import ActorType, ConfirmationActor
from universal_evidence.persistence import (
    LifecyclePersistenceError,
    LifecycleScope,
    SQLiteLifecycleRepository,
)
from universal_evidence.pilot.governed_intelligence import AskState
from universal_evidence.planning import AnalyticalIntentType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _actors():
    admin = ActivationActor(
        "activation-admin",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
            ActivationPermission.TRIGGER_PUE_ROLLBACK,
        ),
    )
    governor = ConfirmationActor("governor", "governor", "super_admin", ActorType.HUMAN)
    return admin, governor


def _build(runtime, admission):
    audit = InMemoryActivationAuditSink()
    resolver, activation = runtime.build_activation_services(audit_sink=audit, clock=lambda: NOW)
    confirmation, semantic, normalization, measurement = runtime.build_pilot_services(
        activation_resolver=resolver, audit_sink=audit, clock=lambda: NOW
    )
    return resolver, activation, confirmation, semantic, normalization, measurement


def _activation_scope(admission):
    return ActivationScope(
        ScopeLevel.ANALYSIS,
        organization_id=admission.scope.organization_id,
        tenant_id=admission.scope.tenant_id,
        prospect_id=admission.scope.prospect_id,
        analysis_id=admission.scope.analysis_id,
    )


def test_full_governed_stack_survives_restart(tmp_path):
    database = tmp_path / "full-stack.db"
    evidence = _content(rows=(("Compute", 12, "USD"), ("Storage", 3, "USD")))
    admission = _admission(content=evidence)
    admin, governor = _actors()
    first = DurableRuntimeComposition(database)
    _resolver, activation, _confirmation, semantic, normalization, measurement = _build(
        first, admission
    )
    activation.configure(
        scope=_activation_scope(admission),
        stage=ActivationStage.CAPABILITY_VISIBLE,
        actor=admin,
        reason="ACT-009C durable activation",
    )
    for header, concept in (
        ("Service", "technology.service"),
        ("Amount", "financial.cost.total"),
        ("Currency", "financial.currency"),
    ):
        _confirm(semantic, admission, governor, header, concept)
    normalized_before = normalization.experience(admission, actor=governor)
    planning_before, result_before = measurement.execute(
        admission,
        actor=governor,
        intent_type=AnalyticalIntentType.TOTAL_MEASURE,
        measure_concept_id="financial.cost.total",
    )
    assert result_before.scalar_value == Decimal("15")
    lifecycle_scope = LifecycleScope(
        admission.scope.organization_id or "UNKNOWN",
        admission.scope.tenant_id or "UNKNOWN",
        admission.scope.prospect_id,
        admission.scope.analysis_id,
    )
    first.lineage.save(
        "entity-checkout",
        lifecycle_scope,
        references=(
            admission.evidence_fingerprint,
            normalized_before.fingerprint,
            result_before.result_fingerprint,
        ),
        fingerprint_value="lineage-checkout",
    )
    registry, graph, bindings = _graph_fixture()
    graph_scope = LifecycleScope(*bindings[0].scope)
    for binding in bindings:
        first.reconciliation.save_binding(binding)
    ask_before = first.build_governed_ask_service(registry, graph, graph_scope)
    owner_before = ask_before.ask("Who owns Checkout?", scope=SCOPE)
    sources_before = ask_before.ask("Which sources describe i-test123?", scope=SCOPE)
    measure_before = first.build_governed_ask_service(registry, graph, graph_scope)
    measure_before.measurement_service = measurement
    cost_before = measure_before.ask(
        "What is the total governed cost?",
        scope=admission.scope,
        admission=admission,
        actor=governor,
    )
    first.answers.save(
        cost_before.answer_fingerprint,
        lifecycle_scope,
        references=(result_before.result_fingerprint,),
    )
    expected = {
        "normalization": normalized_before.fingerprint,
        "plan": planning_before.plan.plan_fingerprint,
        "result": result_before.result_fingerprint,
        "owner": owner_before.answer_fingerprint,
        "sources": sources_before.answer_fingerprint,
    }

    del ask_before, measure_before, measurement, normalization, semantic, activation, first
    gc.collect()

    restarted_admission = _admission(content=evidence)
    second = DurableRuntimeComposition(database)
    resolver, _activation, _confirmation, semantic, normalization, measurement = _build(
        second, restarted_admission
    )
    assert (
        resolver.resolve(_activation_scope(restarted_admission)).stage
        is ActivationStage.CAPABILITY_VISIBLE
    )
    semantic_after = semantic.experience(restarted_admission, actor=governor)
    mappings = semantic_after.mappings
    assert semantic_after.effective_mapping_count == 3
    normalized_after = normalization.experience(restarted_admission, actor=governor)
    assert normalized_after.fingerprint == expected["normalization"]
    plans = second.plans.get_versions(restarted_admission.scope.key)
    results = second.results.get_versions(restarted_admission.scope.key)
    assert plans[-1].plan_fingerprint == expected["plan"]
    assert results[-1].result_fingerprint == expected["result"]
    assert measurement.result_is_current(
        restarted_admission, planning_before, results[-1], actor=governor
    )
    planning_after, result_after = measurement.execute(
        restarted_admission,
        actor=governor,
        intent_type=AnalyticalIntentType.TOTAL_MEASURE,
        measure_concept_id="financial.cost.total",
    )
    assert planning_after.plan.plan_fingerprint == expected["plan"]
    assert result_after.result_fingerprint == expected["result"]
    assert second.lineage.load("entity-checkout", lifecycle_scope).fingerprint == "lineage-checkout"
    assert len(second.reconciliation.bindings(graph_scope)) == 2
    ask_after = second.build_governed_ask_service(registry, graph, graph_scope)
    assert ask_after.ask("Who owns Checkout?", scope=SCOPE).answer_fingerprint == expected["owner"]
    assert (
        ask_after.ask("Which sources describe i-test123?", scope=SCOPE).answer_fingerprint
        == expected["sources"]
    )
    ask_after.measurement_service = measurement
    assert (
        ask_after.ask(
            "What is the total governed cost?",
            scope=restarted_admission.scope,
            admission=restarted_admission,
            actor=governor,
        ).state
        is AskState.SUPPORTED
    )

    amount = next(item for item in mappings if item.source_column_name == "Amount")
    semantic.confirmation_service.clock = lambda: NOW + timedelta(seconds=1)
    semantic.override(
        restarted_admission,
        amount.column_reference,
        "financial.price",
        actor=governor,
        reason="ACT-009C stale authority certification",
    )
    assert not measurement.result_is_current(
        restarted_admission, planning_before, results[-1], actor=governor
    )
    assert second.answers.load(cost_before.answer_fingerprint, lifecycle_scope).payload is not None


def test_activation_kill_switch_and_scoped_purge_survive_restart(tmp_path):
    database = tmp_path / "policy.db"
    admission = _admission()
    admin, governor = _actors()
    first = DurableRuntimeComposition(database)
    _resolver, activation, *_services = _build(first, admission)
    activation.configure(
        scope=_activation_scope(admission),
        stage=ActivationStage.CAPABILITY_VISIBLE,
        actor=admin,
        reason="persist stage",
    )
    activation.set_kill_switch(enabled=True, actor=admin, reason="persist emergency stop")
    retained_scope = LifecycleScope("org-b", "tenant-b", "prospect-b", "analysis-b")
    first.lifecycle.put("answer_reference", "retained", retained_scope, payload={"references": []})
    del first, activation
    gc.collect()

    second = DurableRuntimeComposition(database)
    resolver, activation, _confirmation, _semantic, _normalization, measurement = _build(
        second, admission
    )
    assert resolver.resolve(_activation_scope(admission)).stage is ActivationStage.SHADOW_ONLY
    registry, graph, bindings = _graph_fixture()
    ask = second.build_governed_ask_service(
        registry,
        graph,
        LifecycleScope(*bindings[0].scope),
        activation_resolver=resolver,
    )
    assert ask.ask("Who owns Checkout?", scope=SCOPE).state is AskState.BLOCKED
    with pytest.raises(PermissionError, match="activation"):
        measurement.execute(
            admission, actor=governor, intent_type=AnalyticalIntentType.COUNT_RECORDS
        )
    activation.set_kill_switch(enabled=False, actor=admin, reason="authorized recovery")
    assert (
        resolver.resolve(_activation_scope(admission)).stage is ActivationStage.CAPABILITY_VISIBLE
    )
    target_scope = LifecycleScope(
        admission.scope.organization_id or "UNKNOWN",
        admission.scope.tenant_id or "UNKNOWN",
        admission.scope.prospect_id,
        admission.scope.analysis_id,
    )
    second.lifecycle.put(
        "answer_reference", "purged", target_scope, payload={"references": ["sensitive"]}
    )
    second.lifecycle.purge_scope(target_scope, actor_id="privacy-admin", reason="approved purge")
    del second
    third = DurableRuntimeComposition(database)
    assert third.lifecycle.list_scope(target_scope) == ()
    assert third.lifecycle.list_scope(target_scope, include_purged=True)
    assert (
        third.lifecycle.get("answer_reference", "retained", retained_scope).object_key == "retained"
    )


def test_normal_startup_migrates_upgrades_replays_and_fails_closed(tmp_path, monkeypatch):
    database = tmp_path / "startup.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE existing_record (value TEXT NOT NULL)")
        connection.execute("INSERT INTO existing_record VALUES ('preserved')")
    first = initialize_universal_evidence_runtime(database)
    second = initialize_universal_evidence_runtime(database)
    assert first is not None and second is not None
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM existing_record").fetchone() == ("preserved",)
        assert connection.execute(
            "SELECT COUNT(*) FROM universal_evidence_migrations"
        ).fetchone() == (1,)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(LifecyclePersistenceError, match="migration failed"):
        initialize_universal_evidence_runtime(corrupt)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("NEXORA_UNIVERSAL_EVIDENCE_DB", raising=False)
    with pytest.raises(LifecyclePersistenceError, match="required"):
        initialize_universal_evidence_runtime()


def test_concurrent_duplicate_writes_have_one_effective_authority(tmp_path):
    database = tmp_path / "concurrent.db"
    repository = SQLiteLifecycleRepository(database)
    scope = LifecycleScope("org", "tenant", "prospect", "analysis")

    def write(object_type):
        return repository.put(
            object_type,
            "same-fingerprint",
            scope,
            payload={"fingerprint": "same-fingerprint"},
            fingerprint_value="same-fingerprint",
        )

    for object_type in (
        "mapping_decision",
        "source_binding",
        "analytical_plan",
        "aggregation_result",
    ):
        with ThreadPoolExecutor(max_workers=4) as pool:
            tuple(pool.map(lambda _item: write(object_type), range(8)))
        records = [item for item in repository.list_scope(scope) if item.object_type == object_type]
        assert len(records) == 1
        assert records[0].version == 1
