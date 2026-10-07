"""Read-only domain identity sources for the canonical Enterprise Registry index."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from data_fabric.adapters.supabase import (
    DataFabricDatabaseConfig,
    SupabaseDataFabricClient,
    SupabaseEntityRepository,
    SupabaseRelationshipRepository,
)
from data_fabric.foundation import TenantContext
from data_fabric.persistence.models import PageRequest, RepositoryQuery
from database.db import get_db
from enterprise_registry.adapters import (
    ApplicationEnterpriseAdapter,
    BusinessServiceEnterpriseAdapter,
    CloudAccountEnterpriseAdapter,
    DomainEnterpriseAdapter,
    SaaSEnterpriseAdapter,
    TechnologyEnterpriseAdapter,
)

DOMAIN_SOURCES: tuple[tuple[str, DomainEnterpriseAdapter], ...] = (
    ("cloud_account_registry", CloudAccountEnterpriseAdapter()),
    ("application_registry", ApplicationEnterpriseAdapter()),
    ("business_service_registry", BusinessServiceEnterpriseAdapter()),
    ("technology_inventory", TechnologyEnterpriseAdapter()),
    ("saas_tools", SaaSEnterpriseAdapter()),
)


class SQLiteEnterpriseRegistrySource:
    """Adapt existing local domain tables; absent optional domains are empty."""

    _LOCAL_TABLES = {
        "cloud_account_registry": "local_cloud_account_registry",
        "application_registry": "application_registry",
        "business_service_registry": "business_service_registry",
        "technology_inventory": "technology_inventory",
        "saas_tools": "saas_tools",
    }

    def __init__(self, connection_factory=get_db) -> None:
        self.connection_factory = connection_factory

    def entities(self, context: TenantContext):
        entities = []
        for domain, adapter in DOMAIN_SOURCES:
            for row in self._rows(self._LOCAL_TABLES[domain], context):
                normalized = dict(row)
                if domain == "cloud_account_registry":
                    normalized["source_system"] = str(row.get("provider") or "cloud")
                entities.append(adapter.adapt(context, normalized))
        return tuple(entities)

    def _rows(self, table: str, context: TenantContext):
        conn = self.connection_factory()
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name=?",
                (table,),
            ).fetchone()
            if not exists:
                return ()
            columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
            org_column = next(
                (value for value in ("organization_id", "org_id") if value in columns), None
            )
            tenant_column = "tenant_id" if "tenant_id" in columns else None
            if org_column is None or tenant_column is None:
                return ()
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {org_column}=? AND {tenant_column}=?",
                (context.organization_id, context.tenant_id),
            ).fetchall()
            return tuple(dict(row) for row in rows)
        finally:
            conn.close()


class SupabaseEnterpriseRegistrySource:
    """Read existing tenant-scoped domain rows without copying them."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def entities(self, context: TenantContext):
        entities = []
        for table, adapter in DOMAIN_SOURCES:
            for row in self._rows(table, context):
                normalized = dict(row)
                if table == "cloud_account_registry":
                    normalized["source_system"] = str(row.get("provider") or "cloud")
                entities.append(adapter.adapt(context, normalized))
        account_adapter = CloudAccountEnterpriseAdapter()
        for row in self._account_posture(context):
            normalized = {
                **row,
                "provider": "aws",
                "source_system": "aws",
                "account_name": row.get("account_id"),
                "classification_status": "NEEDS_REVIEW",
                "confidence": 0,
                "financial_context_reference": (
                    f"tenant_cloud_account_posture:{row.get('account_id')}"
                ),
            }
            entities.append(account_adapter.adapt(context, normalized))
        return tuple(entities)

    def _rows(self, table: str, context: TenantContext):
        try:
            response = (
                self.client.table(table)
                .select("*")
                .eq("organization_id", context.organization_id)
                .eq("tenant_id", context.tenant_id)
                .execute()
            )
            return tuple(dict(row) for row in response.data or ())
        except Exception:
            return ()

    def _account_posture(self, context: TenantContext):
        try:
            response = self.client.rpc(
                "tenant_cloud_account_posture",
                {
                    "requested_organization_id": context.organization_id,
                    "requested_period_start": None,
                    "requested_period_end": None,
                },
            ).execute()
            return tuple(dict(row) for row in response.data or ())
        except Exception:
            return ()


class CanonicalDataFabricRegistrySource:
    """Read canonical entities and relationships within an explicit tenant scope."""

    def __init__(
        self,
        entity_repository,
        relationship_repository,
        *,
        page_size: int = 500,
    ) -> None:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self.entity_repository = entity_repository
        self.relationship_repository = relationship_repository
        self.page_size = page_size

    @classmethod
    def from_supabase(cls, url: str, service_role_key: str):
        config = DataFabricDatabaseConfig(
            url,
            service_role_key,
            enable_health_check=False,
        )
        client = SupabaseDataFabricClient(config)
        return cls(
            SupabaseEntityRepository(client),
            SupabaseRelationshipRepository(client),
        )

    def entities(self, context: TenantContext):
        if not isinstance(context, TenantContext):
            raise PermissionError("Explicit Data Fabric tenant context is required")
        records = self._records(self.entity_repository, context)
        entities = []
        for record in records:
            entity = self.entity_repository.mapper.record_to_domain(record)
            context.assert_record_matches(entity, "canonical entity")
            entities.append(entity)
        return tuple(entities)

    def relationships(self, context: TenantContext):
        if not isinstance(context, TenantContext):
            raise PermissionError("Explicit Data Fabric tenant context is required")
        records = self._records(self.relationship_repository, context)
        relationships = []
        for record in records:
            relationship = self.relationship_repository.mapper.record_to_domain(record)
            context.assert_record_matches(relationship, "canonical relationship")
            relationships.append(relationship)
        return tuple(relationships)

    def _records(self, repository, context: TenantContext):
        records = []
        offset = 0
        while True:
            query = RepositoryQuery(
                context,
                page=PageRequest(offset=offset, limit=self.page_size),
            )
            page = repository.search(query)
            records.extend(page.items)
            if len(page.items) < self.page_size:
                break
            offset += self.page_size
        return tuple(records)


class SupabaseEntityFinancialContext:
    """Expose existing account posture by reference; never persists or totals spend."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def get_financial_context(self, context, entity) -> Mapping[str, Any]:
        context.assert_record_matches(entity, "financial entity")
        if entity.entity_type.value != "cloud_account":
            return {}
        try:
            response = self.client.rpc(
                "tenant_cloud_account_posture",
                {
                    "requested_organization_id": context.organization_id,
                    "requested_period_start": None,
                    "requested_period_end": None,
                },
            ).execute()
            row = next(
                (
                    dict(item)
                    for item in response.data or ()
                    if str(item.get("account_id")) == entity.source_identifier
                ),
                None,
            )
            return row or {}
        except Exception:
            return {}
