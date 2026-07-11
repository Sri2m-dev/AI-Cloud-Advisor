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
    "data_fabric.quality_assessments": "assessment_id",
    "data_fabric.ontology_concepts": "concept_id",
    "data_fabric.ontology_relationships": "relationship_id",
    "data_fabric.semantic_mappings": "mapping_id",
    "data_fabric.idempotency_records": "idempotency_key",
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
        if self.function_name == "data_fabric_update_ontology_concept":
            return self._update_mutable("data_fabric.ontology_concepts", "p_concept_id", "p_concept")
        if self.function_name == "data_fabric_update_ontology_relationship":
            return self._update_mutable("data_fabric.ontology_relationships", "p_relationship_id", "p_relationship")
        if self.function_name == "data_fabric_update_semantic_mapping":
            return self._update_mutable("data_fabric.semantic_mappings", "p_mapping_id", "p_mapping")
        if self.function_name == "data_fabric_reserve_idempotency_key":
            return self._reserve_idempotency()
        if self.function_name == "data_fabric_complete_idempotency_key":
            return self._transition_idempotency("completed", result_payload=self.params.get("p_result_payload"))
        if self.function_name == "data_fabric_fail_idempotency_key":
            return self._transition_idempotency("failed", failure_reason=self.params.get("p_failure_reason"))
        if self.function_name == "data_fabric_expire_idempotency_key":
            return self._transition_idempotency("expired")
        return FakeResponse(error="unknown rpc")

    def _reserve_idempotency(self) -> FakeResponse:
        table = self.raw_client.tables["data_fabric.idempotency_records"]
        key = self.params["p_idempotency_key"]
        for row in table:
            if row["organization_id"] == self.params["p_organization_id"] and row["tenant_id"] == self.params["p_tenant_id"] and row["idempotency_key"] == key:
                if row["payload_hash"] != self.params["p_payload_hash"]:
                    return FakeResponse([])
                if row["status"] in {"failed", "expired"}:
                    row["status"] = "in_progress"
                    row["revision"] += 1
                return FakeResponse([deepcopy(row)])
        row = {"record_id": f"record-{key}", "organization_id": self.params["p_organization_id"], "tenant_id": self.params["p_tenant_id"], "idempotency_key": key, "payload_hash": self.params["p_payload_hash"], "status": "in_progress", "result_payload": {}, "failure_reason": None, "reserved_at": "2026-01-01T00:00:00+00:00", "completed_at": None, "failed_at": None, "expires_at": self.params.get("p_expires_at"), "correlation_id": self.params.get("p_correlation_id"), "revision": 1, "metadata": {}, "schema_version": 1}
        table.append(row)
        return FakeResponse([deepcopy(row)])

    def _transition_idempotency(self, status: str, result_payload=None, failure_reason=None) -> FakeResponse:
        table = self.raw_client.tables["data_fabric.idempotency_records"]
        for row in table:
            if row["organization_id"] == self.params["p_organization_id"] and row["tenant_id"] == self.params["p_tenant_id"] and row["idempotency_key"] == self.params["p_idempotency_key"] and row["status"] == "in_progress":
                row["status"] = status
                row["revision"] += 1
                if status == "completed":
                    row["result_payload"] = result_payload or {}
                    row["completed_at"] = "2026-01-01T00:01:00+00:00"
                elif status == "failed":
                    row["failure_reason"] = failure_reason
                    row["failed_at"] = "2026-01-01T00:01:00+00:00"
                elif status == "expired":
                    row["expires_at"] = row.get("expires_at") or "2026-01-01T00:01:00+00:00"
                return FakeResponse([deepcopy(row)])
        return FakeResponse([])

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
            "data_fabric.quality_assessments": [],
            "data_fabric.ontology_concepts": [],
            "data_fabric.ontology_relationships": [],
            "data_fabric.semantic_mappings": [],
            "data_fabric.idempotency_records": [],
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
        if table_name in {"data_fabric.ontology_concepts", "data_fabric.idempotency_records"}:
            if any(existing["organization_id"] == row["organization_id"] and existing["tenant_id"] == row["tenant_id"] and existing[primary] == row[primary] for existing in rows):
                return f"duplicate {primary}"
        elif primary and any(existing[primary] == row[primary] for existing in rows):
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
