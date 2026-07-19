"""Adapters that apply the shared tenant envelope at application boundaries."""

from __future__ import annotations

from typing import Any, Mapping

from auth.tenant_authorization import (
    TenantAuthorizationContext,
    require_trusted_service_context,
)


def authorize_api(
    principal: Mapping[str, Any], requested_tenant: str | None, permission: str
) -> TenantAuthorizationContext:
    context = TenantAuthorizationContext.from_principal(
        principal, source_boundary="api", permissions=principal.get("permissions")
    )
    context.authorize(
        organization_id=context.organization_id,
        tenant_id=requested_tenant or context.tenant_id,
        permission=permission,
    )
    return context


def authorize_streamlit(
    principal: Mapping[str, Any], requested_organization: str | None, permission: str
) -> TenantAuthorizationContext:
    context = TenantAuthorizationContext.from_principal(
        principal, source_boundary="streamlit", permissions=principal.get("permissions")
    )
    context.authorize(
        organization_id=requested_organization or context.organization_id,
        tenant_id=principal.get("tenant_id") or context.tenant_id,
        permission=permission,
    )
    return context


def authorize_connector(
    context: TenantAuthorizationContext, organization_id: str, permission: str = "connector:run"
) -> None:
    context.authorize(
        organization_id=organization_id,
        tenant_id=context.tenant_id,
        permission=permission,
    )


def authorize_cache(
    context: TenantAuthorizationContext, namespace: str, key: str, permission: str = "cache:access"
) -> tuple[str, str, str, str]:
    context.authorize(
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        permission=permission,
    )
    return context.scoped_cache_key(namespace, key)


def authorize_job(context: TenantAuthorizationContext, payload: Mapping[str, Any]) -> None:
    require_trusted_service_context(context, boundary="background_job", permission="job:execute")
    context.authorize_payload(payload, "job:execute")


def authorize_event(context: TenantAuthorizationContext, payload: Mapping[str, Any]) -> None:
    require_trusted_service_context(context, boundary="event_consumer", permission="event:consume")
    context.authorize_payload(payload, "event:consume")


def authorize_ai(context: TenantAuthorizationContext, organization_id: str) -> None:
    require_trusted_service_context(context, boundary="ai_service", permission="ai:read")
    context.authorize(
        organization_id=organization_id,
        tenant_id=context.tenant_id,
        permission="ai:read",
    )
