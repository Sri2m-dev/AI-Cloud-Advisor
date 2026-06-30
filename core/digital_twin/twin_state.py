from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class TwinStateStatus(str, Enum):
    CURRENT = "Current"
    STALE = "Stale"
    DEGRADED = "Degraded"
    BUILDING = "Building"


class TwinLifecycle(str, Enum):
    DRAFT = "Draft"
    INITIALIZING = "Initializing"
    SYNCHRONIZING = "Synchronizing"
    HEALTHY = "Healthy"
    WARNING = "Warning"
    DEGRADED = "Degraded"
    ARCHIVED = "Archived"


class TwinRefreshStatus(str, Enum):
    NEVER_RUN = "Never Run"
    RUNNING = "Running"
    SUCCESS = "Success"
    WARNING = "Warning"
    FAILED = "Failed"


@dataclass(slots=True)
class TwinState:
    twin_id: UUID
    status: str = TwinStateStatus.BUILDING.value
    id: UUID = field(default_factory=uuid4)
    state_version: str = "1.0.0"
    lifecycle: str = TwinLifecycle.INITIALIZING.value
    entity_count: int = 0
    relationship_count: int = 0
    snapshot_count: int = 0
    health_score: float = 100.0
    freshness_score: float = 100.0
    graph_version: str = "1.0.0"
    refresh_source: str = "manual"
    refresh_status: str = TwinRefreshStatus.NEVER_RUN.value
    health_components: dict[str, float] = field(default_factory=dict)
    last_refreshed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=utc_now_iso)

    def mark_refreshed(
        self,
        entity_count: int,
        relationship_count: int,
        health_score: float = 100.0,
        freshness_score: float = 100.0,
        refresh_source: str = "manual",
        health_components: dict[str, float] | None = None,
    ) -> None:
        self.entity_count = entity_count
        self.relationship_count = relationship_count
        self.health_score = round(max(0.0, min(100.0, health_score)), 2)
        self.freshness_score = round(max(0.0, min(100.0, freshness_score)), 2)
        self.refresh_source = refresh_source
        self.refresh_status = TwinRefreshStatus.SUCCESS.value
        self.health_components = health_components or {}
        self.status = TwinStateStatus.CURRENT.value if self.health_score >= 80 else TwinStateStatus.DEGRADED.value
        if self.health_score >= 90:
            self.lifecycle = TwinLifecycle.HEALTHY.value
        elif self.health_score >= 70:
            self.lifecycle = TwinLifecycle.WARNING.value
        else:
            self.lifecycle = TwinLifecycle.DEGRADED.value
        self.last_refreshed_at = utc_now_iso()
        self.updated_at = self.last_refreshed_at

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["twin_id"] = str(self.twin_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TwinState":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["twin_id"] = UUID(str(data["twin_id"]))
        return cls(**data)
