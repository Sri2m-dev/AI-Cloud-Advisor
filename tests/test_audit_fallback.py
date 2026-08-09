from __future__ import annotations

import sqlite3

import pytest

from repositories.audit_repository import SQLiteAuditRepository, SupabaseAuditRepository
from services import audit_service
from services.audit_composition import AuditConfigurationError, audit_repository
from services.audit_timeline_service import get_approvals_assignments_timeline


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows, operation="select", payload=None):
        self.rows = rows
        self.operation = operation
        self.payload = payload
        self.filters = []
        self.maximum = None

    def select(self, *_args):
        return self

    def insert(self, payload):
        return _Query(self.rows, "insert", dict(payload))

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, value):
        self.maximum = value
        return self

    def execute(self):
        if self.operation == "insert":
            row = {"id": f"event-{len(self.rows) + 1}", **self.payload}
            self.rows.append(row)
            return _Response([row])
        result = [
            row
            for row in self.rows
            if all(str(row.get(column)) == str(value) for column, value in self.filters)
        ]
        return _Response(result[: self.maximum])


class _Client:
    def __init__(self):
        self.rows = []

    def table(self, name):
        assert name == "audit_events"
        return _Query(self.rows)


@pytest.fixture
def local_runtime(monkeypatch, tmp_path):
    database_path = tmp_path / "audit.db"
    monkeypatch.setattr("database.db.SQLITE_DB_PATH", str(database_path))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    return database_path


def test_local_audit_persists_reconstructable_event_without_supabase(local_runtime):
    inserted = audit_service.log_event(
        "CLASSIFICATION_CORRECTED",
        "admin@company.com",
        "corrected",
        "classification",
        "result-1",
        org_id="org-a",
        details={
            "before_state": {"business_unit": "Unknown"},
            "after_state": {"business_unit": "Banking"},
            "reason": "approved evidence correction",
            "actor_role": "super_admin",
        },
    )

    assert "error" not in inserted
    events = audit_service.get_events(org_id="org-a")
    assert len(events) == 1
    assert events[0]["event_data"]["details"]["reason"] == "approved evidence correction"
    assert events[0]["event_data"]["details"]["before_state"] == {
        "business_unit": "Unknown"
    }
    assert events[0]["created_at"]


def test_local_audit_timeline_uses_same_repository_without_traceback(local_runtime, capsys):
    audit_service.log_user_login(
        user_id="local-admin",
        username="admin@company.com",
        organization_id="org-a",
        actor_role="super_admin",
    )

    timeline = get_approvals_assignments_timeline("org-a")

    assert timeline["success"] is True
    assert timeline["data"][0]["event_type"] == "USER_LOGIN"
    output = capsys.readouterr()
    assert "RuntimeError" not in output.out + output.err
    assert "AUDIT INSERT FAILED" not in output.out + output.err


def test_local_audit_is_tenant_scoped_and_append_only(local_runtime):
    for org_id in ("tenant-a", "tenant-b"):
        audit_service.log_event("ACCOUNT_UPDATED", "actor", "update", "account", "1", org_id)

    assert len(audit_service.get_events(org_id="tenant-a")) == 1
    assert len(audit_service.get_events(org_id="tenant-b")) == 1
    assert audit_service.get_events(org_id="tenant-c") == []

    conn = sqlite3.connect(local_runtime)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE local_audit_events SET event_type = 'ALTERED'")
    conn.close()


def test_repository_selection_rejects_placeholders_and_falls_back_locally(tmp_path):
    repository = audit_repository(
        environment="development",
        supabase_url="https://your-project.supabase.co",
        supabase_key="replace-with-supabase-service-or-anon-key",
        connection_factory=lambda: sqlite3.connect(tmp_path / "fallback.db"),
    )
    assert isinstance(repository, SQLiteAuditRepository)


def test_repository_selection_uses_supabase_when_configuration_is_valid():
    client = _Client()
    repository = audit_repository(
        environment="development",
        supabase_url="https://valid-project.supabase.co",
        supabase_key="valid-test-key",
        client=client,
    )
    assert isinstance(repository, SupabaseAuditRepository)


def test_production_without_valid_supabase_configuration_fails_closed():
    with pytest.raises(AuditConfigurationError, match="production audit persistence"):
        audit_repository(environment="production", supabase_url="", supabase_key="")


def test_supabase_repository_preserves_event_shape_and_scope():
    repository = SupabaseAuditRepository(_Client())
    event = {
        "organization_id": 1,
        "event_type": "ACCOUNT_UPDATED",
        "event_source": "account",
        "entity_id": "account-1",
        "actor_id": "admin@company.com",
        "event_data": {"org_id": "org-a", "details": {"reason": "reviewed"}},
        "created_at": "2026-08-09T00:00:00+00:00",
    }
    inserted = repository.insert_event(event)
    assert inserted["event_data"] == event["event_data"]
    assert repository.list_events(org_id="org-a") == [inserted]
    assert repository.list_events(org_id="org-b") == []
    assert repository.get_event(org_id="org-a", event_id=inserted["id"]) == inserted
