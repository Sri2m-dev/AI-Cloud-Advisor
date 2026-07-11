"""Unit tests for the P3.14 Supabase relationship repository."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient, SupabaseRelationshipRepository
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError, SupabaseAdapterOperationError
from data_fabric.contracts import EnterpriseRelationship, RelationshipType
from data_fabric.foundation import TenantContext
from tests.data_fabric.supabase_fake import FakeRawSupabaseClient, tenant_filters_seen


def make_repository() -> tuple[SupabaseRelationshipRepository, FakeRawSupabaseClient]:
    raw = FakeRawSupabaseClient()
    client = SupabaseDataFabricClient(DataFabricDatabaseConfig("https://example.supabase.co", "server-side-secret", max_retries=0), raw_client=raw)
    return SupabaseRelationshipRepository(client), raw


def make_relationship(record_id: str = "11111111-1111-4111-8111-111111111111") -> EnterpriseRelationship:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return EnterpriseRelationship(
        id=record_id,
        relationship_type=RelationshipType.DEPENDS_ON,
        source_entity_id="22222222-2222-4222-8222-222222222222",
        target_entity_id="33333333-3333-4333-8333-333333333333",
        organization_id="org-1",
        tenant_id="tenant-1",
        source_system="cmdb",
        source_identifier=f"rel-{record_id}",
        created_at=now,
        updated_at=now,
        confidence_score=0.8,
        quality_score=0.9,
        metadata={"criticality": "high"},
    )


def test_add_get_and_lookup_relationships_are_tenant_scoped() -> None:
    repository, raw = make_repository()
    created = repository.add(make_relationship())

    tenant = TenantContext("org-1", "tenant-1")
    assert repository.get(tenant, created.record_id) is not None
    assert repository.get(TenantContext("org-1", "tenant-2"), created.record_id) is None
    assert repository.find_by_source_entity(tenant, "22222222-2222-4222-8222-222222222222").total_count == 1
    assert repository.find_by_target_entity(tenant, "33333333-3333-4333-8333-333333333333").total_count == 1
    assert tenant_filters_seen(raw, "data_fabric.enterprise_relationships")


def test_update_uses_rpc_revision_check_and_stale_revision_conflicts() -> None:
    repository, raw = make_repository()
    created = repository.add(make_relationship())
    changed = replace(created, payload={**dict(created.payload), "relationship_type": "impacts"})

    updated = repository.update(changed, expected_revision=1)

    assert updated.revision == 2
    assert updated.payload["relationship_type"] == "impacts"
    assert raw.rpc_calls[0][0] == "data_fabric_update_enterprise_relationship"
    assert raw.rpc_calls[0][1]["p_tenant_id"] == "tenant-1"

    with pytest.raises(SupabaseAdapterConflictError):
        repository.update(changed, expected_revision=1)


def test_deactivate_hides_inactive_by_default_and_include_inactive_restores() -> None:
    repository, _ = make_repository()
    repository.add(make_relationship())
    tenant = TenantContext("org-1", "tenant-1")

    deactivated = repository.deactivate(tenant, "11111111-1111-4111-8111-111111111111", deactivated_by="tester")

    assert deactivated.active is False
    assert repository.get(tenant, deactivated.record_id) is None
    assert repository.get(tenant, deactivated.record_id, include_inactive=True) is not None


def test_duplicate_active_relationship_is_rejected_and_input_not_mutated() -> None:
    repository, _ = make_repository()
    relationship = make_relationship()
    original_metadata = dict(relationship.metadata)
    repository.add(relationship)

    with pytest.raises(SupabaseAdapterOperationError):
        repository.add(make_relationship("44444444-4444-4444-8444-444444444444"))

    assert relationship.metadata == original_metadata
