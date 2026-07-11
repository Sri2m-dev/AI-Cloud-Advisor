"""Unit tests for the P3 Supabase canonical entity repository foundation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pytest

from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient
from data_fabric.adapters.supabase.entity_repository import SupabaseEntityRepository
from data_fabric.adapters.supabase.exceptions import (
    SupabaseAdapterConflictError,
    SupabaseAdapterOperationError,
)
from data_fabric.contracts import EnterpriseEntity, EntityType
from data_fabric.foundation import TenantContext
from data_fabric.persistence.models import PageRequest, RepositoryQuery


class FakeResponse:
    def __init__(self, data: Any = None, error: Any = None) -> None:
        self.data = data
        self.error = error


class FakeTable:
    def __init__(self, raw_client: "FakeRawSupabaseClient", name: str) -> None:
        self.raw_client = raw_client
        self.name = name
        self.operation = "select"
        self.payload: dict[str, Any] | None = None
        self.filters: list[tuple[str, Any]] = []
        self.ordering: tuple[str, bool] | None = None
        self.range_bounds: tuple[int, int] | None = None
        self.limit_count: int | None = None

    def select(self, columns: str = "*") -> "FakeTable":
        self.operation = "select"
        return self

    def insert(self, payload: dict[str, Any]) -> "FakeTable":
        self.operation = "insert"
        self.payload = deepcopy(payload)
        return self

    def update(self, payload: dict[str, Any]) -> "FakeTable":
        self.operation = "update"
        self.payload = deepcopy(payload)
        return self

    def eq(self, column: str, value: Any) -> "FakeTable":
        self.filters.append((column, value))
        return self

    def order(self, column: str, desc: bool = False) -> "FakeTable":
        self.ordering = (column, desc)
        return self

    def range(self, start: int, end: int) -> "FakeTable":
        self.range_bounds = (start, end)
        return self

    def limit(self, count: int) -> "FakeTable":
        self.limit_count = count
        return self

    def execute(self) -> FakeResponse:
        self.raw_client.executed_filters.append(tuple(self.filters))
        rows = self.raw_client.tables.setdefault(self.name, [])
        if self.operation == "insert":
            row = deepcopy(self.payload or {})
            rows.append(row)
            return FakeResponse([deepcopy(row)])
        selected = [deepcopy(row) for row in rows if self._matches(row)]
        if self.ordering:
            field, descending = self.ordering
            selected = sorted(selected, key=lambda row: row.get(field), reverse=descending)
        if self.range_bounds:
            start, end = self.range_bounds
            selected = selected[start : end + 1]
        if self.limit_count is not None:
            selected = selected[: self.limit_count]
        return FakeResponse(selected)

    def _matches(self, row: dict[str, Any]) -> bool:
        for column, value in self.filters:
            if column.startswith("metadata->"):
                field = column.split("->", 1)[1]
                if row.get("metadata", {}).get(field) != value:
                    return False
            elif row.get(column) != value:
                return False
        return True


class FakeRpcOperation:
    def __init__(self, raw_client: "FakeRawSupabaseClient", function_name: str, params: dict[str, Any]) -> None:
        self.raw_client = raw_client
        self.function_name = function_name
        self.params = deepcopy(params)

    def execute(self) -> FakeResponse:
        if self.function_name != "data_fabric_update_enterprise_entity":
            return FakeResponse(error="unknown rpc")
        self.raw_client.rpc_calls.append((self.function_name, deepcopy(self.params)))
        table = self.raw_client.tables["data_fabric.enterprise_entities"]
        for index, row in enumerate(table):
            if (
                row["id"] == self.params["p_entity_id"]
                and row["organization_id"] == self.params["p_organization_id"]
                and row["tenant_id"] == self.params["p_tenant_id"]
                and row["revision"] == self.params["p_expected_revision"]
            ):
                updated = deepcopy(self.params["p_entity"])
                updated["revision"] = row["revision"] + 1
                table[index] = updated
                return FakeResponse([deepcopy(updated)])
        return FakeResponse([])


class FakeRawSupabaseClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {"data_fabric.enterprise_entities": []}
        self.executed_filters: list[tuple[tuple[str, Any], ...]] = []
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []

    def table(self, name: str) -> FakeTable:
        return FakeTable(self, name)

    def rpc(self, function_name: str, params: dict[str, Any]) -> FakeRpcOperation:
        return FakeRpcOperation(self, function_name, params)


def make_repository() -> tuple[SupabaseEntityRepository, FakeRawSupabaseClient]:
    raw_client = FakeRawSupabaseClient()
    config = DataFabricDatabaseConfig(
        "https://example.supabase.co",
        "server-side-secret",
        max_retries=0,
    )
    client = SupabaseDataFabricClient(config, raw_client=raw_client)
    return SupabaseEntityRepository(client), raw_client


def make_entity(entity_id: str = "entity-1", canonical_id: str = "canonical-1") -> EnterpriseEntity:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return EnterpriseEntity(
        id=entity_id,
        canonical_id=canonical_id,
        entity_type=EntityType.APPLICATION,
        name="Nexora Core",
        source_system="cmdb",
        source_identifier=f"cmdb-{entity_id}",
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=now,
        updated_at=now,
        confidence_score=0.84,
        quality_score=0.91,
        tags=["tier-1", "owned"],
        metadata={"owner": "platform"},
    )


def test_add_and_get_entity_round_trips_contract_fields() -> None:
    repository, raw_client = make_repository()
    entity = make_entity()

    record = repository.add(entity)
    fetched = repository.get(TenantContext("org-1", "tenant-1"), "entity-1")

    assert record.record_id == "entity-1"
    assert fetched is not None
    assert fetched.payload["canonical_id"] == "canonical-1"
    assert fetched.payload["entity_type"] == "application"
    assert fetched.payload["confidence_score"] == pytest.approx(0.84)
    assert fetched.payload["quality_score"] == pytest.approx(0.91)
    assert raw_client.tables["data_fabric.enterprise_entities"][0]["confidence_score"] == pytest.approx(84.0)
    assert raw_client.tables["data_fabric.enterprise_entities"][0]["quality_score"] == pytest.approx(91.0)


def test_repository_applies_tenant_filters_to_reads() -> None:
    repository, raw_client = make_repository()
    repository.add(make_entity())

    assert repository.get(TenantContext("org-1", "tenant-2"), "entity-1") is None
    assert repository.find_by_canonical_id(TenantContext("org-1", "tenant-1"), "canonical-1") is not None
    assert repository.find_by_source_identity(
        TenantContext("org-1", "tenant-1"),
        "cmdb",
        "cmdb-entity-1",
    ) is not None

    filter_sets = raw_client.executed_filters
    tenant_scoped = [filters for filters in filter_sets if ("organization_id", "org-1") in filters]
    assert tenant_scoped
    assert all(any(column == "tenant_id" for column, _ in filters) for filters in tenant_scoped)


def test_update_uses_rpc_revision_check_and_advances_revision() -> None:
    repository, raw_client = make_repository()
    original = repository.add(make_entity())
    changed = replace(original, payload={**dict(original.payload), "name": "Nexora Core Updated"})

    updated = repository.update(changed, expected_revision=1)

    assert updated.revision == 2
    assert updated.payload["name"] == "Nexora Core Updated"
    assert raw_client.rpc_calls[0][1]["p_expected_revision"] == 1
    assert raw_client.rpc_calls[0][1]["p_tenant_id"] == "tenant-1"


def test_update_raises_conflict_for_stale_revision() -> None:
    repository, _ = make_repository()
    original = repository.add(make_entity())
    changed = replace(original, payload={**dict(original.payload), "name": "Changed"})
    repository.update(changed, expected_revision=1)

    with pytest.raises(SupabaseAdapterConflictError):
        repository.update(changed, expected_revision=1)


def test_deactivate_soft_deletes_and_default_reads_hide_inactive_records() -> None:
    repository, _ = make_repository()
    repository.add(make_entity())

    deactivated = repository.deactivate(
        TenantContext("org-1", "tenant-1"),
        "entity-1",
        deactivated_by="reviewer",
    )

    assert deactivated.active is False
    assert deactivated.deactivated_by == "reviewer"
    assert repository.get(TenantContext("org-1", "tenant-1"), "entity-1") is None
    assert repository.get(TenantContext("org-1", "tenant-1"), "entity-1", include_inactive=True) is not None


def test_search_supports_filters_ordering_and_pagination() -> None:
    repository, _ = make_repository()
    repository.add(make_entity("entity-1", "canonical-1"))
    second = make_entity("entity-2", "canonical-2")
    second.name = "Another App"
    repository.add(second)

    query = RepositoryQuery(
        TenantContext("org-1", "tenant-1"),
        filters={"entity_type": "application"},
        page=PageRequest(offset=1, limit=1),
    )

    result = repository.search(query)

    assert result.total_count == 1
    assert result.items[0].record_id == "entity-2"


def test_client_execute_normalizes_errors_and_retries() -> None:
    config = DataFabricDatabaseConfig(
        "https://example.supabase.co",
        "server-side-secret",
        max_retries=1,
        retry_backoff_seconds=0,
    )
    client = SupabaseDataFabricClient(config, raw_client=FakeRawSupabaseClient())
    calls = {"count": 0}

    def flaky_operation() -> FakeResponse:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary failure")
        return FakeResponse([])

    assert client.execute(flaky_operation).data == []
    assert calls["count"] == 2

    with pytest.raises(SupabaseAdapterOperationError):
        client.execute(lambda: FakeResponse(error="boom"))


def test_domain_input_is_not_mutated_by_repository_mapping() -> None:
    repository, _ = make_repository()
    entity = make_entity()
    original_tags = list(entity.tags)
    original_metadata = dict(entity.metadata)

    repository.add(entity)

    assert entity.tags == original_tags
    assert entity.metadata == original_metadata
