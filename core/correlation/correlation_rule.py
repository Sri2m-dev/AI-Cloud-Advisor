from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class CorrelationPatternType(str, Enum):
    DEPLOYMENT_DRIVEN_COST_INCREASE = "Deployment Driven Cost Increase"
    SAAS_OPTIMIZATION_OPPORTUNITY = "SaaS Optimization Opportunity"
    BUSINESS_IMPACT_RISK = "Business Impact Risk"
    SECURITY_CONTROL_GAP = "Security Control Gap"
    CHANGE_RELATED_INCIDENT = "Change Related Incident"


@dataclass(frozen=True, slots=True)
class CorrelationRuleCondition:
    event_type: str
    source_system: str = ""
    metadata_key: str = ""
    metadata_value: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CorrelationRule:
    name: str
    pattern_type: str
    event_types: list[str]
    description: str
    id: UUID = field(default_factory=uuid4)
    minimum_events: int = 2
    lookback_hours: int = 72
    confidence_weight: float = 1.0
    conditions: list[CorrelationRuleCondition] = field(default_factory=list)
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["conditions"] = [condition.to_dict() for condition in self.conditions]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CorrelationRule":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["conditions"] = [
            CorrelationRuleCondition(**condition)
            for condition in data.get("conditions", [])
        ]
        return cls(**data)
