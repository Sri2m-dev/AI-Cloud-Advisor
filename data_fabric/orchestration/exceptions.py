"""Orchestration-specific exceptions."""

from __future__ import annotations

from data_fabric.foundation.exceptions import (
    DataFabricConflictError,
    DataFabricIdempotencyError,
    DataFabricOrchestrationError,
    DataFabricTenantBoundaryError,
    DataFabricTransactionError,
    DataFabricValidationError,
)


class OrchestrationValidationError(DataFabricValidationError):
    """Raised when an orchestration request is invalid."""


class OrchestrationConflictError(DataFabricConflictError):
    """Raised when orchestration state conflicts with a request."""


class OrchestrationTenantBoundaryError(DataFabricTenantBoundaryError):
    """Raised when orchestration crosses tenant boundaries."""


class OrchestrationIdempotencyError(DataFabricIdempotencyError):
    """Raised when idempotency state rejects orchestration."""


class OrchestrationTransactionError(DataFabricTransactionError):
    """Raised when orchestration unit-of-work state is invalid."""


class OrchestrationExecutionError(DataFabricOrchestrationError):
    """Raised when orchestration cannot complete."""
