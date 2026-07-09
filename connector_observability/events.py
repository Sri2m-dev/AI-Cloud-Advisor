"""Connector lifecycle event names and event store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class ConnectorEventName(str, Enum):
    STARTED = "connector.started"
    AUTHENTICATED = "connector.authenticated"
    DISCOVERED = "connector.discovered"
    EXTRACTED = "connector.extracted"
    NORMALIZED = "connector.normalized"
    VALIDATED = "connector.validated"
    PUBLISHED = "connector.published"
    SUCCEEDED = "connector.succeeded"
    FAILED = "connector.failed"
    HEALTH_UPDATED = "connector.health_updated"


@dataclass(frozen=True)
class ConnectorObservabilityEvent:
    connector_id: str
    name: ConnectorEventName | str
    execution_id: str | None = None
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Mapping[str, Any] = field(default_factory=dict)


class ConnectorObservabilityEventStore:
    """In-memory event store for connector lifecycle observations."""

    def __init__(self) -> None:
        self._events: list[ConnectorObservabilityEvent] = []

    def record(self, event: ConnectorObservabilityEvent) -> ConnectorObservabilityEvent:
        self._events.append(event)
        return event

    def record_event(
        self,
        connector_id: str,
        name: ConnectorEventName | str,
        *,
        execution_id: str | None = None,
        correlation_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> ConnectorObservabilityEvent:
        return self.record(
            ConnectorObservabilityEvent(
                connector_id=connector_id,
                name=name,
                execution_id=execution_id,
                correlation_id=correlation_id,
                payload=payload or {},
            )
        )

    def list_events(self, connector_id: str | None = None) -> list[ConnectorObservabilityEvent]:
        events = self._events
        if connector_id is not None:
            events = [event for event in events if event.connector_id == connector_id]
        return list(events)

    def clear(self) -> None:
        self._events.clear()


event_store = ConnectorObservabilityEventStore()
