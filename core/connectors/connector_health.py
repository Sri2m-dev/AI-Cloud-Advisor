from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class ConnectorHealthStatus(str, Enum):
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    UNHEALTHY = "Unhealthy"
    UNKNOWN = "Unknown"


@dataclass(slots=True)
class ConnectorHealth:
    connector_id: UUID
    status: str = ConnectorHealthStatus.UNKNOWN.value
    id: UUID = field(default_factory=uuid4)
    score: float = 0.0
    message: str = ""
    last_success_at: str | None = None
    last_error_at: str | None = None
    error_count: int = 0
    latency_ms: int = 0
    checked_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["connector_id"] = str(self.connector_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorHealth":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["connector_id"] = UUID(str(data["connector_id"]))
        return cls(**data)
