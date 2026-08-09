"""Tenant-scoped persistence for the Operations persona landing page."""

from __future__ import annotations

from typing import Any, Protocol

from database.db import get_db


class OperationsWorkspaceRepository(Protocol):
    def get_approval_requests(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_recommendations(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_audit_events(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_cost_anomalies(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_cloud_costs(self, organization_id: str) -> list[dict[str, Any]]: ...


class SQLiteOperationsWorkspaceRepository:
    _TABLES = frozenset(
        {
            "approval_requests",
            "recommendations",
            "audit_events",
            "cost_anomaly_org_view",
            "unified_cloud_costs",
        }
    )

    def __init__(self, connection_factory=get_db) -> None:
        self.connection_factory = connection_factory

    @staticmethod
    def _require_organization(organization_id: str) -> str:
        value = str(organization_id or "").strip()
        if not value:
            raise ValueError("organization_id is required for operations workspace")
        return value

    def _rows(self, table, organization_id, *, limit):
        if table not in self._TABLES:
            raise ValueError("unsupported operations workspace table")
        organization_id = self._require_organization(organization_id)
        conn = self.connection_factory()
        try:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE (type = 'table' OR type = 'view') AND name = ?",
                (table,),
            ).fetchone():
                return []
            columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
            scope = next(
                (name for name in ("organization_id", "org_id", "tenant_id") if name in columns),
                None,
            )
            if scope is None:
                return []
            order = " ORDER BY created_at DESC" if "created_at" in columns else ""
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {scope} = ?{order} LIMIT ?",
                (organization_id, int(limit)),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_approval_requests(self, organization_id):
        return self._rows("approval_requests", organization_id, limit=50)

    def get_recommendations(self, organization_id):
        return self._rows("recommendations", organization_id, limit=50)

    def get_audit_events(self, organization_id):
        return self._rows("audit_events", organization_id, limit=50)

    def get_cost_anomalies(self, organization_id):
        return self._rows("cost_anomaly_org_view", organization_id, limit=100)

    def get_cloud_costs(self, organization_id):
        return self._rows("unified_cloud_costs", organization_id, limit=1000)


class SupabaseOperationsWorkspaceRepository:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _rows(self, table, organization_id, *, limit, order=False):
        organization_id = SQLiteOperationsWorkspaceRepository._require_organization(organization_id)
        try:
            query = (
                self.client.table(table)
                .select("*")
                .eq("organization_id", organization_id)
            )
            if order:
                query = query.order("created_at", desc=True)
            return [dict(row) for row in query.limit(limit).execute().data or []]
        except Exception:
            # Never retry a legacy or optional table without tenant scope.
            return []

    def get_approval_requests(self, organization_id):
        return self._rows("approval_requests", organization_id, limit=50, order=True)

    def get_recommendations(self, organization_id):
        return self._rows("recommendations", organization_id, limit=50, order=True)

    def get_audit_events(self, organization_id):
        return self._rows("audit_events", organization_id, limit=50, order=True)

    def get_cost_anomalies(self, organization_id):
        return self._rows("cost_anomaly_org_view", organization_id, limit=100)

    def get_cloud_costs(self, organization_id):
        return self._rows("unified_cloud_costs", organization_id, limit=1000)
