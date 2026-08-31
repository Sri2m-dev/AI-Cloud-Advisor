from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from cryptography.fernet import Fernet

from data_fabric.contracts import EntityType
from data_fabric.foundation import TenantContext
from services.prospect_data_intake_service import (
    ProspectIntakeError,
    ingest_upload,
    load_analysis,
)
from tests.prospect_intake.test_prospect_data_intake import _tenant
from tests.universal_evidence.test_act012_security_certification import (
    ORG,
    TENANT,
    _operation_context,
    _proposal,
    _trusted,
)
from tests.universal_evidence.test_pue_governed_materialization import (
    Activation as MaterializationActivation,
)
from tests.universal_evidence.test_pue_governed_materialization import (
    _fixture as materialization_fixture,
)
from tests.universal_evidence.test_pue_governed_materialization import (
    _service as materialization_service,
)
from tests.universal_evidence.test_pue_governed_measurement_pilot import (
    _admission,
    _confirm,
    _measurement,
)
from tests.universal_evidence.test_pue_governed_reconciliation import (
    Activation,
    _entity,
    _service,
)
from universal_evidence.durable_runtime import DurableRuntimeComposition
from universal_evidence.operations import (
    AuditQuery,
    GovernedEventType,
    GovernedLifecycleOperations,
    GovernedOperationsService,
)
from universal_evidence.persistence import (
    LifecyclePersistenceError,
    LifecycleScope,
    SQLiteLifecycleRepository,
)
from universal_evidence.pilot.governed_intelligence import AskState, GovernedAskNexoraService
from universal_evidence.pilot.materialization import GovernedEntityMaterializationService
from universal_evidence.pilot.production_views import confirm_reconciliation
from universal_evidence.pilot.reconciliation import GovernedIdentityReconciliationService
from universal_evidence.planning import AnalyticalIntentType


def test_forged_role_argument_is_not_a_production_authority(tmp_path):
    tenant = TenantContext(ORG, TENANT)
    registry, _relationships = _service(tenant)
    canonical = _entity(
        registry,
        tenant,
        EntityType.APPLICATION,
        "Payments",
        "catalogue",
        "APP-PAYMENTS",
    )
    rows, proposal = _proposal(registry)
    operations = GovernedOperationsService(SQLiteLifecycleRepository(tmp_path / "forged.db"))
    service = GovernedIdentityReconciliationService(
        registry, operations=operations, operation_context=_operation_context("executive")
    )
    with pytest.raises(TypeError):
        confirm_reconciliation(
            service,
            proposal,
            canonical_id=canonical.canonical_id,
            authorization=_trusted("executive", "executive@example"),
            role="super_admin",
            reason="forged caller role",
        )
    with pytest.raises(PermissionError):
        confirm_reconciliation(
            service,
            proposal,
            canonical_id=canonical.canonical_id,
            authorization=_trusted("executive", "executive@example"),
            reason="forged caller role",
        )
    assert not service.reconcile(rows, context=tenant, activation=Activation()).decisions
    event = operations.query(AuditQuery(_operation_context("executive"), "auditor"))[0]
    assert event.event_type is GovernedEventType.UNAUTHORIZED_ACTION
    assert event.context.actor_id == "executive@example"


@pytest.mark.parametrize(
    "scope",
    (
        (ORG, "foreign-tenant", "prospect-1", "analysis-1"),
        (ORG, TENANT, "foreign-prospect", "analysis-1"),
        (ORG, TENANT, "prospect-1", "foreign-analysis"),
    ),
)
def test_trusted_scope_cannot_be_overridden(scope, tmp_path):
    tenant = TenantContext(ORG, TENANT)
    registry, _relationships = _service(tenant)
    canonical = _entity(
        registry, tenant, EntityType.APPLICATION, "Payments", "catalogue", "APP-PAYMENTS"
    )
    _rows, proposal = _proposal(registry)
    proposal = replace(proposal, scope=scope)
    operations = GovernedOperationsService(SQLiteLifecycleRepository(tmp_path / "scope.db"))
    service = GovernedIdentityReconciliationService(
        registry, operations=operations, operation_context=_operation_context()
    )
    with pytest.raises(PermissionError):
        service.confirm_match(
            proposal,
            canonical_id=canonical.canonical_id,
            authorization=_trusted(),
            reason="tampered scope",
        )
    event = operations.query(AuditQuery(_operation_context(), "auditor"))[0]
    assert event.event_type is GovernedEventType.SCOPE_ACCESS_REJECTED
    assert "foreign" not in str(event.payload())


def test_encryption_restart_missing_wrong_and_corrupt_key_fail_closed(tmp_path, monkeypatch):
    key = Fernet.generate_key()
    tenant = _tenant(tmp_path, key)
    ingest_upload(
        tenant,
        profile="GCP billing export",
        filename="safe.csv",
        content=b"provider,service,cost\nGCP,Compute,100\n",
        actor="sales@example.com",
        role="sales_engineer",
        root=tmp_path,
        key=key,
    )
    assert load_analysis(tenant.tenant_id, root=tmp_path, key=key).row_count == 1
    monkeypatch.delenv("NEXORA_PROSPECT_DATA_KEY", raising=False)
    with pytest.raises(ProspectIntakeError, match="required"):
        load_analysis(tenant.tenant_id, root=tmp_path)
    with pytest.raises(ProspectIntakeError, match="cannot be read"):
        load_analysis(tenant.tenant_id, root=tmp_path, key=Fernet.generate_key())
    encrypted = tmp_path / tenant.tenant_id / "analysis.enc"
    encrypted.write_bytes(encrypted.read_bytes()[:-8] + b"corrupt!")
    with pytest.raises(ProspectIntakeError, match="cannot be read") as error:
        load_analysis(tenant.tenant_id, root=tmp_path, key=key)
    rendered = str(error.value)
    assert str(tmp_path) not in rendered and key.decode() not in rendered
    assert not (tmp_path / ".streamlit" / "prospect-data.key").exists()


def test_reconciliation_decision_persistence_failure_leaves_no_authority(tmp_path):
    tenant = TenantContext(ORG, TENANT)
    registry, _relationships = _service(tenant)
    canonical = _entity(
        registry, tenant, EntityType.APPLICATION, "Payments", "catalogue", "APP-PAYMENTS"
    )
    rows, proposal = _proposal(registry)

    class BrokenPersistence:
        def save_decision(self, _decision):
            raise OSError("write failed")

    service = GovernedIdentityReconciliationService(registry, persistence=BrokenPersistence())
    with pytest.raises(OSError, match="write failed"):
        service.confirm_match(
            proposal,
            canonical_id=canonical.canonical_id,
            authorization=_trusted(),
            reason="reviewed",
        )
    assert not service.reconcile(rows, context=tenant, activation=Activation()).decisions


def test_binding_partial_failure_is_explicit_and_retry_is_idempotent():
    tenant = TenantContext(ORG, TENANT)
    registry, _relationships = _service(tenant)
    canonical = _entity(
        registry, tenant, EntityType.APPLICATION, "Payments", "catalogue", "APP-PAYMENTS"
    )
    rows, proposal = _proposal(registry)

    class RecoverablePersistence:
        fail = False

        def save_decision(self, _decision):
            return None

        def save_binding(self, _binding):
            if self.fail:
                raise OSError("binding unavailable")

    persistence = RecoverablePersistence()
    service = GovernedIdentityReconciliationService(registry, persistence=persistence)
    service.confirm_match(
        proposal,
        canonical_id=canonical.canonical_id,
        authorization=_trusted(),
        reason="reviewed",
    )
    persistence.fail = True
    with pytest.raises(OSError, match="binding unavailable"):
        service.reconcile(rows, context=tenant, activation=Activation())
    persistence.fail = False
    recovered = service.reconcile(rows, context=tenant, activation=Activation())
    replay = service.reconcile(rows, context=tenant, activation=Activation())
    assert len(recovered.bindings) == len(replay.bindings) == 2
    assert replay.counts["bindings_created"] == 0


def test_concurrent_confirm_reject_has_one_authoritative_outcome(tmp_path):
    tenant = TenantContext(ORG, TENANT)
    registry, _relationships = _service(tenant)
    canonical = _entity(
        registry, tenant, EntityType.APPLICATION, "Payments", "catalogue", "APP-PAYMENTS"
    )
    rows, proposal = _proposal(registry)
    service = GovernedIdentityReconciliationService(registry)

    def confirm():
        return service.confirm_match(
            proposal,
            canonical_id=canonical.canonical_id,
            authorization=_trusted(actor_id="confirm-actor"),
            reason="confirm",
        )

    def reject():
        return service.reject_match(
            proposal,
            authorization=_trusted(actor_id="reject-actor"),
            reason="reject",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.exception() for future in (pool.submit(confirm), pool.submit(reject))]
    assert sum(item is None for item in outcomes) == 1
    report = service.reconcile(rows, context=tenant, activation=Activation())
    assert len(report.decisions) == 1


def test_entity_relationship_partial_failure_has_safe_idempotent_retry():
    tenant = TenantContext("org-act006", "tenant-act006")
    registry, relationships = materialization_service(tenant)
    original = relationships.register_relationship
    failed = {"once": False}

    def fail_once(edge):
        if not failed["once"]:
            failed["once"] = True
            raise OSError("relationship unavailable")
        return original(edge)

    relationships.register_relationship = fail_once
    service = GovernedEntityMaterializationService(registry, relationships)
    with pytest.raises(OSError, match="relationship unavailable"):
        service.materialize(
            materialization_fixture(), context=tenant, activation=MaterializationActivation()
        )
    recovered = service.materialize(
        materialization_fixture(), context=tenant, activation=MaterializationActivation()
    )
    assert len(registry.list_entities()) == 6
    assert recovered.relationships


def test_purge_partial_failure_is_audited_and_retry_preserves_other_scope(tmp_path):
    repository = SQLiteLifecycleRepository(tmp_path / "purge-partial.db")
    scope = LifecycleScope(ORG, TENANT, "prospect-1", "analysis-1")
    other = LifecycleScope(ORG, TENANT, "prospect-other", "analysis-other")
    repository.put("fixture", "target", scope, payload={"safe": True})
    repository.put("fixture", "other", other, payload={"safe": True})
    original = repository.purge_scope
    repository.purge_scope = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        LifecyclePersistenceError("purge failed")
    )
    operations = GovernedOperationsService(repository)
    lifecycle = GovernedLifecycleOperations(repository, operations, _operation_context())
    with pytest.raises(LifecyclePersistenceError):
        lifecycle.purge_scope(scope, authorization=_trusted(), reason="retention")
    assert repository.get("fixture", "target", scope)
    assert repository.get("fixture", "other", other)
    repository.purge_scope = original
    assert lifecycle.purge_scope(scope, authorization=_trusted(), reason="retry") == 1
    events = operations.query(AuditQuery(_operation_context(), "auditor"))
    assert GovernedEventType.PURGE_FAILED in {item.event_type for item in events}


def test_corrupt_database_and_migration_failure_never_construct_runtime(tmp_path):
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database and never replace me")
    with pytest.raises(Exception):
        DurableRuntimeComposition(corrupt)
    assert corrupt.read_bytes().startswith(b"not a sqlite")

    def broken_connection():
        raise OSError("database unavailable")

    with pytest.raises(LifecyclePersistenceError, match="migration failed") as error:
        SQLiteLifecycleRepository(
            tmp_path / "migration.db", connection_factory=broken_connection
        )
    assert str(tmp_path) not in str(error.value)


def test_kill_switch_race_rechecks_after_ready_plan_before_execution(monkeypatch):
    admission = _admission()
    service, _normalization, semantic, activation, admin, _scope, actor, audit = _measurement(
        admission
    )
    _confirm(semantic, admission, actor, "Service", "technology.service")
    original_plan = service.planner.plan

    def plan_then_kill(intent):
        planning = original_plan(intent)
        activation.set_kill_switch(enabled=True, actor=admin, reason="ACT-012 race")
        return planning

    monkeypatch.setattr(service.planner, "plan", plan_then_kill)
    with pytest.raises(PermissionError, match="activation changed"):
        service.execute(
            admission,
            actor=actor,
            intent_type=AnalyticalIntentType.COUNT_RECORDS,
        )
    assert any(item.event_type == "PUE_MEASUREMENT_EXECUTION_BLOCKED" for item in audit.events)


def test_kill_switch_race_blocks_ask_after_prior_authority_exists():
    admission = _admission()
    measurement, normalization, semantic, activation, admin, _scope, actor, _audit = _measurement(
        admission
    )
    _confirm(semantic, admission, actor, "Service", "technology.service")
    assert measurement.readiness(admission, actor=actor).available_operations
    activation.set_kill_switch(enabled=True, actor=admin, reason="ACT-012 Ask race")
    ask = GovernedAskNexoraService(
        measurement_service=measurement,
        activation_resolver=normalization.activation_resolver,
    )
    response = ask.ask(
        "How many governed records are there?",
        scope=admission.scope,
        admission=admission,
        actor=actor,
    )
    assert response.state is AskState.BLOCKED
    assert response.execution is None
