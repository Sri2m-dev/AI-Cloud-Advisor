"""In-memory reference stores for versioning and temporal history."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.versioning.comparison import DeterministicVersionComparator
from data_fabric.versioning.exceptions import VersioningValidationError
from data_fabric.versioning.interfaces import TemporalHistoryStore, VersionStore
from data_fabric.versioning.models import (
    EntitySnapshot,
    HistoryQuery,
    HistoryResult,
    RelationshipSnapshot,
    TemporalRecord,
    VersionComparison,
    VersionRecord,
    payload_hash,
)

PartitionKey = tuple[str, str | None, str]


class InMemoryVersionStore(VersionStore):
    """Non-persistent immutable snapshot store."""

    def __init__(self, comparator: DeterministicVersionComparator | None = None) -> None:
        self._entity_snapshots: dict[PartitionKey, list[EntitySnapshot]] = {}
        self._relationship_snapshots: dict[PartitionKey, list[RelationshipSnapshot]] = {}
        self._snapshots: dict[tuple[str, str | None, str], VersionRecord] = {}
        self._comparator = comparator or DeterministicVersionComparator()

    def create_entity_snapshot(
        self,
        entity: EnterpriseEntity,
        *,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        allow_unchanged: bool = False,
        lineage_ref: str | None = None,
        provenance_ref: str | None = None,
    ) -> EntitySnapshot:
        version = int(entity.version)
        effective_from = _resolve_effective_from(entity, effective_from)
        effective_to = _resolve_effective_to(entity, effective_to)
        payload = _payload_from_contract(entity)
        hash_value = payload_hash(payload)
        key = _key(entity.organization_id, entity.tenant_id, entity.id)
        self._validate_new_version(self._entity_snapshots.get(key, []), version, hash_value, allow_unchanged)
        snapshot = EntitySnapshot(
            snapshot_id=f"entity:{entity.organization_id}:{entity.tenant_id}:{entity.id}:v{version}",
            subject_id=entity.id,
            subject_type="entity",
            organization_id=entity.organization_id,
            tenant_id=entity.tenant_id,
            version=version,
            recorded_at=datetime.now(timezone.utc),
            effective_from=effective_from,
            effective_to=effective_to,
            source_system=entity.source_system,
            source_identifier=entity.source_identifier,
            payload=payload,
            payload_hash=hash_value,
            lineage_ref=lineage_ref,
            provenance_ref=provenance_ref,
            entity_id=entity.id,
            canonical_id=entity.canonical_id,
        )
        self._entity_snapshots.setdefault(key, []).append(snapshot)
        self._snapshots[(snapshot.organization_id, snapshot.tenant_id, snapshot.snapshot_id)] = snapshot
        return snapshot

    def create_relationship_snapshot(
        self,
        relationship: EnterpriseRelationship,
        *,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        allow_unchanged: bool = False,
        lineage_ref: str | None = None,
        provenance_ref: str | None = None,
    ) -> RelationshipSnapshot:
        version = int(relationship.version)
        effective_from = _resolve_effective_from(relationship, effective_from)
        effective_to = _resolve_effective_to(relationship, effective_to)
        payload = _payload_from_contract(relationship)
        hash_value = payload_hash(payload)
        key = _key(relationship.organization_id, relationship.tenant_id, relationship.id)
        self._validate_new_version(self._relationship_snapshots.get(key, []), version, hash_value, allow_unchanged)
        snapshot = RelationshipSnapshot(
            snapshot_id=f"relationship:{relationship.organization_id}:{relationship.tenant_id}:{relationship.id}:v{version}",
            subject_id=relationship.id,
            subject_type="relationship",
            organization_id=relationship.organization_id,
            tenant_id=relationship.tenant_id,
            version=version,
            recorded_at=datetime.now(timezone.utc),
            effective_from=effective_from,
            effective_to=effective_to,
            source_system=relationship.source_system,
            source_identifier=relationship.source_identifier,
            payload=payload,
            payload_hash=hash_value,
            lineage_ref=lineage_ref,
            provenance_ref=provenance_ref,
            relationship_id=relationship.id,
        )
        self._relationship_snapshots.setdefault(key, []).append(snapshot)
        self._snapshots[(snapshot.organization_id, snapshot.tenant_id, snapshot.snapshot_id)] = snapshot
        return snapshot

    def get_snapshot(
        self,
        snapshot_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> VersionRecord:
        try:
            return self._snapshots[(organization_id, tenant_id, snapshot_id)]
        except KeyError as exc:
            raise VersioningValidationError("snapshot not found in organization/tenant partition") from exc

    def get_latest_entity_snapshot(
        self,
        entity_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> EntitySnapshot | None:
        versions = self.list_entity_versions(entity_id, organization_id=organization_id, tenant_id=tenant_id)
        return versions[-1] if versions else None

    def get_latest_relationship_snapshot(
        self,
        relationship_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> RelationshipSnapshot | None:
        versions = self.list_relationship_versions(relationship_id, organization_id=organization_id, tenant_id=tenant_id)
        return versions[-1] if versions else None

    def list_entity_versions(
        self,
        entity_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> list[EntitySnapshot]:
        return sorted(self._entity_snapshots.get(_key(organization_id, tenant_id, entity_id), []), key=lambda item: item.version)

    def list_relationship_versions(
        self,
        relationship_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> list[RelationshipSnapshot]:
        return sorted(self._relationship_snapshots.get(_key(organization_id, tenant_id, relationship_id), []), key=lambda item: item.version)

    def compare_entity_versions(self, first: EntitySnapshot, second: EntitySnapshot) -> VersionComparison:
        return self._comparator.compare(first, second)

    def compare_relationship_versions(self, first: RelationshipSnapshot, second: RelationshipSnapshot) -> VersionComparison:
        return self._comparator.compare(first, second)

    @staticmethod
    def _validate_new_version(
        existing: list[VersionRecord],
        version: int,
        hash_value: str,
        allow_unchanged: bool,
    ) -> None:
        if any(record.version == version for record in existing):
            raise VersioningValidationError(f"duplicate version rejected: {version}")
        latest = max(existing, key=lambda item: item.version, default=None)
        if latest is not None and version <= latest.version:
            raise VersioningValidationError("out-of-order version rejected")
        if latest is not None and latest.payload_hash == hash_value and not allow_unchanged:
            raise VersioningValidationError("unchanged payload rejected by default")


class InMemoryTemporalHistoryStore(TemporalHistoryStore):
    """Non-persistent effective-time history store."""

    def __init__(self) -> None:
        self._records: dict[PartitionKey, list[TemporalRecord]] = {}

    def append_record(self, record: TemporalRecord, *, allow_overlap: bool = False) -> TemporalRecord:
        key = _key(record.organization_id, record.tenant_id, record.subject_id)
        existing = self._records.get(key, [])
        if record.effective_to is None and any(item.effective_to is None for item in existing):
            raise VersioningValidationError("only one current open record may exist")
        if not allow_overlap and _overlaps_any(record, existing):
            raise VersioningValidationError("overlapping effective period rejected")
        self._records.setdefault(key, []).append(record)
        return record

    def close_current_record(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
        effective_to: datetime,
    ) -> TemporalRecord:
        key = _key(organization_id, tenant_id, subject_id)
        records = self._records.get(key, [])
        current = next((record for record in records if record.effective_to is None), None)
        if current is None:
            raise VersioningValidationError("current open record not found")
        if effective_to <= current.effective_from:
            raise VersioningValidationError("effective_to must be after effective_from")
        closed = TemporalRecord(
            record_id=current.record_id,
            subject_id=current.subject_id,
            subject_type=current.subject_type,
            organization_id=current.organization_id,
            tenant_id=current.tenant_id,
            version=current.version,
            effective_from=current.effective_from,
            effective_to=effective_to,
            recorded_at=current.recorded_at,
            payload=current.payload,
            payload_hash=current.payload_hash,
            lineage_ref=current.lineage_ref,
            provenance_ref=current.provenance_ref,
        )
        self._records[key] = [closed if record.record_id == current.record_id else record for record in records]
        return closed

    def get_current_record(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> TemporalRecord | None:
        records = self._records.get(_key(organization_id, tenant_id, subject_id), [])
        return next((record for record in records if record.effective_to is None), None)

    def get_record_at_time(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
        query_time: datetime,
    ) -> TemporalRecord | None:
        records = self._records.get(_key(organization_id, tenant_id, subject_id), [])
        matches = [record for record in records if _contains(record, query_time)]
        return sorted(matches, key=lambda item: item.effective_from)[-1] if matches else None

    def query_history(self, query: HistoryQuery) -> HistoryResult:
        records = self.list_history(query.subject_id, organization_id=query.organization_id, tenant_id=query.tenant_id)
        filtered = [record for record in records if _matches_query(record, query)]
        return HistoryResult(query=query, records=tuple(filtered))

    def list_history(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> list[TemporalRecord]:
        return sorted(self._records.get(_key(organization_id, tenant_id, subject_id), []), key=lambda item: (item.effective_from, item.version, item.record_id))

    def detect_overlapping_effective_periods(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> list[tuple[TemporalRecord, TemporalRecord]]:
        records = self.list_history(subject_id, organization_id=organization_id, tenant_id=tenant_id)
        overlaps: list[tuple[TemporalRecord, TemporalRecord]] = []
        for index, first in enumerate(records):
            for second in records[index + 1:]:
                if _overlap(first, second):
                    overlaps.append((first, second))
        return overlaps


def _payload_from_contract(subject: EnterpriseEntity | EnterpriseRelationship) -> Mapping[str, Any]:
    if is_dataclass(subject):
        payload = asdict(subject)
        payload.pop("version", None)
        return payload
    raise TypeError(f"Unsupported snapshot subject: {type(subject).__name__}")


def _resolve_effective_from(subject: Any, explicit: datetime | None) -> datetime:
    if explicit is not None:
        return explicit
    entity_version = getattr(subject, "entity_version", None)
    if entity_version is not None and entity_version.effective_from is not None:
        return entity_version.effective_from
    return datetime.now(timezone.utc)


def _resolve_effective_to(subject: Any, explicit: datetime | None) -> datetime | None:
    if explicit is not None:
        return explicit
    entity_version = getattr(subject, "entity_version", None)
    if entity_version is not None:
        return entity_version.effective_to
    return None


def _key(organization_id: str, tenant_id: str | None, subject_id: str) -> PartitionKey:
    return (organization_id, tenant_id, subject_id)


def _contains(record: TemporalRecord, query_time: datetime) -> bool:
    return record.effective_from <= query_time and (record.effective_to is None or query_time < record.effective_to)


def _matches_query(record: TemporalRecord, query: HistoryQuery) -> bool:
    if query.effective_from is not None and _end(record) <= query.effective_from:
        return False
    if query.effective_to is not None and record.effective_from >= query.effective_to:
        return False
    return True


def _overlaps_any(record: TemporalRecord, records: list[TemporalRecord]) -> bool:
    return any(_overlap(record, existing) for existing in records)


def _overlap(first: TemporalRecord, second: TemporalRecord) -> bool:
    return first.effective_from < _end(second) and second.effective_from < _end(first)


def _end(record: TemporalRecord) -> datetime:
    return record.effective_to or datetime.max.replace(tzinfo=timezone.utc)


