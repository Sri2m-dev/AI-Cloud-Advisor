"""Evidence-governed traversal over canonical P3 entities and relationships."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.foundation import TenantContext


class RelationshipDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class RelationshipPath:
    entities: tuple[EnterpriseEntity, ...]
    relationships: tuple[EnterpriseRelationship, ...]

    @property
    def hops(self) -> int:
        return len(self.relationships)


@dataclass(frozen=True, slots=True)
class ImpactSummary:
    root: EnterpriseEntity
    impacted: tuple[EnterpriseEntity, ...]
    paths: tuple[RelationshipPath, ...]
    narrative: str


class RelationshipIntelligenceService:
    def __init__(self, context: TenantContext, *, role: str, entities, relationships) -> None:
        if role not in {
            "super_admin",
            "client_admin",
            "executive",
            "cio",
            "finance",
            "operations",
            "auditor",
        }:
            raise PermissionError("relationship intelligence read denied")
        self.context = context
        self.role = role
        self._entities = {entity.id: entity for entity in entities}
        self._canonical = {entity.canonical_id: entity for entity in entities}
        self._relationships = tuple(relationships)
        for entity in self._entities.values():
            context.assert_record_matches(entity, "relationship entity")
        for relationship in self._relationships:
            context.assert_record_matches(relationship, "relationship")
            if not relationship.evidence:
                raise ValueError(f"relationship evidence is required: {relationship.id}")

    def search(self, query: str = "", limit: int = 100):
        wanted = str(query).strip().casefold()
        rows = sorted(self._entities.values(), key=lambda row: row.canonical_id)
        return tuple(
            row
            for row in rows
            if not wanted
            or any(
                wanted in str(value or "").casefold()
                for value in (
                    row.canonical_id,
                    row.canonical_name,
                    row.display_name,
                    row.source_identifier,
                )
            )
        )[:limit]

    def get_relationships(
        self,
        canonical_id: str,
        *,
        direction: RelationshipDirection | str = RelationshipDirection.BOTH,
        relationship_type: str | None = None,
    ):
        entity = self._canonical[canonical_id]
        direction = RelationshipDirection(direction)
        return tuple(
            relationship
            for relationship in self._relationships
            if (
                relationship_type is None
                or relationship.relationship_type.value == relationship_type
            )
            and (
                direction in {RelationshipDirection.OUTBOUND, RelationshipDirection.BOTH}
                and relationship.source_entity_id == entity.id
                or direction in {RelationshipDirection.INBOUND, RelationshipDirection.BOTH}
                and relationship.target_entity_id == entity.id
            )
        )

    def traverse(
        self,
        canonical_id: str,
        *,
        max_hops: int | None = 3,
        direction: RelationshipDirection | str = RelationshipDirection.BOTH,
        relationship_types: set[str] | None = None,
    ) -> tuple[RelationshipPath, ...]:
        root = self._canonical[canonical_id]
        direction = RelationshipDirection(direction)
        limit = len(self._entities) if max_hops is None else max(0, int(max_hops))
        queue = deque([(root, (root,), ())])
        seen = {root.id}
        paths = []
        while queue:
            current, entities, relationships = queue.popleft()
            if len(relationships) >= limit:
                continue
            for edge, next_id in self._neighbors(current.id, direction, relationship_types):
                if next_id in seen or next_id not in self._entities:
                    continue
                seen.add(next_id)
                next_entity = self._entities[next_id]
                path = RelationshipPath((*entities, next_entity), (*relationships, edge))
                paths.append(path)
                queue.append((next_entity, path.entities, path.relationships))
        return tuple(paths)

    def get_dependencies(self, canonical_id: str, max_hops: int | None = 3):
        return self.traverse(
            canonical_id,
            max_hops=max_hops,
            direction=RelationshipDirection.OUTBOUND,
            relationship_types={"depends_on", "runs_on", "hosted_on", "consumes", "supports"},
        )

    def get_owners(self, canonical_id: str):
        return self._related_entities(
            canonical_id, {"owned_by", "managed_by", "belongs_to", "funded_by"}
        )

    def get_consumers(self, canonical_id: str):
        return self._related_entities(canonical_id, {"consumes", "supports", "provides"})

    def get_providers(self, canonical_id: str):
        return self._related_entities(
            canonical_id, {"provided_by", "supplied_by", "hosted_on", "runs_on"}
        )

    def get_impact(self, canonical_id: str, max_hops: int | None = 3) -> ImpactSummary:
        root = self._canonical[canonical_id]
        paths = self.traverse(
            canonical_id, max_hops=max_hops, direction=RelationshipDirection.INBOUND
        )
        impacted = tuple(path.entities[-1] for path in paths)
        counts = {}
        for entity in impacted:
            label = entity.entity_type.value.replace("_", " ")
            counts[label] = counts.get(label, 0) + 1
        detail = ", ".join(f"{count} {label}(s)" for label, count in sorted(counts.items()))
        narrative = (
            f"{root.display_name} has no governed upstream impact relationships."
            if not detail
            else f"{root.display_name} impacts {detail} across {len(paths)} governed path(s)."
        )
        return ImpactSummary(root, impacted, paths, narrative)

    def get_blast_radius(self, canonical_id: str, max_hops: int | None = None):
        return self.get_impact(canonical_id, max_hops=max_hops)

    def _neighbors(self, entity_id, direction, relationship_types):
        for edge in self._relationships:
            if relationship_types and edge.relationship_type.value not in relationship_types:
                continue
            if direction in {RelationshipDirection.OUTBOUND, RelationshipDirection.BOTH}:
                if edge.source_entity_id == entity_id:
                    yield edge, edge.target_entity_id
            if direction in {RelationshipDirection.INBOUND, RelationshipDirection.BOTH}:
                if edge.target_entity_id == entity_id:
                    yield edge, edge.source_entity_id

    def _related_entities(self, canonical_id, relationship_types):
        rows = self.get_relationships(canonical_id)
        entity = self._canonical[canonical_id]
        return tuple(
            self._entities[target]
            for relationship in rows
            if relationship.relationship_type.value in relationship_types
            for target in (
                relationship.target_entity_id
                if relationship.source_entity_id == entity.id
                else relationship.source_entity_id,
            )
            if target in self._entities
        )
