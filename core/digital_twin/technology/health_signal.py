from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class HealthSignalType(str, Enum):
    AVAILABILITY = "Availability"
    PERFORMANCE = "Performance"
    CAPACITY = "Capacity"
    UTILIZATION = "Utilization"
    RELIABILITY = "Reliability"
    SECURITY = "Security"
    OPERATIONAL_STABILITY = "Operational Stability"
    COST_EFFICIENCY = "Cost Efficiency"
    INCIDENTS = "Incidents"
    RISK = "Risk"
    INFRASTRUCTURE = "Infrastructure"


class HealthSignalStatus(str, Enum):
    HEALTHY = "Healthy"
    WARNING = "Warning"
    DEGRADED = "Degraded"
    UNKNOWN = "Unknown"


@dataclass(frozen=True, slots=True)
class HealthSignal:
    technology_id: UUID
    signal_type: str
    value: float
    weight: float = 1.0
    status: str = HealthSignalStatus.UNKNOWN.value
    source_system: str = "manual"
    last_observed: str = field(default_factory=utc_now_iso)
    confidence_score: float = 1.0
    id: UUID = field(default_factory=uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        technology_id: UUID | str,
        signal_type: str,
        value: float,
        weight: float = 1.0,
        source_system: str = "manual",
        confidence_score: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> "HealthSignal":
        bounded_value = _bounded(value)
        return cls(
            technology_id=UUID(str(technology_id)),
            signal_type=signal_type,
            value=bounded_value,
            weight=max(0.0, float(weight)),
            status=status_for_score(bounded_value),
            source_system=source_system,
            confidence_score=max(0.0, min(1.0, float(confidence_score))),
            metadata=metadata or {},
        )

    def weighted_score(self) -> float:
        return self.value * self.weight * self.confidence_score

    def effective_weight(self) -> float:
        return self.weight * self.confidence_score

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["technology_id"] = str(self.technology_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HealthSignal":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["technology_id"] = UUID(str(data["technology_id"]))
        return cls(**data)


def status_for_score(score: float) -> str:
    value = _bounded(score)
    if value < 70:
        return HealthSignalStatus.DEGRADED.value
    if value < 85:
        return HealthSignalStatus.WARNING.value
    return HealthSignalStatus.HEALTHY.value


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)
