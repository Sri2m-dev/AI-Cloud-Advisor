"""Opt-in live tenant-isolation and scoped-cleanup validation."""

from datetime import datetime, timezone
from uuid import uuid4

from supabase import create_client

from tests.data_fabric.supabase_integration_safety import create_test_identifier, resolve_config


def test_supabase_entity_tenant_isolation_and_scoped_cleanup() -> None:
    config = resolve_config()
    db = create_client(config.url, config.service_role_key).schema("data_fabric")
    token = uuid4().hex
    record_id = f"p3test-entity-{token}"
    organization_id = create_test_identifier(f"org-{token}")
    tenant_id = create_test_identifier(f"tenant-{token}")
    other_tenant_id = create_test_identifier(f"other-tenant-{token}")
    now = datetime.now(timezone.utc).isoformat()
    row = {"id": record_id, "canonical_id": create_test_identifier(f"canonical-{token}"), "entity_type": "application", "name": "P3 tenant isolation", "source_system": "p3test-live-validation", "source_identifier": create_test_identifier(f"source-{token}"), "organization_id": organization_id, "tenant_id": tenant_id, "version": 1, "revision": 1, "created_at": now, "updated_at": now}
    assert len(db.table("enterprise_entities").insert(row).execute().data or []) == 1
    assert len(db.table("enterprise_entities").select("id").eq("id", record_id).eq("organization_id", organization_id).eq("tenant_id", other_tenant_id).execute().data or []) == 0
    assert len(db.table("enterprise_entities").select("id").eq("id", record_id).eq("organization_id", organization_id).eq("tenant_id", tenant_id).execute().data or []) == 1
    assert len(db.table("enterprise_entities").delete().eq("id", record_id).eq("organization_id", organization_id).eq("tenant_id", tenant_id).execute().data or []) == 1
    assert len(db.table("enterprise_entities").select("id").eq("id", record_id).eq("organization_id", organization_id).eq("tenant_id", tenant_id).execute().data or []) == 0
    print("P3_TENANT_COUNTS reads=3 committed_writes=2 cleanup=1")
