from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class ConnectorHealthGrade(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    WATCH = "Watch"
    POOR = "Poor"
    UNKNOWN = "Unknown"


@dataclass(slots=True)
class ConnectorHealthPolicy:
    name: str = "Default Connector Health Policy"
    id: UUID = field(default_factory=uuid4)
    healthy_score: float = 90.0
    degraded_score: float = 70.0
    max_error_count: int = 3
    max_latency_ms: int = 5000
    stale_after_hours: int = 24
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def grade_for(self, score: float, error_count: int = 0, latency_ms: int = 0) -> str:
        if score <= 0:
            return ConnectorHealthGrade.UNKNOWN.value
        if error_count > self.max_error_count or latency_ms > self.max_latency_ms:
            return ConnectorHealthGrade.POOR.value
        if score >= self.healthy_score:
            return ConnectorHealthGrade.EXCELLENT.value
        if score >= self.degraded_score:
            return ConnectorHealthGrade.GOOD.value
        return ConnectorHealthGrade.WATCH.value

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorHealthPolicy":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        return cls(**data)


@dataclass(slots=True)
class ConnectorHealthAssessment:
    connector_id: UUID
    grade: str
    score: float
    id: UUID = field(default_factory=uuid4)
    policy_name: str = "Default Connector Health Policy"
    findings: list[str] = field(default_factory=list)
    assessed_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["connector_id"] = str(self.connector_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorHealthAssessment":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["connector_id"] = UUID(str(data["connector_id"]))
        return cls(**data)
