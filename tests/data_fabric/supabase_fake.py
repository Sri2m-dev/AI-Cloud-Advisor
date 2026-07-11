"""Fake Supabase client for P3 adapter unit tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class FakeResponse:
    def __init__(self, data: Any = None, error: Any = None) -> None:
        self.data = data
        self.error = error


PRIMARY_KEYS = {
    "data_fabric.enterprise_relationships": "id",
    "data_fabric.entity_versions": "snapshot_id",
    "data_fabric.lineage_events": "event_id",
    "data_fabric.provenance_records": "provenance_id",
    "data_fabric.enterprise_entities": "id",
}


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
        self.raw_client.executed_filters.append((self.name, tuple(self.filters)))
        rows = self.raw_client.tables.setdefault(self.name, [])
        if self.operation == "insert":
            row = deepcopy(self.payload or {})
            error = self.raw_client.insert_error(self.name, row)
            if error:
                return FakeResponse(error=error)
            rows.append(row)
            return FakeResponse([deepcopy(row)])
        selected = [deepcopy(row) for row in rows if self._matches(row)]
        if self.ordering:
            field, descending = self.ordering
            selected = sorted(selected, key=lambda row: (row.get(field) is None, row.get(field)), reverse=descending)
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
        self.raw_client.rpc_calls.append((self.function_name, deepcopy(self.params)))
        if self.function_name == "data_fabric_update_enterprise_relationship":
            return self._update_mutable(
                "data_fabric.enterprise_relationships",
                "p_relationship_id",
                "p_relationship",
            )
        if self.function_name == "data_fabric_update_enterprise_entity":
            return self._update_mutable("data_fabric.enterprise_entities", "p_entity_id", "p_entity")
        return FakeResponse(error="unknown rpc")

    def _update_mutable(self, table_name: str, id_param: str, payload_param: str) -> FakeResponse:
        table = self.raw_client.tables[table_name]
        for index, row in enumerate(table):
            if (
                row[PRIMARY_KEYS[table_name]] == self.params[id_param]
                and row["organization_id"] == self.params["p_organization_id"]
                and row["tenant_id"] == self.params["p_tenant_id"]
                and row["revision"] == self.params["p_expected_revision"]
            ):
                updated = deepcopy(self.params[payload_param])
                updated["revision"] = row["revision"] + 1
                table[index] = updated
                return FakeResponse([deepcopy(updated)])
        return FakeResponse([])


class FakeRawSupabaseClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "data_fabric.enterprise_entities": [],
            "data_fabric.enterprise_relationships": [],
            "data_fabric.entity_versions": [],
            "data_fabric.lineage_events": [],
            "data_fabric.provenance_records": [],
        }
        self.executed_filters: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []

    def table(self, name: str) -> FakeTable:
        return FakeTable(self, name)

    def rpc(self, function_name: str, params: dict[str, Any]) -> FakeRpcOperation:
        return FakeRpcOperation(self, function_name, params)

    def insert_error(self, table_name: str, row: dict[str, Any]) -> str | None:
        rows = self.tables.setdefault(table_name, [])
        primary = PRIMARY_KEYS.get(table_name)
        if primary and any(existing[primary] == row[primary] for existing in rows):
            return f"duplicate {primary}"
        if table_name == "data_fabric.enterprise_relationships":
            for existing in rows:
                if (
                    existing.get("active", True)
                    and row.get("active", True)
                    and existing["organization_id"] == row["organization_id"]
                    and existing["tenant_id"] == row["tenant_id"]
                    and existing["source_entity_id"] == row["source_entity_id"]
                    and existing["target_entity_id"] == row["target_entity_id"]
                    and existing["relationship_type"] == row["relationship_type"]
                ):
                    return "duplicate active relationship"
        if table_name == "data_fabric.entity_versions":
            for existing in rows:
                if (
                    existing["organization_id"] == row["organization_id"]
                    and existing["tenant_id"] == row["tenant_id"]
                    and existing["entity_id"] == row["entity_id"]
                    and existing["version"] == row["version"]
                ):
                    return "duplicate entity version"
        return None


def tenant_filters_seen(raw_client: FakeRawSupabaseClient, table_name: str) -> bool:
    scoped = [filters for name, filters in raw_client.executed_filters if name == table_name and filters]
    return bool(scoped) and all(
        any(column == "organization_id" for column, _ in filters)
        and any(column == "tenant_id" for column, _ in filters)
        for filters in scoped
    )
