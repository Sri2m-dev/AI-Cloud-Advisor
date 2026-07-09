"""Registry interfaces and in-memory implementations for P3 Data Fabric."""

from data_fabric.registry.entity_registry import InMemoryEntityRegistry
from data_fabric.registry.exceptions import (
    DuplicateCanonicalIdError,
    RegistryError,
    RegistryValidationError,
    RelationshipNotFoundError,
    EntityNotFoundError,
)
from data_fabric.registry.interfaces import EntityRegistry, RelationshipRegistry
from data_fabric.registry.relationship_registry import InMemoryRelationshipRegistry

__all__ = [
    "DuplicateCanonicalIdError",
    "EntityNotFoundError",
    "EntityRegistry",
    "InMemoryEntityRegistry",
    "InMemoryRelationshipRegistry",
    "RegistryError",
    "RegistryValidationError",
    "RelationshipNotFoundError",
    "RelationshipRegistry",
]
