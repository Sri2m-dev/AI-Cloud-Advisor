from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


@dataclass(slots=True)
class CorrelationResult:
    pattern_type: str
    summary: str
    organization_id: UUID
    entity_ids: list[UUID]
    event_ids: list[UUID]
    id: UUID = field(default_factory=uuid4)
    confidence_score: float = 0.0
    severity: str = "Medium"
    evidence: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["organization_id"] = str(self.organization_id)
        payload["entity_ids"] = [str(entity_id) for entity_id in self.entity_ids]
        payload["event_ids"] = [str(event_id) for event_id in self.event_ids]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CorrelationResult":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["organization_id"] = UUID(str(data["organization_id"]))
        data["entity_ids"] = [UUID(str(entity_id)) for entity_id in data.get("entity_ids", [])]
        data["event_ids"] = [UUID(str(event_id)) for event_id in data.get("event_ids", [])]
        return cls(**data)
