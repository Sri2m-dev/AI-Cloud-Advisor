from __future__ import annotations

import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from repositories.operations_workspace_repository import (
    SQLiteOperationsWorkspaceRepository,
    SupabaseOperationsWorkspaceRepository,
)
from repositories.technology_spend_repository import (
    SQLiteTechnologySpendRepository,
    SupabaseTechnologySpendRepository,
)
from services.operations_workspace_composition import (
    OperationsWorkspaceConfigurationError,
    operations_workspace_repository,
)
from services.technology_spend_composition import (
    TechnologySpendConfigurationError,
    technology_spend_repository,
)

ORG_A = "org-a"
ORG_B = "org-b"


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []
        self.maximum = None

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, value):
        self.maximum = value
        return self

    def execute(self):
        rows = [
            dict(row)
            for row in self.rows
            if all(str(row.get(column)) == str(value) for column, value in self.filters)
        ]
        return _Response(rows[: self.maximum] if self.maximum is not None else rows)


class _Client:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _Query(self.tables.get(name, []))


def _tables():
    finance = {
        "mart_enterprise_spend_v2": [
            {"organization_id": ORG_A, "cloud_spend": 10.0},
            {"organization_id": ORG_B, "cloud_spend": 99.0},
        ],
        "managed_services_cost": [{"organization_id": ORG_A, "cost": 2.0}],
        "saas_cost": [{"organization_id": ORG_A, "cost": 3.0}],
        "mart_budget_vs_actual": [{"organization_id": ORG_A, "budget": 20.0}],
        "mart_enterprise_forecast": [{"organization_id": ORG_A, "amount": 12.0}],
        "mart_executive_summary": [{"organization_id": ORG_A, "optimization": 1.0}],
    }
    operations = {
        "approval_requests": [{"organization_id": ORG_A, "id": "approval-a"}],
        "recommendations": [
            {"organization_id": ORG_A, "id": "recommendation-a"},
            {"organization_id": ORG_B, "id": "recommendation-b"},
        ],
        "audit_events": [{"organization_id": ORG_A, "id": "audit-a"}],
        "cost_anomaly_org_view": [{"organization_id": ORG_A, "id": "anomaly-a"}],
        "unified_cloud_costs": [{"organization_id": ORG_A, "id": "cost-a"}],
    }
    finance["recommendations"] = operations["recommendations"]
    return finance | operations


@pytest.fixture
def sqlite_factory(tmp_path):
    path = tmp_path / "persona-runtime.db"
    conn = sqlite3.connect(path)
    for table, rows in _tables().items():
        columns = list(rows[0])
        definitions = ", ".join(
            f"{column} {'REAL' if isinstance(rows[0][column], float) else 'TEXT'}"
            for column in columns
        )
        conn.execute(f"CREATE TABLE {table} ({definitions})")
        placeholders = ", ".join("?" for _ in columns)
        conn.executemany(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            [[row[column] for column in columns] for row in rows],
        )
    conn.commit()
    conn.close()

    def connect():
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection

    return connect


@pytest.mark.parametrize(
    ("compose", "expected"),
    [
        (technology_spend_repository, SQLiteTechnologySpendRepository),
        (operations_workspace_repository, SQLiteOperationsWorkspaceRepository),
    ],
)
@pytest.mark.parametrize(
    ("url", "key"),
    [
        ("", ""),
        ("https://your-project.supabase.co", "replace-with-key"),
        ("not-a-url", "key"),
        ("https://database.example.com", "key"),
    ],
)
def test_development_missing_placeholder_and_invalid_use_sqlite(
    compose, expected, url, key, sqlite_factory
):
    selected = compose(
        environment="development",
        supabase_url=url,
        supabase_key=key,
        connection_factory=sqlite_factory,
    )
    assert isinstance(selected, expected)


@pytest.mark.parametrize(
    ("compose", "expected"),
    [
        (technology_spend_repository, SupabaseTechnologySpendRepository),
        (operations_workspace_repository, SupabaseOperationsWorkspaceRepository),
    ],
)
def test_valid_supabase_selects_supabase(compose, expected):
    selected = compose(
        environment="development",
        supabase_url="https://project-ref.supabase.co",
        supabase_key="configured-key",
        client=_Client(_tables()),
    )
    assert isinstance(selected, expected)


def test_production_invalid_configuration_fails_closed():
    with pytest.raises(TechnologySpendConfigurationError):
        technology_spend_repository(environment="production", supabase_url="", supabase_key="")
    with pytest.raises(OperationsWorkspaceConfigurationError):
        operations_workspace_repository(environment="production", supabase_url="", supabase_key="")


def test_finance_repositories_are_tenant_scoped_and_have_parity(sqlite_factory):
    local = SQLiteTechnologySpendRepository(sqlite_factory)
    remote = SupabaseTechnologySpendRepository(_Client(_tables()))
    methods = (
        "get_enterprise_spend_breakdown",
        "get_managed_services_cost",
        "get_saas_cost",
        "get_budget_vs_actual",
        "get_enterprise_forecast",
        "get_recommendations",
        "get_executive_summary",
    )
    for method in methods:
        assert getattr(local, method)(ORG_A) == getattr(remote, method)(ORG_A)


def test_operations_repositories_are_tenant_scoped_and_have_parity(sqlite_factory):
    local = SQLiteOperationsWorkspaceRepository(sqlite_factory)
    remote = SupabaseOperationsWorkspaceRepository(_Client(_tables()))
    methods = (
        "get_approval_requests",
        "get_recommendations",
        "get_audit_events",
        "get_cost_anomalies",
        "get_cloud_costs",
    )
    for method in methods:
        rows = getattr(local, method)(ORG_A)
        assert rows == getattr(remote, method)(ORG_A)
        assert all(row["organization_id"] == ORG_A for row in rows)


def test_optional_local_tables_return_safe_empty(tmp_path):
    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()

    def connect():
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection

    assert SQLiteTechnologySpendRepository(connect).get_budget_vs_actual(ORG_A) == []
    assert SQLiteOperationsWorkspaceRepository(connect).get_cloud_costs(ORG_A) == []


@pytest.mark.parametrize(
    ("role", "page", "heading"),
    [
        ("finance", "pages/finance_dashboard.py", "FinOps Dashboard"),
        ("operations", "pages/operations_workspace.py", "Operations Workspace"),
    ],
)
def test_persona_page_renders_without_supabase(monkeypatch, role, page, heading):
    for name in (
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_ANON_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    app = AppTest.from_file(page, default_timeout=30)
    for key, value in {
        "authenticated": True,
        "auth_backend": "local",
        "user": f"{role}@company.com",
        "role": role,
        "organization_id": ORG_A,
        "organization_name": "Default Org",
        "authorized_organization_ids": [ORG_A],
        "permissions": [],
    }.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    assert any(heading in title.value for title in app.title)
