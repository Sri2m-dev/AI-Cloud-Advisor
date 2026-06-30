from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


@dataclass(frozen=True, slots=True)
class CompositionResult:
    organization_id: UUID
    twin_type: str
    id: UUID = field(default_factory=uuid4)
    root_entity_id: UUID | None = None
    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    aggregates: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "root_entity_id": str(self.root_entity_id) if self.root_entity_id else None,
            "twin_type": self.twin_type,
            "entities": self.entities,
            "relationships": self.relationships,
            "aggregates": self.aggregates,
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }
