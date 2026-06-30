from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class AISignalType(str, Enum):
    RECOMMENDATION = "Recommendation"
    PREDICTION = "Prediction"
    ROOT_CAUSE = "Root Cause"
    OPTIMIZATION = "Optimization"
    FORECAST = "Forecast"
    BUSINESS_IMPACT = "Business Impact"
    AUTOMATION = "Automation"


class AIInsightType(str, Enum):
    COST = "Cost"
    HEALTH = "Health"
    RISK = "Risk"
    OPERATIONS = "Operations"
    SECURITY = "Security"
    RELIABILITY = "Reliability"
    BUSINESS = "Business"


class AIInsightStatus(str, Enum):
    NEW = "New"
    REVIEWING = "Reviewing"
    APPROVED = "Approved"
    AUTOMATION_READY = "Automation Ready"
    AUTOMATED = "Automated"
    DISMISSED = "Dismissed"


@dataclass(frozen=True, slots=True)
class AISignal:
    technology_id: UUID
    signal_type: str
    insight_type: str
    title: str
    description: str
    recommendation: str = ""
    predicted_impact: float = 0.0
    business_impact: str = ""
    confidence_score: float = 1.0
    model_name: str = ""
    source_context: dict[str, Any] = field(default_factory=dict)
    status: str = AIInsightStatus.NEW.value
    owner: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    id: UUID = field(default_factory=uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        technology_id: UUID | str,
        signal_type: str,
        insight_type: str,
        title: str,
        description: str,
        recommendation: str = "",
        predicted_impact: float = 0.0,
        business_impact: str = "",
        confidence_score: float = 1.0,
        model_name: str = "",
        source_context: dict[str, Any] | None = None,
        status: str = AIInsightStatus.NEW.value,
        owner: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "AISignal":
        return cls(
            technology_id=UUID(str(technology_id)),
            signal_type=signal_type,
            insight_type=insight_type,
            title=title,
            description=description,
            recommendation=recommendation,
            predicted_impact=round(float(predicted_impact), 2),
            business_impact=business_impact,
            confidence_score=max(0.0, min(1.0, float(confidence_score))),
            model_name=model_name,
            source_context=source_context or {},
            status=status,
            owner=owner,
            metadata=metadata or {},
        )

    def automation_score(self) -> float:
        readiness = float(self.metadata.get("automation_readiness", 0.0) or 0.0)
        return round(max(0.0, min(100.0, readiness)) * self.confidence_score, 2)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["technology_id"] = str(self.technology_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AISignal":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["technology_id"] = UUID(str(data["technology_id"]))
        return cls(**data)
