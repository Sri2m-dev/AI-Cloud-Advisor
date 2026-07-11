"""Supabase PostgreSQL canonical relationship repository adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError
from data_fabric.adapters.supabase.repository_utils import (
    apply_query_filters,
    default_page,
    dt,
    ensure_inserted,
    iso,
    optional_row,
    page_result,
    plain_mapping,
    ratio_to_100,
    response_rows,
    score_to_ratio,
)
from data_fabric.contracts import EnterpriseRelationship
from data_fabric.foundation import TenantContext
from data_fabric.persistence.interfaces import RelationshipRepository
from data_fabric.persistence.mappers import RelationshipPersistenceMapper
from data_fabric.persistence.models import MutableRecord, PageRequest, PageResult, RepositoryQuery


class SupabaseRelationshipRepository(RelationshipRepository):
    """Supabase adapter for mutable canonical relationship current state."""

    table_name = "enterprise_relationships"

    def __init__(self, client: SupabaseDataFabricClient) -> None:
        self.client = client
        self.mapper = RelationshipPersistenceMapper()

    def add(self, record: MutableRecord | EnterpriseRelationship) -> MutableRecord:
        persistence_record = self._coerce_record(record)
        row = self._record_to_row(persistence_record)
        response = self.client.execute(lambda: self.client.table(self.table_name).insert(row).execute())
        return self._row_to_record(ensure_inserted(response, "relationship"))

    def get(self, tenant_context: TenantContext, record_id: str, *, include_inactive: bool = False) -> MutableRecord | None:
        query = self._tenant_query(tenant_context).eq("id", record_id)
        if not include_inactive:
            query = query.eq("active", True)
        response = self.client.execute(lambda: query.limit(1).execute())
        row = optional_row(response)
        return self._row_to_record(row) if row else None

    def find_by_source_entity(self, tenant_context: TenantContext, source_entity_id: str, *, include_inactive: bool = False) -> PageResult:
        return self.search(RepositoryQuery(tenant_context, filters={"source_entity_id": source_entity_id}, include_inactive=include_inactive))

    def find_by_target_entity(self, tenant_context: TenantContext, target_entity_id: str, *, include_inactive: bool = False) -> PageResult:
        return self.search(RepositoryQuery(tenant_context, filters={"target_entity_id": target_entity_id}, include_inactive=include_inactive))

    def update(self, record: MutableRecord, *, expected_revision: int) -> MutableRecord:
        row = self._record_to_row(record)
        response = self.client.execute(
            lambda: self.client.rpc(
                "data_fabric_update_enterprise_relationship",
                {
                    "p_relationship_id": record.record_id,
                    "p_organization_id": record.organization_id,
                    "p_tenant_id": record.tenant_id,
                    "p_expected_revision": expected_revision,
                    "p_relationship": row,
                },
            )
        )
        rows = response_rows(response)
        if not rows:
            raise SupabaseAdapterConflictError("stale revision or relationship not found")
        return self._row_to_record(rows[0])

    def deactivate(self, tenant_context: TenantContext, record_id: str, *, deactivated_by: str | None = None) -> MutableRecord:
        current = self.get(tenant_context, record_id, include_inactive=True)
        if current is None:
            raise SupabaseAdapterConflictError("relationship not found")
        updated = replace(current, active=False, deactivated_at=datetime.now(timezone.utc), deactivated_by=deactivated_by)
        return self.update(updated, expected_revision=current.revision)

    def exists(self, tenant_context: TenantContext, record_id: str) -> bool:
        return self.get(tenant_context, record_id, include_inactive=True) is not None

    def count(self, query: RepositoryQuery) -> int:
        return self.search(query).total_count

    def search(self, query: RepositoryQuery) -> PageResult:
        builder = self._tenant_query(query.tenant_context)
        if not query.include_inactive:
            builder = builder.eq("active", True)
        builder = apply_query_filters(builder, query)
        response = self.client.execute(lambda: builder.execute())
        return page_result([self._row_to_record(row) for row in response_rows(response)], query)

    def list_relationships(self, tenant_context: TenantContext, *, include_inactive: bool = False, page: PageRequest | None = None) -> PageResult:
        return self.search(RepositoryQuery(tenant_context, include_inactive=include_inactive, page=default_page(page)))

    def _tenant_query(self, tenant_context: TenantContext):
        return self.client.table(self.table_name).select("*").eq("organization_id", tenant_context.organization_id).eq("tenant_id", tenant_context.tenant_id)

    def _coerce_record(self, value: MutableRecord | EnterpriseRelationship) -> MutableRecord:
        if isinstance(value, EnterpriseRelationship):
            return self.mapper.domain_to_record(value, TenantContext(value.organization_id, value.tenant_id or ""))
        return value

    def _record_to_row(self, record: MutableRecord) -> dict[str, Any]:
        payload = plain_mapping(record.payload)
        metadata = plain_mapping(record.metadata)
        return {
            "id": record.record_id,
            "source_entity_id": payload.get("source_entity_id") or metadata.get("source_entity_id"),
            "target_entity_id": payload.get("target_entity_id") or metadata.get("target_entity_id"),
            "relationship_type": payload.get("relationship_type") or metadata.get("relationship_type"),
            "organization_id": record.organization_id,
            "tenant_id": record.tenant_id,
            "source_system": payload.get("source_system") or metadata.get("source_system"),
            "source_identifier": payload.get("source_identifier") or metadata.get("source_identifier"),
            "confidence_score": ratio_to_100(payload.get("confidence_score")),
            "quality_score": ratio_to_100(payload.get("quality_score")),
            "metadata": plain_mapping(payload.get("metadata", {})),
            "active": record.active,
            "revision": record.revision,
            "version": int(payload.get("version", 1)),
            "created_at": iso(record.created_at),
            "updated_at": iso(record.updated_at),
            "deactivated_at": iso(record.deactivated_at),
            "deactivated_by": record.deactivated_by,
            "created_by": record.created_by,
            "updated_by": record.updated_by,
            "schema_version": record.schema_version,
        }

    def _row_to_record(self, row: dict[str, Any]) -> MutableRecord:
        payload = {
            "id": row["id"],
            "source_entity_id": row["source_entity_id"],
            "target_entity_id": row["target_entity_id"],
            "relationship_type": row["relationship_type"],
            "organization_id": row["organization_id"],
            "tenant_id": row["tenant_id"],
            "source_system": row.get("source_system"),
            "source_identifier": row.get("source_identifier"),
            "confidence_score": score_to_ratio(row.get("confidence_score")),
            "quality_score": score_to_ratio(row.get("quality_score")),
            "metadata": plain_mapping(row.get("metadata", {})),
            "version": row.get("version", 1),
            "created_at": dt(row["created_at"]),
            "updated_at": dt(row["updated_at"]),
        }
        return MutableRecord(
            record_id=row["id"],
            organization_id=row["organization_id"],
            tenant_id=row["tenant_id"],
            created_at=dt(row["created_at"]),
            updated_at=dt(row["updated_at"]),
            created_by=row.get("created_by"),
            updated_by=row.get("updated_by"),
            schema_version=row.get("schema_version", 1),
            metadata={
                "relationship_type": row["relationship_type"],
                "source_entity_id": row["source_entity_id"],
                "target_entity_id": row["target_entity_id"],
                "source_system": row.get("source_system"),
                "source_identifier": row.get("source_identifier"),
            },
            payload=payload,
            revision=row.get("revision", 1),
            active=row.get("active", True),
            deactivated_at=dt(row.get("deactivated_at")),
            deactivated_by=row.get("deactivated_by"),
        )
