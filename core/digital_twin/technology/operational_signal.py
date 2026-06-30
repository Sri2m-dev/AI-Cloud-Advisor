from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class OperationalSignalType(str, Enum):
    ALERT = "Alert"
    INCIDENT = "Incident"
    DEPLOYMENT = "Deployment"
    CHANGE = "Change"
    MAINTENANCE = "Maintenance Window"
    PERFORMANCE_DEGRADATION = "Performance Degradation"
    AVAILABILITY = "Availability Trend"
    RECOVERY = "Recovery"


class OperationalSeverity(str, Enum):
    INFO = "Info"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class OperationalStatus(str, Enum):
    OPEN = "Open"
    ACTIVE = "Active"
    IN_PROGRESS = "In Progress"
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


@dataclass(frozen=True, slots=True)
class OperationalSignal:
    technology_id: UUID
    signal_type: str
    source_system: str
    severity: str
    status: str
    event_time: str = field(default_factory=utc_now_iso)
    duration: float = 0.0
    affected_component: str = ""
    owner: str = ""
    confidence_score: float = 1.0
    id: UUID = field(default_factory=uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        technology_id: UUID | str,
        signal_type: str,
        source_system: str,
        severity: str = OperationalSeverity.INFO.value,
        status: str = OperationalStatus.OPEN.value,
        event_time: str | None = None,
        duration: float = 0.0,
        affected_component: str = "",
        owner: str = "",
        confidence_score: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> "OperationalSignal":
        return cls(
            technology_id=UUID(str(technology_id)),
            signal_type=signal_type,
            source_system=source_system,
            severity=severity,
            status=status,
            event_time=event_time or utc_now_iso(),
            duration=max(0.0, float(duration)),
            affected_component=affected_component,
            owner=owner,
            confidence_score=max(0.0, min(1.0, float(confidence_score))),
            metadata=metadata or {},
        )

    def is_active(self) -> bool:
        return self.status in {
            OperationalStatus.OPEN.value,
            OperationalStatus.ACTIVE.value,
            OperationalStatus.IN_PROGRESS.value,
            OperationalStatus.SCHEDULED.value,
        }

    def impact_weight(self) -> float:
        multiplier = {
            OperationalSeverity.CRITICAL.value: 2.0,
            OperationalSeverity.HIGH.value: 1.5,
            OperationalSeverity.MEDIUM.value: 1.0,
            OperationalSeverity.LOW.value: 0.5,
            OperationalSeverity.INFO.value: 0.25,
        }.get(self.severity, 1.0)
        return round(multiplier * self.confidence_score, 4)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["technology_id"] = str(self.technology_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperationalSignal":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["technology_id"] = UUID(str(data["technology_id"]))
        return cls(**data)
