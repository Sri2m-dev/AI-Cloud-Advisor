"""Unit tests for the P3.14 Supabase lineage repository."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient, SupabaseLineageRepository
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterOperationError
from data_fabric.foundation import TenantContext
from data_fabric.persistence.models import AppendOnlyRecord
from tests.data_fabric.supabase_fake import FakeRawSupabaseClient, tenant_filters_seen


def make_repository() -> tuple[SupabaseLineageRepository, FakeRawSupabaseClient]:
    raw = FakeRawSupabaseClient()
    client = SupabaseDataFabricClient(DataFabricDatabaseConfig("https://example.supabase.co", "server-side-secret", max_retries=0), raw_client=raw)
    return SupabaseLineageRepository(client), raw


def make_event(event_id: str, occurred_day: int = 1) -> AppendOnlyRecord:
    occurred = datetime(2026, 1, occurred_day, tzinfo=timezone.utc)
    return AppendOnlyRecord(
        record_id=event_id,
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=occurred,
        updated_at=occurred,
        payload={
            "entity_id": "22222222-2222-4222-8222-222222222222",
            "relationship_id": "11111111-1111-4111-8111-111111111111",
            "event_type": "canonicalized",
            "source_system": "cmdb",
            "source_identifier": "entity-1",
            "occurred_at": occurred,
            "correlation_id": "corr-1",
            "payload": {"step": occurred_day},
        },
    )


def test_append_get_and_query_lineage_by_subjects() -> None:
    repository, raw = make_repository()
    first = repository.append(make_event("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1", 1))
    repository.append(make_event("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2", 2))
    tenant = TenantContext("org-1", "tenant-1")

    assert repository.get(tenant, first.record_id) is not None
    assert len(repository.list_by_entity(tenant, "22222222-2222-4222-8222-222222222222")) == 2
    assert len(repository.list_by_relationship(tenant, "11111111-1111-4111-8111-111111111111")) == 2
    assert [record.record_id for record in repository.list_by_correlation_id(tenant, "corr-1")] == [first.record_id, "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2"]
    assert repository.get(TenantContext("org-1", "tenant-2"), first.record_id) is None
    assert tenant_filters_seen(raw, "data_fabric.lineage_events")


def test_lineage_duplicate_and_update_are_rejected() -> None:
    repository, _ = make_repository()
    event = make_event("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1")
    repository.append(event)

    with pytest.raises(SupabaseAdapterOperationError):
        repository.append(event)
    with pytest.raises(SupabaseAdapterOperationError):
        repository.update(event)
