"""Audited ACT-009 lifecycle mutation boundary."""

from __future__ import annotations

from dataclasses import replace

from universal_evidence.operations.models import (
    FailureClass,
    GovernedEventType,
    OperationContext,
    Severity,
)


class GovernedLifecycleOperations:
    def __init__(self, repository, operations, context: OperationContext):
        self.repository = repository
        self.operations = operations
        self.context = context

    def purge_scope(self, scope, *, actor_id: str, reason: str) -> int:
        context = replace(
            self.context,
            organization_id=scope.organization_id,
            tenant_id=scope.tenant_id,
            prospect_id=scope.prospect_id,
            analysis_id=scope.analysis_id,
            actor_id=actor_id,
        )
        self.operations.emit(
            GovernedEventType.PURGE_REQUESTED,
            context,
            attributes={"reason": reason, "phase": "AUTHORIZED"},
        )
        try:
            count = self.repository.purge_scope(scope, actor_id=actor_id, reason=reason)
        except Exception:
            self.operations.emit(
                GovernedEventType.PURGE_FAILED,
                context,
                audit=False,
                severity=Severity.ERROR,
                outcome="FAILED",
                failure_class=FailureClass.PERSISTENCE_FAILURE,
            )
            raise
        self.operations.emit(
            GovernedEventType.PURGE_COMPLETED,
            context,
            attributes={"purged_objects": count},
        )
        return count
