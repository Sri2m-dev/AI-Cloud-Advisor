"""Supabase PostgreSQL Data Fabric adapter foundation."""

from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.config import DataFabricDatabaseConfig
from data_fabric.adapters.supabase.entity_repository import SupabaseEntityRepository
from data_fabric.adapters.supabase.exceptions import (
    SupabaseAdapterConfigurationError,
    SupabaseAdapterError,
    SupabaseAdapterOperationError,
)
from data_fabric.adapters.supabase.health import SupabaseAdapterHealthCheck
from data_fabric.adapters.supabase.unit_of_work import SupabaseDataFabricUnitOfWork

__all__ = [
    "DataFabricDatabaseConfig",
    "SupabaseAdapterConfigurationError",
    "SupabaseAdapterError",
    "SupabaseAdapterHealthCheck",
    "SupabaseAdapterOperationError",
    "SupabaseDataFabricClient",
    "SupabaseDataFabricUnitOfWork",
    "SupabaseEntityRepository",
]
