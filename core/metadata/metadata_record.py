from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class FreshnessStatus(str, Enum):
    CURRENT = "Current"
    WARNING = "Warning"
    STALE = "Stale"
    UNKNOWN = "Unknown"


@dataclass(slots=True)
class MetadataRecord:
    entity_id: UUID
    source_system: str
    sync_time: str
    organization_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    steward_id: UUID | None = None
    owner_id: UUID | None = None
    confidence_score: float = 100.0
    completeness_score: float = 100.0
    freshness_score: float = 100.0
    source_coverage: float = 0.0
    owner_coverage: float = 0.0
    relationship_coverage: float = 0.0
    lineage_depth: int = 0
    staleness_days: int = 0
    freshness_status: str = FreshnessStatus.CURRENT.value
    provenance_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "entity_id", "organization_id", "steward_id", "owner_id", "provenance_id"):
            payload[key] = str(payload[key]) if payload.get(key) else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MetadataRecord":
        data = dict(payload)
        for key in ("id", "entity_id", "organization_id", "steward_id", "owner_id", "provenance_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        return cls(**data)
