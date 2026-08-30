from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from data_fabric.contracts import EntityType
from data_fabric.foundation import TenantContext
from enterprise_registry.relationship_intelligence import RelationshipIntelligenceService
from services.prospect_data_intake_service import ProspectTenant
from tests.universal_evidence.test_pue_governed_materialization import (
    ORG,
    TENANT,
    Activation,
    _fixture,
    _service,
)
from tests.universal_evidence.test_pue_governed_measurement_pilot import (
    _confirm,
    _measurement,
)
from tests.universal_evidence.test_pue_governed_reconciliation import (
    _entity as _reconciliation_entity,
)
from tests.universal_evidence.test_pue_governed_reconciliation import (
    _observation as _reconciliation_observation,
)
from tests.universal_evidence.test_pue_governed_reconciliation import (
    _service as _reconciliation_service,
)
from universal_evidence.activation import (
    ActivationActor,
    ActivationPermission,
    InMemoryActivationAuditSink,
    InMemoryPueActivationRepository,
    PueActivationService,
)
from universal_evidence.operations import (
    AuditQuery,
    FailureClass,
    GovernedEventType,
    GovernedLifecycleOperations,
    GovernedOperationsHealthService,
    GovernedOperationsService,
    OperationContext,
)
from universal_evidence.persistence import (
    LifecyclePersistenceError,
    LifecycleScope,
    SQLiteLifecycleRepository,
)
from universal_evidence.pilot.admission import admit_uploaded_evidence
from universal_evidence.pilot.governed_intelligence import AskState, GovernedAskNexoraService
from universal_evidence.pilot.materialization import GovernedEntityMaterializationService
from universal_evidence.pilot.reconciliation import (
    GovernedIdentityReconciliationService,
    SourceIdentityObservation,
)
from universal_evidence.planning import AnalyticalIntentType


def _context(**overrides):
    values = dict(
        organization_id=ORG,
        tenant_id=TENANT,
        prospect_id="prospect-1",
        analysis_id="analysis-1",
        actor_id="alice",
        actor_role="operations",
        correlation_id="NX-COR-ACT011B-CONTROLLED",
    )
    values.update(overrides)
    return OperationContext(**values)


def _operations(tmp_path):
    return GovernedOperationsService(SQLiteLifecycleRepository(tmp_path / "act011b.db"))


def test_controlled_production_materialization_reconciliation_and_ask_share_trace(tmp_path):
    operations = _operations(tmp_path)
    operation_context = _context()
    tenant = TenantContext(ORG, TENANT)
    registry, relationships = _service(tenant)
    materializer = GovernedEntityMaterializationService(
        registry,
        relationships,
        operations=operations,
        operation_context=operation_context,
    )
    first = materializer.materialize(
        _fixture(), context=tenant, actor_id="alice", activation=Activation()
    )
    replay = materializer.materialize(
        _fixture(), context=tenant, actor_id="alice", activation=Activation()
    )
    resource = next(
        item for item in first.entities if item.entity_type is EntityType.CLOUD_RESOURCE
    )
    observations = (
        SourceIdentityObservation(
            source_system="aws",
            source_type="cloud",
            source_identifier="i-test123",
            entity_type=EntityType.CLOUD_RESOURCE,
            normalized_attributes={"resource_id": "i-test123"},
            organization_id=ORG,
            tenant_id=TENANT,
            prospect_id="prospect-1",
            analysis_id="analysis-1",
            source_id="aws",
            file_id="aws-safe",
            evidence_fingerprint="evidence-aws",
        ),
        SourceIdentityObservation(
            source_system="cmdb",
            source_type="cmdb",
            source_identifier="CI-10001",
            entity_type=EntityType.CLOUD_RESOURCE,
            normalized_attributes={"resource_id": "i-test123"},
            organization_id=ORG,
            tenant_id=TENANT,
            prospect_id="prospect-1",
            analysis_id="analysis-1",
            source_id="cmdb",
            file_id="cmdb-safe",
            evidence_fingerprint="evidence-cmdb",
        ),
    )
    reconciler = GovernedIdentityReconciliationService(
        registry, operations=operations, operation_context=operation_context
    )
    reconciled = reconciler.reconcile(observations, context=tenant, activation=Activation())
    graph = RelationshipIntelligenceService(
        tenant,
        role="auditor",
        entities=registry.list_entities(),
        relationships=relationships.search_relationships(organization_id=ORG),
    )
    ask = GovernedAskNexoraService(
        registry=registry,
        graph=graph,
        bindings=reconciled.bindings,
        operations=operations,
        operation_context=operation_context,
    )
    owner = ask.ask("Who owns Checkout?", scope=tenant, actor_id="alice")
    sources = ask.ask("Which sources describe i-test123?", scope=tenant, actor_id="alice")

    assert owner.state is AskState.SUPPORTED and "Alice" in owner.answer
    assert sources.state is AskState.SUPPORTED and "aws:i-test123" in sources.answer
    assert resource.canonical_id in {item.candidate_canonical_id for item in reconciled.proposals}
    emitted = operations.telemetry.events
    types = {item.event_type for item in emitted}
    assert {
        GovernedEventType.ENTITY_MATERIALIZED,
        GovernedEventType.MATCH_PROPOSED,
        GovernedEventType.BINDING_CREATED,
        GovernedEventType.ASK_RECEIVED,
        GovernedEventType.ASK_EXECUTED,
        GovernedEventType.ASK_ANSWER_COMPOSED,
    } <= types
    assert {item.context.correlation_id for item in emitted} == {
        operation_context.correlation_id
    }
    created = [item for item in emitted if item.event_type is GovernedEventType.ENTITY_MATERIALIZED]
    assert len(created) == len(first.entities)
    assert len(replay.entities) == len(first.entities)


def test_real_cur_admission_and_measurement_emit_safe_non_error_trace(tmp_path):
    workbook = Path("temp_uploads/CUR Jan 2026.xlsx")
    operations = _operations(tmp_path)
    context = _context(correlation_id="NX-COR-ACT011B-CUR")
    tenant = ProspectTenant(
        "prospect-cur",
        "audit-cur",
        "2026-08-30T00:00:00+00:00",
        "2026-09-30T00:00:00+00:00",
        31,
    )
    admission = admit_uploaded_evidence(
        tenant,
        filename=workbook.name,
        content=workbook.read_bytes(),
        operations=operations,
        operation_context=context,
    )
    measurement, normalization, semantic, *_items, actor, _audit = _measurement(admission)
    for service in (semantic, normalization, measurement):
        service.operations = operations
        service.operation_context = context
    _confirm(semantic, admission, actor, "Price Per Service (USD)", "financial.cost.total")
    planning, result = measurement.execute(
        admission,
        actor=actor,
        intent_type=AnalyticalIntentType.TOTAL_MEASURE,
        measure_concept_id="financial.cost.total",
    )
    events = operations.telemetry.events
    admitted = next(
        item for item in events if item.event_type is GovernedEventType.EVIDENCE_ADMITTED
    )
    assert admitted.attributes["detail_records"] == 184
    assert admitted.attributes["fields"] == 10
    assert result is None and planning.plan.planning_status.value in {"BLOCKED", "REJECTED"}
    block = next(item for item in events if item.event_type is GovernedEventType.CAPABILITY_BLOCKED)
    assert block.reason_code.value == "MISSING_GOVERNED_CURRENCY"
    assert block.severity.value == "INFO"
    assert not any(item.event_type is GovernedEventType.EXECUTION_FAILED for item in events)
    assert "861830" not in str([item.payload() for item in events])


def test_real_governance_mutation_fails_before_change_when_audit_is_unavailable(tmp_path):
    workbook = Path("temp_uploads/CUR Jan 2026.xlsx")
    tenant = ProspectTenant(
        "prospect-cur",
        "audit-cur",
        "2026-08-30T00:00:00+00:00",
        "2026-09-30T00:00:00+00:00",
        31,
    )
    admission = admit_uploaded_evidence(
        tenant, filename=workbook.name, content=workbook.read_bytes()
    )
    _measurement_service, _normalization, semantic, *_items, actor, _audit = _measurement(
        admission
    )

    class BrokenLifecycle:
        def put(self, *_args, **_kwargs):
            raise OSError("audit unavailable")

    semantic.operations = GovernedOperationsService(BrokenLifecycle())
    semantic.operation_context = _context()
    column = next(
        item
        for item in semantic.discovery(admission).columns
        if item.original_header == "Price Per Service (USD)"
    )
    before = semantic.confirmation_service.get_decision_history(column, actor=actor).decisions
    with pytest.raises(LifecyclePersistenceError):
        semantic.override(
            admission,
            column.source_column_reference,
            "financial.cost.total",
            actor=actor,
            reason="reviewed",
        )
    after = semantic.confirmation_service.get_decision_history(column, actor=actor).decisions
    assert after == before


def test_operations_status_is_derived_from_real_events(tmp_path):
    operations = _operations(tmp_path)
    operations.emit(
        GovernedEventType.ASK_BLOCKED,
        _context(),
        audit=False,
        outcome="BLOCKED",
        failure_class=FailureClass.EXPECTED_BLOCK,
    )
    status = GovernedOperationsHealthService(
        (("runtime", lambda: True), ("persistence", lambda: True))
    ).status(telemetry=operations.telemetry.events, activation_state="ACTIVE")
    assert status.ready and status.recent_blocks == 1 and status.recent_failures == 0


def test_real_cross_scope_materialization_denial_is_durably_audited(tmp_path):
    operations = _operations(tmp_path)
    tenant = TenantContext(ORG, TENANT)
    registry, relationships = _service(tenant)
    materializer = GovernedEntityMaterializationService(
        registry,
        relationships,
        operations=operations,
        operation_context=_context(),
    )
    foreign = _fixture()[0]
    foreign = replace(foreign, organization_id="foreign-organization")
    with pytest.raises(ValueError, match="organization or tenant"):
        materializer.materialize((foreign,), context=tenant, actor_id="alice")
    events = operations.query(AuditQuery(_context(), "auditor"))
    denial = next(
        item for item in events if item.event_type is GovernedEventType.SCOPE_ACCESS_REJECTED
    )
    assert denial.outcome == "DENIED"
    assert "foreign-organization" not in str(denial.payload())


def test_real_purge_trace_survives_restart_and_appends(tmp_path):
    database = tmp_path / "purge-restart.db"
    scope = LifecycleScope(ORG, TENANT, "prospect-1", "analysis-1")
    repository = SQLiteLifecycleRepository(database)
    repository.put("fixture", "one", scope, payload={"safe": True})
    first_ops = GovernedOperationsService(repository)
    lifecycle = GovernedLifecycleOperations(repository, first_ops, _context())
    assert lifecycle.purge_scope(scope, actor_id="alice", reason="retention request") == 1
    restarted_repo = SQLiteLifecycleRepository(database)
    restarted_ops = GovernedOperationsService(restarted_repo)
    before = restarted_ops.query(AuditQuery(_context(), "auditor"))
    appended = restarted_ops.emit(GovernedEventType.ACTIVATION_CHANGED, _context())
    after = restarted_ops.query(AuditQuery(_context(), "auditor"))
    assert {item.event_type for item in before} == {
        GovernedEventType.PURGE_REQUESTED,
        GovernedEventType.PURGE_COMPLETED,
    }
    assert len(after) == len(before) + 1 and appended.event_id not in {
        item.event_id for item in before
    }


def test_telemetry_export_failure_does_not_break_safe_operation(tmp_path):
    class BrokenTelemetry:
        def record(self, _event):
            raise OSError("exporter unavailable")

    service = GovernedOperationsService(
        SQLiteLifecycleRepository(tmp_path / "telemetry-failure.db"),
        telemetry=BrokenTelemetry(),
    )
    event = service.emit(
        GovernedEventType.NORMALIZATION_COMPLETED, _context(), audit=False
    )
    assert event.event_type is GovernedEventType.NORMALIZATION_COMPLETED


def test_real_kill_switch_changes_are_audited_and_drive_readiness(tmp_path):
    operations = _operations(tmp_path)
    repository = InMemoryPueActivationRepository()
    actor = ActivationActor(
        "security-admin",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (ActivationPermission.TRIGGER_PUE_KILL_SWITCH,),
    )
    service = PueActivationService(
        repository=repository,
        audit_sink=InMemoryActivationAuditSink(),
        clock=lambda: admission_time(),
        operations=operations,
        operation_context=_context(),
    )
    service.set_kill_switch(enabled=True, actor=actor, reason="incident containment")
    degraded = GovernedOperationsHealthService((("runtime", lambda: True),)).status(
        telemetry=operations.telemetry.events, kill_switch_enabled=True
    )
    service.set_kill_switch(enabled=False, actor=actor, reason="incident resolved")
    events = operations.query(AuditQuery(_context(), "auditor"))
    assert {item.event_type for item in events} == {
        GovernedEventType.KILL_SWITCH_ENABLED,
        GovernedEventType.KILL_SWITCH_DISABLED,
    }
    assert degraded.live and not degraded.ready


def test_real_reconciliation_confirmation_fails_before_change_without_audit(tmp_path):
    tenant = TenantContext("org-act007", "tenant-act007")
    registry, _relationships = _reconciliation_service(tenant)
    canonical = _reconciliation_entity(
        registry,
        tenant,
        EntityType.APPLICATION,
        "Payments",
        "catalogue",
        "APP-PAYMENTS",
    )
    rows = (
        _reconciliation_observation("source-a", "row-a", name="Payments"),
        _reconciliation_observation("source-b", "row-b", name="Payments"),
    )
    service = GovernedIdentityReconciliationService(registry)
    proposal = service.reconcile(rows, context=tenant, activation=Activation()).proposals[0]

    class BrokenLifecycle:
        def put(self, *_args, **_kwargs):
            raise OSError("audit unavailable")

    service.operations = GovernedOperationsService(BrokenLifecycle())
    service.operation_context = _context(
        organization_id=tenant.organization_id, tenant_id=tenant.tenant_id
    )
    with pytest.raises(LifecyclePersistenceError):
        service.confirm_match(
            proposal,
            canonical_id=canonical.canonical_id,
            actor_id="owner",
            reason="reviewed",
        )
    assert not service.reconcile(rows, context=tenant, activation=Activation()).decisions


def admission_time():
    from datetime import datetime, timezone

    return datetime(2026, 8, 30, tzinfo=timezone.utc)
