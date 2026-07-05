"""In-memory canonical repository adapter."""

from __future__ import annotations

from typing import Sequence

from connector_normalization import CanonicalEnterpriseRecord
from connector_persistence.metadata import PersistenceMetadata, PersistenceResult
from connector_persistence.repository import CanonicalRepository


class MemoryCanonicalRepository(CanonicalRepository):
    """In-memory repository for tests and local smoke validation."""

    def __init__(self) -> None:
        self.records: dict[str, CanonicalEnterpriseRecord] = {}
        self.metadata: dict[str, PersistenceMetadata] = {}

    def save(self, record: CanonicalEnterpriseRecord, metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        if record.record_id in self.records:
            return PersistenceResult(attempted=1, succeeded=0, failed=1, errors=("Record already exists.",), batch_id=metadata.batch_id if metadata else None)
        self.records[record.record_id] = record
        if metadata:
            self.metadata[record.record_id] = metadata
        return PersistenceResult(attempted=1, succeeded=1, batch_id=metadata.batch_id if metadata else None)

    def save_batch(self, records: Sequence[CanonicalEnterpriseRecord], metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        attempted = len(records)
        succeeded = 0
        errors: list[str] = []
        for record in records:
            result = self.upsert(record, metadata=metadata)
            succeeded += result.succeeded
            errors.extend(result.errors)
        return PersistenceResult(
            attempted=attempted,
            succeeded=succeeded,
            failed=attempted - succeeded,
            errors=tuple(errors),
            batch_id=metadata.batch_id if metadata else None,
        )

    def upsert(self, record: CanonicalEnterpriseRecord, metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        self.records[record.record_id] = record
        if metadata:
            self.metadata[record.record_id] = metadata
        return PersistenceResult(attempted=1, succeeded=1, batch_id=metadata.batch_id if metadata else None)

    def exists(self, record_id: str) -> bool:
        return record_id in self.records

    def delete(self, record_id: str) -> PersistenceResult:
        existed = record_id in self.records
        self.records.pop(record_id, None)
        self.metadata.pop(record_id, None)
        return PersistenceResult(attempted=1, succeeded=1 if existed else 0, failed=0 if existed else 1)

    def find(self, record_id: str) -> CanonicalEnterpriseRecord | None:
        return self.records.get(record_id)

    def list_records(self) -> list[CanonicalEnterpriseRecord]:
        return list(self.records.values())
