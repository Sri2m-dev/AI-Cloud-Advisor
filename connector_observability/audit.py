"""Connector audit event framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class AuditEventType(str, Enum):
    CONNECTOR_REGISTERED = "connector_registered"
    CONNECTOR_ENABLED = "connector_enabled"
    CONNECTOR_DISABLED = "connector_disabled"
    SCHEDULE_CHANGED = "schedule_changed"
    MANUAL_EXECUTION = "manual_execution"
    AUTHENTICATION_FAILURE = "authentication_failure"
    VALIDATION_FAILURE = "validation_failure"
    PUBLISH_FAILURE = "publish_failure"
    EXECUTION_FAILURE = "execution_failure"
    EXECUTION_SUCCEEDED = "execution_succeeded"


@dataclass(frozen=True)
class ConnectorAuditEvent:
    """Governance-grade connector audit event."""

    connector_id: str
    event_type: AuditEventType | str
    actor: str | None = None
    execution_id: str | None = None
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ConnectorAuditLog:
    """In-memory audit log for connector governance events."""

    def __init__(self) -> None:
        self._events: list[ConnectorAuditEvent] = []

    def record(self, event: ConnectorAuditEvent) -> ConnectorAuditEvent:
        self._events.append(event)
        return event

    def record_event(
        self,
        connector_id: str,
        event_type: AuditEventType | str,
        *,
        actor: str | None = None,
        execution_id: str | None = None,
        correlation_id: str | None = None,
        message: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> ConnectorAuditEvent:
        return self.record(
            ConnectorAuditEvent(
                connector_id=connector_id,
                event_type=event_type,
                actor=actor,
                execution_id=execution_id,
                correlation_id=correlation_id,
                message=message,
                metadata=metadata or {},
            )
        )

    def list_events(self, connector_id: str | None = None, event_type: AuditEventType | str | None = None) -> list[ConnectorAuditEvent]:
        events = self._events
        if connector_id is not None:
            events = [event for event in events if event.connector_id == connector_id]
        if event_type is not None:
            expected = getattr(event_type, "value", event_type)
            events = [event for event in events if getattr(event.event_type, "value", event.event_type) == expected]
        return list(events)

    def clear(self) -> None:
        self._events.clear()


audit_log = ConnectorAuditLog()
