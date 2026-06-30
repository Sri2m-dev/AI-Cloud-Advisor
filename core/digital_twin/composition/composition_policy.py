from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CompositionPolicy:
    include_metadata: bool = True
    include_relationships: bool = True
    include_health: bool = True
    include_cost: bool = True
    include_risk: bool = True
    include_operations: bool = True
    max_depth: int = 4
    relationship_types: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "include_metadata": self.include_metadata,
            "include_relationships": self.include_relationships,
            "include_health": self.include_health,
            "include_cost": self.include_cost,
            "include_risk": self.include_risk,
            "include_operations": self.include_operations,
            "max_depth": self.max_depth,
            "relationship_types": sorted(self.relationship_types),
        }
