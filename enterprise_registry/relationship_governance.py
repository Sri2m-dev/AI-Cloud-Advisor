"""Durable, append-only governance for canonical enterprise relationships."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol

from data_fabric.contracts import EnterpriseRelationship, RelationshipDecisionState
from data_fabric.foundation import TenantContext


class RelationshipStore(Protocol):
    def save(self, relationship: EnterpriseRelationship) -> None: ...


class GovernanceEventStore(Protocol):
    def append(self, event: "RelationshipGovernanceEvent") -> None: ...


@dataclass(frozen=True, slots=True)
class RelationshipGovernanceEvent:
    event_id: str
    organization_id: str
    tenant_id: str
    relationship_id: str
    relationship_version: int
    previous_state: RelationshipDecisionState
    new_state: RelationshipDecisionState
    actor: str
    actor_role: str
    reason: str
    decided_at: datetime
    authority_fingerprint: str


TRANSITIONS = {
    RelationshipDecisionState.CANDIDATE: {RelationshipDecisionState.UNDER_REVIEW},
    RelationshipDecisionState.UNDER_REVIEW: {
        RelationshipDecisionState.CONFIRMED,
        RelationshipDecisionState.REJECTED,
        RelationshipDecisionState.REVISION_REQUIRED,
    },
    RelationshipDecisionState.REVISION_REQUIRED: {RelationshipDecisionState.UNDER_REVIEW},
    RelationshipDecisionState.CONFIRMED: {
        RelationshipDecisionState.SUPERSEDED,
        RelationshipDecisionState.INACTIVE,
    },
}


class RelationshipGovernanceService:
    """Applies explicit transitions and records immutable decision history."""

    allowed_roles = {"super_admin", "client_admin", "operations", "auditor"}

    def __init__(
        self, context: TenantContext, relationships: RelationshipStore, events: GovernanceEventStore
    ):
        self.context, self.relationships, self.events = context, relationships, events

    def transition(
        self,
        relationship: EnterpriseRelationship,
        new_state: RelationshipDecisionState | str,
        *,
        actor: str,
        actor_role: str,
        reason: str,
        decided_at: datetime | None = None,
        superseded_by: str | None = None,
    ) -> EnterpriseRelationship:
        self.context.assert_record_matches(relationship, "relationship")
        state = RelationshipDecisionState(new_state)
        current = RelationshipDecisionState(relationship.decision_state)
        if actor_role not in self.allowed_roles:
            raise PermissionError("relationship governance mutation denied")
        if state not in TRANSITIONS.get(current, set()):
            raise ValueError(f"invalid relationship transition: {current.value} -> {state.value}")
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and decision reason are required")
        if state is RelationshipDecisionState.SUPERSEDED and not superseded_by:
            raise ValueError("superseded_by is required")
        moment = decided_at or datetime.now(timezone.utc)
        updated = replace(
            relationship,
            decision_state=state,
            actor=actor,
            actor_role=actor_role,
            decision_reason=reason,
            updated_at=moment,
            version=relationship.version + 1,
            superseded_by=superseded_by,
            effective_to=moment
            if state in {RelationshipDecisionState.SUPERSEDED, RelationshipDecisionState.INACTIVE}
            else relationship.effective_to,
        )
        event = RelationshipGovernanceEvent(
            event_id=f"rge:{relationship.id}:{updated.version}",
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
            relationship_id=relationship.id,
            relationship_version=updated.version,
            previous_state=current,
            new_state=state,
            actor=actor,
            actor_role=actor_role,
            reason=reason,
            decided_at=moment,
            authority_fingerprint=_fingerprint(updated),
        )
        self.relationships.save(updated)
        self.events.append(event)
        return updated


def _fingerprint(relationship: EnterpriseRelationship) -> str:
    payload = asdict(relationship)
    payload.pop("updated_at", None)
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
