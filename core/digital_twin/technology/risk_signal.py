from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class RiskSignalType(str, Enum):
    SECURITY = "Security Risk"
    COMPLIANCE = "Compliance Risk"
    OPERATIONAL = "Operational Risk"
    FINANCIAL = "Financial Risk"
    BUSINESS_IMPACT = "Business Impact Risk"
    TECHNICAL_DEBT = "Technical Debt"
    DR_READINESS = "DR Readiness"
    PATCH = "Patch Risk"
    VENDOR = "Vendor Risk"


class RiskSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class RiskStatus(str, Enum):
    OPEN = "Open"
    MITIGATING = "Mitigating"
    ACCEPTED = "Accepted"
    RESOLVED = "Resolved"


@dataclass(frozen=True, slots=True)
class RiskSignal:
    technology_id: UUID
    risk_type: str
    severity: str
    probability: float
    impact: float
    score: float
    source_system: str = "manual"
    affected_entity: str = ""
    mitigation: str = ""
    owner: str = ""
    status: str = RiskStatus.OPEN.value
    last_observed: str = field(default_factory=utc_now_iso)
    confidence_score: float = 1.0
    id: UUID = field(default_factory=uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        technology_id: UUID | str,
        risk_type: str,
        severity: str,
        probability: float,
        impact: float,
        source_system: str = "manual",
        affected_entity: str = "",
        mitigation: str = "",
        owner: str = "",
        status: str = RiskStatus.OPEN.value,
        confidence_score: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> "RiskSignal":
        bounded_probability = _bounded(probability)
        bounded_impact = _bounded(impact)
        confidence = max(0.0, min(1.0, float(confidence_score)))
        score = round((bounded_probability * bounded_impact / 100.0) * confidence, 2)
        severity_value = severity or severity_for_score(score)
        return cls(
            technology_id=UUID(str(technology_id)),
            risk_type=risk_type,
            severity=severity_value,
            probability=bounded_probability,
            impact=bounded_impact,
            score=score,
            source_system=source_system,
            affected_entity=affected_entity,
            mitigation=mitigation,
            owner=owner,
            status=status,
            confidence_score=confidence,
            metadata=metadata or {},
        )

    def weighted_score(self, weight: float) -> float:
        if self.status == RiskStatus.RESOLVED.value:
            return 0.0
        if self.status == RiskStatus.ACCEPTED.value:
            return self.score * weight * 0.5
        return self.score * weight

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["technology_id"] = str(self.technology_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RiskSignal":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["technology_id"] = UUID(str(data["technology_id"]))
        return cls(**data)


def severity_for_score(score: float) -> str:
    value = _bounded(score)
    if value >= 75:
        return RiskSeverity.CRITICAL.value
    if value >= 50:
        return RiskSeverity.HIGH.value
    if value >= 25:
        return RiskSeverity.MEDIUM.value
    return RiskSeverity.LOW.value


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)
