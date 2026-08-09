"""Persistence contract and implementations for Leadership Dashboard inputs."""

from __future__ import annotations

from typing import Any, Protocol

from database.db import get_db


class LeadershipRepository(Protocol):
    def get_enterprise_spend(self, organization_id: str) -> dict[str, Any]: ...

    def get_enterprise_spend_breakdown(self, organization_id: str) -> dict[str, Any]: ...

    def get_savings(self, organization_id: str) -> dict[str, Any]: ...

    def get_approval_requests(self, organization_id: str) -> list[dict[str, Any]]: ...

    def get_optimization_opportunities(
        self, organization_id: str
    ) -> list[dict[str, Any]]: ...

    def get_cost_anomalies(self, organization_id: str) -> list[dict[str, Any]]: ...

    def get_recommendations(self, organization_id: str) -> list[dict[str, Any]]: ...


class SQLiteLeadershipRepository:
    """Read leadership projections from tenant-scoped local SQLite tables."""

    _TABLES = frozenset(
        {
            "mart_enterprise_spend",
            "mart_enterprise_spend_breakdown",
            "mart_savings",
            "approval_requests",
            "mart_optimization_opportunities",
            "mart_cost_anomalies",
            "recommendations",
        }
    )

    def __init__(self, connection_factory=get_db) -> None:
        self.connection_factory = connection_factory

    @staticmethod
    def _require_organization(organization_id: str) -> str:
        normalized = str(organization_id or "").strip()
        if not normalized:
            raise ValueError("organization_id is required for leadership metrics")
        return normalized

    @staticmethod
    def _columns(conn, table_name: str) -> set[str]:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table_name})")}

    def _rows(
        self,
        table_name: str,
        organization_id: str,
        *,
        limit: int | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        if table_name not in self._TABLES:
            raise ValueError("unsupported leadership table")
        organization_id = self._require_organization(organization_id)
        conn = self.connection_factory()
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if not exists:
                return []
            columns = self._columns(conn, table_name)
            scope_column = next(
                (
                    column
                    for column in ("organization_id", "org_id", "tenant_id")
                    if column in columns
                ),
                None,
            )
            if scope_column is None:
                return []
            sql = f"SELECT * FROM {table_name} WHERE {scope_column} = ?"
            if order_by and order_by in columns:
                sql += f" ORDER BY {order_by} DESC"
            if limit is not None:
                sql += " LIMIT ?"
                rows = conn.execute(sql, (organization_id, int(limit))).fetchall()
            else:
                rows = conn.execute(sql, (organization_id,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_enterprise_spend(self, organization_id):
        rows = self._rows("mart_enterprise_spend", organization_id, limit=1)
        return rows[0] if rows else {}

    def get_enterprise_spend_breakdown(self, organization_id):
        rows = self._rows("mart_enterprise_spend_breakdown", organization_id, limit=1)
        return rows[0] if rows else {}

    def get_savings(self, organization_id):
        rows = self._rows("mart_savings", organization_id, limit=1)
        return rows[0] if rows else {}

    def get_approval_requests(self, organization_id):
        return self._rows("approval_requests", organization_id)

    def get_optimization_opportunities(self, organization_id):
        return self._rows(
            "mart_optimization_opportunities",
            organization_id,
            limit=10,
            order_by="total_cost",
        )

    def get_cost_anomalies(self, organization_id):
        return self._rows("mart_cost_anomalies", organization_id, limit=20)

    def get_recommendations(self, organization_id):
        return self._rows("recommendations", organization_id, limit=20)


class SupabaseLeadershipRepository:
    """Read the existing tenant-scoped Supabase leadership projections."""

    def __init__(self, client: Any) -> None:
        self.client = client

    @staticmethod
    def _require_organization(organization_id: str) -> str:
        return SQLiteLeadershipRepository._require_organization(organization_id)

    def _rows(
        self,
        table_name: str,
        organization_id: str,
        *,
        limit: int | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        organization_id = self._require_organization(organization_id)
        query = self.client.table(table_name).select("*").eq("organization_id", organization_id)
        if order_by:
            query = query.order(order_by, desc=True)
        if limit is not None:
            query = query.limit(limit)
        return [dict(row) for row in query.execute().data or []]

    def get_enterprise_spend(self, organization_id):
        rows = self._rows("mart_enterprise_spend", organization_id, limit=1)
        return rows[0] if rows else {}

    def get_enterprise_spend_breakdown(self, organization_id):
        rows = self._rows("mart_enterprise_spend_breakdown", organization_id, limit=1)
        return rows[0] if rows else {}

    def get_savings(self, organization_id):
        rows = self._rows("mart_savings", organization_id, limit=1)
        return rows[0] if rows else {}

    def get_approval_requests(self, organization_id):
        return self._rows("approval_requests", organization_id)

    def get_optimization_opportunities(self, organization_id):
        return self._rows(
            "mart_optimization_opportunities",
            organization_id,
            limit=10,
            order_by="total_cost",
        )

    def get_cost_anomalies(self, organization_id):
        return self._rows("mart_cost_anomalies", organization_id, limit=20)

    def get_recommendations(self, organization_id):
        return self._rows("recommendations", organization_id, limit=20)
