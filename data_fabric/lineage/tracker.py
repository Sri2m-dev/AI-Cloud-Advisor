"""In-memory lineage tracker implementation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from data_fabric.lineage.exceptions import LineageValidationError
from data_fabric.lineage.interfaces import LineageTracker

LineageEventType = Literal[
    "source",
    "normalization",
    "canonicalization",
    "relationship",
]


@dataclass(frozen=True, slots=True)
class LineageEvent:
    """One explainability event in a source-to-canonical flow."""

    id: str
    event_type: LineageEventType
    source_system: str
    source_identifier: str
    organization_id: str
    tenant_id: str | None = None
    entity_id: str | None = None
    relationship_id: str | None = None
    raw_record_id: str | None = None
    normalized_record_id: str | None = None
    transformation_name: str | None = None
    transformation_version: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LineagePath:
    """Ordered lineage events for a canonical entity or relationship."""

    subject_id: str
    events: tuple[LineageEvent, ...]

    @property
    def is_empty(self) -> bool:
        return not self.events


class InMemoryLineageTracker(LineageTracker):
    """Non-persistent reference tracker for lineage events."""

    _ORDER = {
        "source": 0,
        "normalization": 1,
        "canonicalization": 2,
        "relationship": 3,
    }

    def __init__(self) -> None:
        self._events: list[LineageEvent] = []

    def record_source_event(self, event: LineageEvent) -> LineageEvent:
        return self._record(event, expected_type="source")

    def record_normalization_event(self, event: LineageEvent) -> LineageEvent:
        return self._record(event, expected_type="normalization")

    def record_canonicalization_event(self, event: LineageEvent) -> LineageEvent:
        self._validate_subject(event, requires_entity=True)
        return self._record(event, expected_type="canonicalization")

    def record_relationship_event(self, event: LineageEvent) -> LineageEvent:
        self._validate_subject(event, requires_relationship=True)
        return self._record(event, expected_type="relationship")

    def trace_lineage_by_entity_id(self, entity_id: str) -> LineagePath:
        events = [event for event in self._events if event.entity_id == entity_id]
        return LineagePath(subject_id=entity_id, events=self._sort_and_copy(events))

    def trace_lineage_by_relationship_id(self, relationship_id: str) -> LineagePath:
        events = [event for event in self._events if event.relationship_id == relationship_id]
        return LineagePath(subject_id=relationship_id, events=self._sort_and_copy(events))

    def explain_entity_origin(self, entity_id: str) -> str:
        path = self.trace_lineage_by_entity_id(entity_id)
        if path.is_empty:
            return f"No lineage recorded for entity {entity_id}."
        first = path.events[0]
        steps = " -> ".join(event.event_type for event in path.events)
        return (
            f"Entity {entity_id} originated from {first.source_system}/"
            f"{first.source_identifier} via {steps}."
        )

    def explain_relationship_origin(self, relationship_id: str) -> str:
        path = self.trace_lineage_by_relationship_id(relationship_id)
        if path.is_empty:
            return f"No lineage recorded for relationship {relationship_id}."
        first = path.events[0]
        steps = " -> ".join(event.event_type for event in path.events)
        return (
            f"Relationship {relationship_id} originated from {first.source_system}/"
            f"{first.source_identifier} via {steps}."
        )

    def _record(self, event: LineageEvent, *, expected_type: LineageEventType) -> LineageEvent:
        self._validate_event(event)
        if event.event_type != expected_type:
            raise LineageValidationError(
                f"Expected {expected_type} lineage event, received {event.event_type}"
            )
        stored = deepcopy(event)
        self._events.append(stored)
        return deepcopy(stored)

    @staticmethod
    def _validate_event(event: LineageEvent) -> None:
        required = {
            "id": event.id,
            "event_type": event.event_type,
            "source_system": event.source_system,
            "source_identifier": event.source_identifier,
            "organization_id": event.organization_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise LineageValidationError(
                f"Lineage event is missing required field(s): {', '.join(missing)}"
            )

    @staticmethod
    def _validate_subject(
        event: LineageEvent,
        *,
        requires_entity: bool = False,
        requires_relationship: bool = False,
    ) -> None:
        if requires_entity and not event.entity_id:
            raise LineageValidationError("Lineage event requires entity_id")
        if requires_relationship and not event.relationship_id:
            raise LineageValidationError("Lineage event requires relationship_id")

    def _sort_and_copy(self, events: list[LineageEvent]) -> tuple[LineageEvent, ...]:
        ordered = sorted(
            events,
            key=lambda event: (self._ORDER[event.event_type], event.occurred_at),
        )
        return tuple(deepcopy(event) for event in ordered)

