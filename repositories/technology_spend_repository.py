"""Tenant-scoped persistence for the Finance persona landing page."""

from __future__ import annotations

from typing import Any, Protocol

from database.db import get_db


def _spend_value(row: dict[str, Any], new_key: str, old_key: str) -> float:
    return float(row.get(new_key, row.get(old_key, 0)) or 0)


class TechnologySpendRepository(Protocol):
    def get_enterprise_spend_breakdown(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_managed_services_cost(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_saas_cost(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_budget_vs_actual(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_enterprise_forecast(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_recommendations(self, organization_id: str) -> list[dict[str, Any]]: ...
    def get_executive_summary(self, organization_id: str) -> dict[str, Any]: ...


class SQLiteTechnologySpendRepository:
    """Read optional local finance marts without crossing tenant boundaries."""

    _TABLES = frozenset(
        {
            "mart_enterprise_spend_v2",
            "managed_services_cost",
            "saas_cost",
            "mart_budget_vs_actual",
            "mart_enterprise_forecast",
            "recommendations",
            "mart_executive_summary",
        }
    )

    def __init__(self, connection_factory=get_db) -> None:
        self.connection_factory = connection_factory

    @staticmethod
    def _require_organization(organization_id: str) -> str:
        value = str(organization_id or "").strip()
        if not value:
            raise ValueError("organization_id is required for technology spend")
        return value

    def _rows(self, table: str, organization_id: str, *, limit: int | None = None):
        if table not in self._TABLES:
            raise ValueError("unsupported technology spend table")
        organization_id = self._require_organization(organization_id)
        conn = self.connection_factory()
        try:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone():
                return []
            columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
            scope = next(
                (name for name in ("organization_id", "org_id", "tenant_id") if name in columns),
                None,
            )
            if scope is None:
                return []
            sql = f"SELECT * FROM {table} WHERE {scope} = ?"
            params: tuple[Any, ...] = (organization_id,)
            if limit is not None:
                sql += " LIMIT ?"
                params += (int(limit),)
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_enterprise_spend_breakdown(self, organization_id):
        return self._rows("mart_enterprise_spend_v2", organization_id)

    def get_managed_services_cost(self, organization_id):
        return self._rows("managed_services_cost", organization_id)

    def get_saas_cost(self, organization_id):
        return self._rows("saas_cost", organization_id)

    def get_budget_vs_actual(self, organization_id):
        return self._rows("mart_budget_vs_actual", organization_id)

    def get_enterprise_forecast(self, organization_id):
        return self._rows("mart_enterprise_forecast", organization_id)

    def get_recommendations(self, organization_id):
        return self._rows("recommendations", organization_id)

    def get_executive_summary(self, organization_id):
        rows = self._rows("mart_executive_summary", organization_id, limit=1)
        return rows[0] if rows else {}


class SupabaseTechnologySpendRepository:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _rows(self, table: str, organization_id: str, *, limit: int | None = None):
        organization_id = SQLiteTechnologySpendRepository._require_organization(organization_id)
        try:
            query = (
                self.client.table(table)
                .select("*")
                .eq("organization_id", organization_id)
            )
            if limit is not None:
                query = query.limit(limit)
            return [dict(row) for row in query.execute().data or []]
        except Exception:
            # Optional legacy marts may be absent or lack an explicit scope
            # column. Never retry them with an unsafe unscoped query.
            return []

    def get_enterprise_spend_breakdown(self, organization_id):
        return self._rows("mart_enterprise_spend_v2", organization_id)

    def get_managed_services_cost(self, organization_id):
        return self._rows("managed_services_cost", organization_id)

    def get_saas_cost(self, organization_id):
        return self._rows("saas_cost", organization_id)

    def get_budget_vs_actual(self, organization_id):
        return self._rows("mart_budget_vs_actual", organization_id)

    def get_enterprise_forecast(self, organization_id):
        return self._rows("mart_enterprise_forecast", organization_id)

    def get_recommendations(self, organization_id):
        return self._rows("recommendations", organization_id)

    def get_executive_summary(self, organization_id):
        rows = self._rows("mart_executive_summary", organization_id, limit=1)
        return rows[0] if rows else {}


def technology_spend_kpis(repository: TechnologySpendRepository, organization_id: str):
    rows = repository.get_enterprise_spend_breakdown(organization_id)
    summary = rows[0] if rows else {}
    cloud = _spend_value(summary, "cloud_spend", "cloud_cost")
    saas = _spend_value(summary, "saas_spend", "saas_cost")
    msp = _spend_value(summary, "msp_spend", "msp_cost")
    license_cost = _spend_value(summary, "license_spend", "license_cost")
    return {
        "cloud_cost": cloud,
        "saas_cost": saas,
        "msp_cost": msp,
        "license_cost": license_cost,
        "total_spend": cloud + saas + msp + license_cost,
    }
