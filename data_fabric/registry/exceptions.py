"""Registry-specific exceptions for P3 interfaces."""


class RegistryError(Exception):
    """Base exception for registry operations."""


class RegistryValidationError(RegistryError, ValueError):
    """Raised when a contract cannot be accepted by a registry."""


class DuplicateCanonicalIdError(RegistryValidationError):
    """Raised when an entity canonical_id conflicts with an existing entity."""


class EntityNotFoundError(RegistryError, KeyError):
    """Raised when an entity id is not present in the registry."""


class RelationshipNotFoundError(RegistryError, KeyError):
    """Raised when a relationship id is not present in the registry."""
