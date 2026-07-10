"""Supabase Data Fabric adapter exceptions."""

from __future__ import annotations

from data_fabric.foundation import DataFabricConflictError, DataFabricError, DataFabricValidationError


class SupabaseAdapterError(DataFabricError):
    """Base error for the Supabase Data Fabric adapter."""


class SupabaseAdapterConfigurationError(SupabaseAdapterError, DataFabricValidationError):
    """Raised when adapter configuration is invalid."""


class SupabaseAdapterOperationError(SupabaseAdapterError):
    """Raised when a Supabase operation fails."""


class SupabaseAdapterConflictError(SupabaseAdapterOperationError, DataFabricConflictError):
    """Raised when Supabase reports a conflict or stale revision."""
