"""Opt-in relationship schema and deferred-history contract validation."""

from pathlib import Path

from supabase import create_client

from tests.data_fabric.supabase_integration_safety import resolve_config


def test_relationship_schema_access_and_history_contract() -> None:
    config = resolve_config()
    db = create_client(config.url, config.service_role_key).schema("data_fabric")
    assert len(db.table("enterprise_relationships").select("id").limit(0).execute().data or []) == 0
    migration = Path("migrations/data_fabric/0018_create_atomic_relationship_write_rpc.sql").read_text(encoding="utf-8")
    assert "'version_created',false" in migration
    assert "Relationship-version history is deferred" in migration
    print("P3_RELATIONSHIP_CONTRACT_COUNTS reads=1 history=deferred")
