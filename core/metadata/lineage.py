from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


@dataclass(slots=True)
class LineageEdge:
    source_entity_id: UUID
    target_entity_id: UUID
    transformation: str
    organization_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    source_system: str = "metadata_catalog"
    confidence_score: float = 100.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "source_entity_id", "target_entity_id", "organization_id"):
            payload[key] = str(payload[key]) if payload.get(key) else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LineageEdge":
        data = dict(payload)
        for key in ("id", "source_entity_id", "target_entity_id", "organization_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        return cls(**data)
