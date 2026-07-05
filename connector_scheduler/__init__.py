"""Connector scheduling contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ConnectorSchedule:
    connector_id: str
    cadence: str
    enabled: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None


class ConnectorScheduler:
    """Minimal scheduler contract for future full and incremental sync jobs."""

    def due(self, schedules: list[ConnectorSchedule]) -> list[ConnectorSchedule]:
        now = datetime.now(timezone.utc)
        return [schedule for schedule in schedules if schedule.enabled and (schedule.next_run_at is None or schedule.next_run_at <= now)]
