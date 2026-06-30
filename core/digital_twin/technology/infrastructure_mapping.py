from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


@dataclass(frozen=True, slots=True)
class InfrastructureMapping:
    technology_id: UUID
    resource_id: UUID
    relationship_type: str = "RUNS_ON"
    id: UUID = field(default_factory=uuid4)
    confidence_score: float = 1.0
    source_system: str = "technology_twin"
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "technology_id", "resource_id"):
            payload[key] = str(payload[key])
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InfrastructureMapping":
        data = dict(payload)
        for key in ("id", "technology_id", "resource_id"):
            data[key] = UUID(str(data[key]))
        return cls(**data)
