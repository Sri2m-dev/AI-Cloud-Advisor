from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


@dataclass(slots=True)
class TechnologyHealth:
    technology_id: UUID
    id: UUID = field(default_factory=uuid4)
    availability: float = 100.0
    performance: float = 100.0
    capacity: float = 100.0
    utilization: float = 100.0
    reliability: float = 100.0
    operational_score: float = 100.0
    health_score: float = 100.0
    assessed_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_metadata(cls, technology_id: UUID, metadata: dict[str, Any]) -> "TechnologyHealth":
        health = cls(
            technology_id=technology_id,
            availability=_bounded_number(metadata, "availability", "availability_score", default=100.0),
            performance=_bounded_number(metadata, "performance", "performance_score", default=100.0),
            capacity=_bounded_number(metadata, "capacity", "capacity_score", default=100.0),
            utilization=_bounded_number(metadata, "utilization", "utilization_score", default=100.0),
            reliability=_bounded_number(metadata, "reliability", "reliability_score", default=100.0),
            operational_score=_bounded_number(metadata, "operational_score", "operations_health", default=100.0),
            metadata={key: value for key, value in metadata.items() if "health" in key or "score" in key},
        )
        health.recalculate()
        return health

    def recalculate(self) -> float:
        components = [
            self.availability,
            self.performance,
            self.capacity,
            self.utilization,
            self.reliability,
            self.operational_score,
        ]
        self.health_score = round(sum(components) / len(components), 2)
        self.assessed_at = utc_now_iso()
        return self.health_score

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["technology_id"] = str(self.technology_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TechnologyHealth":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["technology_id"] = UUID(str(data["technology_id"]))
        return cls(**data)


def _bounded_number(metadata: dict[str, Any], *keys: str, default: float) -> float:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return round(max(0.0, min(100.0, float(value))), 2)
        except (TypeError, ValueError):
            continue
    return default
