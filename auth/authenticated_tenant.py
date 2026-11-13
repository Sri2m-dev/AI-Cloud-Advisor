"""Authenticated tenant contract for application service boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from uuid import UUID

from auth.role_constants import normalize_role
from data_fabric.foundation import TenantContext


class ProtectedWorkflowUnavailable(RuntimeError):
    """A real G08 assurance/atomic writer/read contract has not been configured."""


@dataclass(frozen=True, slots=True)
class ApplicationAccount:
    """Account scope from an existing authenticated boundary, NOT owner assurance."""

    organization_id: str
    user_id: str
    source: str


def api_application_account(user: Mapping[str, Any]) -> ApplicationAccount:
    """Use only AFTER backend.security.get_current_user has verified current state."""
    tenant = str(user.get("tenant_id") or "").strip()
    actor = str(user.get("username") or "").strip()
    if not tenant or not actor or str(user.get("org_id") or tenant).strip() != tenant:
        raise PermissionError("Authenticated account scope is required")
    return ApplicationAccount(tenant, actor, "api_current_account")


def require_protected_workflow(
    workflow: str, context=None, *, organization_id=None, actor=None
) -> None:
    """Shared actual application gate. No environment flag or role enables G08.

    Existing account/session identity proves scope only. It supplies neither a
    natural-person attestation nor owner-operation policy/fencing/atomicity.
    Keep this gate closed until those actual providers and projections exist.
    """
    if context is not None:
        if not isinstance(context, (AuthenticatedTenantContext, ApplicationAccount)):
            raise PermissionError("Authenticated application context is required")
        if organization_id is not None and str(organization_id) != context.organization_id:
            raise PermissionError("Organization access denied")
        if actor is not None and str(actor) != context.user_id:
            raise PermissionError("Actor does not match authenticated identity")
    # Lazy dependency: accepted release packaging excludes the staged M2 modules.
    # Missing packaged code is a denial, never an application startup/import error.
    try:
        from services.g08_owner_authorization import (
            OwnerDependencyUnavailable,
            UnavailableOwnerTrust,
        )
    except ImportError as error:
        raise ProtectedWorkflowUnavailable(
            "G08 implementation is not packaged for activation"
        ) from error
    try:
        UnavailableOwnerTrust().verify_operator()
    except OwnerDependencyUnavailable as error:
        raise ProtectedWorkflowUnavailable(
            "G08 independent operator assurance is unavailable"
        ) from error
    raise ProtectedWorkflowUnavailable(
        "G08_UNAVAILABLE: verified operator, authority scope, atomic workflow "
        "and authorized projection required"
    )


class AuthenticatedTenantError(PermissionError):
    """Raised when an authenticated tenant cannot be proven."""


def _required(value: Any, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AuthenticatedTenantError(f"{name} is required")
    return normalized


def _uuid(value: Any, name: str) -> str:
    normalized = _required(value, name)
    try:
        return str(UUID(normalized))
    except (TypeError, ValueError) as exc:
        raise AuthenticatedTenantError(f"{name} must be a valid UUID") from exc


@dataclass(frozen=True, slots=True)
class AuthenticatedTenantContext:
    """Verified session identity passed to tenant-owned application services."""

    organization_id: str
    organization_name: str
    user_id: str
    user_email: str
    role: str
    authorization_claims: frozenset[str]
    tenant_id: str
    environment: str | None = None
    auth_access_token: str | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "organization_id", _uuid(self.organization_id, "organization_id"))
        object.__setattr__(self, "tenant_id", _uuid(self.tenant_id, "tenant_id"))
        if self.organization_id != self.tenant_id:
            raise AuthenticatedTenantError("tenant_id is not authorized for organization_id")
        object.__setattr__(
            self, "organization_name", _required(self.organization_name, "organization_name")
        )
        object.__setattr__(self, "user_id", _required(self.user_id, "user_id"))
        object.__setattr__(self, "user_email", _required(self.user_email, "user_email").lower())
        object.__setattr__(self, "role", normalize_role(_required(self.role, "role")))
        object.__setattr__(
            self,
            "authorization_claims",
            frozenset(
                str(value).strip() for value in self.authorization_claims if str(value).strip()
            ),
        )

    @property
    def fabric_context(self) -> TenantContext:
        return TenantContext(self.organization_id, self.tenant_id)

    @property
    def authorization_scope(self) -> tuple[str, tuple[str, ...]]:
        return self.role, tuple(sorted(self.authorization_claims))

    @classmethod
    def from_session(
        cls,
        session: Mapping[str, Any],
        *,
        organization_resolver: Callable[[str], str | None],
        environment: str | None = None,
    ) -> "AuthenticatedTenantContext":
        if not bool(session.get("authenticated")):
            raise AuthenticatedTenantError("authenticated session is required")
        organization_id = _uuid(
            session.get("organization_id") or session.get("org_id"),
            "organization_id",
        )
        profile = session.get("profile")
        is_supabase = str(session.get("auth_backend") or "").strip().lower() == "supabase"
        if is_supabase and not isinstance(profile, Mapping):
            raise AuthenticatedTenantError("UID-bound tenant membership is required")
        if isinstance(profile, Mapping):
            profile_org = profile.get("org_id") or profile.get("organization_id")
            if is_supabase and not profile_org:
                raise AuthenticatedTenantError("profile organization_id is required")
            if profile_org and _uuid(profile_org, "profile organization_id") != organization_id:
                raise AuthenticatedTenantError(
                    "session organization is not authorized by the profile"
                )
        authorized = session.get("authorized_organization_ids")
        if authorized is not None:
            authorized_ids = {_uuid(item, "authorized organization_id") for item in authorized}
            if organization_id not in authorized_ids:
                raise AuthenticatedTenantError("organization is not an authorized membership")
        organization_name = organization_resolver(organization_id)
        if not organization_name:
            raise AuthenticatedTenantError("organization_name could not be resolved")
        user = session.get("user")
        user_id = session.get("user_id") or getattr(user, "id", None)
        if is_supabase:
            user_id = _uuid(user_id, "Supabase Auth user_id")
            auth_identity = _uuid(getattr(user, "id", None), "Supabase Auth identity")
            if auth_identity != user_id:
                raise AuthenticatedTenantError("session identity does not match Supabase Auth")
            if not isinstance(profile, Mapping) or _uuid(
                profile.get("auth_user_id"), "profile auth_user_id"
            ) != user_id:
                raise AuthenticatedTenantError("profile is not bound to the Supabase Auth identity")
            if authorized is None:
                raise AuthenticatedTenantError("trusted tenant membership is required")
            auth_client = session.get("auth_client")
            auth_session = (
                auth_client.auth.get_session()
                if auth_client is not None
                else session.get("session")
            )
            access_token = (
                auth_session.get("access_token")
                if isinstance(auth_session, Mapping)
                else getattr(auth_session, "access_token", None)
            )
            if not isinstance(access_token, str) or not access_token.strip():
                raise AuthenticatedTenantError(
                    "verified Supabase access token is required"
                )
        else:
            access_token = None
        user_email = session.get("email") or getattr(user, "email", None)
        if is_supabase:
            role = profile.get("role")
            permissions = profile.get("permissions") or ()
        else:
            role = session.get("role")
            permissions = session.get("permissions") or ()
        return cls(
            organization_id=organization_id,
            organization_name=organization_name,
            user_id=_required(user_id if is_supabase else user_id or user_email, "user_id"),
            user_email=_required(user_email, "user_email"),
            role=_required(role, "role"),
            authorization_claims=frozenset(permissions),
            tenant_id=organization_id,
            environment=environment,
            auth_access_token=access_token,
        )
