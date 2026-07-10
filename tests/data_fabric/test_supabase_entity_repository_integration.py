"""Opt-in integration tests for the P3 Supabase entity adapter foundation.

These tests never run against a real Supabase project unless explicitly enabled with
P3_SUPABASE_RUN_INTEGRATION=1 and test-only credentials.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient
from data_fabric.adapters.supabase.entity_repository import SupabaseEntityRepository
from data_fabric.contracts import EnterpriseEntity, EntityType
from data_fabric.foundation import TenantContext



def _integration_config() -> DataFabricDatabaseConfig:
    if os.getenv("P3_SUPABASE_RUN_INTEGRATION") != "1":
        pytest.skip("P3 Supabase integration tests are opt-in only")
    url = os.getenv("P3_SUPABASE_TEST_URL")
    key = os.getenv("P3_SUPABASE_TEST_SERVICE_ROLE_KEY")
    if not url or not key:
        pytest.skip("P3 Supabase test URL/service role key are not configured")
    return DataFabricDatabaseConfig(url, key)


def test_supabase_entity_repository_integration_smoke() -> None:
    config = _integration_config()
    repository = SupabaseEntityRepository(SupabaseDataFabricClient(config))
    unique = uuid4().hex
    tenant_context = TenantContext(f"org-it-{unique}", f"tenant-it-{unique}")
    now = datetime.now(timezone.utc)
    entity = EnterpriseEntity(
        id=f"entity-it-{unique}",
        canonical_id=f"canonical-it-{unique}",
        entity_type=EntityType.APPLICATION,
        name="Integration Entity",
        source_system="integration-test",
        source_identifier=f"source-it-{unique}",
        organization_id=tenant_context.organization_id,
        tenant_id=tenant_context.tenant_id,
        created_at=now,
        updated_at=now,
        metadata={"purpose": "p3.13 integration smoke"},
    )

    created = repository.add(entity)
    fetched = repository.get(tenant_context, created.record_id)

    assert fetched is not None
    assert fetched.payload["canonical_id"] == entity.canonical_id
    assert repository.find_by_source_identity(
        tenant_context,
        entity.source_system,
        entity.source_identifier,
    ) is not None
