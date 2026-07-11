"""Unit tests for the P3.14 Supabase entity version repository."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient, SupabaseVersionRepository
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError, SupabaseAdapterOperationError
from data_fabric.foundation import TenantContext
from data_fabric.persistence.models import AppendOnlyRecord
from tests.data_fabric.supabase_fake import FakeRawSupabaseClient, tenant_filters_seen


def make_repository() -> tuple[SupabaseVersionRepository, FakeRawSupabaseClient]:
    raw = FakeRawSupabaseClient()
    client = SupabaseDataFabricClient(DataFabricDatabaseConfig("https://example.supabase.co", "server-side-secret", max_retries=0), raw_client=raw)
    return SupabaseVersionRepository(client), raw


def make_version(snapshot_id: str, version: int) -> AppendOnlyRecord:
    now = datetime(2026, 1, max(version, 1), tzinfo=timezone.utc)
    return AppendOnlyRecord(
        record_id=snapshot_id,
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=now,
        updated_at=now,
        payload={
            "entity_id": "22222222-2222-4222-8222-222222222222",
            "canonical_id": "canonical-1",
            "version": version,
            "source_system": "cmdb",
            "source_identifier": "entity-1",
            "effective_from": now,
            "payload": {"name": f"Entity v{version}"},
        },
    )


def test_append_latest_ordering_hash_lookup_and_tenant_isolation() -> None:
    repository, raw = make_repository()
    first = repository.append(make_version("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1", 1))
    second = repository.append(make_version("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2", 2))
    tenant = TenantContext("org-1", "tenant-1")

    assert repository.get_snapshot(tenant, first.record_id) is not None
    assert repository.get_latest_for_entity(tenant, "22222222-2222-4222-8222-222222222222").record_id == second.record_id
    assert [record.payload["version"] for record in repository.list_entity_versions(tenant, "22222222-2222-4222-8222-222222222222")] == [1, 2]
    assert repository.find_by_payload_hash(tenant, first.payload_hash)
    assert repository.get_snapshot(TenantContext("org-1", "tenant-2"), first.record_id) is None
    assert tenant_filters_seen(raw, "data_fabric.entity_versions")


def test_duplicate_and_out_of_order_versions_are_rejected() -> None:
    repository, _ = make_repository()
    repository.append(make_version("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1", 1))

    with pytest.raises(SupabaseAdapterConflictError):
        repository.append(make_version("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2", 1))

    with pytest.raises(SupabaseAdapterOperationError):
        repository.append(make_version("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0", 0))


def test_update_is_unsupported_for_append_only_versions() -> None:
    repository, _ = make_repository()
    record = make_version("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1", 1)

    with pytest.raises(SupabaseAdapterOperationError):
        repository.update(record)
