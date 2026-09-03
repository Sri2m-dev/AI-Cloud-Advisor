from datetime import datetime, timezone
from decimal import Decimal

import pytest

from data_fabric.contracts import EnterpriseRelationship, RelationshipDecisionState
from data_fabric.foundation import TenantContext
from enterprise_registry.context_attribution import (
    Allocation,
    AttributionState,
    ContextAttribution,
    EnterpriseContextAttributionService,
    MonetaryFact,
)
from enterprise_registry.relationship_governance import RelationshipGovernanceService

CTX = TenantContext("org-1", "tenant-1")
NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


class RelationshipStore:
    def __init__(self):
        self.rows = []

    def save(self, row):
        self.rows.append(row)


class EventStore:
    def __init__(self):
        self.rows = []

    def append(self, row):
        self.rows.append(row)


def relationship(state="candidate"):
    return EnterpriseRelationship(
        "rel-1",
        "owned_by",
        "app-1",
        "team-1",
        "org-1",
        "tenant-1",
        evidence=("cmdb:owner-1",),
        decision_state=state,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_governance_lifecycle_is_explicit_and_history_is_append_only():
    store, events = RelationshipStore(), EventStore()
    service = RelationshipGovernanceService(CTX, store, events)
    reviewed = service.transition(
        relationship(),
        "under_review",
        actor="alice",
        actor_role="client_admin",
        reason="triage",
        decided_at=NOW,
    )
    confirmed = service.transition(
        reviewed, "confirmed", actor="bob", actor_role="auditor", reason="verified", decided_at=NOW
    )
    assert confirmed.decision_state is RelationshipDecisionState.CONFIRMED
    assert [event.previous_state.value for event in events.rows] == ["candidate", "under_review"]
    assert [event.new_state.value for event in events.rows] == ["under_review", "confirmed"]
    with pytest.raises(ValueError, match="invalid relationship transition"):
        service.transition(confirmed, "rejected", actor="bob", actor_role="auditor", reason="late")


def test_reconciliation_preserves_unresolved_and_deduplicates_paths():
    service = EnterpriseContextAttributionService(CTX)
    facts = [
        MonetaryFact("o1", "org-1", "tenant-1", Decimal("100")),
        MonetaryFact("o2", "org-1", "tenant-1", Decimal("50")),
        MonetaryFact("o3", "org-1", "tenant-1", Decimal("25")),
    ]
    rows = [
        ContextAttribution(
            "o1", ("resource-1", "app-1", "service-1", "app-1"), AttributionState.RESOLVED
        ),
        ContextAttribution("o2", ("shared-db",), AttributionState.SHARED_UNALLOCATED),
    ]
    result = service.reconcile(facts, rows)
    assert (
        result.enterprise_total,
        result.resolved,
        result.shared,
        result.unresolved,
        result.variance,
    ) == (Decimal("175"), Decimal("100"), Decimal("50"), Decimal("25"), Decimal("0"))
    assert service.totals_by_entity(facts, rows)["app-1"] == Decimal("100")


def test_shared_allocation_requires_governed_exact_total():
    service = EnterpriseContextAttributionService(CTX)
    assert service.validate_allocations(
        [Allocation("app-a", Decimal(".6")), Allocation("app-b", Decimal(".4"))]
    )
    for rows in (
        [Allocation("app-a", Decimal(".5")), Allocation("app-b", Decimal(".4"))],
        [Allocation("app-a", Decimal(".6")), Allocation("app-a", Decimal(".4"))],
        [Allocation("app-a", Decimal("1.1")), Allocation("app-b", Decimal("-.1"))],
    ):
        with pytest.raises(ValueError):
            service.validate_allocations(rows)


def test_cross_tenant_facts_fail_closed():
    service = EnterpriseContextAttributionService(CTX)
    with pytest.raises(Exception):
        service.reconcile([MonetaryFact("o1", "org-1", "tenant-2", Decimal("1"))], [])
