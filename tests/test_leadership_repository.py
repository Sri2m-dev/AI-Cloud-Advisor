from __future__ import annotations

import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from repositories.leadership_repository import (
    SQLiteLeadershipRepository,
    SupabaseLeadershipRepository,
)
from services.leadership_composition import (
    LeadershipConfigurationError,
    leadership_repository,
)
from services.leadership_metrics import get_leadership_dashboard_metrics

ORG_A = "org-a"
ORG_B = "org-b"


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []
        self.ordering = None
        self.maximum = None

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column, desc=False):
        self.ordering = (column, desc)
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
        if self.ordering:
            column, descending = self.ordering
            rows.sort(key=lambda row: row.get(column) or 0, reverse=descending)
        if self.maximum is not None:
            rows = rows[: self.maximum]
        return _Response(rows)


class _Client:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _Query(self.tables.get(name, []))


def _datasets():
    return {
        "mart_enterprise_spend": [
            {"organization_id": ORG_A, "total_spend": 1000.0},
            {"organization_id": ORG_B, "total_spend": 9000.0},
        ],
        "mart_enterprise_spend_breakdown": [
            {
                "organization_id": ORG_A,
                "cloud_cost": 600.0,
                "saas_cost": 200.0,
                "msp_cost": 100.0,
                "license_cost": 100.0,
            },
            {
                "organization_id": ORG_B,
                "cloud_cost": 9000.0,
                "saas_cost": 0.0,
                "msp_cost": 0.0,
                "license_cost": 0.0,
            },
        ],
        "mart_savings": [
            {"organization_id": ORG_A, "savings": 250.0, "optimized_cost": 900.0},
            {"organization_id": ORG_B, "savings": 999.0, "optimized_cost": 8000.0},
        ],
        "approval_requests": [
            {"organization_id": ORG_A, "id": "approval-a", "status": "PENDING"},
            {"organization_id": ORG_B, "id": "approval-b", "status": "PENDING"},
        ],
        "mart_optimization_opportunities": [
            {
                "organization_id": ORG_A,
                "id": "optimization-a",
                "cloud": "aws",
                "service_name": "EC2",
                "total_cost": 600.0,
            },
            {
                "organization_id": ORG_B,
                "id": "optimization-b",
                "cloud": "aws",
                "service_name": "S3",
                "total_cost": 9000.0,
            },
        ],
        "mart_cost_anomalies": [
            {"organization_id": ORG_A, "id": "anomaly-a"},
            {"organization_id": ORG_B, "id": "anomaly-b"},
        ],
        "recommendations": [
            {"organization_id": ORG_A, "id": "recommendation-a"},
            {"organization_id": ORG_B, "id": "recommendation-b"},
        ],
    }


@pytest.fixture
def sqlite_factory(tmp_path):
    database_path = tmp_path / "leadership.db"
    conn = sqlite3.connect(database_path)
    for table_name, rows in _datasets().items():
        columns = list(rows[0])
        definitions = ", ".join(
            f"{column} {'REAL' if isinstance(rows[0][column], float) else 'TEXT'}"
            for column in columns
        )
        conn.execute(f"CREATE TABLE {table_name} ({definitions})")
        placeholders = ", ".join("?" for _ in columns)
        conn.executemany(
            f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})",
            [[row[column] for column in columns] for row in rows],
        )
    conn.commit()
    conn.close()

    def connect():
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        return connection

    return connect


def test_development_without_supabase_selects_sqlite(sqlite_factory):
    repository = leadership_repository(
        environment="development",
        supabase_url="",
        supabase_key="",
        connection_factory=sqlite_factory,
    )
    assert isinstance(repository, SQLiteLeadershipRepository)


def test_development_with_valid_supabase_still_selects_sqlite(sqlite_factory):
    repository = leadership_repository(
        environment="development",
        supabase_url="https://project-ref.supabase.co",
        supabase_key="configured-key",
        client=_Client(_datasets()),
        connection_factory=sqlite_factory,
    )
    assert isinstance(repository, SQLiteLeadershipRepository)


@pytest.mark.parametrize(
    ("url", "key"),
    [
        ("https://your-project.supabase.co", "replace-with-supabase-service-or-anon-key"),
        ("not-a-url", "configured-key"),
        ("https://database.example.com", "configured-key"),
    ],
)
def test_placeholder_and_invalid_configuration_fall_back_in_development(
    sqlite_factory, url, key
):
    repository = leadership_repository(
        environment="development",
        supabase_url=url,
        supabase_key=key,
        connection_factory=sqlite_factory,
    )
    assert isinstance(repository, SQLiteLeadershipRepository)


def test_valid_supabase_configuration_selects_supabase():
    client = _Client(_datasets())
    repository = leadership_repository(
        environment="production",
        supabase_url="https://project-ref.supabase.co",
        supabase_key="configured-key",
        client=client,
    )
    assert isinstance(repository, SupabaseLeadershipRepository)


def test_production_invalid_configuration_fails_closed():
    with pytest.raises(LeadershipConfigurationError, match="production leadership metrics"):
        leadership_repository(
            environment="production",
            supabase_url="https://database.example.com",
            supabase_key="configured-key",
        )


def test_sqlite_and_supabase_repositories_have_tenant_scoped_parity(sqlite_factory):
    sqlite_repository = SQLiteLeadershipRepository(sqlite_factory)
    supabase_repository = SupabaseLeadershipRepository(_Client(_datasets()))
    methods = (
        "get_enterprise_spend",
        "get_enterprise_spend_breakdown",
        "get_savings",
        "get_approval_requests",
        "get_optimization_opportunities",
        "get_cost_anomalies",
        "get_recommendations",
    )
    for method_name in methods:
        sqlite_result = getattr(sqlite_repository, method_name)(ORG_A)
        supabase_result = getattr(supabase_repository, method_name)(ORG_A)
        assert sqlite_result == supabase_result
        assert all(
            row.get("organization_id") == ORG_A
            for row in (
                sqlite_result if isinstance(sqlite_result, list) else [sqlite_result]
            )
        )


def test_metrics_render_from_sqlite_without_supabase(sqlite_factory):
    metrics = get_leadership_dashboard_metrics(
        ORG_A, repository=SQLiteLeadershipRepository(sqlite_factory)
    )
    assert metrics["kpis"]["total_spend"] == 1000.0
    assert metrics["kpis"]["pending_approvals"] == 1
    assert metrics["kpis"]["active_anomalies"] == 1
    assert metrics["spend_by_cloud"] == [{"cloud": "aws", "spend": 600.0}]


def test_leadership_dashboard_renders_without_supabase(monkeypatch):
    for name in (
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_ANON_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    app = AppTest.from_file("pages/leadership_dashboard.py", default_timeout=30)
    session = {
        "authenticated": True,
        "auth_backend": "local",
        "user": "admin@company.com",
        "user_id": "leadership-certification",
        "email": "admin@company.com",
        "role": "super_admin",
        "organization_id": ORG_A,
        "organization_name": "Default Org",
        "authorized_organization_ids": [ORG_A],
        "permissions": [],
    }
    for key, value in session.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    assert any("Leadership Dashboard" in title.value for title in app.title)
