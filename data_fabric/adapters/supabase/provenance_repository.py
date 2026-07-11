"""Supabase PostgreSQL append-only provenance record repository adapter."""

from __future__ import annotations

from typing import Any

from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterOperationError
from data_fabric.adapters.supabase.repository_utils import apply_query_filters, dt, ensure_inserted, iso, optional_row, page_result, plain_mapping, response_rows
from data_fabric.foundation import TenantContext
from data_fabric.persistence.interfaces import ProvenanceRepository
from data_fabric.persistence.models import AppendOnlyRecord, ImmutableRecord, PageResult, RepositoryQuery


class SupabaseProvenanceRepository(ProvenanceRepository):
    """Append-only Supabase adapter for provenance records."""

    table_name = "provenance_records"

    def __init__(self, client: SupabaseDataFabricClient) -> None:
        self.client = client

    def append(self, record: AppendOnlyRecord) -> AppendOnlyRecord:
        row = self._record_to_row(record)
        response = self.client.execute(lambda: self.client.table(self.table_name).insert(row).execute())
        return self._row_to_record(ensure_inserted(response, "provenance record"))

    def update(self, record: ImmutableRecord, *, expected_revision: int | None = None) -> ImmutableRecord:
        raise SupabaseAdapterOperationError("provenance_records is append-only and does not support update")

    def get(self, tenant_context: TenantContext, record_id: str, *, include_inactive: bool = False) -> AppendOnlyRecord | None:
        response = self.client.execute(lambda: self._tenant_query(tenant_context).eq("provenance_id", record_id).limit(1).execute())
        row = optional_row(response)
        return self._row_to_record(row) if row else None

    def find_by_source_identity(self, tenant_context: TenantContext, source_system: str, source_identifier: str) -> tuple[AppendOnlyRecord, ...]:
        response = self.client.execute(lambda: self._tenant_query(tenant_context).eq("source_system", source_system).eq("source_identifier", source_identifier).order("captured_at").execute())
        return tuple(self._row_to_record(row) for row in response_rows(response))

    def list_by_entity(self, tenant_context: TenantContext, entity_id: str) -> tuple[AppendOnlyRecord, ...]:
        return self._list(tenant_context, "entity_id", entity_id)

    def list_by_relationship(self, tenant_context: TenantContext, relationship_id: str) -> tuple[AppendOnlyRecord, ...]:
        return self._list(tenant_context, "relationship_id", relationship_id)

    def exists(self, tenant_context: TenantContext, record_id: str) -> bool:
        return self.get(tenant_context, record_id) is not None

    def count(self, query: RepositoryQuery) -> int:
        return self.search(query).total_count

    def search(self, query: RepositoryQuery) -> PageResult:
        response = self.client.execute(lambda: apply_query_filters(self._tenant_query(query.tenant_context), query).execute())
        return page_result([self._row_to_record(row) for row in response_rows(response)], query)

    def _list(self, tenant_context: TenantContext, field: str, value: str) -> tuple[AppendOnlyRecord, ...]:
        response = self.client.execute(lambda: self._tenant_query(tenant_context).eq(field, value).order("captured_at").execute())
        return tuple(self._row_to_record(row) for row in response_rows(response))

    def _tenant_query(self, tenant_context: TenantContext):
        return self.client.table(self.table_name).select("*").eq("organization_id", tenant_context.organization_id).eq("tenant_id", tenant_context.tenant_id)

    def _record_to_row(self, record: AppendOnlyRecord) -> dict[str, Any]:
        payload = plain_mapping(record.payload)
        metadata = plain_mapping(record.metadata)
        return {
            "provenance_id": record.record_id,
            "entity_id": payload.get("entity_id") or metadata.get("entity_id"),
            "relationship_id": payload.get("relationship_id") or metadata.get("relationship_id"),
            "organization_id": record.organization_id,
            "tenant_id": record.tenant_id,
            "source_system": payload.get("source_system") or metadata.get("source_system"),
            "source_identifier": payload.get("source_identifier") or metadata.get("source_identifier"),
            "captured_at": iso(dt(payload.get("captured_at")) or record.created_at),
            "payload_hash": record.payload_hash,
            "evidence": plain_mapping(payload.get("evidence", {})),
            "metadata": plain_mapping(payload.get("metadata", metadata)),
            "schema_version": record.schema_version,
        }

    def _row_to_record(self, row: dict[str, Any]) -> AppendOnlyRecord:
        payload = {
            "entity_id": row.get("entity_id"),
            "relationship_id": row.get("relationship_id"),
            "source_system": row["source_system"],
            "source_identifier": row["source_identifier"],
            "captured_at": dt(row["captured_at"]),
            "payload_hash": row.get("payload_hash"),
            "evidence": plain_mapping(row.get("evidence", {})),
            "metadata": plain_mapping(row.get("metadata", {})),
        }
        return AppendOnlyRecord(
            record_id=row["provenance_id"],
            organization_id=row["organization_id"],
            tenant_id=row["tenant_id"],
            created_at=dt(row["captured_at"]),
            updated_at=dt(row["captured_at"]),
            schema_version=row.get("schema_version", 1),
            metadata={"source_system": row["source_system"], "source_identifier": row["source_identifier"]},
            payload=payload,
            payload_hash=row.get("payload_hash") or "",
        )
