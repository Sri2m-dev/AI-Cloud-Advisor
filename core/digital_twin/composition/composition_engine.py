from __future__ import annotations

from collections import deque
from uuid import UUID

from core.digital_twin.composition.composition_context import CompositionContext
from core.digital_twin.composition.composition_result import CompositionResult
from repositories.entity_repository import EntityRepository


class TwinCompositionEngine:
    def __init__(self, entity_repository: EntityRepository | None = None):
        self.entity_repository = entity_repository or EntityRepository()

    def compose(self, context: CompositionContext) -> CompositionResult:
        entities = [
            entity
            for entity in self.entity_repository.get_entities()
            if entity.organization_id == context.organization_id
        ]
        entity_by_id = {entity.id: entity for entity in entities}
        relationships = [
            relationship
            for relationship in self.entity_repository.get_relationships()
            if relationship.source_entity_id in entity_by_id or relationship.target_entity_id in entity_by_id
        ]
        selected_ids = self._traverse(context.root_entity_id, relationships, set(entity_by_id), context.policy.max_depth)
        if selected_ids:
            entities = [entity for entity in entities if entity.id in selected_ids]
            relationships = [
                relationship
                for relationship in relationships
                if relationship.source_entity_id in selected_ids or relationship.target_entity_id in selected_ids
            ]
        return CompositionResult(
            organization_id=context.organization_id,
            root_entity_id=context.root_entity_id,
            twin_type=context.twin_type,
            entities=[entity.to_dict() for entity in entities],
            relationships=[relationship.to_dict() for relationship in relationships],
            aggregates={
                "entity_count": len(entities),
                "relationship_count": len(relationships),
                "source_systems": sorted({source.system for entity in entities for source in entity.source_systems}),
                "entity_types": sorted({entity.entity_type for entity in entities}),
            },
            metadata={
                "policy": context.policy.to_dict(),
                **context.metadata,
            },
        )

    @staticmethod
    def _traverse(
        root_entity_id: UUID | None,
        relationships: list,
        valid_entity_ids: set[UUID],
        max_depth: int,
    ) -> set[UUID]:
        if root_entity_id is None:
            return set()
        adjacency: dict[UUID, set[UUID]] = {}
        for relationship in relationships:
            adjacency.setdefault(relationship.source_entity_id, set()).add(relationship.target_entity_id)
            adjacency.setdefault(relationship.target_entity_id, set()).add(relationship.source_entity_id)
        selected = {root_entity_id}
        queue: deque[tuple[UUID, int]] = deque([(root_entity_id, 0)])
        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for next_id in adjacency.get(current_id, set()):
                if next_id in valid_entity_ids and next_id not in selected:
                    selected.add(next_id)
                    queue.append((next_id, depth + 1))
        return selected
