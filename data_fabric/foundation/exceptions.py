"""Shared Data Fabric foundation exceptions."""

from __future__ import annotations


class DataFabricError(Exception):
    """Base error for catchable Data Fabric failures."""


class DataFabricValidationError(DataFabricError, ValueError):
    """Raised when a Data Fabric contract or request is invalid."""


class DataFabricNotFoundError(DataFabricError, LookupError):
    """Raised when a Data Fabric object cannot be found."""


class DataFabricDuplicateError(DataFabricError):
    """Raised when a uniqueness boundary is violated."""


class DataFabricConflictError(DataFabricError):
    """Raised when a request conflicts with existing state."""


class DataFabricTenantBoundaryError(DataFabricValidationError):
    """Raised when tenant isolation would be violated."""


class DataFabricImmutableStateError(DataFabricConflictError):
    """Raised when immutable state would be modified."""


class DataFabricIdempotencyError(DataFabricConflictError):
    """Raised when idempotency state rejects a request."""


class DataFabricTransactionError(DataFabricConflictError):
    """Raised when a unit-of-work or transaction boundary fails."""


class DataFabricOrchestrationError(DataFabricError):
    """Raised when orchestration cannot complete safely."""
