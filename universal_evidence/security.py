"""ACT-012 backend mutation authorization policy using canonical Nexora roles."""

from __future__ import annotations

from dataclasses import dataclass

from auth.role_constants import normalize_role
from auth.tenant_authorization import TenantAuthorizationContext

RECONCILIATION_MUTATION_ROLES = frozenset({"super_admin", "client_admin", "operations"})
PURGE_ROLES = frozenset({"super_admin", "client_admin", "operations"})
MATERIALIZATION_MUTATION_ROLES = frozenset({"super_admin", "client_admin", "operations"})


@dataclass(frozen=True, slots=True)
class UniversalEvidenceSecurityPolicy:
    version: str = "act012-security-policy-1"

    @staticmethod
    def authorize(role, allowed_roles, action):
        normalized = normalize_role(role)
        if normalized not in allowed_roles:
            raise PermissionError(f"{action} requires an authorized operational role")
        return normalized


@dataclass(frozen=True, slots=True)
class WorkflowAuthorizationContext:
    """Trusted authenticated principal plus the authorized governed-workflow scope."""

    tenant: TenantAuthorizationContext
    prospect_id: str
    analysis_id: str

    def __post_init__(self):
        if not str(self.prospect_id or "").strip() or not str(self.analysis_id or "").strip():
            raise PermissionError("trusted prospect and analysis scope are required")

    @property
    def actor_id(self):
        return self.tenant.subject_id

    @property
    def role(self):
        if len(self.tenant.roles) != 1:
            raise PermissionError("one trusted active role is required")
        return next(iter(self.tenant.roles))

    def authorize_scope(self, scope):
        if hasattr(scope, "organization_id"):
            values = (
                scope.organization_id,
                scope.tenant_id,
                scope.prospect_id,
                scope.analysis_id,
            )
        else:
            values = scope
        self.tenant.authorize(
            organization_id=values[0],
            tenant_id=values[1],
        )
        if values[2] != self.prospect_id or values[3] != self.analysis_id:
            raise PermissionError("prospect or analysis boundary mismatch")

    def governance_actor(self):
        """Build the established governance actor from verified authority."""
        from universal_evidence.governance.models import ActorType, ConfirmationActor

        return ConfirmationActor(self.actor_id, self.actor_id, self.role, ActorType.HUMAN)

    def activation_actor(self, permission):
        """Build an activation actor without accepting caller-defined permissions."""
        from universal_evidence.activation.models import ActivationActor, ActivationPermission

        UniversalEvidenceSecurityPolicy.authorize(
            self.role,
            RECONCILIATION_MUTATION_ROLES,
            "activation administration",
        )
        return ActivationActor(
            self.actor_id,
            self.role,
            "HUMAN_ADMIN",
            (ActivationPermission(permission),),
        )
