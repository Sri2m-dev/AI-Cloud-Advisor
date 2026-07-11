"""Opt-in integration tests for the P3 Supabase entity adapter foundation.

These tests never run against a real Supabase project unless the shared P3
integration safety gate is explicitly enabled with test-only credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone

from data_fabric.adapters.supabase import SupabaseDataFabricClient
from data_fabric.adapters.supabase.entity_repository import SupabaseEntityRepository
from data_fabric.contracts import EnterpriseEntity, EntityType
from tests.data_fabric.supabase_integration_safety import (
    cleanup_test_tenant,
    client_or_skip,
    create_test_identifier,
    create_test_tenant_context,
)


def test_supabase_entity_repository_integration_smoke() -> None:
    client = client_or_skip()
    assert isinstance(client, SupabaseDataFabricClient)
    repository = SupabaseEntityRepository(client)
    tenant_context = create_test_tenant_context("entity")
    now = datetime.now(timezone.utc)
    entity = EnterpriseEntity(
        id=create_test_identifier("entity"),
        canonical_id=create_test_identifier("canonical"),
        entity_type=EntityType.APPLICATION,
        name="Integration Entity",
        source_system="integration-test",
        source_identifier=create_test_identifier("source"),
        organization_id=tenant_context.organization_id,
        tenant_id=tenant_context.tenant_id,
        created_at=now,
        updated_at=now,
        metadata={"purpose": "p3.13 integration smoke"},
    )

    try:
        created = repository.add(entity)
        fetched = repository.get(tenant_context, created.record_id)

        assert fetched is not None
        assert fetched.payload["canonical_id"] == entity.canonical_id
        assert repository.find_by_source_identity(
            tenant_context,
            entity.source_system,
            entity.source_identifier,
        ) is not None
    finally:
        cleanup_test_tenant(client, tenant_context)
