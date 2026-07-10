"""Persistence-specific exceptions for Data Fabric repository contracts."""

from __future__ import annotations

from data_fabric.foundation import (
    DataFabricConflictError,
    DataFabricDuplicateError,
    DataFabricImmutableStateError,
    DataFabricNotFoundError,
    DataFabricTenantBoundaryError,
    DataFabricTransactionError,
    DataFabricValidationError,
)


class PersistenceValidationError(DataFabricValidationError):
    """Raised when a persistence record or query is invalid."""


class PersistenceNotFoundError(DataFabricNotFoundError):
    """Raised when a persistence record cannot be found."""


class PersistenceDuplicateError(DataFabricDuplicateError):
    """Raised when duplicate persistence identity is rejected."""


class PersistenceConflictError(DataFabricConflictError):
    """Raised when persistence state conflicts with a request."""


class PersistenceTenantBoundaryError(DataFabricTenantBoundaryError):
    """Raised when a persistence operation crosses tenant context."""


class PersistenceImmutableStateError(DataFabricImmutableStateError):
    """Raised when immutable persistence state would be updated."""


class PersistenceTransactionError(DataFabricTransactionError):
    """Raised when a persistence transaction cannot complete."""
