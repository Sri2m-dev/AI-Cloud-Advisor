from types import SimpleNamespace

import pytest

from backend.jobs import tasks
from scripts import generate_recommendations as generator


class _SourceQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        rows = [
            row
            for row in self.rows
            if all(str(row.get(column)) == str(value) for column, value in self.filters)
        ]
        return SimpleNamespace(data=rows)


class _SourceClient:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.queries = {}

    def table(self, name):
        query = _SourceQuery(self.rows_by_table.get(name, []))
        self.queries[name] = query
        return query


class _AdminQuery:
    def __init__(self, writes):
        self.writes = writes

    def upsert(self, rows, *, on_conflict):
        self.writes.append((rows, on_conflict))
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _AdminClient:
    def __init__(self):
        self.writes = []

    def table(self, name):
        assert name == "recommendations"
        return _AdminQuery(self.writes)


def test_direct_generator_requires_explicit_tenant_before_any_database_access(monkeypatch):
    source = _SourceClient({})
    source_calls = []
    admin_calls = []
    monkeypatch.setattr(
        generator,
        "_get_supabase_source",
        lambda: source_calls.append(True) or source,
    )
    monkeypatch.setattr(generator, "_get_supabase_admin", lambda: admin_calls.append(True))

    with pytest.raises(ValueError, match="explicit organization ID is required"):
        generator.generate_recommendations()

    with pytest.raises(ValueError, match="explicit organization ID is required"):
        generator.generate_recommendations(org_id="  ")
    with pytest.raises(ValueError, match="must be a valid UUID"):
        generator.generate_recommendations(org_id="not-a-tenant")

    assert source_calls == []
    assert source.queries == {}
    assert admin_calls == []
    assert not hasattr(generator, "DEFAULT_ORG_ID")


def test_explicit_tenant_scopes_reads_and_recommendation_writes(monkeypatch):
    tenant = "11111111-1111-4111-8111-111111111111"
    other_tenant = "22222222-2222-4222-8222-222222222222"
    source = _SourceClient(
        {
            "usage_metrics": [
                {"organization_id": tenant, "utilization": 90},
                {"organization_id": other_tenant, "utilization": 99},
            ],
            "unallocated_cost": [
                {"organization_id": tenant, "unallocated_percent": 25},
            ],
            "optimization_results": [
                {
                    "organization_id": tenant,
                    "baseline_cost": 20,
                    "optimized_cost": 10,
                },
            ],
        }
    )
    admin = _AdminClient()
    monkeypatch.setattr(generator, "_get_supabase_source", lambda: source)
    monkeypatch.setattr(generator, "_get_supabase_admin", lambda: admin)

    generator.generate_recommendations(org_id=f" {tenant} ")

    assert set(source.queries) == {
        "usage_metrics",
        "unallocated_cost",
        "optimization_results",
    }
    assert all(query.filters == [("organization_id", tenant)] for query in source.queries.values())
    assert len(admin.writes) == 1
    rows, conflict = admin.writes[0]
    assert conflict == "org_id,message"
    assert len(rows) == 3
    assert all(row["organization_id"] == tenant and row["org_id"] == tenant for row in rows)


def test_empty_tenant_enumeration_skips_without_generator_calls(monkeypatch, caplog):
    calls = []
    monkeypatch.setattr(tasks, "_get_tenant_ids", lambda **_kwargs: [])
    monkeypatch.setattr(
        generator,
        "generate_recommendations",
        lambda **kwargs: calls.append(kwargs),
    )

    tasks.job_optimization_engine_daily()

    assert calls == []
    assert "No tenants found" in caplog.text


def test_tenant_enumeration_failure_surfaces_sanitized_error_without_generator_call(
    monkeypatch, caplog
):
    calls = []

    class _FailingSupabase:
        def table(self, _name):
            raise RuntimeError("sensitive connection details")

    monkeypatch.setattr(tasks, "supabase", _FailingSupabase())
    monkeypatch.setattr(
        generator,
        "generate_recommendations",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(tasks.TenantEnumerationError, match="Tenant enumeration failed"):
        tasks.job_optimization_engine_daily()

    assert calls == []
    assert "Tenant enumeration failed" in caplog.text
    assert "sensitive connection details" not in caplog.text


def test_multiple_tenants_process_only_explicitly_discovered_tenants(monkeypatch):
    discovered = [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    ]
    calls = []
    monkeypatch.setattr(tasks, "_get_tenant_ids", lambda **_kwargs: discovered)
    monkeypatch.setattr(
        generator,
        "generate_recommendations",
        lambda **kwargs: calls.append(kwargs),
    )

    tasks.job_optimization_engine_daily()

    assert calls == [{"org_id": tenant} for tenant in discovered]
    assert {item["org_id"] for item in calls} == set(discovered)
