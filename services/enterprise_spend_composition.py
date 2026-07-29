"""Streamlit composition boundary for authenticated enterprise spend."""

from __future__ import annotations

import os
from typing import Any, Mapping

from auth.authenticated_tenant import (
    AuthenticatedTenantContext,
    AuthenticatedTenantError,
)
from repositories.enterprise_spend_repository import EnterpriseSpendRepository
from services.enterprise_spend_service import EnterpriseSpendService
from services.supabase_client import supabase

_service = EnterpriseSpendService(EnterpriseSpendRepository(supabase))


def _organization_name(organization_id: str) -> str | None:
    response = (
        supabase.table("organizations")
        .select("id,name")
        .eq("id", organization_id)
        .limit(1)
        .execute()
    )
    rows = response.data or ()
    if not rows:
        return None
    row = rows[0]
    if str(row.get("id")) != organization_id:
        raise AuthenticatedTenantError("organization resolver crossed a tenant boundary")
    return str(row.get("name") or "").strip() or None


def authenticated_tenant_context(session: Mapping[str, Any]) -> AuthenticatedTenantContext:
    context = AuthenticatedTenantContext.from_session(
        session,
        organization_resolver=_organization_name,
        environment=os.getenv("ENVIRONMENT", os.getenv("CLOUD_ADVISOR_ENV", "development")),
    )
    try:
        session["organization_name"] = context.organization_name
    except (TypeError, AttributeError):
        pass
    return context


def enterprise_spend_service() -> EnterpriseSpendService:
    return _service
