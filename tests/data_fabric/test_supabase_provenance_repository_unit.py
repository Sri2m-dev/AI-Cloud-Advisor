"""Unit tests for the P3.14 Supabase provenance repository."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient, SupabaseProvenanceRepository
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterOperationError
from data_fabric.foundation import TenantContext
from data_fabric.persistence.models import AppendOnlyRecord
from tests.data_fabric.supabase_fake import FakeRawSupabaseClient, tenant_filters_seen


def make_repository() -> tuple[SupabaseProvenanceRepository, FakeRawSupabaseClient]:
    raw = FakeRawSupabaseClient()
    client = SupabaseDataFabricClient(DataFabricDatabaseConfig("https://example.supabase.co", "server-side-secret", max_retries=0), raw_client=raw)
    return SupabaseProvenanceRepository(client), raw


def make_record(record_id: str, captured_day: int = 1) -> AppendOnlyRecord:
    captured = datetime(2026, 1, captured_day, tzinfo=timezone.utc)
    return AppendOnlyRecord(
        record_id=record_id,
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=captured,
        updated_at=captured,
        payload={
            "entity_id": "22222222-2222-4222-8222-222222222222",
            "relationship_id": "11111111-1111-4111-8111-111111111111",
            "source_system": "cmdb",
            "source_identifier": "entity-1",
            "captured_at": captured,
            "evidence": {"field": "owner"},
        },
    )


def test_append_get_source_and_subject_queries_are_tenant_scoped() -> None:
    repository, raw = make_repository()
    first = repository.append(make_record("cccccccc-cccc-4ccc-8ccc-ccccccccccc1", 1))
    repository.append(make_record("cccccccc-cccc-4ccc-8ccc-ccccccccccc2", 2))
    tenant = TenantContext("org-1", "tenant-1")

    assert repository.get(tenant, first.record_id) is not None
    assert len(repository.find_by_source_identity(tenant, "cmdb", "entity-1")) == 2
    assert len(repository.list_by_entity(tenant, "22222222-2222-4222-8222-222222222222")) == 2
    assert len(repository.list_by_relationship(tenant, "11111111-1111-4111-8111-111111111111")) == 2
    assert repository.get(TenantContext("org-1", "tenant-2"), first.record_id) is None
    assert tenant_filters_seen(raw, "data_fabric.provenance_records")


def test_provenance_duplicate_and_update_are_rejected() -> None:
    repository, _ = make_repository()
    record = make_record("cccccccc-cccc-4ccc-8ccc-ccccccccccc1")
    repository.append(record)

    with pytest.raises(SupabaseAdapterOperationError):
        repository.append(record)
    with pytest.raises(SupabaseAdapterOperationError):
        repository.update(record)
