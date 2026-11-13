"""
Central Supabase client initialization for the entire app.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from postgrest import SyncPostgrestClient

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
        "technology_inventory",
        "business_services",
        "vw_department_spend",
        "vw_saas_renewal_risk",
        "vw_inactive_saas_users",
        "enterprise_cost_attribution",
        "impact_analysis_cache",
        "simulation_results",
        "ai_reasoning_history",
        "forecast_history",
        "prediction_accuracy",
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
        "mart_service_classification",
        "mart_ai_recommendations",
        "mart_savings",
        "managed_services_cost",
        "recommendations",
        "security_findings",
        "approval_queue",
        "saas_cost",
        "unified_cloud_costs",
        "vw_vendor_spend",
    }
)
VERIFIED_TENANT_COLUMNS = {
    "recommendations": "org_id",
    "mart_recommendations": "org_id",
    "mart_cost_anomalies": "org_id",
    "mart_optimization_opportunities": "org_id",
}
READ_METHODS = frozenset({"select"})
WRITE_METHODS = frozenset({"delete", "insert", "update", "upsert"})


def create_user_auth_client():
    """Create an uncached, per-session client with the explicitly public key."""
    anon_key = _supabase_anon_key()
    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is required to initialize the authentication client")
    if not anon_key:
        raise RuntimeError("SUPABASE_ANON_KEY is required to initialize the authentication client")
    return create_client(SUPABASE_URL, anon_key)


def _supabase_anon_key() -> str:
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if anon_key:
        return anon_key
    key_file = os.getenv("SUPABASE_ANON_KEY_FILE", "").strip()
    if key_file:
        return Path(key_file).read_text(encoding="utf-8").strip()
    return ""


def create_user_financial_data_client(auth_client):
    """Create a financial-data client carrying only the current Auth session token."""
    data_url = os.getenv("FINANCIAL_DATA_URL", "").strip()
    if data_url != "http://r5-financial-data-postgrest:3000":
        raise RuntimeError("the isolated r5 financial-data endpoint is not configured")

    anon_key = _supabase_anon_key()
    if not anon_key:
        raise RuntimeError("SUPABASE_ANON_KEY is required for financial-data access")
    if auth_client is None:
        raise PermissionError("an authenticated Supabase session is required")

    session = auth_client.auth.get_session()
    access_token = getattr(session, "access_token", None)
    if not isinstance(access_token, str) or not access_token.strip():
        raise PermissionError("a verified Supabase access token is required")

    client = SyncPostgrestClient(data_url, headers={"apikey": anon_key})
    client.auth(access_token)
    return client


class TenantScopeRequiredError(PermissionError):
    """Raised when protected financial access cannot prove tenant authorization."""


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
        authorized_tenant_id: str | None = None,
        tenant_column: str | None = None,
    ) -> None:
        self._target = target
        self._table_name = table_name
        self._scoped = scoped
        self._operation = operation
        self._authorized_tenant_id = authorized_tenant_id
        self._tenant_column = tenant_column

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
            protected = self._table_name in LEGACY_FINANCIAL_TABLES
            result = attribute(*args, **kwargs)
            scoped = self._scoped
            if protected and name == "eq" and len(args) >= 2:
                column = str(args[0])
                value = str(args[1] or "").strip()
                if (
                    self._authorized_tenant_id
                    and column == self._tenant_column
                    and value != self._authorized_tenant_id
                ):
                    raise TenantScopeRequiredError(
                        f"query tenant does not match authenticated tenant for {self._table_name}"
                    )
                scoped = bool(
                    self._authorized_tenant_id
                    and column == self._tenant_column
                    and value == self._authorized_tenant_id
                ) or scoped
            if protected and name in {"insert", "upsert", "update"}:
                payload = args[0] if args else kwargs.get("json")
                rows = payload if isinstance(payload, list) else [payload]
                if name in {"insert", "upsert"} and (
                    not rows
                    or any(
                        not isinstance(row, dict)
                        or row.get(self._tenant_column) != self._authorized_tenant_id
                        for row in rows
                    )
                ):
                    raise TenantScopeRequiredError(
                        f"write tenant must match authenticated tenant for {self._table_name}"
                    )
                if name in {"insert", "upsert"}:
                    scoped = bool(self._authorized_tenant_id)
                if name == "update" and any(
                    isinstance(row, dict)
                    and self._tenant_column in row
                    and row[self._tenant_column] != self._authorized_tenant_id
                    for row in rows
                ):
                    raise TenantScopeRequiredError(
                        f"write tenant must match authenticated tenant for {self._table_name}"
                    )
            operation = name if name in READ_METHODS | WRITE_METHODS else self._operation
            return _TenantGuardedQuery(
                result,
                table_name=self._table_name,
                scoped=scoped,
                operation=operation,
                authorized_tenant_id=self._authorized_tenant_id,
                tenant_column=self._tenant_column,
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

    def tenant_table(self, name: str, context):
        from auth.authenticated_tenant import AuthenticatedTenantContext

        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("AuthenticatedTenantContext is required")
        tenant_column = VERIFIED_TENANT_COLUMNS.get(name)
        if tenant_column is None:
            raise TenantScopeRequiredError(
                f"verified tenant column is unavailable for {name}"
            )
        client = self._initialize()
        return _TenantGuardedQuery(
            client.table(name),
            table_name=name,
            authorized_tenant_id=context.organization_id,
            tenant_column=tenant_column,
        )


supabase = _SupabaseProxy()
