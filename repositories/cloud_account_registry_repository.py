"""Tenant-scoped persistence for the authoritative cloud account registry."""

from __future__ import annotations

from typing import Any, Mapping

from auth.authenticated_tenant import AuthenticatedTenantContext


class CloudAccountRegistryRepository:
    def __init__(self, client: Any) -> None:
        self.client = client

    @staticmethod
    def _require(context: AuthenticatedTenantContext) -> None:
        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("AuthenticatedTenantContext is required")

    def list_accounts(self, context: AuthenticatedTenantContext) -> list[dict[str, Any]]:
        self._require(context)
        response = (
            self.client.table("cloud_account_registry")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .order("provider")
            .order("account_id")
            .execute()
        )
        return list(response.data or [])

    def create(self, context: AuthenticatedTenantContext, payload: Mapping[str, Any]):
        self._require(context)
        row = {**payload, "organization_id": context.organization_id, "tenant_id": context.tenant_id}
        return self.client.table("cloud_account_registry").insert(row).execute().data[0]

    def update(self, context: AuthenticatedTenantContext, registry_id: str, payload: Mapping[str, Any]):
        self._require(context)
        response = (
            self.client.table("cloud_account_registry")
            .update(dict(payload))
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("id", registry_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def append_audit(self, context: AuthenticatedTenantContext, payload: Mapping[str, Any]):
        row = {**payload, "organization_id": context.organization_id, "tenant_id": context.tenant_id}
        return self.client.table("cloud_account_registry_audit").insert(row).execute().data[0]

    def audit_history(self, context: AuthenticatedTenantContext, registry_id: str):
        response = (
            self.client.table("cloud_account_registry_audit")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("registry_id", registry_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(response.data or [])
