"""Canonical persistence adapters."""

from connector_persistence.adapters.memory import MemoryCanonicalRepository
from connector_persistence.adapters.supabase import SupabaseCanonicalRepository

__all__ = ["MemoryCanonicalRepository", "SupabaseCanonicalRepository"]
