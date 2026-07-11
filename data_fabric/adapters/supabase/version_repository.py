"""Supabase PostgreSQL append-only entity version repository adapter."""

from __future__ import annotations

from typing import Any

from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError, SupabaseAdapterOperationError
from data_fabric.adapters.supabase.repository_utils import apply_query_filters, dt, ensure_inserted, iso, optional_row, page_result, plain_mapping, response_rows
from data_fabric.foundation import TenantContext
from data_fabric.persistence.interfaces import VersionRepository
from data_fabric.persistence.models import AppendOnlyRecord, ImmutableRecord, PageResult, RepositoryQuery


class SupabaseVersionRepository(VersionRepository):
    """Append-only Supabase adapter for entity snapshots."""

    table_name = "entity_versions"

    def __init__(self, client: SupabaseDataFabricClient) -> None:
        self.client = client

    def append(self, record: AppendOnlyRecord) -> AppendOnlyRecord:
        self._reject_out_of_order(record)
        row = self._record_to_row(record)
        response = self.client.execute(lambda: self.client.table(self.table_name).insert(row).execute())
        return self._row_to_record(ensure_inserted(response, "entity version"))

    def update(self, record: ImmutableRecord, *, expected_revision: int | None = None) -> ImmutableRecord:
        raise SupabaseAdapterOperationError("entity_versions is append-only and does not support update")

    def get(self, tenant_context: TenantContext, record_id: str, *, include_inactive: bool = False) -> AppendOnlyRecord | None:
        return self.get_snapshot(tenant_context, record_id)

    def get_snapshot(self, tenant_context: TenantContext, snapshot_id: str) -> AppendOnlyRecord | None:
        response = self.client.execute(lambda: self._tenant_query(tenant_context).eq("snapshot_id", snapshot_id).limit(1).execute())
        row = optional_row(response)
        return self._row_to_record(row) if row else None

    def get_latest_for_entity(self, tenant_context: TenantContext, entity_id: str) -> AppendOnlyRecord | None:
        response = self.client.execute(lambda: self._tenant_query(tenant_context).eq("entity_id", entity_id).order("version", desc=True).limit(1).execute())
        row = optional_row(response)
        return self._row_to_record(row) if row else None

    def list_entity_versions(self, tenant_context: TenantContext, entity_id: str) -> tuple[AppendOnlyRecord, ...]:
        response = self.client.execute(lambda: self._tenant_query(tenant_context).eq("entity_id", entity_id).order("version").execute())
        return tuple(self._row_to_record(row) for row in response_rows(response))

    def find_by_payload_hash(self, tenant_context: TenantContext, payload_hash: str) -> tuple[AppendOnlyRecord, ...]:
        response = self.client.execute(lambda: self._tenant_query(tenant_context).eq("payload_hash", payload_hash).order("recorded_at").execute())
        return tuple(self._row_to_record(row) for row in response_rows(response))

    def exists(self, tenant_context: TenantContext, record_id: str) -> bool:
        return self.get_snapshot(tenant_context, record_id) is not None

    def count(self, query: RepositoryQuery) -> int:
        return self.search(query).total_count

    def search(self, query: RepositoryQuery) -> PageResult:
        response = self.client.execute(lambda: apply_query_filters(self._tenant_query(query.tenant_context), query).execute())
        return page_result([self._row_to_record(row) for row in response_rows(response)], query)

    def _reject_out_of_order(self, record: AppendOnlyRecord) -> None:
        entity_id = str(record.payload.get("entity_id") or record.metadata.get("entity_id") or "")
        version = int(record.payload.get("version", 0))
        if not entity_id or version < 1:
            raise SupabaseAdapterOperationError("entity_id and positive version are required")
        latest = self.get_latest_for_entity(record.tenant_context, entity_id)
        if latest and version <= int(latest.payload.get("version", 0)):
            raise SupabaseAdapterConflictError("entity version must increase monotonically")

    def _tenant_query(self, tenant_context: TenantContext):
        return self.client.table(self.table_name).select("*").eq("organization_id", tenant_context.organization_id).eq("tenant_id", tenant_context.tenant_id)

    def _record_to_row(self, record: AppendOnlyRecord) -> dict[str, Any]:
        payload = plain_mapping(record.payload)
        metadata = plain_mapping(record.metadata)
        return {
            "snapshot_id": record.record_id,
            "entity_id": payload.get("entity_id") or metadata.get("entity_id"),
            "canonical_id": payload.get("canonical_id") or metadata.get("canonical_id"),
            "organization_id": record.organization_id,
            "tenant_id": record.tenant_id,
            "version": int(payload.get("version", 1)),
            "source_system": payload.get("source_system") or metadata.get("source_system"),
            "source_identifier": payload.get("source_identifier") or metadata.get("source_identifier"),
            "recorded_at": iso(record.created_at),
            "effective_from": iso(dt(payload.get("effective_from"))),
            "effective_to": iso(dt(payload.get("effective_to"))),
            "payload": payload.get("payload", payload),
            "payload_hash": record.payload_hash,
            "lineage_references": payload.get("lineage_references", []),
            "provenance_references": payload.get("provenance_references", []),
            "schema_version": record.schema_version,
        }

    def _row_to_record(self, row: dict[str, Any]) -> AppendOnlyRecord:
        payload = {
            "entity_id": row["entity_id"],
            "canonical_id": row["canonical_id"],
            "version": row["version"],
            "source_system": row.get("source_system"),
            "source_identifier": row.get("source_identifier"),
            "recorded_at": dt(row["recorded_at"]),
            "effective_from": dt(row.get("effective_from")),
            "effective_to": dt(row.get("effective_to")),
            "payload": plain_mapping(row.get("payload", {})),
            "lineage_references": row.get("lineage_references") or [],
            "provenance_references": row.get("provenance_references") or [],
        }
        return AppendOnlyRecord(
            record_id=row["snapshot_id"],
            organization_id=row["organization_id"],
            tenant_id=row["tenant_id"],
            created_at=dt(row["recorded_at"]),
            updated_at=dt(row["recorded_at"]),
            schema_version=row.get("schema_version", 1),
            metadata={"entity_id": row["entity_id"], "canonical_id": row["canonical_id"]},
            payload=payload,
            payload_hash=row["payload_hash"],
        )
