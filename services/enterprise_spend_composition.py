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


class _EmptyTenantSpendRepository:
    """Tenant-required empty repository for local development without Supabase."""

    @staticmethod
    def _require_context(context: AuthenticatedTenantContext) -> None:
        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("AuthenticatedTenantContext is required")

    def get_posture(self, context, period_start=None, period_end=None):
        self._require_context(context)
        return None

    def get_spend_by_service(self, context, period_start=None, period_end=None):
        self._require_context(context)
        return ()

    def get_account_posture(self, context, period_start=None, period_end=None):
        self._require_context(context)
        return ()

    def get_import_history(self, context):
        self._require_context(context)
        return ()


_local_service = EnterpriseSpendService(_EmptyTenantSpendRepository())


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


def _organization_resolver(session: Mapping[str, Any]):
    """Use tenant claims from local auth; keep Supabase authoritative otherwise."""
    if session.get("auth_backend") != "local":
        return _organization_name

    organization_id = str(session.get("organization_id") or session.get("org_id") or "").strip()
    authorized_ids = {
        str(value).strip() for value in session.get("authorized_organization_ids") or ()
    }
    organization_name = str(session.get("organization_name") or "").strip()

    def resolve(requested_organization_id: str) -> str | None:
        if (
            requested_organization_id != organization_id
            or requested_organization_id not in authorized_ids
        ):
            raise AuthenticatedTenantError("local organization resolver crossed a tenant boundary")
        return organization_name or None

    return resolve


def authenticated_tenant_context(session: Mapping[str, Any]) -> AuthenticatedTenantContext:
    context = AuthenticatedTenantContext.from_session(
        session,
        organization_resolver=_organization_resolver(session),
        environment=os.getenv("ENVIRONMENT", os.getenv("CLOUD_ADVISOR_ENV", "development")),
    )
    try:
        session["organization_name"] = context.organization_name
    except (TypeError, AttributeError):
        pass
    return context


def enterprise_spend_service() -> EnterpriseSpendService:
    environment = (
        os.getenv("ENVIRONMENT", os.getenv("CLOUD_ADVISOR_ENV", "development")).strip().lower()
    )
    if environment != "production" and not os.getenv("SUPABASE_URL", "").strip():
        return _local_service
    return _service
