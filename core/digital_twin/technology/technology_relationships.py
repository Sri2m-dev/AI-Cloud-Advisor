from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import EntityRelationship


@dataclass(frozen=True, slots=True)
class TechnologyRelationship:
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    id: UUID = field(default_factory=uuid4)
    strength: str = "Medium"
    confidence_score: float = 1.0
    source_system: str = "manual"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_relationship(cls, relationship: EntityRelationship) -> "TechnologyRelationship":
        return cls(
            id=relationship.id,
            source_entity_id=relationship.source_entity_id,
            target_entity_id=relationship.target_entity_id,
            relationship_type=relationship.relationship_type,
            strength=relationship.strength,
            confidence_score=relationship.confidence_score,
            source_system=relationship.source_system,
            metadata=dict(relationship.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "source_entity_id", "target_entity_id"):
            payload[key] = str(payload[key])
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TechnologyRelationship":
        data = dict(payload)
        for key in ("id", "source_entity_id", "target_entity_id"):
            data[key] = UUID(str(data[key]))
        return cls(**data)
