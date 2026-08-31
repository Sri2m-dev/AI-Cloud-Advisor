"""Audited ACT-009 lifecycle mutation boundary."""

from __future__ import annotations

from dataclasses import replace

from universal_evidence.operations.models import (
    FailureClass,
    GovernedEventType,
    OperationContext,
    Severity,
)
from universal_evidence.security import (
    PURGE_ROLES,
    UniversalEvidenceSecurityPolicy,
    WorkflowAuthorizationContext,
)


class GovernedLifecycleOperations:
    def __init__(self, repository, operations, context: OperationContext):
        self.repository = repository
        self.operations = operations
        self.context = context

    def purge_scope(
        self, scope, *, authorization: WorkflowAuthorizationContext, reason: str
    ) -> int:
        actor_id = authorization.actor_id
        actor_role = authorization.role
        trusted_context = replace(
            self.context,
            organization_id=authorization.tenant.organization_id,
            tenant_id=authorization.tenant.tenant_id,
            prospect_id=authorization.prospect_id,
            analysis_id=authorization.analysis_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        try:
            authorization.authorize_scope(scope.values)
        except PermissionError:
            self.operations.emit(
                GovernedEventType.SCOPE_ACCESS_REJECTED,
                trusted_context,
                severity=Severity.SECURITY,
                outcome="DENIED",
                failure_class=FailureClass.SECURITY_REJECTION,
                attributes={"attempted_action": "lifecycle purge"},
            )
            raise
        context = replace(
            self.context,
            organization_id=scope.organization_id,
            tenant_id=scope.tenant_id,
            prospect_id=scope.prospect_id,
            analysis_id=scope.analysis_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        try:
            UniversalEvidenceSecurityPolicy.authorize(
                actor_role, PURGE_ROLES, "lifecycle purge"
            )
        except PermissionError:
            self.operations.emit(
                GovernedEventType.UNAUTHORIZED_ACTION,
                context,
                severity=Severity.SECURITY,
                outcome="DENIED",
                failure_class=FailureClass.SECURITY_REJECTION,
                attributes={"attempted_action": "lifecycle purge"},
            )
            raise
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
                audit=True,
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
