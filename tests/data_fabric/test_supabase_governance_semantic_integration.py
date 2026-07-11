"""Opt-in P3.15A Supabase governance/semantic integration tests."""

from __future__ import annotations

from data_fabric.adapters.supabase import SupabaseDataFabricClient
from tests.data_fabric.supabase_integration_safety import client_or_skip


def test_governance_semantic_integration_is_gated() -> None:
    assert isinstance(client_or_skip(), SupabaseDataFabricClient)
