"""Regression tests for the P3 Supabase integration safety gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from data_fabric.foundation import TenantContext
from tests.data_fabric import supabase_integration_safety as safety


BASE_ENV = {
    safety.ENABLE_ENV: "1",
    safety.URL_ENV: "https://abcdefghijklmnopqrst.supabase.co",
    safety.KEY_ENV: "local-test-secret",
}

INTEGRATION_FILES = (
    Path("tests/data_fabric/test_supabase_entity_repository_integration.py"),
    Path("tests/data_fabric/test_supabase_relationship_history_integration.py"),
    Path("tests/data_fabric/test_supabase_governance_semantic_integration.py"),
    Path("tests/data_fabric/test_supabase_atomic_write_integration.py"),
)


class FakeResponse:
    def __init__(self, count: int = 1) -> None:
        self.count = count
        self.data: list[dict[str, Any]] = [{} for _ in range(count)]


class FakeDeleteQuery:
    def __init__(self, table_name: str, client: FakeClient) -> None:
        self.table_name = table_name
        self.client = client
        self.filters: list[tuple[str, str]] = []

    def eq(self, column: str, value: str) -> FakeDeleteQuery:
        self.filters.append((column, value))
        return self

    def execute(self) -> FakeResponse:
        self.client.executed.append((self.table_name, tuple(self.filters)))
        if self.table_name == self.client.fail_table:
            raise RuntimeError("cleanup failure")
        return FakeResponse(count=1)


class FakeTable:
    def __init__(self, table_name: str, client: FakeClient) -> None:
        self.table_name = table_name
        self.client = client

    def delete(self) -> FakeDeleteQuery:
        self.client.deleted_tables.append(self.table_name)
        return FakeDeleteQuery(self.table_name, self.client)


class FakeClient:
    def __init__(self, fail_table: str | None = None) -> None:
        self.fail_table = fail_table
        self.deleted_tables: list[str] = []
        self.executed: list[tuple[str, tuple[tuple[str, str], ...]]] = []

    def table(self, table_name: str) -> FakeTable:
        return FakeTable(table_name, self)


def test_exact_flag_one_enables_integration() -> None:
    assert safety.integration_enabled(BASE_ENV)
    config = safety.resolve_config(BASE_ENV)
    assert config.redacted_report()["url_present"] is True


@pytest.mark.parametrize("value", ["true", "yes", "", "0"])
def test_non_exact_flag_values_disable_integration(value: str) -> None:
    env = {**BASE_ENV, safety.ENABLE_ENV: value}
    assert not safety.integration_enabled(env)
    with pytest.raises(safety.SupabaseIntegrationDisabled):
        safety.resolve_config(env)


def test_missing_flag_disables_integration() -> None:
    env = dict(BASE_ENV)
    env.pop(safety.ENABLE_ENV)
    assert not safety.integration_enabled(env)
    with pytest.raises(safety.SupabaseIntegrationDisabled):
        safety.resolve_config(env)


def test_missing_url_fails_closed() -> None:
    env = {**BASE_ENV, safety.URL_ENV: ""}
    with pytest.raises(safety.SupabaseIntegrationDisabled):
        safety.resolve_config(env)


def test_missing_service_role_key_fails_closed() -> None:
    env = {**BASE_ENV, safety.KEY_ENV: ""}
    with pytest.raises(safety.SupabaseIntegrationDisabled):
        safety.resolve_config(env)


def test_product_runtime_env_vars_are_never_used_as_fallback() -> None:
    env = {
        safety.ENABLE_ENV: "1",
        safety.APP_SUPABASE_URL_ENV: "https://runtime.example.test",
        safety.APP_SUPABASE_KEY_ENV: "runtime-key",
        safety.APP_SUPABASE_SERVICE_ROLE_KEY_ENV: "runtime-service-role",
    }
    with pytest.raises(safety.SupabaseIntegrationDisabled):
        safety.resolve_config(env)


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "http://disposable-p3.supabase.co",
        "https://localhost",
        "https://127.0.0.1",
        "https://nexora-production.example.test",
    ],
)
def test_malformed_or_unsafe_url_rejected(url: str) -> None:
    env = {**BASE_ENV, safety.URL_ENV: url}
    with pytest.raises(safety.SupabaseIntegrationSafetyError):
        safety.resolve_config(env)


@pytest.mark.parametrize(
    "url",
    [
        "https://abcdefghijklmnopqrst.supabase.co/rest/v1",
        "https://abcdefghijklmnopqrst.supabase.co/other",
        "https://abcdefghijklmnopqrst.supabase.co?mode=test",
        "https://abcdefghijklmnopqrst.supabase.co#fragment",
        "https://abcdefghijklmnopqrst.supabase.co:443",
        "https://abcdefghijklmnopqrs.supabase.co",
        "https://abcdefghijklmnopqrstu.supabase.co",
        "https://abcdefghijklmnopqrst.example.com",
        "https://supabase.co",
    ],
)
def test_non_root_or_invalid_supabase_project_url_rejected(url: str) -> None:
    with pytest.raises(safety.SupabaseIntegrationSafetyError):
        safety.resolve_config({**BASE_ENV, safety.URL_ENV: url})


@pytest.mark.parametrize(
    "url",
    [
        "https://abcdefghijklmnopqrst.supabase.co",
        "https://abcdefghijklmnopqrst.supabase.co/",
        "https://abc123def456ghi789jk.supabase.co",
    ],
)
def test_valid_supabase_project_root_url_accepted(url: str) -> None:
    assert safety.resolve_config({**BASE_ENV, safety.URL_ENV: url}).redacted_report()["url_present"]


def test_known_prohibited_project_ref_rejected() -> None:
    env = {
        **BASE_ENV,
        safety.URL_ENV: "https://blockedref00000000000.supabase.co",
        safety.PROHIBITED_PROJECT_REFS_ENV: "blockedref00000000000",
    }
    with pytest.raises(safety.SupabaseIntegrationSafetyError):
        safety.resolve_config(env)


def test_normal_application_url_is_rejected_when_detectable() -> None:
    env = {
        **BASE_ENV,
        safety.URL_ENV: "https://normalapp00000000000.supabase.co",
        safety.APP_SUPABASE_URL_ENV: "https://normalapp00000000000.supabase.co",
    }
    with pytest.raises(safety.SupabaseIntegrationSafetyError):
        safety.resolve_config(env)


def test_unsafe_target_rejected_before_client_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"client": 0}

    def fake_client(*args: Any, **kwargs: Any) -> object:
        calls["client"] += 1
        return object()

    monkeypatch.setattr(safety, "SupabaseDataFabricClient", fake_client)
    env = {**BASE_ENV, safety.URL_ENV: "https://prodtarget0000000000.supabase.co"}
    with pytest.raises(safety.SupabaseIntegrationSafetyError):
        safety.client_or_skip(env)
    assert calls["client"] == 0


def test_test_owned_identifiers_use_required_prefix_and_are_unique() -> None:
    organization_id = safety.create_test_organization_id()
    tenant_id = safety.create_test_tenant_id()
    identifiers = {safety.create_test_identifier("canonical") for _ in range(5)}
    assert organization_id.startswith(safety.TEST_ID_PREFIX)
    assert tenant_id.startswith(safety.TEST_ID_PREFIX)
    assert len(identifiers) == 5


def test_cleanup_accepts_test_owned_context() -> None:
    client = FakeClient()
    tenant = safety.create_test_tenant_context()
    result = safety.cleanup_test_tenant(client, tenant)
    assert set(result) == set(safety.DATA_FABRIC_CLEANUP_TABLES)


def test_cleanup_rejects_non_test_organization() -> None:
    client = FakeClient()
    tenant = TenantContext("normal-org", safety.create_test_tenant_id())
    with pytest.raises(safety.SupabaseIntegrationSafetyError):
        safety.cleanup_test_tenant(client, tenant)
    assert client.deleted_tables == []


def test_cleanup_rejects_non_test_tenant() -> None:
    client = FakeClient()
    tenant = TenantContext(safety.create_test_organization_id(), "normal-tenant")
    with pytest.raises(safety.SupabaseIntegrationSafetyError):
        safety.cleanup_test_tenant(client, tenant)
    assert client.deleted_tables == []


def test_cleanup_applies_both_organization_and_tenant_filters() -> None:
    client = FakeClient()
    tenant = safety.create_test_tenant_context()
    safety.cleanup_test_tenant(client, tenant)
    assert client.executed
    for _, filters in client.executed:
        assert ("organization_id", tenant.organization_id) in filters
        assert ("tenant_id", tenant.tenant_id) in filters


def test_cleanup_never_issues_unscoped_delete() -> None:
    client = FakeClient()
    tenant = safety.create_test_tenant_context()
    safety.cleanup_test_tenant(client, tenant)
    assert all(len(filters) >= 2 for _, filters in client.executed)


def test_cleanup_covers_expected_tables_in_dependency_safe_order() -> None:
    client = FakeClient()
    tenant = safety.create_test_tenant_context()
    safety.cleanup_test_tenant(client, tenant)
    assert tuple(client.deleted_tables) == safety.DATA_FABRIC_CLEANUP_TABLES


def test_cleanup_failure_is_surfaced() -> None:
    client = FakeClient(fail_table="lineage_events")
    tenant = safety.create_test_tenant_context()
    with pytest.raises(RuntimeError, match="cleanup failure"):
        safety.cleanup_test_tenant(client, tenant)


def test_secret_values_are_absent_from_helper_repr_and_errors() -> None:
    config = safety.resolve_config(BASE_ENV)
    assert "local-test-secret" not in repr(config)
    assert "***REDACTED***" in repr(config)

    with pytest.raises(safety.SupabaseIntegrationSafetyError) as exc_info:
        safety.resolve_config({**BASE_ENV, safety.URL_ENV: "https://prodtarget0000000000.supabase.co"})
    assert "local-test-secret" not in str(exc_info.value)


def test_all_integration_files_use_shared_safety_helper() -> None:
    for file_path in INTEGRATION_FILES:
        text = file_path.read_text(encoding="utf-8")
        assert "supabase_integration_safety" in text
        assert "client_or_skip" in text or "resolve_config" in text


def test_integration_files_do_not_read_product_supabase_env_vars() -> None:
    prohibited = {
        safety.APP_SUPABASE_URL_ENV,
        safety.APP_SUPABASE_KEY_ENV,
        safety.APP_SUPABASE_SERVICE_ROLE_KEY_ENV,
        "os.getenv",
    }
    for file_path in INTEGRATION_FILES:
        text = file_path.read_text(encoding="utf-8")
        for marker in prohibited:
            assert marker not in text
