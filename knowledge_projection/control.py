"""Canonical-to-graph projection orchestration."""

from __future__ import annotations

from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext

from knowledge_projection.exceptions import ProjectionControlError
from knowledge_projection.models import ProjectionCheckpoint, ReconciliationResult
from knowledge_projection.stores import (
    InMemoryCanonicalChangeLog,
    InMemoryProjectionStore,
)

_SERIALIZER = DefaultDeterministicSerializer()


class KnowledgeProjectionController:
    """The only write coordinator for a rebuildable derived projection."""

    def __init__(
        self,
        source: InMemoryCanonicalChangeLog,
        projection: InMemoryProjectionStore,
    ) -> None:
        self._source = source
        self._projection = projection
        self._capability = projection._controller_capability()

    def replay(self, context: TenantContext) -> ProjectionCheckpoint:
        previous = self._projection.checkpoint(context)
        start = previous.sequence if previous else 0
        state = self._projection.snapshot(context)
        changes = self._source.changes_after(context, start)
        expected = start + 1
        for change in changes:
            if change.sequence != expected:
                raise ProjectionControlError(
                    f"projection sequence gap: expected {expected}"
                )
            self._projection._apply_change(context, state, change)
            expected += 1
        sequence = changes[-1].sequence if changes else start
        checkpoint = ProjectionCheckpoint(
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            sequence=sequence,
            state_hash=_SERIALIZER.content_hash(
                self._projection.comparable_state(state)
            ),
            applied_changes=(previous.applied_changes if previous else 0)
            + len(changes),
        )
        self._projection._replace(context, state, checkpoint, self._capability)
        return checkpoint

    def rebuild(self, context: TenantContext) -> ProjectionCheckpoint:
        state: dict[str, object] = {}
        changes = self._source.changes_after(context, 0)
        expected = 1
        for change in changes:
            if change.sequence != expected:
                raise ProjectionControlError(
                    f"canonical sequence gap: expected {expected}"
                )
            self._projection._apply_change(context, state, change)
            expected += 1
        checkpoint = ProjectionCheckpoint(
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            sequence=changes[-1].sequence if changes else 0,
            state_hash=_SERIALIZER.content_hash(
                self._projection.comparable_state(state)
            ),
            applied_changes=len(changes),
        )
        self._projection._replace(context, state, checkpoint, self._capability)
        return checkpoint

    def reconcile(self, context: TenantContext) -> ReconciliationResult:
        canonical = self._source.authoritative_state(context)
        projected = self._projection.snapshot(context)
        canonical_values = self._projection.comparable_state(canonical)
        projected_values = self._projection.comparable_state(projected)
        canonical_keys = set(canonical_values)
        projected_keys = set(projected_values)
        common = canonical_keys & projected_keys
        divergent = tuple(
            sorted(
                key
                for key in common
                if _SERIALIZER.content_hash(canonical_values[key])
                != _SERIALIZER.content_hash(projected_values[key])
            )
        )
        return ReconciliationResult(
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            canonical_hash=_SERIALIZER.content_hash(canonical_values),
            projection_hash=_SERIALIZER.content_hash(projected_values),
            missing=tuple(sorted(canonical_keys - projected_keys)),
            unexpected=tuple(sorted(projected_keys - canonical_keys)),
            divergent=divergent,
        )
