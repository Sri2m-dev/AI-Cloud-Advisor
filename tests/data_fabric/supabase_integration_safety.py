"""Shared safety gate for opt-in P3 Supabase integration tests.

This module is test-only. It must not be imported by runtime code.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import pytest

from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient
from data_fabric.foundation import TenantContext


ENABLE_ENV = "P3_SUPABASE_RUN_INTEGRATION"
URL_ENV = "P3_SUPABASE_TEST_URL"
KEY_ENV = "P3_SUPABASE_TEST_SERVICE_ROLE_KEY"
PROHIBITED_URLS_ENV = "P3_SUPABASE_PROHIBITED_URLS"
PROHIBITED_PROJECT_REFS_ENV = "P3_SUPABASE_PROHIBITED_PROJECT_REFS"

APP_SUPABASE_URL_ENV = "SUPABASE_URL"
APP_SUPABASE_KEY_ENV = "SUPABASE_KEY"
APP_SUPABASE_SERVICE_ROLE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"

ENABLE_VALUE = "1"
TEST_ID_PREFIX = "p3test-"
SUPABASE_PROJECT_HOST_PATTERN = re.compile(r"^[a-z0-9]{20}\.supabase\.co$")

DATA_FABRIC_CLEANUP_TABLES = (
    "idempotency_records",
    "semantic_mappings",
    "ontology_relationships",
    "ontology_concepts",
    "quality_assessments",
    "provenance_records",
    "lineage_events",
    "entity_versions",
    "enterprise_relationships",
    "enterprise_entities",
)


class SupabaseIntegrationDisabled(RuntimeError):
    """Raised when integration tests are not explicitly enabled."""


class SupabaseIntegrationSafetyError(RuntimeError):
    """Raised when a configured integration target is unsafe."""


@dataclass(frozen=True, slots=True)
class SupabaseIntegrationConfig:
    """Resolved P3 integration config with redacted representation."""

    url: str
    service_role_key: str

    def to_database_config(self) -> DataFabricDatabaseConfig:
        return DataFabricDatabaseConfig(self.url, self.service_role_key)

    def __repr__(self) -> str:
        return "SupabaseIntegrationConfig(url='***REDACTED***', service_role_key='***REDACTED***')"

    def redacted_report(self) -> dict[str, Any]:
        return {
            "url_present": bool(self.url),
            "service_role_key_present": bool(self.service_role_key),
            "enable_value": ENABLE_VALUE,
        }


def integration_enabled(env: Mapping[str, str] | None = None) -> bool:
    values = _env(env)
    return values.get(ENABLE_ENV) == ENABLE_VALUE


def resolve_config(env: Mapping[str, str] | None = None) -> SupabaseIntegrationConfig:
    values = _env(env)
    if values.get(ENABLE_ENV) != ENABLE_VALUE:
        raise SupabaseIntegrationDisabled("P3 Supabase integration tests are opt-in only")

    url = (values.get(URL_ENV) or "").strip()
    key = values.get(KEY_ENV) or ""
    if not url or not key:
        raise SupabaseIntegrationDisabled("P3 Supabase test URL/service-role key are not configured")

    _validate_url(url, values)
    return SupabaseIntegrationConfig(url=url, service_role_key=key)


def config_or_skip(env: Mapping[str, str] | None = None) -> SupabaseIntegrationConfig:
    try:
        return resolve_config(env)
    except SupabaseIntegrationDisabled as exc:
        pytest.skip(str(exc))


def client_or_skip(env: Mapping[str, str] | None = None) -> SupabaseDataFabricClient:
    config = config_or_skip(env)
    return SupabaseDataFabricClient(config.to_database_config())


def create_test_identifier(label: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "-" for ch in label.lower()).strip("-")
    return f"{TEST_ID_PREFIX}{normalized}-{uuid4().hex}"


def create_test_organization_id(label: str = "org") -> str:
    return create_test_identifier(label)


def create_test_tenant_id(label: str = "tenant") -> str:
    return create_test_identifier(label)


def create_test_tenant_context(label: str = "tenant") -> TenantContext:
    return TenantContext(
        create_test_organization_id(f"{label}-org"),
        create_test_tenant_id(f"{label}-tenant"),
    )


def is_test_owned_identifier(value: str) -> bool:
    return str(value or "").startswith(TEST_ID_PREFIX)


def assert_test_owned_scope(organization_id: str, tenant_id: str) -> None:
    if not is_test_owned_identifier(organization_id):
        raise SupabaseIntegrationSafetyError("cleanup refused for non-test organization_id")
    if not is_test_owned_identifier(tenant_id):
        raise SupabaseIntegrationSafetyError("cleanup refused for non-test tenant_id")


class SupabaseIntegrationCleanup:
    """Scoped cleanup for test-owned Data Fabric tenant records."""

    table_order = DATA_FABRIC_CLEANUP_TABLES

    def __init__(self, client: Any) -> None:
        self.client = client

    def cleanup_tenant(self, tenant_context: TenantContext) -> dict[str, int]:
        organization_id = tenant_context.organization_id
        tenant_id = tenant_context.tenant_id
        assert_test_owned_scope(organization_id, tenant_id)

        results: dict[str, int] = {}
        for table_name in self.table_order:
            response = (
                self.client.table(table_name)
                .delete()
                .eq("organization_id", organization_id)
                .eq("tenant_id", tenant_id)
                .execute()
            )
            results[table_name] = _response_count(response)
        return results


def cleanup_test_tenant(client: Any, tenant_context: TenantContext) -> dict[str, int]:
    return SupabaseIntegrationCleanup(client).cleanup_tenant(tenant_context)


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _validate_url(url: str, env: Mapping[str, str]) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise SupabaseIntegrationSafetyError("P3 Supabase test URL must use HTTPS")
    if not SUPABASE_PROJECT_HOST_PATTERN.fullmatch(host):
        raise SupabaseIntegrationSafetyError("P3 Supabase test URL must use a valid Supabase project hostname")
    if parsed.port is not None:
        raise SupabaseIntegrationSafetyError("P3 Supabase test URL must not specify a port")
    if parsed.path not in {"", "/"}:
        raise SupabaseIntegrationSafetyError("P3 Supabase test URL must be the project root")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise SupabaseIntegrationSafetyError("P3 Supabase test URL must not contain credentials, query, or fragment")
    if "prod" in host or "production" in host or "prod" in parsed.path.lower():
        raise SupabaseIntegrationSafetyError("refusing production-looking P3 Supabase test URL")

    prohibited_urls = _split_env_list(env.get(PROHIBITED_URLS_ENV))
    if _normalize_url(url) in {_normalize_url(item) for item in prohibited_urls}:
        raise SupabaseIntegrationSafetyError("refusing configured prohibited P3 Supabase URL")

    project_ref = _project_ref(host)
    prohibited_refs = set(_split_env_list(env.get(PROHIBITED_PROJECT_REFS_ENV)))
    if project_ref and project_ref in prohibited_refs:
        raise SupabaseIntegrationSafetyError("refusing configured prohibited P3 Supabase project")

    app_url = (env.get(APP_SUPABASE_URL_ENV) or "").strip()
    if app_url and _normalize_url(app_url) == _normalize_url(url):
        raise SupabaseIntegrationSafetyError("refusing normal application Supabase URL")


def _split_env_list(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


def _normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    return f"{scheme}://{host}{path}"


def _project_ref(host: str) -> str:
    if host.endswith(".supabase.co") or ".supabase." in host:
        return host.split(".")[0]
    return ""


def _response_count(response: Any) -> int:
    count = getattr(response, "count", None)
    if isinstance(count, int):
        return count
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return len(data)
    return 0
