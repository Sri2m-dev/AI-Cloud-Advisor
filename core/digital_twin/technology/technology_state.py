from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class TechnologyTwinStatus(str, Enum):
    ACTIVE = "Active"
    WARNING = "Warning"
    DEGRADED = "Degraded"
    STALE = "Stale"
    UNKNOWN = "Unknown"


@dataclass(slots=True)
class TechnologyState:
    technology_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: str = TechnologyTwinStatus.UNKNOWN.value
    health_score: float = 100.0
    risk_score: float = 0.0
    cost_score: float = 0.0
    security_score: float = 100.0
    operations_score: float = 100.0
    business_impact_score: float = 0.0
    last_refreshed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=utc_now_iso)

    def refresh(
        self,
        *,
        health_score: float,
        risk_score: float,
        cost_score: float,
        security_score: float = 100.0,
        operations_score: float = 100.0,
        business_impact_score: float = 0.0,
    ) -> None:
        self.health_score = _bounded(health_score)
        self.risk_score = _bounded(risk_score)
        self.cost_score = _bounded(cost_score)
        self.security_score = _bounded(security_score)
        self.operations_score = _bounded(operations_score)
        self.business_impact_score = _bounded(business_impact_score)
        self.status = self._derive_status()
        self.last_refreshed_at = utc_now_iso()
        self.updated_at = self.last_refreshed_at

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["technology_id"] = str(self.technology_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TechnologyState":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["technology_id"] = UUID(str(data["technology_id"]))
        return cls(**data)

    def _derive_status(self) -> str:
        if self.health_score < 70 or self.security_score < 70 or self.risk_score >= 75:
            return TechnologyTwinStatus.DEGRADED.value
        if self.health_score < 85 or self.security_score < 85 or self.risk_score >= 50:
            return TechnologyTwinStatus.WARNING.value
        return TechnologyTwinStatus.ACTIVE.value


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)
