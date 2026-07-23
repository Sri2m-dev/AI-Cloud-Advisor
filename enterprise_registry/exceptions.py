"""Business Service Registry exceptions."""


class BusinessServiceRegistryError(Exception):
    """Base exception for WP-006 Phase 1 registry operations."""


class BusinessServiceValidationError(BusinessServiceRegistryError, ValueError):
    """Raised when a business service violates the approved contract."""


class BusinessServiceNotFoundError(BusinessServiceRegistryError, KeyError):
    """Raised when a scoped business service cannot be found."""


class DuplicateBusinessServiceError(BusinessServiceValidationError):
    """Raised when canonical or source identity is already registered."""


class BusinessServiceVersionConflictError(BusinessServiceRegistryError):
    """Raised when an update is attempted against a stale version."""


class BusinessServiceRelationshipError(BusinessServiceValidationError):
    """Raised when a relationship is incompatible or crosses scope."""


class EMRPValidationError(BusinessServiceRegistryError, ValueError):
    """Raised when EMRP orchestration rejects canonical metadata."""


class EMRPTaxonomyError(EMRPValidationError):
    """Raised when a taxonomy assignment is invalid."""


class EMRPRelationshipError(EMRPValidationError):
    """Raised when canonical relationship topology is invalid."""
