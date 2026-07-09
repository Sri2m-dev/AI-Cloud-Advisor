import pytest

from data_fabric.lineage import (
    InMemoryLineageTracker,
    InMemoryProvenanceTracker,
    LineageEvent,
    LineageValidationError,
    ProvenanceRecord,
)


def make_lineage_event(**overrides):
    values = {
        "id": "lin-1",
        "event_type": "source",
        "source_system": "servicenow",
        "source_identifier": "app-123",
        "organization_id": "org-1",
        "raw_record_id": "raw-1",
    }
    values.update(overrides)
    return LineageEvent(**values)


def make_provenance_record(**overrides):
    values = {
        "id": "prov-1",
        "source_system": "servicenow",
        "source_identifier": "app-123",
        "organization_id": "org-1",
        "collection_method": "connector_sync",
        "entity_id": "ent-1",
        "connector_version": "1.0.0",
        "normalization_rule": "servicenow_application_v1",
    }
    values.update(overrides)
    return ProvenanceRecord(**values)


def test_lineage_tracker_records_entity_flow_in_order() -> None:
    tracker = InMemoryLineageTracker()

    tracker.record_canonicalization_event(
        make_lineage_event(
            id="lin-3",
            event_type="canonicalization",
            entity_id="ent-1",
            normalized_record_id="norm-1",
            transformation_name="canonical_entity_mapper",
        )
    )
    tracker.record_source_event(make_lineage_event(id="lin-1", event_type="source"))
    tracker.record_normalization_event(
        make_lineage_event(
            id="lin-2",
            event_type="normalization",
            normalized_record_id="norm-1",
            transformation_name="servicenow_normalizer",
        )
    )

    path = tracker.trace_lineage_by_entity_id("ent-1")

    assert path.subject_id == "ent-1"
    assert [event.event_type for event in path.events] == ["canonicalization"]


def test_lineage_tracker_traces_shared_entity_events() -> None:
    tracker = InMemoryLineageTracker()

    for event_type in ["source", "normalization", "canonicalization"]:
        tracker_method = getattr(tracker, f"record_{event_type}_event")
        tracker_method(
            make_lineage_event(
                id=f"lin-{event_type}",
                event_type=event_type,
                entity_id="ent-1",
            )
        )

    path = tracker.trace_lineage_by_entity_id("ent-1")

    assert [event.event_type for event in path.events] == [
        "source",
        "normalization",
        "canonicalization",
    ]
    assert "servicenow/app-123" in tracker.explain_entity_origin("ent-1")


def test_lineage_tracker_records_relationship_origin() -> None:
    tracker = InMemoryLineageTracker()
    event = make_lineage_event(
        id="lin-rel-1",
        event_type="relationship",
        relationship_id="rel-1",
        entity_id="ent-1",
    )

    recorded = tracker.record_relationship_event(event)

    assert recorded == event
    explanation = tracker.explain_relationship_origin("rel-1")
    assert "Relationship rel-1 originated from servicenow/app-123" in explanation


def test_lineage_tracker_validates_event_type_and_required_subjects() -> None:
    tracker = InMemoryLineageTracker()

    with pytest.raises(LineageValidationError):
        tracker.record_source_event(make_lineage_event(source_system=""))

    with pytest.raises(LineageValidationError):
        tracker.record_source_event(make_lineage_event(event_type="normalization"))

    with pytest.raises(LineageValidationError):
        tracker.record_canonicalization_event(
            make_lineage_event(event_type="canonicalization", entity_id=None)
        )

    with pytest.raises(LineageValidationError):
        tracker.record_relationship_event(
            make_lineage_event(event_type="relationship", relationship_id=None)
        )


def test_lineage_tracker_returns_copies() -> None:
    tracker = InMemoryLineageTracker()
    tracker.record_source_event(
        make_lineage_event(entity_id="ent-1", metadata={"stage": "raw"})
    )

    path = tracker.trace_lineage_by_entity_id("ent-1")
    path.events[0].metadata["stage"] = "changed"

    second_path = tracker.trace_lineage_by_entity_id("ent-1")
    assert second_path.events[0].metadata["stage"] == "raw"


def test_lineage_tracker_explains_missing_records() -> None:
    tracker = InMemoryLineageTracker()

    assert tracker.explain_entity_origin("missing") == "No lineage recorded for entity missing."
    assert (
        tracker.explain_relationship_origin("missing")
        == "No lineage recorded for relationship missing."
    )


def test_provenance_tracker_records_and_traces_by_source() -> None:
    tracker = InMemoryProvenanceTracker()
    record = make_provenance_record()

    recorded = tracker.record_provenance(record)
    traced = tracker.trace_provenance_by_source("servicenow", "app-123")

    assert recorded == record
    assert traced == [record]


def test_provenance_tracker_explains_entity_and_relationship_origin() -> None:
    tracker = InMemoryProvenanceTracker()
    tracker.record_provenance(make_provenance_record(entity_id="ent-1"))
    tracker.record_provenance(
        make_provenance_record(
            id="prov-2",
            entity_id=None,
            relationship_id="rel-1",
            source_identifier="rel-123",
        )
    )

    assert "Entity ent-1 is derived from servicenow/app-123" in tracker.explain_entity_origin(
        "ent-1"
    )
    assert (
        "Relationship rel-1 is derived from servicenow/rel-123"
        in tracker.explain_relationship_origin("rel-1")
    )


def test_provenance_tracker_validates_required_fields_and_subject() -> None:
    tracker = InMemoryProvenanceTracker()

    with pytest.raises(LineageValidationError):
        tracker.record_provenance(make_provenance_record(collection_method=""))

    with pytest.raises(LineageValidationError):
        tracker.record_provenance(
            make_provenance_record(entity_id=None, relationship_id=None)
        )


def test_provenance_tracker_returns_copies() -> None:
    tracker = InMemoryProvenanceTracker()
    tracker.record_provenance(make_provenance_record(metadata={"trust": "high"}))

    traced = tracker.trace_provenance_by_source("servicenow", "app-123")
    traced[0].metadata["trust"] = "low"

    second_trace = tracker.trace_provenance_by_source("servicenow", "app-123")
    assert second_trace[0].metadata["trust"] == "high"
