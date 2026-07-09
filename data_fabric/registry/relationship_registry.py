"""In-memory reference implementation for relationship registry interfaces."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

from data_fabric.contracts import EnterpriseRelationship
from data_fabric.registry.exceptions import (
    RegistryValidationError,
    RelationshipNotFoundError,
)
from data_fabric.registry.interfaces import RelationshipRegistry


class InMemoryRelationshipRegistry(RelationshipRegistry):
    """Non-persistent reference registry for canonical relationships."""

    def __init__(self) -> None:
        self._relationships: dict[str, EnterpriseRelationship] = {}

    def register_relationship(
        self,
        relationship: EnterpriseRelationship,
    ) -> EnterpriseRelationship:
        self._validate_relationship(relationship)
        if relationship.id in self._relationships:
            raise RegistryValidationError(
                f"Relationship id already exists: {relationship.id}"
            )
        stored = self._copy(relationship)
        self._relationships[stored.id] = stored
        return self._copy(stored)

    def get_relationship(self, relationship_id: str) -> EnterpriseRelationship:
        try:
            return self._copy(self._relationships[relationship_id])
        except KeyError as exc:
            raise RelationshipNotFoundError(
                f"Relationship not found: {relationship_id}"
            ) from exc

    def search_relationships(
        self,
        *,
        relationship_type: str | None = None,
        source_entity_id: str | None = None,
        target_entity_id: str | None = None,
        organization_id: str | None = None,
        source_system: str | None = None,
        include_inactive: bool = False,
    ) -> list[EnterpriseRelationship]:
        results = []
        for relationship in self._relationships.values():
            if not include_inactive and not self._is_active(relationship):
                continue
            if relationship_type is not None and relationship.relationship_type.value != relationship_type:
                continue
            if source_entity_id is not None and relationship.source_entity_id != source_entity_id:
                continue
            if target_entity_id is not None and relationship.target_entity_id != target_entity_id:
                continue
            if organization_id is not None and relationship.organization_id != organization_id:
                continue
            if source_system is not None and relationship.source_system != source_system:
                continue
            results.append(self._copy(relationship))
        return results

    def deactivate_relationship(self, relationship_id: str) -> EnterpriseRelationship:
        relationship = self.get_relationship(relationship_id)
        metadata = dict(relationship.metadata)
        metadata["active"] = False
        metadata["deactivated_at"] = datetime.now(timezone.utc).isoformat()
        updated = replace(
            relationship,
            metadata=metadata,
            updated_at=datetime.now(timezone.utc),
        )
        self._relationships[relationship_id] = self._copy(updated)
        return self._copy(updated)

    @staticmethod
    def _validate_relationship(relationship: EnterpriseRelationship) -> None:
        required = {
            "id": relationship.id,
            "source_entity_id": relationship.source_entity_id,
            "target_entity_id": relationship.target_entity_id,
            "source_system": relationship.source_system,
            "source_identifier": relationship.source_identifier,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RegistryValidationError(
                f"Relationship is missing required field(s): {', '.join(missing)}"
            )

    @staticmethod
    def _is_active(relationship: EnterpriseRelationship) -> bool:
        return relationship.metadata.get("active", True) is not False

    @staticmethod
    def _copy(relationship: EnterpriseRelationship) -> EnterpriseRelationship:
        return deepcopy(relationship)
