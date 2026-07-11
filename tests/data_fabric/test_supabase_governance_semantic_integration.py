"""Opt-in P3.15A Supabase governance/semantic integration tests."""
from __future__ import annotations
import os
import pytest
from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient

def _client():
    if os.getenv("P3_SUPABASE_RUN_INTEGRATION") != "1":
        pytest.skip("P3 Supabase governance/semantic integration tests are opt-in only")
    url=os.getenv("P3_SUPABASE_TEST_URL"); key=os.getenv("P3_SUPABASE_TEST_SERVICE_ROLE_KEY")
    if not url or not key: pytest.skip("P3 Supabase test URL/service role key are not configured")
    return SupabaseDataFabricClient(DataFabricDatabaseConfig(url,key))

def test_governance_semantic_integration_is_gated():
    assert _client() is not None
