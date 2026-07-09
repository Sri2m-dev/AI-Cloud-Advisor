"""Abstract registry interfaces for canonical P3 contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship


class EntityRegistry(ABC):
    """Interface for canonical enterprise entity registration and lookup."""

    @abstractmethod
    def register_entity(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        """Register a new canonical entity."""

    @abstractmethod
    def get_entity(self, entity_id: str) -> EnterpriseEntity:
        """Return an entity by registry id."""

    @abstractmethod
    def find_entity_by_canonical_id(self, canonical_id: str) -> EnterpriseEntity | None:
        """Return an entity by canonical id, if present."""

    @abstractmethod
    def search_entities(
        self,
        *,
        entity_type: str | None = None,
        organization_id: str | None = None,
        source_system: str | None = None,
        tags: Iterable[str] | None = None,
        include_inactive: bool = False,
    ) -> list[EnterpriseEntity]:
        """Search entities by common contract attributes."""

    @abstractmethod
    def update_entity(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        """Replace an existing entity contract."""

    @abstractmethod
    def deactivate_entity(self, entity_id: str) -> EnterpriseEntity:
        """Mark an entity inactive without deleting it."""


class RelationshipRegistry(ABC):
    """Interface for canonical relationship registration and lookup."""

    @abstractmethod
    def register_relationship(
        self,
        relationship: EnterpriseRelationship,
    ) -> EnterpriseRelationship:
        """Register a new canonical relationship."""

    @abstractmethod
    def get_relationship(self, relationship_id: str) -> EnterpriseRelationship:
        """Return a relationship by registry id."""

    @abstractmethod
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
        """Search relationships by common contract attributes."""

    @abstractmethod
    def deactivate_relationship(self, relationship_id: str) -> EnterpriseRelationship:
        """Mark a relationship inactive without deleting it."""
