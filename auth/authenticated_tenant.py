"""Authenticated tenant contract for application service boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from uuid import UUID

from auth.role_constants import normalize_role
from data_fabric.foundation import TenantContext


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
        if isinstance(profile, Mapping):
            profile_org = profile.get("org_id") or profile.get("organization_id")
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
        user_email = session.get("email") or getattr(user, "email", None)
        return cls(
            organization_id=organization_id,
            organization_name=organization_name,
            user_id=_required(user_id or user_email, "user_id"),
            user_email=_required(user_email, "user_email"),
            role=_required(session.get("role"), "role"),
            authorization_claims=frozenset(session.get("permissions") or ()),
            tenant_id=organization_id,
            environment=environment,
        )
