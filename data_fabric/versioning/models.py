"""Immutable versioning and temporal-history value models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID

from data_fabric.versioning.exceptions import VersioningValidationError


@dataclass(frozen=True, slots=True)
class VersionRecord:
    """Base immutable snapshot record for canonical object state."""

    snapshot_id: str
    subject_id: str
    subject_type: str
    organization_id: str
    tenant_id: str | None
    version: int
    recorded_at: datetime
    effective_from: datetime
    effective_to: datetime | None
    source_system: str | None
    source_identifier: str | None
    payload: Mapping[str, Any]
    payload_hash: str
    lineage_ref: str | None = None
    provenance_ref: str | None = None

    def __post_init__(self) -> None:
        _validate_common(self.version, self.effective_from, self.effective_to)
        object.__setattr__(self, "payload", freeze_value(self.payload))


@dataclass(frozen=True, slots=True)
class EntitySnapshot(VersionRecord):
    """Immutable version snapshot for a canonical entity."""

    entity_id: str = ""
    canonical_id: str | None = None


@dataclass(frozen=True, slots=True)
class RelationshipSnapshot(VersionRecord):
    """Immutable version snapshot for a canonical relationship."""

    relationship_id: str = ""


@dataclass(frozen=True, slots=True)
class TemporalRecord:
    """Immutable effective-time record for one canonical subject."""

    record_id: str
    subject_id: str
    subject_type: str
    organization_id: str
    tenant_id: str | None
    version: int
    effective_from: datetime
    effective_to: datetime | None
    recorded_at: datetime
    payload: Mapping[str, Any]
    payload_hash: str
    lineage_ref: str | None = None
    provenance_ref: str | None = None

    def __post_init__(self) -> None:
        _validate_common(self.version, self.effective_from, self.effective_to)
        object.__setattr__(self, "payload", freeze_value(self.payload))

    @property
    def is_current(self) -> bool:
        return self.effective_to is None


@dataclass(frozen=True, slots=True)
class VersionDifference:
    """One deterministic payload difference."""

    path: str
    change_type: str
    old_value: Any = None
    new_value: Any = None


@dataclass(frozen=True, slots=True)
class VersionComparison:
    """Stable comparison result for two version records."""

    first_id: str
    second_id: str
    differences: tuple[VersionDifference, ...]

    @property
    def has_differences(self) -> bool:
        return bool(self.differences)


@dataclass(frozen=True, slots=True)
class HistoryQuery:
    """Query for effective-time history inside one tenant partition."""

    subject_id: str
    organization_id: str
    tenant_id: str | None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class HistoryResult:
    """Temporal history query result."""

    query: HistoryQuery
    records: tuple[TemporalRecord, ...]


def freeze_value(value: Any) -> Any:
    """Recursively freeze values so snapshots cannot expose mutable state."""

    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): freeze_value(value[key]) for key in sorted(value, key=str)})
    if isinstance(value, tuple):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, list):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze_value(item) for item in value)
    return value


def to_canonical_value(value: Any) -> Any:
    """Convert values into deterministic JSON-safe content for hashing/comparison."""

    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {str(key): to_canonical_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, tuple | list):
        return [to_canonical_value(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted((to_canonical_value(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    return value


def payload_hash(payload: Mapping[str, Any]) -> str:
    """Return a deterministic content hash for canonical snapshot payload."""

    canonical = to_canonical_value(payload)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_common(version: int, effective_from: datetime, effective_to: datetime | None) -> None:
    if version < 1:
        raise VersioningValidationError("version must be greater than or equal to 1")
    if effective_from is None:
        raise VersioningValidationError("effective_from is required")
    if effective_to is not None and effective_to <= effective_from:
        raise VersioningValidationError("effective_to must be after effective_from")
