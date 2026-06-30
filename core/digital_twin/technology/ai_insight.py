from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


@dataclass(frozen=True, slots=True)
class AIInsight:
    technology_id: UUID
    insight_type: str
    title: str
    description: str
    recommendation: str = ""
    confidence_score: float = 1.0
    predicted_impact: float = 0.0
    business_impact: str = ""
    automation_readiness: float = 0.0
    source_signal_ids: list[UUID] = field(default_factory=list)
    status: str = "New"
    owner: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "technology_id": str(self.technology_id),
            "insight_type": self.insight_type,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
            "confidence_score": self.confidence_score,
            "predicted_impact": self.predicted_impact,
            "business_impact": self.business_impact,
            "automation_readiness": self.automation_readiness,
            "source_signal_ids": [str(value) for value in self.source_signal_ids],
            "status": self.status,
            "owner": self.owner,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
