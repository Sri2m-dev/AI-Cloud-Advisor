"""Connector audit and execution log contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class ConnectorLogEvent:
    connector_id: str
    event_type: str
    message: str
    level: str = "info"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ConnectorLogger:
    """In-memory connector logger contract.

    Future implementations can publish to database audit tables, platform logs,
    or observability systems.
    """

    def __init__(self) -> None:
        self.events: list[ConnectorLogEvent] = []

    def record(self, event: ConnectorLogEvent) -> None:
        self.events.append(event)

    def list_events(self, connector_id: str | None = None) -> list[ConnectorLogEvent]:
        if connector_id is None:
            return list(self.events)
        return [event for event in self.events if event.connector_id == connector_id]
