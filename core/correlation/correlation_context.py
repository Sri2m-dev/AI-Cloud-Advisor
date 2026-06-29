from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from core.correlation.correlation_event import CorrelationEvent
from core.correlation.correlation_result import CorrelationResult
from core.entities.entity import EnterpriseEntity, EntityRelationship


@dataclass(slots=True)
class CorrelationContext:
    entity: EnterpriseEntity
    events: list[CorrelationEvent] = field(default_factory=list)
    relationships: list[EntityRelationship] = field(default_factory=list)
    related_entities: list[EnterpriseEntity] = field(default_factory=list)
    results: list[CorrelationResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def entity_id(self) -> UUID:
        return self.entity.id

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "relationships": [relationship.to_dict() for relationship in self.relationships],
            "related_entities": [entity.to_dict() for entity in self.related_entities],
            "results": [result.to_dict() for result in self.results],
            "metadata": self.metadata,
        }
