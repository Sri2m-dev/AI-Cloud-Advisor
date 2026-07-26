"""Service-role repository for PVT-003A CUR ingestion tables.

The client is injected by backend composition.  It must be created with the
service-role credential; this module deliberately does not import a browser
Supabase client or expose a UI-facing constructor.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from data_fabric.foundation import TenantContext
from data_fabric.foundation.exceptions import DataFabricTenantBoundaryError
from services.aws_cur_ingestion_engine import AccountMapping


class SupabaseAwsCurIngestionRepository:
    def __init__(self, service_role_client: Any) -> None:
        self._client = service_role_client

    @staticmethod
    def _scope(context: TenantContext, payload: Mapping[str, Any]) -> None:
        if (
            payload.get("organization_id") != context.organization_id
            or payload.get("tenant_id") != context.tenant_id
        ):
            raise DataFabricTenantBoundaryError("CUR persistence crosses tenant boundary")

    def _table(self, name: str):
        return self._client.table(name)

    def find_import(
        self, context: TenantContext, payer: str, file_hash: str
    ) -> Mapping[str, Any] | None:
        response = (
            self._table("cloud_cost_import")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("payer_account_id", payer)
            .eq("source_file_sha256", file_hash)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def list_account_mappings(self, context: TenantContext) -> Iterable[AccountMapping]:
        response = (
            self._table("cloud_account_mapping")
            .select("organization_id,tenant_id,payer_account_id,account_id,status")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .execute()
        )
        return tuple(AccountMapping(**row) for row in response.data)

    def create_import(self, context: TenantContext, payload: Mapping[str, Any]) -> None:
        self._scope(context, payload)
        self._table("cloud_cost_import").insert(dict(payload)).execute()

    def update_import(
        self, context: TenantContext, import_id: str, payload: Mapping[str, Any]
    ) -> None:
        self._table("cloud_cost_import").update(dict(payload)).eq(
            "organization_id", context.organization_id
        ).eq("tenant_id", context.tenant_id).eq("import_id", import_id).execute()

    def create_part(self, context: TenantContext, payload: Mapping[str, Any]) -> None:
        self._scope(context, payload)
        self._table("cloud_cost_import_part").upsert(
            dict(payload),
            on_conflict="organization_id,tenant_id,import_id,part_key",
        ).execute()

    def update_part(
        self, context: TenantContext, part_id: str, payload: Mapping[str, Any]
    ) -> None:
        self._table("cloud_cost_import_part").update(dict(payload)).eq(
            "organization_id", context.organization_id
        ).eq("tenant_id", context.tenant_id).eq("import_part_id", part_id).execute()

    def write_facts(self, context: TenantContext, facts: list[Mapping[str, Any]]) -> int:
        for fact in facts:
            self._scope(context, fact)
        if not facts:
            return 0
        # The PVT-003A unique source identities make this a replay-safe batch.
        response = self._table("cloud_cost_fact").upsert(
            [dict(fact) for fact in facts],
            on_conflict="organization_id,tenant_id,source_row_key",
        ).execute()
        return len(response.data or facts)

    def upsert_reconciliation(self, context: TenantContext, payload: Mapping[str, Any]) -> None:
        self._scope(context, payload)
        self._table("cloud_cost_reconciliation").upsert(
            dict(payload),
            on_conflict="organization_id,tenant_id,import_id",
        ).execute()
