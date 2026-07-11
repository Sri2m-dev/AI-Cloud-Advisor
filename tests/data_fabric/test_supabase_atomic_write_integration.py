"""Opt-in P3.15B Supabase atomic canonical write integration tests."""

from __future__ import annotations

import pytest

from data_fabric.adapters.supabase import SupabaseDataFabricClient
from tests.data_fabric.supabase_integration_safety import (
    client_or_skip,
    create_test_identifier,
    create_test_tenant_context,
)


def test_atomic_write_integration_is_gated_and_uses_unique_scope() -> None:
    tenant_context = create_test_tenant_context("atomic")
    idempotency_key = create_test_identifier("idempotency")
    correlation_id = create_test_identifier("correlation")
    assert tenant_context.organization_id.startswith("p3test-")
    assert tenant_context.tenant_id.startswith("p3test-")
    assert idempotency_key.startswith("p3test-")
    assert correlation_id.startswith("p3test-")
    assert isinstance(client_or_skip(), SupabaseDataFabricClient)


def test_entity_bundle_scenarios_require_safe_supabase_environment() -> None:
    client_or_skip()
    pytest.skip(
        "Scenario implementation requires a provisioned disposable Supabase database "
        "with P3.15B migrations applied manually"
    )


def test_relationship_bundle_scenarios_require_safe_supabase_environment() -> None:
    client_or_skip()
    pytest.skip(
        "Scenario implementation requires a provisioned disposable Supabase database "
        "with P3.15B migrations applied manually"
    )
