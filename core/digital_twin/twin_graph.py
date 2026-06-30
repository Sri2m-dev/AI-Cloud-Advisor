from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.digital_twin.twin_entity import TwinEntity
from core.entities.entity import EntityRelationship, utc_now_iso


@dataclass(frozen=True, slots=True)
class TwinGraphNode:
    id: UUID
    label: str
    entity_type: str
    layer: str
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        return payload


@dataclass(frozen=True, slots=True)
class TwinGraphEdge:
    source_id: UUID
    target_id: UUID
    relationship_type: str
    id: UUID = field(default_factory=uuid4)
    strength: str = "Medium"
    confidence_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_relationship(
        cls,
        relationship: EntityRelationship,
        source_twin_id: UUID,
        target_twin_id: UUID,
    ) -> "TwinGraphEdge":
        return cls(
            source_id=source_twin_id,
            target_id=target_twin_id,
            relationship_type=relationship.relationship_type,
            strength=relationship.strength,
            confidence_score=relationship.confidence_score,
            metadata=dict(relationship.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "source_id", "target_id"):
            payload[key] = str(payload[key])
        return payload


@dataclass(slots=True)
class TwinGraph:
    twin_id: UUID
    nodes: list[TwinGraphNode] = field(default_factory=list)
    edges: list[TwinGraphEdge] = field(default_factory=list)
    graph_version: str = "1.0.0"
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        twin_id: UUID,
        twin_entities: dict[UUID, TwinEntity],
        relationships: list[EntityRelationship],
    ) -> "TwinGraph":
        source_to_twin = {entity.source_entity_id: entity.id for entity in twin_entities.values()}
        nodes = [
            TwinGraphNode(
                id=entity.id,
                label=entity.display_name,
                entity_type=entity.entity_type,
                layer=entity.layer,
                status=entity.status,
                metadata={"source_entity_id": str(entity.source_entity_id)},
            )
            for entity in twin_entities.values()
        ]
        edges = []
        for relationship in relationships:
            source_twin_id = source_to_twin.get(relationship.source_entity_id)
            target_twin_id = source_to_twin.get(relationship.target_entity_id)
            if source_twin_id and target_twin_id:
                edges.append(TwinGraphEdge.from_relationship(relationship, source_twin_id, target_twin_id))
        return cls(
            twin_id=twin_id,
            nodes=nodes,
            edges=edges,
            metadata={"node_count": len(nodes), "edge_count": len(edges)},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "twin_id": str(self.twin_id),
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "graph_version": self.graph_version,
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }
