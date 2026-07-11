"""Supabase Data Fabric adapter exceptions."""

from __future__ import annotations

from data_fabric.foundation import (
    DataFabricConflictError,
    DataFabricError,
    DataFabricIdempotencyError,
    DataFabricTenantBoundaryError,
    DataFabricTransactionError,
    DataFabricValidationError,
)


class SupabaseAdapterError(DataFabricError):
    """Base error for the Supabase Data Fabric adapter."""


class SupabaseAdapterConfigurationError(SupabaseAdapterError, DataFabricValidationError):
    """Raised when adapter configuration is invalid."""


class SupabaseAdapterOperationError(SupabaseAdapterError):
    """Raised when a Supabase operation fails."""


class SupabaseAdapterConflictError(SupabaseAdapterOperationError, DataFabricConflictError):
    """Raised when Supabase reports a conflict or stale revision."""


class SupabaseAdapterTenantBoundaryError(SupabaseAdapterOperationError, DataFabricTenantBoundaryError):
    """Raised when a Supabase adapter operation crosses tenant scope."""


class SupabaseAdapterIdempotencyError(SupabaseAdapterConflictError, DataFabricIdempotencyError):
    """Raised when durable Supabase idempotency state rejects a request."""


class SupabaseAdapterTransactionError(SupabaseAdapterOperationError, DataFabricTransactionError):
    """Raised when a reviewed Supabase transaction boundary fails."""
