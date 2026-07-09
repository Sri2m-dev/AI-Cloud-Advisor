"""Connector telemetry event contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class TelemetryEventType(str, Enum):
    CONNECTOR_STARTED = "ConnectorStarted"
    AUTHENTICATION_COMPLETED = "AuthenticationCompleted"
    DISCOVERY_COMPLETED = "DiscoveryCompleted"
    EXTRACTION_COMPLETED = "ExtractionCompleted"
    VALIDATION_COMPLETED = "ValidationCompleted"
    PUBLISH_COMPLETED = "PublishCompleted"
    CONNECTOR_SUCCEEDED = "ConnectorSucceeded"
    CONNECTOR_FAILED = "ConnectorFailed"


@dataclass(frozen=True)
class TelemetryEvent:
    """Structured connector telemetry event."""

    connector_id: str
    event_type: TelemetryEventType | str
    execution_id: str | None = None
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ConnectorTelemetry:
    """In-memory telemetry event stream."""

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> TelemetryEvent:
        self._events.append(event)
        return event

    def emit_event(
        self,
        connector_id: str,
        event_type: TelemetryEventType | str,
        *,
        execution_id: str | None = None,
        correlation_id: str | None = None,
        message: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> TelemetryEvent:
        return self.emit(
            TelemetryEvent(
                connector_id=connector_id,
                event_type=event_type,
                execution_id=execution_id,
                correlation_id=correlation_id,
                message=message,
                metadata=metadata or {},
            )
        )

    def list_events(
        self,
        *,
        connector_id: str | None = None,
        execution_id: str | None = None,
        correlation_id: str | None = None,
    ) -> list[TelemetryEvent]:
        events = self._events
        if connector_id is not None:
            events = [event for event in events if event.connector_id == connector_id]
        if execution_id is not None:
            events = [event for event in events if event.execution_id == execution_id]
        if correlation_id is not None:
            events = [event for event in events if event.correlation_id == correlation_id]
        return list(events)

    def clear(self) -> None:
        self._events.clear()


telemetry = ConnectorTelemetry()
