"""Shared deny-by-default tenant identity and authorization foundation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class TenantAuthorizationError(PermissionError):
    """Raised when a boundary cannot prove tenant authorization."""


class AuthorizationState(str, Enum):
    VERIFIED = "verified"


def _required(value: Any, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise TenantAuthorizationError(f"{field_name} is required")
    return normalized


def _values(values: Iterable[Any] | None) -> frozenset[str]:
    if isinstance(values, str):
        values = (values,)
    return frozenset(str(value).strip() for value in (values or ()) if str(value).strip())


@dataclass(frozen=True, slots=True)
class TenantAuthorizationContext:
    """Verified identity carried across tenant-aware application boundaries."""

    organization_id: str
    tenant_id: str
    subject_id: str
    subject_type: str
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    correlation_id: str | None = None
    source_boundary: str = "unknown"
    authorization_state: AuthorizationState = AuthorizationState.VERIFIED

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required(self.organization_id, "organization_id"),
        )
        object.__setattr__(self, "tenant_id", _required(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "subject_id", _required(self.subject_id, "subject_id"))
        object.__setattr__(self, "subject_type", _required(self.subject_type, "subject_type"))
        object.__setattr__(
            self,
            "source_boundary",
            _required(self.source_boundary, "source_boundary"),
        )
        object.__setattr__(self, "roles", _values(self.roles))
        object.__setattr__(self, "permissions", _values(self.permissions))
        if self.authorization_state is not AuthorizationState.VERIFIED:
            raise TenantAuthorizationError("authorization_state must be verified")

    @classmethod
    def from_principal(
        cls,
        principal: Mapping[str, Any],
        *,
        source_boundary: str,
        permissions: Iterable[str] | None = None,
        correlation_id: str | None = None,
    ) -> "TenantAuthorizationContext":
        organization_id = (
            principal.get("organization_id")
            or principal.get("org_id")
            or principal.get("tenant_id")
        )
        tenant_id = principal.get("tenant_id") or organization_id
        roles = principal.get("roles") or [principal.get("role")]
        return cls(
            organization_id=_required(organization_id, "organization_id"),
            tenant_id=_required(tenant_id, "tenant_id"),
            subject_id=_required(
                principal.get("subject_id")
                or principal.get("sub")
                or principal.get("id")
                or principal.get("username"),
                "subject_id",
            ),
            subject_type=str(principal.get("subject_type") or "user"),
            roles=_values(roles),
            permissions=_values(permissions or principal.get("permissions")),
            correlation_id=correlation_id,
            source_boundary=source_boundary,
        )

    def authorize(
        self,
        *,
        organization_id: Any,
        tenant_id: Any | None = None,
        permission: str | None = None,
    ) -> None:
        if _required(organization_id, "organization_id") != self.organization_id:
            raise TenantAuthorizationError("organization boundary mismatch")
        requested_tenant = _required(tenant_id or organization_id, "tenant_id")
        if requested_tenant != self.tenant_id:
            raise TenantAuthorizationError("tenant boundary mismatch")
        if permission and permission not in self.permissions:
            raise TenantAuthorizationError(f"permission denied: {permission}")

    def scoped_cache_key(self, namespace: str, key: str) -> tuple[str, str, str, str]:
        return (
            _required(namespace, "cache namespace"),
            self.organization_id,
            self.tenant_id,
            _required(key, "cache key"),
        )

    def authorize_payload(self, payload: Mapping[str, Any], permission: str | None = None) -> None:
        self.authorize(
            organization_id=payload.get("organization_id") or payload.get("org_id"),
            tenant_id=payload.get("tenant_id"),
            permission=permission,
        )


def require_trusted_service_context(
    context: TenantAuthorizationContext,
    *,
    boundary: str,
    permission: str,
) -> None:
    if context.subject_type not in {"service", "job", "event_consumer", "ai_service"}:
        raise TenantAuthorizationError(f"{boundary} requires a trusted service subject")
    if context.source_boundary != boundary:
        raise TenantAuthorizationError(f"untrusted {boundary} context")
    context.authorize(
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        permission=permission,
    )
