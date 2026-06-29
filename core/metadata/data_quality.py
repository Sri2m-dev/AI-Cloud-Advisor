from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso
from core.metadata.metadata_record import FreshnessStatus


@dataclass(slots=True)
class DataQualityAssessment:
    entity_id: UUID
    completeness_score: float
    freshness_score: float
    confidence_score: float
    lineage_depth: int
    source_coverage: float
    owner_coverage: float
    relationship_coverage: float
    staleness_days: int
    organization_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    freshness_status: str = FreshnessStatus.CURRENT.value
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    assessed_at: str = field(default_factory=utc_now_iso)

    @property
    def overall_score(self) -> float:
        weights = {
            "completeness": 0.25,
            "freshness": 0.20,
            "confidence": 0.20,
            "source": 0.15,
            "owner": 0.10,
            "relationship": 0.10,
        }
        score = (
            self.completeness_score * weights["completeness"]
            + self.freshness_score * weights["freshness"]
            + self.confidence_score * weights["confidence"]
            + self.source_coverage * weights["source"]
            + self.owner_coverage * weights["owner"]
            + self.relationship_coverage * weights["relationship"]
        )
        return round(max(0.0, min(100.0, score)), 2)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "entity_id", "organization_id"):
            payload[key] = str(payload[key]) if payload.get(key) else None
        payload["overall_score"] = self.overall_score
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DataQualityAssessment":
        data = dict(payload)
        data.pop("overall_score", None)
        for key in ("id", "entity_id", "organization_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        return cls(**data)
