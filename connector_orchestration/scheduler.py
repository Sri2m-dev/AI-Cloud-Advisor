"""Connector orchestration scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping

from connector_orchestration.trigger import ConnectorTrigger, ConnectorTriggerType


class ScheduleType(str, Enum):
    MANUAL = "manual"
    CRON = "cron"
    INTERVAL = "interval"
    WEBHOOK = "webhook"
    EVENT = "event"
    ON_DEMAND = "on_demand"


@dataclass(frozen=True)
class OrchestrationSchedule:
    connector_id: str
    schedule_type: ScheduleType = ScheduleType.MANUAL
    enabled: bool = True
    interval_seconds: int | None = None
    cron: str | None = None
    next_run_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class OrchestrationScheduler:
    """Creates triggers from schedules."""

    def due(self, schedules: list[OrchestrationSchedule]) -> list[OrchestrationSchedule]:
        now = datetime.now(timezone.utc)
        return [schedule for schedule in schedules if schedule.enabled and schedule.next_run_at is not None and schedule.next_run_at <= now]

    def trigger_for(self, schedule: OrchestrationSchedule) -> ConnectorTrigger:
        trigger_type = ConnectorTriggerType.SCHEDULED if schedule.schedule_type in {ScheduleType.CRON, ScheduleType.INTERVAL} else ConnectorTriggerType.ON_DEMAND
        return ConnectorTrigger(trigger_type=trigger_type, source="scheduler", payload={"schedule_type": schedule.schedule_type.value})

    def next_interval(self, schedule: OrchestrationSchedule) -> datetime | None:
        if schedule.interval_seconds is None:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=schedule.interval_seconds)
