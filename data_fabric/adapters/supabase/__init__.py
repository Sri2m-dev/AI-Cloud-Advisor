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
from data_fabric.adapters.supabase.lineage_repository import SupabaseLineageRepository
from data_fabric.adapters.supabase.provenance_repository import SupabaseProvenanceRepository
from data_fabric.adapters.supabase.relationship_repository import SupabaseRelationshipRepository
from data_fabric.adapters.supabase.unit_of_work import SupabaseDataFabricUnitOfWork
from data_fabric.adapters.supabase.version_repository import SupabaseVersionRepository

__all__ = [
    "DataFabricDatabaseConfig",
    "SupabaseAdapterConfigurationError",
    "SupabaseAdapterError",
    "SupabaseAdapterHealthCheck",
    "SupabaseAdapterOperationError",
    "SupabaseDataFabricClient",
    "SupabaseLineageRepository",
    "SupabaseProvenanceRepository",
    "SupabaseRelationshipRepository",
    "SupabaseDataFabricUnitOfWork",
    "SupabaseEntityRepository",
    "SupabaseVersionRepository",
]
