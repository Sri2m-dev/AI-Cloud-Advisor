"""Structural tests for the P3 Supabase adapter foundation."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_fabric.adapters.supabase import (
    DataFabricDatabaseConfig,
    SupabaseAdapterConfigurationError,
    SupabaseDataFabricClient,
    SupabaseEntityRepository,
)

ROOT = Path(__file__).resolve().parents[2]
ADAPTER_ROOT = ROOT / "data_fabric" / "adapters" / "supabase"
MIGRATION_ROOT = ROOT / "migrations" / "data_fabric"


def test_adapter_package_exports_foundation_contracts() -> None:
    assert DataFabricDatabaseConfig
    assert SupabaseDataFabricClient
    assert SupabaseEntityRepository


def test_adapter_config_rejects_placeholder_secrets_and_redacts_repr() -> None:
    with pytest.raises(SupabaseAdapterConfigurationError):
        DataFabricDatabaseConfig("https://example.supabase.co", "replace-me")

    config = DataFabricDatabaseConfig("https://example.supabase.co", "server-side-secret")

    assert "server-side-secret" not in repr(config)
    assert "***REDACTED***" in repr(config)


def test_adapter_does_not_import_product_runtime_paths() -> None:
    forbidden_imports = (
        "from pages",
        "import pages",
        "from connectors",
        "import connectors",
        "from connector_runtime",
        "import connector_runtime",
        "from services",
        "import services",
        "streamlit",
    )
    combined = "\n".join(path.read_text() for path in ADAPTER_ROOT.glob("*.py"))

    for forbidden in forbidden_imports:
        assert forbidden not in combined


def test_migrations_are_explicit_and_non_destructive() -> None:
    migration_names = sorted(path.name for path in MIGRATION_ROOT.glob("*.sql"))

    assert migration_names == [
        "0001_create_data_fabric_schema.sql",
        "0002_create_enterprise_entities.sql",
        "0003_create_entity_update_rpc.sql",
    ]

    combined = "\n".join(path.read_text().lower() for path in MIGRATION_ROOT.glob("*.sql"))
    forbidden_sql = ("drop table", "drop schema", "truncate", "delete from")

    for forbidden in forbidden_sql:
        assert forbidden not in combined


def test_entity_migration_defines_tenant_constraints_and_rls() -> None:
    sql = (MIGRATION_ROOT / "0002_create_enterprise_entities.sql").read_text().lower()

    assert "create table if not exists data_fabric.enterprise_entities" in sql
    assert "organization_id text not null" in sql
    assert "tenant_id text not null" in sql
    assert "unique (organization_id, tenant_id, canonical_id)" in sql
    assert "unique (organization_id, tenant_id, source_system, source_identifier)" in sql
    assert "enable row level security" in sql
    assert "id text primary key" in sql


def test_update_rpc_enforces_tenant_and_revision_filters() -> None:
    sql = (MIGRATION_ROOT / "0003_create_entity_update_rpc.sql").read_text().lower()

    assert "p_entity_id text" in sql
    assert "and organization_id = p_organization_id" in sql
    assert "and tenant_id = p_tenant_id" in sql
    assert "and revision = p_expected_revision" in sql
    assert "revision = revision + 1" in sql
