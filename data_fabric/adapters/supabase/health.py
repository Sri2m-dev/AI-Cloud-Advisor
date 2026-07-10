"""Health check wrapper for the Supabase Data Fabric adapter."""

from __future__ import annotations

from dataclasses import dataclass

from data_fabric.adapters.supabase.client import SupabaseDataFabricClient


@dataclass(frozen=True, slots=True)
class SupabaseAdapterHealthCheck:
    client: SupabaseDataFabricClient

    def check(self) -> bool:
        return self.client.health_check()
