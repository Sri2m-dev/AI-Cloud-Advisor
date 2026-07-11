"""Opt-in P3.14 Supabase relationship/history integration tests.

These tests require P3_SUPABASE_RUN_INTEGRATION=1 and test-only Supabase
credentials. They must never run against an unapproved production database.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from data_fabric.adapters.supabase import (
    DataFabricDatabaseConfig,
    SupabaseDataFabricClient,
    SupabaseLineageRepository,
    SupabaseProvenanceRepository,
    SupabaseRelationshipRepository,
    SupabaseVersionRepository,
)
from data_fabric.contracts import EnterpriseRelationship, RelationshipType
from data_fabric.foundation import TenantContext
from data_fabric.persistence.models import AppendOnlyRecord


def _integration_client() -> SupabaseDataFabricClient:
    if os.getenv("P3_SUPABASE_RUN_INTEGRATION") != "1":
        pytest.skip("P3 Supabase relationship/history integration tests are opt-in only")
    url = os.getenv("P3_SUPABASE_TEST_URL")
    key = os.getenv("P3_SUPABASE_TEST_SERVICE_ROLE_KEY")
    if not url or not key:
        pytest.skip("P3 Supabase test URL/service role key are not configured")
    return SupabaseDataFabricClient(DataFabricDatabaseConfig(url, key))


def test_relationship_history_integration_smoke() -> None:
    client = _integration_client()
    relationships = SupabaseRelationshipRepository(client)
    versions = SupabaseVersionRepository(client)
    lineage = SupabaseLineageRepository(client)
    provenance = SupabaseProvenanceRepository(client)
    unique = uuid4().hex
    tenant = TenantContext(f"org-rh-{unique}", f"tenant-rh-{unique}")
    now = datetime.now(timezone.utc)
    source_entity_id = str(uuid4())
    target_entity_id = str(uuid4())
    relationship = EnterpriseRelationship(
        id=str(uuid4()),
        relationship_type=RelationshipType.DEPENDS_ON,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        organization_id=tenant.organization_id,
        tenant_id=tenant.tenant_id,
        created_at=now,
        updated_at=now,
    )

    created_relationship = relationships.add(relationship)
    version = versions.append(AppendOnlyRecord(
        record_id=str(uuid4()),
        organization_id=tenant.organization_id,
        tenant_id=tenant.tenant_id,
        created_at=now,
        updated_at=now,
        payload={"entity_id": source_entity_id, "canonical_id": f"canonical-{unique}", "version": 1, "payload": {"relationship_id": created_relationship.record_id}},
    ))
    lineage_event = lineage.append(AppendOnlyRecord(
        record_id=str(uuid4()),
        organization_id=tenant.organization_id,
        tenant_id=tenant.tenant_id,
        created_at=now,
        updated_at=now,
        payload={"relationship_id": created_relationship.record_id, "event_type": "relationship_created", "occurred_at": now},
    ))
    provenance_record = provenance.append(AppendOnlyRecord(
        record_id=str(uuid4()),
        organization_id=tenant.organization_id,
        tenant_id=tenant.tenant_id,
        created_at=now,
        updated_at=now,
        payload={"relationship_id": created_relationship.record_id, "source_system": "integration-test", "source_identifier": unique, "captured_at": now},
    ))

    assert relationships.get(tenant, created_relationship.record_id) is not None
    assert versions.get_snapshot(tenant, version.record_id) is not None
    assert lineage.get(tenant, lineage_event.record_id) is not None
    assert provenance.get(tenant, provenance_record.record_id) is not None
    assert relationships.get(TenantContext(tenant.organization_id, "other-tenant"), created_relationship.record_id) is None
