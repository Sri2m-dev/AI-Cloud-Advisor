from types import SimpleNamespace

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext, AuthenticatedTenantError
from services import analytics_service

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"


def _context(organization_id, user_id="user-a"):
    return AuthenticatedTenantContext(
        organization_id=organization_id,
        organization_name="Authorized Organization",
        user_id=user_id,
        user_email=f"{user_id}@example.test",
        role="finance",
        authorization_claims=frozenset(),
        tenant_id=organization_id,
    )


class FakeQuery:
    def __init__(self, rows, calls=None):
        self.rows = rows
        self.calls = calls if calls is not None else []

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def insert(self, payload):
        self.calls.append(("insert", payload))
        return self

    def order(self, column, desc=False):
        self.calls.append(("order", column, desc))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def execute(self):
        self.calls.append(("execute",))
        return SimpleNamespace(data=self.rows)


class FakeSupabase:
    def __init__(self, rows_by_org=None):
        self.rows_by_org = rows_by_org or {}
        self.calls = []

    def table(self, table_name):
        self.calls.append(("table", table_name))
        return FakeQuery([], self.calls)

    def tenant_table(self, table_name, context):
        self.calls.append(("tenant_table", table_name, context.organization_id))
        return FakeQuery(
            self.rows_by_org.get(context.organization_id, []),
            self.calls,
        )


def test_missing_tenant_context_does_not_fall_back_to_default(monkeypatch):
    monkeypatch.setattr(
        analytics_service,
        "authenticated_tenant_context",
        lambda _session: (_ for _ in ()).throw(AuthenticatedTenantError("session required")),
        raising=False,
    )
    monkeypatch.setattr(analytics_service.st, "session_state", {})

    with pytest.raises(AuthenticatedTenantError):
        analytics_service._effective_org_id()


def test_supabase_tenant_context_carries_a_verified_access_token():
    user_id = "11111111-1111-4111-8111-111111111112"
    auth_session = SimpleNamespace(access_token="signed-supabase-access-token")
    session = {
        "authenticated": True,
        "auth_backend": "supabase",
        "organization_id": ORG_A,
        "authorized_organization_ids": [ORG_A],
        "user_id": user_id,
        "user": SimpleNamespace(id=user_id, email="customer@example.test"),
        "email": "customer@example.test",
        "role": "finance",
        "profile": {
            "auth_user_id": user_id,
            "org_id": ORG_A,
            "role": "finance",
        },
        "auth_client": SimpleNamespace(
            auth=SimpleNamespace(get_session=lambda: auth_session)
        ),
    }

    context = AuthenticatedTenantContext.from_session(
        session,
        organization_resolver=lambda organization_id: (
            "Authorized Organization" if organization_id == ORG_A else None
        ),
    )
    assert context.auth_access_token == auth_session.access_token
    assert "signed-supabase-access-token" not in repr(context)


def test_supabase_tenant_context_rejects_missing_access_token():
    user_id = "11111111-1111-4111-8111-111111111112"
    session = {
        "authenticated": True,
        "auth_backend": "supabase",
        "organization_id": ORG_A,
        "authorized_organization_ids": [ORG_A],
        "user_id": user_id,
        "user": SimpleNamespace(id=user_id, email="customer@example.test"),
        "email": "customer@example.test",
        "profile": {
            "auth_user_id": user_id,
            "org_id": ORG_A,
            "role": "finance",
        },
        "auth_client": SimpleNamespace(
            auth=SimpleNamespace(get_session=lambda: None)
        ),
    }
    with pytest.raises(AuthenticatedTenantError, match="verified Supabase access token"):
        AuthenticatedTenantContext.from_session(
            session,
            organization_resolver=lambda organization_id: (
                "Authorized Organization" if organization_id == ORG_A else None
            ),
        )


def test_user_supplied_tenant_must_match_authenticated_membership(monkeypatch):
    monkeypatch.setattr(
        analytics_service,
        "authenticated_tenant_context",
        lambda _session: _context(ORG_A),
        raising=False,
    )
    monkeypatch.setattr(analytics_service.st, "session_state", {})

    with pytest.raises(AuthenticatedTenantError):
        analytics_service._effective_org_id(ORG_B)


def test_cached_analytics_data_cannot_bypass_current_session_authorization(monkeypatch):
    fake = FakeSupabase(
        {
            ORG_A: [{"org_id": ORG_A, "id": "tenant-a-row"}],
        }
    )
    monkeypatch.setattr(analytics_service, "supabase", fake)
    monkeypatch.setattr(analytics_service.st, "session_state", {})
    monkeypatch.setattr(
        analytics_service,
        "authenticated_tenant_context",
        lambda _session: _context(ORG_A),
    )
    analytics_service.AnalyticsService.get_recommendations.clear()

    result = analytics_service.AnalyticsService.get_recommendations(ORG_A)
    assert result[0]["id"] == "tenant-a-row"

    monkeypatch.setattr(
        analytics_service,
        "authenticated_tenant_context",
        lambda _session: (_ for _ in ()).throw(AuthenticatedTenantError("session required")),
    )
    with pytest.raises(AuthenticatedTenantError):
        analytics_service.AnalyticsService.get_recommendations(ORG_A)


def test_untrusted_tenant_filter_cannot_authorize_privileged_read():
    from services.supabase_client import _TenantGuardedQuery

    calls = []
    query = FakeQuery([{"id": "tenant-b-row"}], calls)
    response = (
        _TenantGuardedQuery(query, table_name="recommendations")
        .select("*")
        .eq("org_id", ORG_B)
        .execute()
    )

    assert response.data == []
    assert ("execute",) not in calls


def test_untrusted_tenant_filter_cannot_authorize_privileged_write():
    from services.supabase_client import TenantScopeRequiredError, _TenantGuardedQuery

    calls = []
    query = FakeQuery([], calls)
    with pytest.raises(TenantScopeRequiredError):
        (
            _TenantGuardedQuery(query, table_name="recommendations")
            .insert({"org_id": ORG_B, "id": "cross-tenant"})
            .execute()
        )
    assert ("execute",) not in calls


def test_authenticated_tenant_scope_restricts_reads_and_writes(monkeypatch):
    from services import supabase_client

    calls = []
    fake_client = SimpleNamespace(table=lambda name: FakeQuery([{"id": "tenant-a-row"}], calls))
    monkeypatch.setattr(supabase_client.supabase, "_client", fake_client)
    context = _context(ORG_A)

    response = (
        supabase_client.supabase.tenant_table("recommendations", context)
        .select("*")
        .eq("org_id", ORG_A)
        .execute()
    )
    assert response.data == [{"id": "tenant-a-row"}]

    with pytest.raises(supabase_client.TenantScopeRequiredError):
        (
            supabase_client.supabase.tenant_table("recommendations", context)
            .select("*")
            .eq("org_id", ORG_B)
            .execute()
        )
    with pytest.raises(supabase_client.TenantScopeRequiredError):
        supabase_client.supabase.tenant_table("recommendations", context).insert(
            {"org_id": ORG_B, "id": "cross-tenant-row"}
        )

    write_calls = []
    fake_client = SimpleNamespace(table=lambda name: FakeQuery([], write_calls))
    monkeypatch.setattr(supabase_client.supabase, "_client", fake_client)
    (
        supabase_client.supabase.tenant_table("recommendations", context)
        .insert({"org_id": ORG_A, "id": "tenant-a-row"})
        .execute()
    )
    assert ("execute",) in write_calls


def test_cost_intelligence_queries_require_context_and_partition_cache(monkeypatch):
    from repositories import cost_intelligence_repository as repository

    fake = FakeSupabase(
        {
            ORG_A: [{"org_id": ORG_A, "amount": 10}],
            ORG_B: [{"org_id": ORG_B, "amount": 99}],
        }
    )
    monkeypatch.setattr(repository, "supabase", fake)
    repository.CostIntelligenceRepository.get_recommendations.clear()
    result_a = repository.CostIntelligenceRepository.get_recommendations(_context(ORG_A))
    result_b = repository.CostIntelligenceRepository.get_recommendations(
        _context(ORG_B, user_id="user-b")
    )

    assert result_a[0]["org_id"] == ORG_A
    assert result_b[0]["org_id"] == ORG_B
    assert ("tenant_table", "recommendations", ORG_A) in fake.calls
    assert ("tenant_table", "recommendations", ORG_B) in fake.calls


def test_unverified_cost_mart_scope_column_is_not_guessed():
    from services.supabase_client import TenantScopeRequiredError, supabase

    with pytest.raises(TenantScopeRequiredError, match="verified tenant column"):
        supabase.tenant_table("mart_enterprise_forecast", _context(ORG_A))


def test_forecasting_read_failure_never_retries_without_tenant_filter(monkeypatch):
    from repositories import forecasting_repository
    from repositories.forecasting_repository import ForecastingRepository

    calls = []

    class FailingScopedQuery(FakeQuery):
        def execute(self):
            calls.append(("execute",))
            raise RuntimeError("scoped query failed")

    class FailingScopedClient:
        def table(self, table_name):
            calls.append(("table", table_name))
            return FailingScopedQuery([], calls)

    monkeypatch.setattr(forecasting_repository, "supabase", FailingScopedClient())
    with pytest.raises(RuntimeError, match="scoped query failed"):
        ForecastingRepository._fetch_table("mart_enterprise_forecast", ORG_A)
    assert calls.count(("table", "mart_enterprise_forecast")) == 1


def test_service_explorer_financial_reads_are_disabled_until_scoped():
    from services.supabase_client import LEGACY_FINANCIAL_TABLES, _TenantGuardedQuery

    for table_name in ("mart_service_classification", "mart_ai_recommendations"):
        assert table_name in LEGACY_FINANCIAL_TABLES
        calls = []
        response = (
            _TenantGuardedQuery(FakeQuery([{"id": "unscoped"}], calls), table_name=table_name)
            .select("*")
            .execute()
        )
        assert response.data == []
        assert ("execute",) not in calls
