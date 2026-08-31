from __future__ import annotations

from dataclasses import replace

import pytest

from auth.tenant_authorization import TenantAuthorizationContext
from data_fabric.contracts import EntityType
from data_fabric.foundation import TenantContext
from tests.universal_evidence.test_pue_governed_reconciliation import (
    Activation,
    _entity,
    _observation,
    _service,
)
from universal_evidence.operations import (
    AuditQuery,
    GovernedEventType,
    GovernedLifecycleOperations,
    GovernedOperationsService,
    OperationContext,
)
from universal_evidence.persistence import LifecycleScope, SQLiteLifecycleRepository
from universal_evidence.pilot.reconciliation import GovernedIdentityReconciliationService
from universal_evidence.security import WorkflowAuthorizationContext

ORG = "org-act007"
TENANT = "tenant-act007"


def _operation_context(role="operations"):
    return OperationContext(
        ORG,
        TENANT,
        "prospect-1",
        "analysis-1",
        "actor-1",
        role,
        "NX-COR-ACT012-SECURITY",
    )


def _trusted(
    role="operations",
    actor_id="actor-1",
    *,
    organization_id=ORG,
    tenant_id=TENANT,
    prospect_id="prospect-1",
    analysis_id="analysis-1",
):
    return WorkflowAuthorizationContext(
        TenantAuthorizationContext(
            organization_id,
            tenant_id,
            actor_id,
            "user",
            roles=frozenset({role}),
            source_boundary="test-authenticated-principal",
        ),
        prospect_id,
        analysis_id,
    )


def _proposal(registry):
    rows = (
        _observation("source-a", "row-a", name="Payments"),
        _observation("source-b", "row-b", name="Payments"),
    )
    service = GovernedIdentityReconciliationService(registry)
    proposal = service.reconcile(
        rows, context=TenantContext(ORG, TENANT), activation=Activation()
    ).proposals[0]
    return rows, proposal


@pytest.mark.parametrize("role", ("executive", "viewer", "auditor", "finance", "technical"))
@pytest.mark.parametrize("action", ("confirm", "reject"))
def test_unauthorized_reconciliation_mutation_denied_before_state_and_audited(
    role, action, tmp_path
):
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    canonical = _entity(
        registry,
        context,
        EntityType.APPLICATION,
        "Payments",
        "catalogue",
        "APP-PAYMENTS",
    )
    rows, proposal = _proposal(registry)
    operations = GovernedOperationsService(SQLiteLifecycleRepository(tmp_path / f"{role}.db"))
    service = GovernedIdentityReconciliationService(
        registry, operations=operations, operation_context=_operation_context(role)
    )
    with pytest.raises(PermissionError, match="authorized operational role"):
        if action == "confirm":
            service.confirm_match(
                proposal,
                canonical_id=canonical.canonical_id,
                authorization=_trusted(role, "attacker"),
                reason="tampered request",
            )
        else:
            service.reject_match(
                proposal,
                authorization=_trusted(role, "attacker"),
                reason="tampered request",
            )
    assert not service.reconcile(rows, context=context, activation=Activation()).decisions
    events = operations.query(AuditQuery(_operation_context(role), "auditor"))
    assert len(events) == 1
    assert events[0].event_type is GovernedEventType.UNAUTHORIZED_ACTION
    assert events[0].outcome == "DENIED"
    assert canonical.canonical_id not in str(events[0].payload())


@pytest.mark.parametrize("role", ("super_admin", "client_admin", "operations"))
def test_authorized_reconciliation_confirmation_succeeds_and_is_audited(role, tmp_path):
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    canonical = _entity(
        registry,
        context,
        EntityType.APPLICATION,
        "Payments",
        "catalogue",
        "APP-PAYMENTS",
    )
    rows, proposal = _proposal(registry)
    operations = GovernedOperationsService(SQLiteLifecycleRepository(tmp_path / f"{role}.db"))
    service = GovernedIdentityReconciliationService(
        registry, operations=operations, operation_context=_operation_context(role)
    )
    decision = service.confirm_match(
        proposal,
        canonical_id=canonical.canonical_id,
        authorization=_trusted(role, "operator"),
        reason="reviewed governed sources",
    )
    report = service.reconcile(rows, context=context, activation=Activation())
    assert decision in report.decisions and report.bindings
    events = operations.query(AuditQuery(_operation_context(role), "auditor"))
    assert any(item.event_type is GovernedEventType.MATCH_CONFIRMED for item in events)


def test_target_tampering_cross_type_and_cross_tenant_fails_without_decision(tmp_path):
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    wrong_type = _entity(
        registry,
        context,
        EntityType.BUSINESS_SERVICE,
        "Payments",
        "catalogue",
        "SERVICE-PAYMENTS",
    )
    rows, proposal = _proposal(registry)
    service = GovernedIdentityReconciliationService(
        registry,
        operations=GovernedOperationsService(SQLiteLifecycleRepository(tmp_path / "tamper.db")),
        operation_context=_operation_context(),
    )
    with pytest.raises(ValueError, match="type"):
        service.confirm_match(
            proposal,
            canonical_id=wrong_type.canonical_id,
            authorization=_trusted(actor_id="operator"),
            reason="tampered target",
        )
    foreign = replace(proposal, scope=("foreign-org", "foreign-tenant", *proposal.scope[2:]))
    with pytest.raises(Exception):
        service.confirm_match(
            foreign,
            canonical_id=wrong_type.canonical_id,
            authorization=_trusted(actor_id="operator"),
            reason="tampered scope",
        )
    assert not service.reconcile(rows, context=context, activation=Activation()).decisions


def test_unauthorized_purge_is_denied_and_other_scope_remains(tmp_path):
    repository = SQLiteLifecycleRepository(tmp_path / "purge-security.db")
    scope_a = LifecycleScope(ORG, TENANT, "prospect-a", "analysis-a")
    scope_b = LifecycleScope(ORG, TENANT, "prospect-b", "analysis-b")
    repository.put("fixture", "a", scope_a, payload={"safe": "a"})
    repository.put("fixture", "b", scope_b, payload={"safe": "b"})
    operations = GovernedOperationsService(repository)
    lifecycle = GovernedLifecycleOperations(repository, operations, _operation_context())
    with pytest.raises(PermissionError):
        lifecycle.purge_scope(
            scope_a,
            authorization=_trusted(
                "executive",
                "executive",
                prospect_id="prospect-a",
                analysis_id="analysis-a",
            ),
            reason="tampered",
        )
    assert repository.get("fixture", "a", scope_a)
    assert repository.get("fixture", "b", scope_b)
    query_context = replace(
        _operation_context("executive"), prospect_id="prospect-a", analysis_id="analysis-a"
    )
    events = operations.query(AuditQuery(query_context, "auditor"))
    assert events[0].event_type is GovernedEventType.UNAUTHORIZED_ACTION
