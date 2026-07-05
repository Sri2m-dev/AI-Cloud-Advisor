"""Connector audit and execution log contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class ConnectorRunLog:
    """Connector execution log entry."""

    connector_id: str
    run_id: str
    event_type: str
    message: str
    level: str = "info"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


# Backward-compatible name from E8.1.1.
ConnectorLogEvent = ConnectorRunLog


class ConnectorLogger:
    """In-memory connector logger contract.

    Future implementations can publish to database audit tables, platform logs,
    or observability systems.
    """

    def __init__(self) -> None:
        self.events: list[ConnectorRunLog] = []

    def record_run_log(self, event: ConnectorRunLog) -> ConnectorRunLog:
        self.events.append(event)
        return event

    def list_run_logs(self, connector_id: str | None = None, run_id: str | None = None) -> list[ConnectorRunLog]:
        events = self.events
        if connector_id is not None:
            events = [event for event in events if event.connector_id == connector_id]
        if run_id is not None:
            events = [event for event in events if event.run_id == run_id]
        return list(events)

    # Backward-compatible aliases from E8.1.1.
    def record(self, event: ConnectorRunLog) -> None:
        self.record_run_log(event)

    def list_events(self, connector_id: str | None = None) -> list[ConnectorRunLog]:
        return self.list_run_logs(connector_id=connector_id)


logger = ConnectorLogger()


def record_run_log(event: ConnectorRunLog) -> ConnectorRunLog:
    return logger.record_run_log(event)


def list_run_logs(connector_id: str | None = None, run_id: str | None = None) -> list[ConnectorRunLog]:
    return logger.list_run_logs(connector_id=connector_id, run_id=run_id)
