"""Connector scheduling contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class ConnectorSchedule:
    """Schedule configuration for connector sync execution."""

    connector_id: str
    cadence: str
    enabled: bool = True
    sync_mode: str = "incremental"
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    metadata: Mapping[str, Any] | None = None


class ConnectorScheduler:
    """Minimal scheduler contract for future full and incremental sync jobs."""

    def due(self, schedules: list[ConnectorSchedule]) -> list[ConnectorSchedule]:
        now = datetime.now(timezone.utc)
        return [
            schedule
            for schedule in schedules
            if schedule.enabled and (schedule.next_run_at is None or schedule.next_run_at <= now)
        ]

    def enable(self, schedule: ConnectorSchedule) -> ConnectorSchedule:
        return ConnectorSchedule(**{**schedule.__dict__, "enabled": True})

    def disable(self, schedule: ConnectorSchedule) -> ConnectorSchedule:
        return ConnectorSchedule(**{**schedule.__dict__, "enabled": False})
