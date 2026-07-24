"""Persistence-neutral reference stores for WP-008 projection controls."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext

from knowledge_projection.exceptions import ProjectionControlError
from knowledge_projection.models import (
    CanonicalChange,
    ChangeKind,
    ChangeOperation,
    ProjectionCheckpoint,
)

_SERIALIZER = DefaultDeterministicSerializer()


def _key(kind: ChangeKind, subject_id: str) -> str:
    return f"{kind.value}:{subject_id}"


class InMemoryCanonicalChangeLog:
    """Ordered canonical-change input; never reads from the graph projection."""

    def __init__(self) -> None:
        self._changes: dict[tuple[str, str], list[CanonicalChange]] = {}

    def append(self, context: TenantContext, change: CanonicalChange) -> None:
        context.assert_record_matches(change, "canonical change")
        scope = (context.organization_id, context.tenant_id)
        changes = self._changes.setdefault(scope, [])
        expected = len(changes) + 1
        if change.sequence != expected:
            raise ProjectionControlError(
                f"canonical sequence must be contiguous: expected {expected}"
            )
        changes.append(deepcopy(change))

    def changes_after(
        self, context: TenantContext, sequence: int
    ) -> tuple[CanonicalChange, ...]:
        changes = self._changes.get(
            (context.organization_id, context.tenant_id), []
        )
        return tuple(deepcopy(change) for change in changes if change.sequence > sequence)

    def authoritative_state(self, context: TenantContext) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for change in self.changes_after(context, 0):
            key = _key(change.kind, change.subject_id)
            if change.operation is ChangeOperation.REMOVE:
                state.pop(key, None)
            else:
                state[key] = deepcopy(change.payload)
        return state


class InMemoryProjectionStore:
    """Derived graph state. Mutation requires a controller-owned capability."""

    def __init__(self) -> None:
        self._states: dict[tuple[str, str], dict[str, Any]] = {}
        self._checkpoints: dict[tuple[str, str], ProjectionCheckpoint] = {}
        self.__capability = object()

    def _controller_capability(self) -> object:
        return self.__capability

    def snapshot(self, context: TenantContext) -> dict[str, Any]:
        return deepcopy(
            self._states.get((context.organization_id, context.tenant_id), {})
        )

    def checkpoint(self, context: TenantContext) -> ProjectionCheckpoint | None:
        return self._checkpoints.get((context.organization_id, context.tenant_id))

    def state_hash(self, context: TenantContext) -> str:
        return _SERIALIZER.content_hash(self.snapshot(context))

    def _replace(
        self,
        context: TenantContext,
        state: dict[str, Any],
        checkpoint: ProjectionCheckpoint,
        capability: object,
    ) -> None:
        if capability is not self.__capability:
            raise ProjectionControlError("projection writes require canonical controller")
        scope = (context.organization_id, context.tenant_id)
        self._states[scope] = deepcopy(state)
        self._checkpoints[scope] = checkpoint

    def _apply_change(
        self, context: TenantContext, state: dict[str, Any], change: CanonicalChange
    ) -> None:
        context.assert_record_matches(change, "canonical change")
        key = _key(change.kind, change.subject_id)
        if change.operation is ChangeOperation.REMOVE:
            state.pop(key, None)
            return
        payload = change.payload
        context.assert_record_matches(payload, "canonical payload")
        if payload.id != change.subject_id:
            raise ProjectionControlError("canonical payload identity mismatch")
        if change.kind is ChangeKind.ENTITY and not isinstance(
            payload, EnterpriseEntity
        ):
            raise ProjectionControlError("entity change requires EnterpriseEntity")
        if change.kind is ChangeKind.RELATIONSHIP:
            if not isinstance(payload, EnterpriseRelationship):
                raise ProjectionControlError(
                    "relationship change requires EnterpriseRelationship"
                )
            source = _key(ChangeKind.ENTITY, payload.source_entity_id)
            target = _key(ChangeKind.ENTITY, payload.target_entity_id)
            if source not in state or target not in state:
                raise ProjectionControlError(
                    "relationship endpoints must exist in canonical projection"
                )
        state[key] = deepcopy(payload)

    @staticmethod
    def comparable_state(state: dict[str, Any]) -> dict[str, Any]:
        return {
            key: asdict(value) if hasattr(value, "__dataclass_fields__") else value
            for key, value in state.items()
        }
