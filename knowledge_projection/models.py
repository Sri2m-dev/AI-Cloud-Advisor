"""Contracts for canonical change projection, checkpoints, and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship


class ChangeKind(str, Enum):
    ENTITY = "entity"
    RELATIONSHIP = "relationship"


class ChangeOperation(str, Enum):
    UPSERT = "upsert"
    REMOVE = "remove"


@dataclass(frozen=True, slots=True)
class CanonicalChange:
    """One ordered change emitted by canonical Data Fabric authority."""

    sequence: int
    organization_id: str
    tenant_id: str
    kind: ChangeKind
    operation: ChangeOperation
    subject_id: str
    payload: EnterpriseEntity | EnterpriseRelationship | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("sequence must be positive")
        if not self.organization_id or not self.tenant_id or not self.subject_id:
            raise ValueError("tenant scope and subject_id are required")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.operation is ChangeOperation.UPSERT and self.payload is None:
            raise ValueError("upsert requires canonical payload")
        if self.operation is ChangeOperation.REMOVE and self.payload is not None:
            raise ValueError("remove must not include payload")


@dataclass(frozen=True, slots=True)
class ProjectionCheckpoint:
    organization_id: str
    tenant_id: str
    sequence: int
    state_hash: str
    applied_changes: int


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    organization_id: str
    tenant_id: str
    canonical_hash: str
    projection_hash: str
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    divergent: tuple[str, ...]

    @property
    def reconciled(self) -> bool:
        return not (self.missing or self.unexpected or self.divergent)
