"""ACT-012 backend mutation authorization policy using canonical Nexora roles."""

from __future__ import annotations

from dataclasses import dataclass

from auth.role_constants import normalize_role
from auth.tenant_authorization import TenantAuthorizationContext

RECONCILIATION_MUTATION_ROLES = frozenset({"super_admin", "client_admin", "operations"})
PURGE_ROLES = frozenset({"super_admin", "client_admin", "operations"})
MATERIALIZATION_MUTATION_ROLES = frozenset({"super_admin", "client_admin", "operations"})


@dataclass(frozen=True, slots=True)
class WorkspaceAuthorizationContext:
    """Trusted principal authorized to discover its own tenant-owned workspaces."""

    tenant: TenantAuthorizationContext

    @classmethod
    def from_authenticated(cls, authenticated):
        return cls(
            TenantAuthorizationContext(
                authenticated.organization_id,
                authenticated.tenant_id,
                authenticated.user_id,
                "user",
                roles=frozenset({authenticated.role}),
                permissions=authenticated.authorization_claims,
                source_boundary="authenticated-tenant-context",
            )
        )

    @property
    def actor_id(self):
        return self.tenant.subject_id

    def authorize_scope(self, scope):
        self.tenant.authorize(
            organization_id=scope.organization_id,
            tenant_id=scope.tenant_id,
        )


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

    @classmethod
    def from_authenticated(cls, authenticated, *, prospect_id, analysis_id):
        """Adapt the application's verified authenticated tenant at a workflow boundary."""
        return cls(
            TenantAuthorizationContext(
                authenticated.organization_id,
                authenticated.tenant_id,
                authenticated.user_id,
                "user",
                roles=frozenset({authenticated.role}),
                permissions=authenticated.authorization_claims,
                source_boundary="authenticated-tenant-context",
            ),
            prospect_id,
            analysis_id,
        )

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

    @property
    def allows_reconciliation_mutation(self):
        """Presentation hint derived from trusted authority; services still enforce it."""
        try:
            UniversalEvidenceSecurityPolicy.authorize(
                self.role,
                RECONCILIATION_MUTATION_ROLES,
                "reconciliation mutation",
            )
        except PermissionError:
            return False
        return True
