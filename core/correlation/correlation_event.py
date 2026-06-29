from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class CorrelationEventType(str, Enum):
    COST_SPIKE = "Cost Spike"
    INCIDENT = "Incident"
    ALERT = "Alert"
    CHANGE = "Change"
    DEPLOYMENT = "Deployment"
    APPROVAL = "Approval"
    RECOMMENDATION = "Recommendation"
    RISK = "Risk"
    COMPLIANCE_FINDING = "Compliance Finding"
    LICENSE_WASTE = "License Waste"
    RENEWAL_RISK = "Renewal Risk"
    PERFORMANCE_DEGRADATION = "Performance Degradation"
    SECURITY_FINDING = "Security Finding"


class CorrelationSeverity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


@dataclass(slots=True)
class CorrelationEvent:
    event_type: str
    title: str
    source_system: str
    organization_id: UUID
    description: str = ""
    occurred_at: str = field(default_factory=utc_now_iso)
    id: UUID = field(default_factory=uuid4)
    severity: str = CorrelationSeverity.MEDIUM.value
    entity_ids: list[UUID] = field(default_factory=list)
    external_id: str = ""
    confidence_score: float = 100.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def link_entity(self, entity_id: UUID | str) -> None:
        resolved_id = UUID(str(entity_id))
        if resolved_id not in self.entity_ids:
            self.entity_ids.append(resolved_id)
            self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["organization_id"] = str(self.organization_id)
        payload["entity_ids"] = [str(entity_id) for entity_id in self.entity_ids]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CorrelationEvent":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["organization_id"] = UUID(str(data["organization_id"]))
        data["entity_ids"] = [UUID(str(entity_id)) for entity_id in data.get("entity_ids", [])]
        return cls(**data)
