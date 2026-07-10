"""In-memory compliance repositories for persistence contract validation."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping

from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext
from data_fabric.orchestration import IdempotencyState
from data_fabric.persistence.exceptions import (
    PersistenceConflictError,
    PersistenceDuplicateError,
    PersistenceImmutableStateError,
    PersistenceNotFoundError,
    PersistenceTenantBoundaryError,
)
from data_fabric.persistence.interfaces import (
    EntityRepository,
    IdempotencyRepository,
    LineageRepository,
    OntologyRepository,
    ProvenanceRepository,
    QualityAssessmentRepository,
    RelationshipRepository,
    SemanticMappingRepository,
    TemporalHistoryRepository,
    VersionRepository,
)
from data_fabric.persistence.models import (
    AppendOnlyRecord,
    MutableRecord,
    PageResult,
    PersistenceRecord,
    RepositoryQuery,
)


class InMemoryMutableRepository(EntityRepository):
    """Reusable tenant-isolated mutable repository compliance implementation."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], MutableRecord] = {}

    def add(self, record: MutableRecord) -> MutableRecord:
        key = self._key(record.tenant_context, record.record_id)
        if key in self._records:
            raise PersistenceDuplicateError(f"record already exists: {record.record_id}")
        stored = _copy_record(record)
        self._records[key] = stored
        return _copy_record(stored)

    def get(self, tenant_context: TenantContext, record_id: str, *, include_inactive: bool = False) -> MutableRecord | None:
        record = self._records.get(self._key(tenant_context, record_id))
        if record is None:
            return None
        if not include_inactive and not record.active:
            return None
        return _copy_record(record)

    def update(self, record: MutableRecord, *, expected_revision: int) -> MutableRecord:
        key = self._key(record.tenant_context, record.record_id)
        current = self._records.get(key)
        if current is None:
            if self._record_id_exists_elsewhere(record.record_id):
                raise PersistenceTenantBoundaryError("cross-tenant update rejected")
            raise PersistenceNotFoundError(f"record not found: {record.record_id}")
        if current.revision != expected_revision:
            raise PersistenceConflictError("stale revision")
        updated = replace(
            record,
            revision=current.revision + 1,
            concurrency_token=None,
            updated_at=datetime.now(timezone.utc),
        )
        stored = _copy_record(updated)
        self._records[key] = stored
        return _copy_record(stored)

    def deactivate(self, tenant_context: TenantContext, record_id: str, *, deactivated_by: str | None = None) -> MutableRecord:
        current = self.get(tenant_context, record_id, include_inactive=True)
        if current is None:
            if self._record_id_exists_elsewhere(record_id):
                raise PersistenceTenantBoundaryError("cross-tenant deactivate rejected")
            raise PersistenceNotFoundError(f"record not found: {record_id}")
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
        return len(self.search(query).items)

    def search(self, query: RepositoryQuery) -> PageResult:
        records = [
            record for key, record in self._records.items()
            if key[0] == query.tenant_context.organization_id and key[1] == query.tenant_context.tenant_id
        ]
        if not query.include_inactive:
            records = [record for record in records if record.active]
        records = _filter_records(records, query)
        ordered = _sort_records(records, query)
        total = len(ordered)
        page = ordered[query.page.offset: query.page.offset + query.page.limit]
        return PageResult(tuple(_copy_record(item) for item in page), total, query.page)

    def _record_id_exists_elsewhere(self, record_id: str) -> bool:
        return any(key[2] == record_id for key in self._records)

    @staticmethod
    def _key(tenant_context: TenantContext, record_id: str) -> tuple[str, str, str]:
        return (tenant_context.organization_id, tenant_context.tenant_id, record_id)

    def _snapshot(self):
        return dict(self._records)

    def _restore(self, snapshot) -> None:
        self._records = dict(snapshot)


class InMemoryAppendOnlyRepository(LineageRepository):
    """Reusable append-only repository compliance implementation."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], AppendOnlyRecord] = {}

    def append(self, record: AppendOnlyRecord) -> AppendOnlyRecord:
        key = self._key(record.tenant_context, record.record_id)
        if key in self._records:
            raise PersistenceDuplicateError(f"append-only record already exists: {record.record_id}")
        stored = _copy_record(record)
        self._records[key] = stored
        return _copy_record(stored)

    def update(self, record: AppendOnlyRecord, *, expected_revision: int | None = None) -> AppendOnlyRecord:
        raise PersistenceImmutableStateError("append-only records cannot be updated")

    def get(self, tenant_context: TenantContext, record_id: str, *, include_inactive: bool = False) -> AppendOnlyRecord | None:
        record = self._records.get(self._key(tenant_context, record_id))
        return _copy_record(record) if record is not None else None

    def exists(self, tenant_context: TenantContext, record_id: str) -> bool:
        return self.get(tenant_context, record_id) is not None

    def count(self, query: RepositoryQuery) -> int:
        return len(self.search(query).items)

    def search(self, query: RepositoryQuery) -> PageResult:
        records = [
            record for key, record in self._records.items()
            if key[0] == query.tenant_context.organization_id and key[1] == query.tenant_context.tenant_id
        ]
        records = _filter_records(records, query)
        ordered = _sort_records(records, query)
        total = len(ordered)
        page = ordered[query.page.offset: query.page.offset + query.page.limit]
        return PageResult(tuple(_copy_record(item) for item in page), total, query.page)

    def history_for_subject(self, tenant_context: TenantContext, subject_id: str) -> tuple[AppendOnlyRecord, ...]:
        query = RepositoryQuery(tenant_context, filters={"subject_id": subject_id})
        return tuple(self.search(query).items)

    @staticmethod
    def _key(tenant_context: TenantContext, record_id: str) -> tuple[str, str, str]:
        return (tenant_context.organization_id, tenant_context.tenant_id, record_id)

    def _snapshot(self):
        return dict(self._records)

    def _restore(self, snapshot) -> None:
        self._records = dict(snapshot)


class InMemoryEntityRepository(InMemoryMutableRepository, EntityRepository):
    pass


class InMemoryRelationshipRepository(InMemoryMutableRepository, RelationshipRepository):
    pass


class InMemoryOntologyRepository(InMemoryMutableRepository, OntologyRepository):
    pass


class InMemorySemanticMappingRepository(InMemoryMutableRepository, SemanticMappingRepository):
    pass


class InMemoryLineageRepository(InMemoryAppendOnlyRepository, LineageRepository):
    pass


class InMemoryProvenanceRepository(InMemoryAppendOnlyRepository, ProvenanceRepository):
    pass


class InMemoryVersionRepository(InMemoryAppendOnlyRepository, VersionRepository):
    pass


class InMemoryQualityAssessmentRepository(InMemoryAppendOnlyRepository, QualityAssessmentRepository):
    pass


class InMemoryTemporalHistoryRepository(InMemoryAppendOnlyRepository, TemporalHistoryRepository):
    pass


class InMemoryIdempotencyRepository(InMemoryMutableRepository, IdempotencyRepository):
    """Tenant-isolated idempotency repository compliance implementation."""

    def reserve_key(self, tenant_context: TenantContext, key: str, payload_hash: str) -> MutableRecord:
        existing = self.get(tenant_context, key, include_inactive=True)
        if existing is None:
            record = MutableRecord(
                record_id=key,
                organization_id=tenant_context.organization_id,
                tenant_id=tenant_context.tenant_id,
                payload={"payload_hash": payload_hash, "state": IdempotencyState.IN_PROGRESS.value},
                metadata={"idempotency_key": key},
            )
            return self.add(record)
        if existing.payload.get("payload_hash") != payload_hash:
            raise PersistenceConflictError("idempotency key reused with different payload hash")
        return existing

    def mark_completed(self, tenant_context: TenantContext, key: str, result_ref: str) -> MutableRecord:
        record = self._require(tenant_context, key)
        payload = dict(record.payload)
        payload.update({"state": IdempotencyState.COMPLETED.value, "result_ref": result_ref})
        return self.update(replace(record, payload=payload), expected_revision=record.revision)

    def mark_failed(self, tenant_context: TenantContext, key: str, reason: str) -> MutableRecord:
        record = self._require(tenant_context, key)
        payload = dict(record.payload)
        payload.update({"state": IdempotencyState.FAILED.value, "failure_reason": reason})
        return self.update(replace(record, payload=payload), expected_revision=record.revision)

    def get_status(self, tenant_context: TenantContext, key: str) -> IdempotencyState | None:
        record = self.get(tenant_context, key, include_inactive=True)
        if record is None:
            return None
        return IdempotencyState(record.payload["state"])

    def _require(self, tenant_context: TenantContext, key: str) -> MutableRecord:
        record = self.get(tenant_context, key, include_inactive=True)
        if record is None:
            raise PersistenceNotFoundError(f"idempotency key not reserved: {key}")
        return record


def _filter_records(records: list[PersistenceRecord], query: RepositoryQuery) -> list[PersistenceRecord]:
    result = []
    for record in records:
        if all(_value_for(record, key) == value for key, value in query.filters.items()) and all(record.metadata.get(key) == value for key, value in query.metadata_filters.items()):
            result.append(record)
    return result


def _sort_records(records: list[PersistenceRecord], query: RepositoryQuery) -> list[PersistenceRecord]:
    field = query.sort.field
    return sorted(records, key=lambda record: (_value_for(record, field), record.record_id), reverse=query.sort.descending)


def _value_for(record: PersistenceRecord, field: str) -> Any:
    if hasattr(record, field):
        return getattr(record, field)
    if field in record.payload:
        return record.payload[field]
    if field in record.metadata:
        return record.metadata[field]
    return ""


def _copy_record(record: PersistenceRecord):
    metadata = _thaw(record.metadata)
    payload = _thaw(record.payload)
    return replace(record, metadata=metadata, payload=payload)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(value[key]) for key in value}
    if isinstance(value, tuple):
        return tuple(_thaw(item) for item in value)
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    if isinstance(value, set | frozenset):
        return {_thaw(item) for item in value}
    return value



