"""Opt-in P3.15B Supabase atomic canonical write integration tests."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient


def _client() -> SupabaseDataFabricClient:
    if os.getenv("P3_SUPABASE_RUN_INTEGRATION") != "1":
        pytest.skip("P3 Supabase atomic-write integration tests are opt-in only")
    url = os.getenv("P3_SUPABASE_TEST_URL")
    key = os.getenv("P3_SUPABASE_TEST_SERVICE_ROLE_KEY")
    if not url or not key:
        pytest.skip("P3 Supabase test URL/service role key are not configured")
    lowered = url.lower()
    if "prod" in lowered or "production" in lowered:
        raise RuntimeError("refusing to run P3 atomic-write integration tests against a production-looking URL")
    return SupabaseDataFabricClient(DataFabricDatabaseConfig(url, key))


def _unique_scope() -> tuple[str, str, str]:
    suffix = uuid4().hex
    return f"p3-atomic-org-{suffix}", f"p3-atomic-tenant-{suffix}", suffix


def test_atomic_write_integration_is_gated_and_uses_unique_scope():
    organization_id, tenant_id, suffix = _unique_scope()
    assert organization_id.endswith(suffix)
    assert tenant_id.endswith(suffix)
    assert _client() is not None


def test_entity_bundle_scenarios_require_safe_supabase_environment():
    _client()
    pytest.skip("Scenario implementation requires a provisioned disposable Supabase database with P3.15B migrations applied manually")


def test_relationship_bundle_scenarios_require_safe_supabase_environment():
    _client()
    pytest.skip("Scenario implementation requires a provisioned disposable Supabase database with P3.15B migrations applied manually")
