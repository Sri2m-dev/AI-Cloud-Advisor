"""Persistence value models for Data Fabric repository boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext, normalize_to_utc
from data_fabric.persistence.exceptions import PersistenceValidationError


class SoftDeleteState(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class ConcurrencyToken:
    """Optimistic concurrency token carried by mutable records."""

    revision: int

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise PersistenceValidationError("revision must be greater than or equal to 1")

    def next(self) -> "ConcurrencyToken":
        return ConcurrencyToken(self.revision + 1)


@dataclass(frozen=True, slots=True)
class PersistenceRecord:
    """Base tenant-scoped persistence record."""

    record_id: str
    organization_id: str
    tenant_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    updated_by: str | None = None
    schema_version: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id:
            raise PersistenceValidationError("record_id is required")
        if not self.organization_id:
            raise PersistenceValidationError("organization_id is required")
        if not self.tenant_id:
            raise PersistenceValidationError("tenant_id is required")
        object.__setattr__(self, "created_at", normalize_to_utc(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", normalize_to_utc(self.updated_at, "updated_at"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))

    @property
    def tenant_context(self) -> TenantContext:
        return TenantContext(self.organization_id, self.tenant_id)


@dataclass(frozen=True, slots=True)
class MutableRecord(PersistenceRecord):
    """Mutable current-state record with soft delete and concurrency state."""

    revision: int = 1
    concurrency_token: ConcurrencyToken | None = None
    active: bool = True
    deactivated_at: datetime | None = None
    deactivated_by: str | None = None

    def __post_init__(self) -> None:
        PersistenceRecord.__post_init__(self)
        if self.revision < 1:
            raise PersistenceValidationError("revision must be greater than or equal to 1")
        token = self.concurrency_token or ConcurrencyToken(self.revision)
        if token.revision != self.revision:
            raise PersistenceValidationError("concurrency token must match revision")
        object.__setattr__(self, "concurrency_token", token)
        if self.deactivated_at is not None:
            object.__setattr__(self, "deactivated_at", normalize_to_utc(self.deactivated_at, "deactivated_at"))

    def advance_revision(self) -> "MutableRecord":
        return replace(
            self,
            revision=self.revision + 1,
            concurrency_token=ConcurrencyToken(self.revision + 1),
            updated_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True, slots=True)
class ImmutableRecord(PersistenceRecord):
    """Immutable record that can be inserted but not updated."""

    payload_hash: str = ""

    def __post_init__(self) -> None:
        PersistenceRecord.__post_init__(self)
        computed = self.payload_hash or DefaultDeterministicSerializer().content_hash(self.payload)
        object.__setattr__(self, "payload_hash", computed)


@dataclass(frozen=True, slots=True)
class AppendOnlyRecord(ImmutableRecord):
    """Append-only record for lineage, provenance, quality, and audit events."""

    sequence: int | None = None


@dataclass(frozen=True, slots=True)
class SortSpecification:
    field: str = "record_id"
    descending: bool = False


@dataclass(frozen=True, slots=True)
class PageRequest:
    offset: int = 0
    limit: int = 100

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise PersistenceValidationError("offset cannot be negative")
        if self.limit < 1:
            raise PersistenceValidationError("limit must be greater than zero")


@dataclass(frozen=True, slots=True)
class RepositoryQuery:
    tenant_context: TenantContext
    filters: Mapping[str, Any] = field(default_factory=dict)
    metadata_filters: Mapping[str, Any] = field(default_factory=dict)
    sort: SortSpecification = field(default_factory=SortSpecification)
    page: PageRequest = field(default_factory=PageRequest)
    include_inactive: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "filters", _freeze_mapping(self.filters))
        object.__setattr__(self, "metadata_filters", _freeze_mapping(self.metadata_filters))


@dataclass(frozen=True, slots=True)
class PageResult:
    items: tuple[PersistenceRecord, ...]
    total_count: int
    page: PageRequest

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class PersistenceOperationResult:
    success: bool
    record_id: str | None = None
    message: str = ""
    record: PersistenceRecord | None = None


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze(value[key]) for key in sorted(value, key=str)})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value
