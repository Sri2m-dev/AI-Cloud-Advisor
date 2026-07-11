"""Supabase PostgreSQL canonical entity repository adapter foundation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping

from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError
from data_fabric.contracts import EnterpriseEntity
from data_fabric.foundation import TenantContext
from data_fabric.persistence.interfaces import EntityRepository
from data_fabric.persistence.mappers import EntityPersistenceMapper
from data_fabric.persistence.models import MutableRecord, PageRequest, PageResult, RepositoryQuery


class SupabaseEntityRepository(EntityRepository):
    """Supabase PostgreSQL adapter for canonical entity current state."""

    table_name = "enterprise_entities"

    def __init__(self, client: SupabaseDataFabricClient) -> None:
        self.client = client
        self.mapper = EntityPersistenceMapper()

    def add(self, record: MutableRecord | EnterpriseEntity) -> MutableRecord:
        persistence_record = self._coerce_record(record)
        row = self._record_to_row(persistence_record)
        response = self.client.execute(lambda: self.client.table(self.table_name).insert(row).execute())
        return self._row_to_record(_single(response))

    def get(
        self,
        tenant_context: TenantContext,
        record_id: str,
        *,
        include_inactive: bool = False,
    ) -> MutableRecord | None:
        query = self._tenant_query(tenant_context).eq("id", record_id)
        if not include_inactive:
            query = query.eq("active", True)
        response = self.client.execute(lambda: query.limit(1).execute())
        return self._optional_record(response)

    def find_by_canonical_id(
        self,
        tenant_context: TenantContext,
        canonical_id: str,
        *,
        include_inactive: bool = False,
    ) -> MutableRecord | None:
        query = self._tenant_query(tenant_context).eq("canonical_id", canonical_id)
        if not include_inactive:
            query = query.eq("active", True)
        response = self.client.execute(lambda: query.limit(1).execute())
        return self._optional_record(response)

    def find_by_source_identity(
        self,
        tenant_context: TenantContext,
        source_system: str,
        source_identifier: str,
        *,
        include_inactive: bool = False,
    ) -> MutableRecord | None:
        query = (
            self._tenant_query(tenant_context)
            .eq("source_system", source_system)
            .eq("source_identifier", source_identifier)
        )
        if not include_inactive:
            query = query.eq("active", True)
        response = self.client.execute(lambda: query.limit(1).execute())
        return self._optional_record(response)

    def update(self, record: MutableRecord, *, expected_revision: int) -> MutableRecord:
        row = self._record_to_row(record)
        response = self.client.execute(
            lambda: self.client.rpc(
                "data_fabric_update_enterprise_entity",
                {
                    "p_entity_id": record.record_id,
                    "p_organization_id": record.organization_id,
                    "p_tenant_id": record.tenant_id,
                    "p_expected_revision": expected_revision,
                    "p_entity": row,
                },
            )
        )
        data = getattr(response, "data", None) or []
        if not data:
            raise SupabaseAdapterConflictError("stale revision or entity not found")
        return self._row_to_record(data[0])

    def deactivate(
        self,
        tenant_context: TenantContext,
        record_id: str,
        *,
        deactivated_by: str | None = None,
    ) -> MutableRecord:
        current = self.get(tenant_context, record_id, include_inactive=True)
        if current is None:
            raise SupabaseAdapterConflictError("entity not found")
        updated = replace(
            current,
            active=False,
            deactivated_at=datetime.now(timezone.utc),
            deactivated_by=deactivated_by,
        )
        return self.update(updated, expected_revision=current.revision)

    def exists(self, tenant_context: TenantContext, record_id: str) -> bool:
        return self.get(tenant_context, record_id, include_inactive=True) is not None

    def count(self, query: RepositoryQuery) -> int:
        return self.search(query).total_count

    def search(self, query: RepositoryQuery) -> PageResult:
        builder = self._tenant_query(query.tenant_context)
        if not query.include_inactive:
            builder = builder.eq("active", True)
        for field, value in query.filters.items():
            builder = builder.eq(field, value)
        for field, value in query.metadata_filters.items():
            builder = builder.eq(f"metadata->{field}", value)
        sort_field = "id" if query.sort.field == "record_id" else query.sort.field
        builder = builder.order(sort_field, desc=query.sort.descending)
        builder = builder.range(query.page.offset, query.page.offset + query.page.limit - 1)
        response = self.client.execute(lambda: builder.execute())
        rows = list(getattr(response, "data", None) or [])
        return PageResult(tuple(self._row_to_record(row) for row in rows), len(rows), query.page)

    def list_entities(
        self,
        tenant_context: TenantContext,
        *,
        include_inactive: bool = False,
        page: PageRequest | None = None,
    ) -> PageResult:
        return self.search(RepositoryQuery(tenant_context, include_inactive=include_inactive, page=page or PageRequest()))

    def _tenant_query(self, tenant_context: TenantContext):
        return (
            self.client.table(self.table_name)
            .select("*")
            .eq("organization_id", tenant_context.organization_id)
            .eq("tenant_id", tenant_context.tenant_id)
        )

    def _coerce_record(self, value: MutableRecord | EnterpriseEntity) -> MutableRecord:
        if isinstance(value, EnterpriseEntity):
            return self.mapper.domain_to_record(value, TenantContext(value.organization_id, value.tenant_id or ""))
        return value

    def _optional_record(self, response: Any) -> MutableRecord | None:
        data = getattr(response, "data", None) or []
        if not data:
            return None
        return self._row_to_record(data[0])

    def _record_to_row(self, record: MutableRecord) -> dict[str, Any]:
        payload = _plain_mapping(record.payload)
        metadata = _plain_mapping(record.metadata)
        return {
            "id": record.record_id,
            "canonical_id": payload.get("canonical_id") or metadata.get("canonical_id"),
            "entity_type": payload.get("entity_type") or metadata.get("entity_type"),
            "name": payload.get("name"),
            "source_system": payload.get("source_system") or metadata.get("source_system"),
            "source_identifier": payload.get("source_identifier") or metadata.get("source_identifier"),
            "organization_id": record.organization_id,
            "tenant_id": record.tenant_id,
            "version": int(payload.get("version", 1)),
            "confidence_score": _ratio_to_100(payload.get("confidence_score")),
            "quality_score": _ratio_to_100(payload.get("quality_score")),
            "tags": list(payload.get("tags", ())),
            "metadata": _plain_mapping(payload.get("metadata", {})),
            "active": record.active,
            "revision": record.revision,
            "created_at": _iso(record.created_at),
            "updated_at": _iso(record.updated_at),
            "deactivated_at": _iso(record.deactivated_at),
            "deactivated_by": record.deactivated_by,
            "created_by": record.created_by,
            "updated_by": record.updated_by,
            "schema_version": record.schema_version,
        }

    def _row_to_record(self, row: dict[str, Any]) -> MutableRecord:
        payload = {
            "id": row["id"],
            "canonical_id": row["canonical_id"],
            "entity_type": row["entity_type"],
            "name": row["name"],
            "source_system": row["source_system"],
            "source_identifier": row["source_identifier"],
            "organization_id": row["organization_id"],
            "tenant_id": row["tenant_id"],
            "version": row.get("version", 1),
            "confidence_score": _score_to_ratio(row.get("confidence_score")),
            "quality_score": _score_to_ratio(row.get("quality_score")),
            "tags": tuple(row.get("tags") or ()),
            "metadata": dict(row.get("metadata") or {}),
            "created_at": _dt(row["created_at"]),
            "updated_at": _dt(row["updated_at"]),
        }
        return MutableRecord(
            record_id=row["id"],
            organization_id=row["organization_id"],
            tenant_id=row["tenant_id"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
            created_by=row.get("created_by"),
            updated_by=row.get("updated_by"),
            schema_version=row.get("schema_version", 1),
            metadata={
                "canonical_id": row["canonical_id"],
                "entity_type": row["entity_type"],
                "source_system": row["source_system"],
                "source_identifier": row["source_identifier"],
            },
            payload=payload,
            revision=row.get("revision", 1),
            active=row.get("active", True),
            deactivated_at=_dt(row.get("deactivated_at")),
            deactivated_by=row.get("deactivated_by"),
        )


def _single(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None) or []
    return data[0] if isinstance(data, list) else data


def _ratio_to_100(value: Any) -> float | None:
    if value is None:
        return None
    score = float(value)
    return score * 100.0 if score <= 1.0 else score


def _score_to_ratio(value: Any) -> float:
    if value is None:
        return 1.0
    score = float(value)
    return score / 100.0 if score > 1.0 else score


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


def _dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value)).astimezone(timezone.utc)


def _plain_mapping(value: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    return {str(key): _plain_value(item) for key, item in dict(value).items()}


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _plain_mapping(value)
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted((_plain_value(item) for item in value), key=str)
    return deepcopy(value)
