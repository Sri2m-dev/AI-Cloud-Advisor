"""Supabase canonical repository adapter skeleton.

This adapter intentionally avoids binding the connector framework directly to a
specific table design. It defines the seam where E8.2 Data Fabric persistence can
map canonical records into Supabase/Postgres tables.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Sequence

from connector_normalization import CanonicalEnterpriseRecord
from connector_persistence.metadata import PersistenceMetadata, PersistenceResult
from connector_persistence.repository import CanonicalRepository


class SupabaseCanonicalRepository(CanonicalRepository):
    """Supabase-backed canonical repository skeleton."""

    def __init__(self, client: Any, table_name: str = "canonical_enterprise_records") -> None:
        self.client = client
        self.table_name = table_name

    def save(self, record: CanonicalEnterpriseRecord, metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        return self.upsert(record, metadata=metadata)

    def save_batch(self, records: Sequence[CanonicalEnterpriseRecord], metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        payload = [self._serialize(record, metadata) for record in records]
        if not payload:
            return PersistenceResult(attempted=0, succeeded=0, batch_id=metadata.batch_id if metadata else None)
        try:
            self.client.table(self.table_name).upsert(payload).execute()
            return PersistenceResult(attempted=len(records), succeeded=len(records), batch_id=metadata.batch_id if metadata else None)
        except Exception as exc:  # pragma: no cover - depends on external client
            return PersistenceResult(attempted=len(records), succeeded=0, failed=len(records), errors=(str(exc),), batch_id=metadata.batch_id if metadata else None)

    def upsert(self, record: CanonicalEnterpriseRecord, metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        try:
            self.client.table(self.table_name).upsert(self._serialize(record, metadata)).execute()
            return PersistenceResult(attempted=1, succeeded=1, batch_id=metadata.batch_id if metadata else None)
        except Exception as exc:  # pragma: no cover - depends on external client
            return PersistenceResult(attempted=1, succeeded=0, failed=1, errors=(str(exc),), batch_id=metadata.batch_id if metadata else None)

    def exists(self, record_id: str) -> bool:
        return self.find(record_id) is not None

    def delete(self, record_id: str) -> PersistenceResult:
        try:
            self.client.table(self.table_name).delete().eq("record_id", record_id).execute()
            return PersistenceResult(attempted=1, succeeded=1)
        except Exception as exc:  # pragma: no cover - depends on external client
            return PersistenceResult(attempted=1, succeeded=0, failed=1, errors=(str(exc),))

    def find(self, record_id: str) -> CanonicalEnterpriseRecord | None:
        # Full deserialization is deferred until the canonical Supabase schema is finalized in E8.2.
        response = self.client.table(self.table_name).select("*").eq("record_id", record_id).limit(1).execute()
        data = getattr(response, "data", None) or []
        return data[0] if data else None  # type: ignore[return-value]

    def list_records(self) -> list[CanonicalEnterpriseRecord]:
        response = self.client.table(self.table_name).select("*").execute()
        return list(getattr(response, "data", None) or [])  # type: ignore[return-value]

    def _serialize(self, record: CanonicalEnterpriseRecord, metadata: PersistenceMetadata | None) -> dict[str, Any]:
        payload = asdict(record)
        payload["record_type"] = record.record_type.value
        payload["persistence_metadata"] = asdict(metadata) if metadata else None
        return payload
