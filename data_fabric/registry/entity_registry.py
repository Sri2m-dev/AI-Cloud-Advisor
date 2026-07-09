"""In-memory reference implementation for entity registry interfaces."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

from data_fabric.contracts import EnterpriseEntity
from data_fabric.registry.exceptions import (
    DuplicateCanonicalIdError,
    EntityNotFoundError,
    RegistryValidationError,
)
from data_fabric.registry.interfaces import EntityRegistry


class InMemoryEntityRegistry(EntityRegistry):
    """Non-persistent reference registry for canonical entities."""

    def __init__(self) -> None:
        self._entities: dict[str, EnterpriseEntity] = {}
        self._canonical_index: dict[str, str] = {}

    def register_entity(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        self._validate_entity(entity)
        if entity.id in self._entities:
            raise RegistryValidationError(f"Entity id already exists: {entity.id}")
        self._ensure_canonical_id_available(entity.canonical_id, entity.id)
        stored = self._copy(entity)
        self._entities[stored.id] = stored
        self._canonical_index[stored.canonical_id] = stored.id
        return self._copy(stored)

    def get_entity(self, entity_id: str) -> EnterpriseEntity:
        try:
            return self._copy(self._entities[entity_id])
        except KeyError as exc:
            raise EntityNotFoundError(f"Entity not found: {entity_id}") from exc

    def find_entity_by_canonical_id(self, canonical_id: str) -> EnterpriseEntity | None:
        entity_id = self._canonical_index.get(canonical_id)
        if entity_id is None:
            return None
        return self.get_entity(entity_id)

    def search_entities(
        self,
        *,
        entity_type: str | None = None,
        organization_id: str | None = None,
        source_system: str | None = None,
        tags: Iterable[str] | None = None,
        include_inactive: bool = False,
    ) -> list[EnterpriseEntity]:
        required_tags = set(tags or [])
        results = []
        for entity in self._entities.values():
            if not include_inactive and not self._is_active(entity):
                continue
            if entity_type is not None and entity.entity_type.value != entity_type:
                continue
            if organization_id is not None and entity.organization_id != organization_id:
                continue
            if source_system is not None and entity.source_system != source_system:
                continue
            if required_tags and not required_tags.issubset(set(entity.tags)):
                continue
            results.append(self._copy(entity))
        return results

    def update_entity(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        self._validate_entity(entity)
        if entity.id not in self._entities:
            raise EntityNotFoundError(f"Entity not found: {entity.id}")
        self._ensure_canonical_id_available(entity.canonical_id, entity.id)
        old = self._entities[entity.id]
        if old.canonical_id != entity.canonical_id:
            self._canonical_index.pop(old.canonical_id, None)
        updated = replace(self._copy(entity), updated_at=datetime.now(timezone.utc))
        self._entities[updated.id] = updated
        self._canonical_index[updated.canonical_id] = updated.id
        return self._copy(updated)

    def deactivate_entity(self, entity_id: str) -> EnterpriseEntity:
        entity = self.get_entity(entity_id)
        metadata = dict(entity.metadata)
        metadata["active"] = False
        metadata["deactivated_at"] = datetime.now(timezone.utc).isoformat()
        return self.update_entity(replace(entity, metadata=metadata))

    def _ensure_canonical_id_available(self, canonical_id: str, entity_id: str) -> None:
        existing_id = self._canonical_index.get(canonical_id)
        if existing_id is not None and existing_id != entity_id:
            raise DuplicateCanonicalIdError(
                f"canonical_id already registered: {canonical_id}"
            )

    @staticmethod
    def _validate_entity(entity: EnterpriseEntity) -> None:
        required = {
            "id": entity.id,
            "canonical_id": entity.canonical_id,
            "source_system": entity.source_system,
            "source_identifier": entity.source_identifier,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RegistryValidationError(
                f"Entity is missing required field(s): {', '.join(missing)}"
            )

    @staticmethod
    def _is_active(entity: EnterpriseEntity) -> bool:
        return entity.metadata.get("active", True) is not False

    @staticmethod
    def _copy(entity: EnterpriseEntity) -> EnterpriseEntity:
        return deepcopy(entity)
