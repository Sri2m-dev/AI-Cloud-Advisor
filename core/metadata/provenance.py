from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


@dataclass(slots=True)
class ProvenanceRecord:
    entity_id: UUID
    source_system: str
    operation: str
    organization_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    source_record_id: str = ""
    source_uri: str = ""
    actor_id: UUID | None = None
    captured_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "entity_id", "organization_id", "actor_id"):
            payload[key] = str(payload[key]) if payload.get(key) else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProvenanceRecord":
        data = dict(payload)
        for key in ("id", "entity_id", "organization_id", "actor_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        return cls(**data)
