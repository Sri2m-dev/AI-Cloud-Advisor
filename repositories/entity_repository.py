from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable
from uuid import UUID

from core.entities.entity import EnterpriseEntity, EntityRelationship, LifecycleState


DEFAULT_ENTITY_STORE = Path("data/entity_registry.json")


class EntityRepository:
    def __init__(self, store_path: str | Path = DEFAULT_ENTITY_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._entities: dict[UUID, EnterpriseEntity] = {}
        self._relationships: list[EntityRelationship] = []
        self._load()

    def get_entity(self, entity_id: UUID | str) -> EnterpriseEntity | None:
        return self._entities.get(UUID(str(entity_id)))

    def get_entities(self, entity_type: str | None = None) -> list[EnterpriseEntity]:
        entities = list(self._entities.values())
        if entity_type:
            entities = [entity for entity in entities if entity.entity_type == entity_type]
        return sorted(entities, key=lambda entity: (entity.entity_type, entity.display_name.lower()))

    def find_by_source(self, system: str, external_id: str) -> EnterpriseEntity | None:
        normalized_system = system.strip().lower()
        normalized_external_id = external_id.strip().lower()
        for entity in self._entities.values():
            for reference in entity.source_systems:
                if (
                    reference.system.strip().lower() == normalized_system
                    and reference.external_id.strip().lower() == normalized_external_id
                ):
                    return entity
        return None

    def search(self, name: str) -> list[EnterpriseEntity]:
        query = name.strip().lower()
        if not query:
            return self.get_entities()

        matches = []
        for entity in self._entities.values():
            searchable = " ".join(
                [
                    entity.display_name,
                    entity.description,
                    entity.entity_type,
                    " ".join(entity.tags.values()),
                    " ".join(reference.external_name for reference in entity.source_systems),
                    " ".join(reference.external_id for reference in entity.source_systems),
                ]
            ).lower()
            if query in searchable:
                matches.append(entity)
        return sorted(matches, key=lambda entity: entity.display_name.lower())

    def save(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        entity.touch()
        self._entities[entity.id] = entity
        self._persist()
        return entity

    def update(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        if entity.id not in self._entities:
            raise KeyError(f"Entity not found: {entity.id}")
        return self.save(entity)

    def archive(self, entity: EnterpriseEntity | UUID | str) -> EnterpriseEntity:
        resolved = self._resolve(entity)
        resolved.lifecycle_state = LifecycleState.RETIRED.value
        return self.save(resolved)

    def merge(self, entity_a: EnterpriseEntity | UUID | str, entity_b: EnterpriseEntity | UUID | str) -> EnterpriseEntity:
        primary = self._resolve(entity_a)
        duplicate = self._resolve(entity_b)

        existing_sources = {
            (reference.system.lower(), reference.external_id.lower())
            for reference in primary.source_systems
        }
        for reference in duplicate.source_systems:
            key = (reference.system.lower(), reference.external_id.lower())
            if key not in existing_sources:
                primary.source_systems.append(reference)

        primary.tags.update(duplicate.tags)
        primary.metadata.setdefault("merged_entity_ids", []).append(str(duplicate.id))
        primary.metadata.setdefault("merged_entity_names", []).append(duplicate.display_name)

        for relationship in self._relationships:
            if relationship.source_entity_id == duplicate.id:
                relationship.source_entity_id = primary.id
            if relationship.target_entity_id == duplicate.id:
                relationship.target_entity_id = primary.id

        self._entities.pop(duplicate.id, None)
        return self.save(primary)

    def add_relationship(self, relationship: EntityRelationship) -> EntityRelationship:
        self._relationships.append(relationship)
        self._persist()
        return relationship

    def get_relationships(self, entity_id: UUID | str | None = None) -> list[EntityRelationship]:
        if entity_id is None:
            return list(self._relationships)
        resolved_id = UUID(str(entity_id))
        return [
            relationship
            for relationship in self._relationships
            if relationship.source_entity_id == resolved_id or relationship.target_entity_id == resolved_id
        ]

    def replace_all(
        self,
        entities: Iterable[EnterpriseEntity],
        relationships: Iterable[EntityRelationship] | None = None,
    ) -> None:
        self._entities = {entity.id: entity for entity in entities}
        self._relationships = list(relationships or [])
        self._persist()

    def _resolve(self, entity: EnterpriseEntity | UUID | str) -> EnterpriseEntity:
        if isinstance(entity, EnterpriseEntity):
            return entity
        resolved = self.get_entity(entity)
        if not resolved:
            raise KeyError(f"Entity not found: {entity}")
        return resolved

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._entities = {
            entity.id: entity
            for entity in [
                EnterpriseEntity.from_dict(item)
                for item in payload.get("entities", [])
            ]
        }
        self._relationships = [
            EntityRelationship.from_dict(item)
            for item in payload.get("relationships", [])
        ]

    def _persist(self) -> None:
        payload = {
            "entities": [entity.to_dict() for entity in self.get_entities()],
            "relationships": [relationship.to_dict() for relationship in self._relationships],
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

