from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.foundation import DataFabricConflictError, DataFabricTenantBoundaryError, DataFabricValidationError, TenantContext
from data_fabric.orchestration import IdempotencyState
from data_fabric.persistence import (
    AppendOnlyRecord,
    EntityPersistenceMapper,
    InMemoryEntityRepository,
    InMemoryIdempotencyRepository,
    InMemoryLineageRepository,
    InMemoryPersistenceUnitOfWork,
    InMemoryRelationshipRepository,
    InMemoryVersionRepository,
    MutableRecord,
    PageRequest,
    PersistenceImmutableStateError,
    RelationshipPersistenceMapper,
    RepositoryQuery,
    SortSpecification,
)


def tenant() -> TenantContext:
    return TenantContext("org-1", "tenant-a")


def entity() -> EnterpriseEntity:
    return EnterpriseEntity(
        id="entity-1",
        canonical_id="canonical-1",
        entity_type="cloud_resource",
        name="Compute",
        source_system="aws",
        source_identifier="i-123",
        organization_id="org-1",
        tenant_id="tenant-a",
        metadata={"owner": "platform"},
    )


def relationship() -> EnterpriseRelationship:
    return EnterpriseRelationship(
        id="rel-1",
        relationship_type="depends_on",
        source_entity_id="entity-1",
        target_entity_id="entity-2",
        organization_id="org-1",
        tenant_id="tenant-a",
        source_system="aws",
        source_identifier="rel-src",
    )


def test_domain_entity_round_trip_mapping():
    mapper = EntityPersistenceMapper()
    record = mapper.domain_to_record(entity(), tenant())
    restored = mapper.record_to_domain(record)

    assert restored.id == "entity-1"
    assert restored.entity_type.value == "cloud_resource"
    assert restored.metadata["owner"] == "platform"


def test_domain_relationship_round_trip_mapping():
    mapper = RelationshipPersistenceMapper()
    record = mapper.domain_to_record(relationship(), tenant())
    restored = mapper.record_to_domain(record)

    assert restored.id == "rel-1"
    assert restored.relationship_type.value == "depends_on"
    assert restored.source_entity_id == "entity-1"


def test_mapper_does_not_mutate_source_and_preserves_tenant_context():
    source = entity()
    source.metadata["aliases"] = ["before"]
    record = EntityPersistenceMapper().domain_to_record(source, tenant())

    assert source.metadata == {"owner": "platform", "aliases": ["before"]}
    assert record.organization_id == "org-1"
    assert record.tenant_id == "tenant-a"
    assert record.payload["entity_type"] == "cloud_resource"


def test_unsupported_schema_version_rejected():
    mapper = EntityPersistenceMapper()
    record = mapper.domain_to_record(entity(), tenant())
    unsupported = replace(record, schema_version=999)

    with pytest.raises(DataFabricValidationError):
        mapper.record_to_domain(unsupported)


def test_mutable_record_create_update_and_revision_increment():
    repo = InMemoryEntityRepository()
    record = EntityPersistenceMapper().domain_to_record(entity(), tenant())

    created = repo.add(record)
    updated = repo.update(replace(created, metadata={"changed": True}), expected_revision=1)

    assert created.revision == 1
    assert updated.revision == 2
    assert updated.concurrency_token.revision == 2


def test_stale_update_rejected():
    repo = InMemoryEntityRepository()
    record = EntityPersistenceMapper().domain_to_record(entity(), tenant())
    repo.add(record)
    repo.update(replace(record, metadata={"first": True}), expected_revision=1)

    with pytest.raises(DataFabricConflictError):
        repo.update(replace(record, metadata={"stale": True}), expected_revision=1)


def test_cross_tenant_lookup_returns_no_result_and_update_rejected():
    repo = InMemoryEntityRepository()
    record = EntityPersistenceMapper().domain_to_record(entity(), tenant())
    other = TenantContext("org-1", "tenant-b")
    repo.add(record)

    assert repo.get(other, "entity-1") is None
    with pytest.raises(DataFabricTenantBoundaryError):
        repo.update(replace(record, tenant_id="tenant-b"), expected_revision=1)


def test_soft_deactivated_record_excluded_by_default_and_included_explicitly():
    repo = InMemoryEntityRepository()
    record = EntityPersistenceMapper().domain_to_record(entity(), tenant())
    repo.add(record)

    deactivated = repo.deactivate(tenant(), "entity-1", deactivated_by="tester")

    assert deactivated.active is False
    assert deactivated.deactivated_by == "tester"
    assert repo.get(tenant(), "entity-1") is None
    assert repo.get(tenant(), "entity-1", include_inactive=True) is not None


def test_immutable_version_record_cannot_be_updated():
    repo = InMemoryVersionRepository()
    record = AppendOnlyRecord("version-1", "org-1", "tenant-a", payload={"subject_id": "entity-1", "version": 1})
    repo.append(record)

    with pytest.raises(PersistenceImmutableStateError):
        repo.update(record)


def test_append_only_lineage_insert_and_duplicate_behavior():
    repo = InMemoryLineageRepository()
    record = AppendOnlyRecord("lineage-1", "org-1", "tenant-a", payload={"entity_id": "entity-1"})

    repo.append(record)
    with pytest.raises(Exception):
        repo.append(record)


def test_stable_query_ordering_and_pagination():
    repo = InMemoryEntityRepository()
    for index in (3, 1, 2):
        repo.add(MutableRecord(f"entity-{index}", "org-1", "tenant-a", payload={"rank": index}))

    query = RepositoryQuery(
        tenant(),
        sort=SortSpecification("rank"),
        page=PageRequest(offset=1, limit=1),
    )
    result = repo.search(query)

    assert result.total_count == 3
    assert [item.record_id for item in result.items] == ["entity-2"]


def test_idempotency_same_key_same_hash_and_different_hash_conflict():
    repo = InMemoryIdempotencyRepository()
    first = repo.reserve_key(tenant(), "idem-1", "hash-a")
    second = repo.reserve_key(tenant(), "idem-1", "hash-a")

    assert first.record_id == second.record_id
    with pytest.raises(DataFabricConflictError):
        repo.reserve_key(tenant(), "idem-1", "hash-b")


def test_idempotency_complete_failed_and_status_behavior():
    repo = InMemoryIdempotencyRepository()
    repo.reserve_key(tenant(), "idem-1", "hash-a")
    completed = repo.mark_completed(tenant(), "idem-1", "result-1")

    assert completed.payload["state"] == IdempotencyState.COMPLETED.value
    assert repo.get_status(tenant(), "idem-1") is IdempotencyState.COMPLETED

    repo.reserve_key(tenant(), "idem-2", "hash-b")
    failed = repo.mark_failed(tenant(), "idem-2", "boom")
    assert failed.payload["failure_reason"] == "boom"


def test_persistence_unit_of_work_commit_and_rollback():
    uow = InMemoryPersistenceUnitOfWork()
    record = MutableRecord("tx-1", "org-1", "tenant-a")

    uow.begin(tenant())
    uow.stage_add(uow.repositories.entities, record)
    uow.commit()
    assert uow.repositories.entities.exists(tenant(), "tx-1")

    rollback_record = MutableRecord("tx-2", "org-1", "tenant-a")
    uow.begin(tenant())
    uow.stage_add(uow.repositories.entities, rollback_record)
    uow.rollback("not today")
    assert not uow.repositories.entities.exists(tenant(), "tx-2")
    assert uow.failure_reason == "not today"


def test_failed_commit_leaves_no_partial_state():
    uow = InMemoryPersistenceUnitOfWork()
    record = MutableRecord("tx-fail", "org-1", "tenant-a")
    duplicate = MutableRecord("tx-fail", "org-1", "tenant-a")

    uow.begin(tenant())
    uow.stage_add(uow.repositories.entities, record)
    uow.stage_add(uow.repositories.entities, duplicate)
    with pytest.raises(Exception):
        uow.commit()

    assert not uow.repositories.entities.exists(tenant(), "tx-fail")


def test_tenant_cannot_change_inside_transaction():
    uow = InMemoryPersistenceUnitOfWork()
    uow.begin(tenant())

    with pytest.raises(Exception):
        uow.stage_add(uow.repositories.entities, MutableRecord("other", "org-1", "tenant-b"))


def test_no_database_supabase_orm_or_migration_import_exists():
    content = "\n".join(path.read_text(encoding="utf-8") for path in Path("data_fabric/persistence").glob("*.py"))
    forbidden = ("supabase", "sqlalchemy", "sqlite", "psycopg", "alembic", "migration")

    assert all(term not in content.casefold() for term in forbidden)


def test_domain_contracts_do_not_import_persistence():
    content = "\n".join(path.read_text(encoding="utf-8") for path in Path("data_fabric/contracts").glob("*.py"))

    assert "data_fabric.persistence" not in content
