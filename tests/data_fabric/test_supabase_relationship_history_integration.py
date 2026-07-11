"""Opt-in P3.14 Supabase relationship/history integration tests.

These tests use the shared P3 integration safety gate and must never run against
an unapproved production or customer database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from data_fabric.adapters.supabase import (
    SupabaseDataFabricClient,
    SupabaseLineageRepository,
    SupabaseProvenanceRepository,
    SupabaseRelationshipRepository,
    SupabaseVersionRepository,
)
from data_fabric.contracts import EnterpriseRelationship, RelationshipType
from data_fabric.foundation import TenantContext
from data_fabric.persistence.models import AppendOnlyRecord
from tests.data_fabric.supabase_integration_safety import (
    cleanup_test_tenant,
    client_or_skip,
    create_test_identifier,
    create_test_tenant_context,
)


def test_relationship_history_integration_smoke() -> None:
    client = client_or_skip()
    assert isinstance(client, SupabaseDataFabricClient)
    relationships = SupabaseRelationshipRepository(client)
    versions = SupabaseVersionRepository(client)
    lineage = SupabaseLineageRepository(client)
    provenance = SupabaseProvenanceRepository(client)
    tenant = create_test_tenant_context("relationship-history")
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

    try:
        created_relationship = relationships.add(relationship)
        version = versions.append(
            AppendOnlyRecord(
                record_id=str(uuid4()),
                organization_id=tenant.organization_id,
                tenant_id=tenant.tenant_id,
                created_at=now,
                updated_at=now,
                payload={
                    "entity_id": source_entity_id,
                    "canonical_id": create_test_identifier("canonical"),
                    "version": 1,
                    "payload": {"relationship_id": created_relationship.record_id},
                },
            )
        )
        lineage_event = lineage.append(
            AppendOnlyRecord(
                record_id=str(uuid4()),
                organization_id=tenant.organization_id,
                tenant_id=tenant.tenant_id,
                created_at=now,
                updated_at=now,
                payload={
                    "relationship_id": created_relationship.record_id,
                    "event_type": "relationship_created",
                    "occurred_at": now,
                },
            )
        )
        provenance_record = provenance.append(
            AppendOnlyRecord(
                record_id=str(uuid4()),
                organization_id=tenant.organization_id,
                tenant_id=tenant.tenant_id,
                created_at=now,
                updated_at=now,
                payload={
                    "relationship_id": created_relationship.record_id,
                    "source_system": "integration-test",
                    "source_identifier": create_test_identifier("source"),
                    "captured_at": now,
                },
            )
        )

        assert relationships.get(tenant, created_relationship.record_id) is not None
        assert versions.get_snapshot(tenant, version.record_id) is not None
        assert lineage.get(tenant, lineage_event.record_id) is not None
        assert provenance.get(tenant, provenance_record.record_id) is not None
        assert relationships.get(TenantContext(tenant.organization_id, "other-tenant"), created_relationship.record_id) is None
    finally:
        cleanup_test_tenant(client, tenant)
