from datetime import datetime, timedelta, timezone

import pytest

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship, EntityType
from data_fabric.versioning import (
    DeterministicVersionComparator,
    HistoryQuery,
    InMemoryTemporalHistoryStore,
    InMemoryVersionStore,
    TemporalRecord,
    VersionRecord,
    VersioningValidationError,
)
from data_fabric.versioning.models import payload_hash


BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_entity(**overrides):
    values = {
        "id": "ent-1",
        "canonical_id": "application:checkout",
        "entity_type": EntityType.APPLICATION,
        "name": "Checkout",
        "source_system": "servicenow",
        "source_identifier": "app-123",
        "organization_id": "org-1",
        "tenant_id": "tenant-1",
        "version": 1,
        "created_at": BASE_TIME,
        "updated_at": BASE_TIME,
        "tags": ["tier-1"],
        "metadata": {"criticality": "high", "nested": {"a": 1}},
    }
    values.update(overrides)
    return EnterpriseEntity(**values)


def make_relationship(**overrides):
    values = {
        "id": "rel-1",
        "relationship_type": "runs_on",
        "source_entity_id": "ent-1",
        "target_entity_id": "ent-2",
        "organization_id": "org-1",
        "tenant_id": "tenant-1",
        "source_system": "servicenow",
        "source_identifier": "rel-123",
        "version": 1,
        "created_at": BASE_TIME,
        "updated_at": BASE_TIME,
        "tags": ["derived"],
        "metadata": {"confidence": "source"},
    }
    values.update(overrides)
    return EnterpriseRelationship(**values)


def make_temporal_record(**overrides):
    payload = overrides.pop("payload", {"name": "Checkout"})
    values = {
        "record_id": "hist-1",
        "subject_id": "ent-1",
        "subject_type": "entity",
        "organization_id": "org-1",
        "tenant_id": "tenant-1",
        "version": 1,
        "effective_from": BASE_TIME,
        "effective_to": None,
        "recorded_at": BASE_TIME,
        "payload": payload,
        "payload_hash": payload_hash(payload),
    }
    values.update(overrides)
    return TemporalRecord(**values)


def make_version_record(snapshot_id, payload):
    return VersionRecord(
        snapshot_id=snapshot_id,
        subject_id="subject-1",
        subject_type="entity",
        organization_id="org-1",
        tenant_id="tenant-1",
        version=1,
        recorded_at=BASE_TIME,
        effective_from=BASE_TIME,
        effective_to=None,
        source_system="source",
        source_identifier="source-1",
        payload=payload,
        payload_hash=payload_hash(payload),
    )


def test_entity_snapshot_remains_unchanged_after_source_mutation() -> None:
    store = InMemoryVersionStore()
    entity = make_entity()

    snapshot = store.create_entity_snapshot(entity, effective_from=BASE_TIME)
    entity.tags.append("mutated")
    entity.metadata["nested"]["a"] = 99
    entity.name = "Changed"

    assert snapshot.payload["tags"] == ("tier-1",)
    assert snapshot.payload["metadata"]["nested"]["a"] == 1
    assert snapshot.payload["name"] == "Checkout"


def test_relationship_snapshot_remains_unchanged_after_source_mutation() -> None:
    store = InMemoryVersionStore()
    relationship = make_relationship()

    snapshot = store.create_relationship_snapshot(relationship, effective_from=BASE_TIME)
    relationship.tags.append("mutated")
    relationship.metadata["confidence"] = "changed"

    assert snapshot.payload["tags"] == ("derived",)
    assert snapshot.payload["metadata"]["confidence"] == "source"


def test_monotonically_increasing_versions_are_accepted() -> None:
    store = InMemoryVersionStore()
    first = make_entity(version=1)
    second = make_entity(version=2, name="Checkout API")

    store.create_entity_snapshot(first, effective_from=BASE_TIME)
    snapshot = store.create_entity_snapshot(second, effective_from=BASE_TIME + timedelta(days=1))

    assert snapshot.version == 2


def test_duplicate_version_is_rejected() -> None:
    store = InMemoryVersionStore()
    store.create_entity_snapshot(make_entity(version=1), effective_from=BASE_TIME)

    with pytest.raises(VersioningValidationError):
        store.create_entity_snapshot(make_entity(version=1, name="Changed"), effective_from=BASE_TIME + timedelta(days=1))


def test_out_of_order_version_is_rejected() -> None:
    store = InMemoryVersionStore()
    store.create_entity_snapshot(make_entity(version=2), effective_from=BASE_TIME)

    with pytest.raises(VersioningValidationError):
        store.create_entity_snapshot(make_entity(version=1, name="Changed"), effective_from=BASE_TIME + timedelta(days=1))


def test_unchanged_payload_is_rejected_by_default() -> None:
    store = InMemoryVersionStore()
    store.create_entity_snapshot(make_entity(version=1), effective_from=BASE_TIME)

    with pytest.raises(VersioningValidationError):
        store.create_entity_snapshot(make_entity(version=2), effective_from=BASE_TIME + timedelta(days=1))


def test_unchanged_payload_can_be_stored_when_explicitly_allowed() -> None:
    store = InMemoryVersionStore()
    store.create_entity_snapshot(make_entity(version=1), effective_from=BASE_TIME)

    snapshot = store.create_entity_snapshot(
        make_entity(version=2),
        effective_from=BASE_TIME + timedelta(days=1),
        allow_unchanged=True,
    )

    assert snapshot.version == 2


def test_deterministic_hash_ignores_dictionary_insertion_order() -> None:
    first = {"a": 1, "b": {"x": 2, "y": 3}}
    second = {"b": {"y": 3, "x": 2}, "a": 1}

    assert payload_hash(first) == payload_hash(second)


def test_latest_snapshot_lookup_works() -> None:
    store = InMemoryVersionStore()
    store.create_entity_snapshot(make_entity(version=1), effective_from=BASE_TIME)
    store.create_entity_snapshot(make_entity(version=2, name="Checkout API"), effective_from=BASE_TIME + timedelta(days=1))

    latest = store.get_latest_entity_snapshot("ent-1", organization_id="org-1", tenant_id="tenant-1")

    assert latest is not None
    assert latest.version == 2
    assert latest.payload["name"] == "Checkout API"


def test_list_versions_returns_stable_order() -> None:
    store = InMemoryVersionStore()
    store.create_entity_snapshot(make_entity(version=1), effective_from=BASE_TIME)
    store.create_entity_snapshot(make_entity(version=2, name="Checkout API"), effective_from=BASE_TIME + timedelta(days=1))

    versions = store.list_entity_versions("ent-1", organization_id="org-1", tenant_id="tenant-1")

    assert [snapshot.version for snapshot in versions] == [1, 2]


def test_nested_comparison_reports_added_removed_and_changed_fields() -> None:
    comparator = DeterministicVersionComparator()
    first = make_version_record("one", {"a": 1, "nested": {"same": True, "old": "x", "changed": 1}, "items": ["a"]})
    second = make_version_record("two", {"a": 2, "nested": {"same": True, "new": "y", "changed": 3}, "items": ["a", "b"]})

    comparison = comparator.compare(first, second)
    changes = {(diff.path, diff.change_type) for diff in comparison.differences}

    assert ("$.a", "changed") in changes
    assert ("$.nested.old", "removed") in changes
    assert ("$.nested.new", "added") in changes
    assert ("$.nested.changed", "changed") in changes
    assert ("$.items[1]", "added") in changes


def test_unchanged_comparison_returns_no_differences() -> None:
    comparator = DeterministicVersionComparator()
    first = make_version_record("one", {"b": 2, "a": {"x": 1}})
    second = make_version_record("two", {"a": {"x": 1}, "b": 2})

    assert comparator.compare(first, second).differences == ()


def test_point_in_time_temporal_lookup_works() -> None:
    store = InMemoryTemporalHistoryStore()
    store.append_record(make_temporal_record(record_id="hist-1", version=1, effective_to=BASE_TIME + timedelta(days=10)))
    store.append_record(make_temporal_record(record_id="hist-2", version=2, effective_from=BASE_TIME + timedelta(days=10), payload={"name": "Checkout API"}))

    record = store.get_record_at_time(
        "ent-1",
        organization_id="org-1",
        tenant_id="tenant-1",
        query_time=BASE_TIME + timedelta(days=12),
    )

    assert record is not None
    assert record.version == 2


def test_open_record_can_be_closed() -> None:
    store = InMemoryTemporalHistoryStore()
    store.append_record(make_temporal_record(payload={"name": "Checkout"}))

    closed = store.close_current_record(
        "ent-1",
        organization_id="org-1",
        tenant_id="tenant-1",
        effective_to=BASE_TIME + timedelta(days=1),
    )

    assert closed.effective_to == BASE_TIME + timedelta(days=1)
    assert closed.payload["name"] == "Checkout"
    assert store.get_current_record("ent-1", organization_id="org-1", tenant_id="tenant-1") is None


def test_invalid_effective_period_is_rejected() -> None:
    with pytest.raises(VersioningValidationError):
        make_temporal_record(effective_to=BASE_TIME - timedelta(seconds=1))


def test_overlapping_periods_are_detected() -> None:
    store = InMemoryTemporalHistoryStore()
    store.append_record(make_temporal_record(record_id="hist-1", effective_to=BASE_TIME + timedelta(days=10)))
    store.append_record(
        make_temporal_record(
            record_id="hist-2",
            version=2,
            effective_from=BASE_TIME + timedelta(days=5),
            effective_to=BASE_TIME + timedelta(days=12),
        ),
        allow_overlap=True,
    )

    overlaps = store.detect_overlapping_effective_periods("ent-1", organization_id="org-1", tenant_id="tenant-1")

    assert len(overlaps) == 1


def test_only_one_current_record_exists() -> None:
    store = InMemoryTemporalHistoryStore()
    store.append_record(make_temporal_record(record_id="hist-1"))

    with pytest.raises(VersioningValidationError):
        store.append_record(make_temporal_record(record_id="hist-2", version=2, effective_from=BASE_TIME + timedelta(days=1)))


def test_organization_and_tenant_isolation_works() -> None:
    store = InMemoryVersionStore()
    first = store.create_entity_snapshot(make_entity(id="shared", tenant_id="tenant-1"), effective_from=BASE_TIME)
    second = store.create_entity_snapshot(make_entity(id="shared", tenant_id="tenant-2", source_identifier="app-456"), effective_from=BASE_TIME)

    assert store.get_latest_entity_snapshot("shared", organization_id="org-1", tenant_id="tenant-1") == first
    assert store.get_latest_entity_snapshot("shared", organization_id="org-1", tenant_id="tenant-2") == second
    assert store.get_latest_entity_snapshot("shared", organization_id="org-1", tenant_id="tenant-3") is None


def test_returned_records_cannot_mutate_internal_store_state() -> None:
    store = InMemoryVersionStore()
    snapshot = store.create_entity_snapshot(make_entity(), effective_from=BASE_TIME)

    with pytest.raises(TypeError):
        snapshot.payload["metadata"] = {"mutated": True}
    with pytest.raises(TypeError):
        snapshot.payload["metadata"]["criticality"] = "low"

    latest = store.get_latest_entity_snapshot("ent-1", organization_id="org-1", tenant_id="tenant-1")
    assert latest is not None
    assert latest.payload["metadata"]["criticality"] == "high"


def test_repeated_operations_produce_deterministic_output() -> None:
    comparator = DeterministicVersionComparator()
    first = make_version_record("one", {"z": 1, "a": {"b": 2}})
    second = make_version_record("two", {"a": {"b": 3}, "z": 1})

    first_result = comparator.compare(first, second)
    second_result = comparator.compare(first, second)

    assert first_result == second_result
    assert [diff.path for diff in first_result.differences] == sorted(diff.path for diff in first_result.differences)


def test_query_history_filters_effective_range() -> None:
    store = InMemoryTemporalHistoryStore()
    store.append_record(make_temporal_record(record_id="hist-1", version=1, effective_to=BASE_TIME + timedelta(days=5)))
    store.append_record(make_temporal_record(record_id="hist-2", version=2, effective_from=BASE_TIME + timedelta(days=5), effective_to=BASE_TIME + timedelta(days=10)))

    result = store.query_history(
        HistoryQuery(
            subject_id="ent-1",
            organization_id="org-1",
            tenant_id="tenant-1",
            effective_from=BASE_TIME + timedelta(days=6),
            effective_to=BASE_TIME + timedelta(days=9),
        )
    )

    assert [record.record_id for record in result.records] == ["hist-2"]



