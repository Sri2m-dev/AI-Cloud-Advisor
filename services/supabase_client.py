"""
Central Supabase client initialization for the entire app.
"""

from dataclasses import dataclass
from typing import Any

from config.settings import (
    SUPABASE_KEY,
    SUPABASE_URL,
)
from supabase import create_client

LEGACY_FINANCIAL_TABLES = frozenset(
    {
        "application_cost_allocations",
        "application_spend_mapping",
        "cost_anomaly_org_view",
        "cost_anomaly_view",
        "cost_allocations",
        "cost_usage_tracking",
        "license_cost",
        "mart_budget_vs_actual",
        "mart_cost_anomalies",
        "mart_cost_forecast",
        "mart_cost_trend",
        "mart_enterprise_forecast",
        "mart_enterprise_spend",
        "mart_enterprise_spend_breakdown",
        "mart_enterprise_spend_v2",
        "mart_executive_summary",
        "mart_optimization_opportunities",
        "mart_recommendations",
        "mart_savings",
        "managed_services_cost",
        "recommendations",
        "saas_cost",
        "unified_cloud_costs",
        "vw_vendor_spend",
    }
)
TENANT_SCOPE_COLUMNS = frozenset({"organization_id", "org_id", "tenant_id"})
READ_METHODS = frozenset({"select"})
WRITE_METHODS = frozenset({"delete", "insert", "update", "upsert"})


class TenantScopeRequiredError(PermissionError):
    """Raised when a protected legacy financial write is not tenant scoped."""


@dataclass(slots=True)
class _EmptyQueryResponse:
    data: list[Any]
    count: int = 0


class _TenantGuardedQuery:
    """Carry explicit tenant scope across a PostgREST query chain."""

    def __init__(
        self,
        target: Any,
        *,
        table_name: str,
        scoped: bool = False,
        operation: str | None = None,
    ) -> None:
        self._target = target
        self._table_name = table_name
        self._scoped = scoped
        self._operation = operation

    def execute(self):
        if self._table_name in LEGACY_FINANCIAL_TABLES and not self._scoped:
            if self._operation in WRITE_METHODS:
                raise TenantScopeRequiredError(f"tenant scope is required for {self._table_name}")
            return _EmptyQueryResponse(data=[])
        return self._target.execute()

    def __getattr__(self, name: str):
        attribute = getattr(self._target, name)
        if not callable(attribute):
            return attribute

        def guarded_call(*args, **kwargs):
            result = attribute(*args, **kwargs)
            scoped = self._scoped
            if name == "eq" and len(args) >= 2:
                scoped = (
                    str(args[0]) in TENANT_SCOPE_COLUMNS and bool(str(args[1] or "").strip())
                ) or scoped
            operation = name if name in READ_METHODS | WRITE_METHODS else self._operation
            return _TenantGuardedQuery(
                result,
                table_name=self._table_name,
                scoped=scoped,
                operation=operation,
            )

        return guarded_call


class _SupabaseProxy:
    def __init__(self) -> None:
        self._client = None

    def _initialize(self):
        if self._client is None:
            print("\n" + "=" * 80)
            print("SUPABASE CLIENT INITIALIZATION")
            print(f"SUPABASE_URL: {SUPABASE_URL}")
            print(f"SUPABASE_KEY PRESENT: {bool(SUPABASE_KEY)}")

            if not SUPABASE_URL:
                raise RuntimeError("SUPABASE_URL is required to initialize the Supabase client")

            if not SUPABASE_KEY:
                raise RuntimeError("SUPABASE_KEY is required to initialize the Supabase client")

            self._client = create_client(
                SUPABASE_URL,
                SUPABASE_KEY,
            )

            print("Supabase client initialized successfully.")
            print("=" * 80 + "\n")

        return self._client

    def __getattr__(self, name):
        client = self._initialize()
        return getattr(client, name)

    def table(self, name: str):
        client = self._initialize()
        return _TenantGuardedQuery(client.table(name), table_name=name)


supabase = _SupabaseProxy()
