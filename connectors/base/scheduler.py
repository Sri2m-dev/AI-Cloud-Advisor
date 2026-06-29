from __future__ import annotations

from datetime import datetime, timedelta, timezone


class ConnectorScheduler:
    INTERVALS = {
        "Manual": None,
        "Every 15 min": timedelta(minutes=15),
        "Hourly": timedelta(hours=1),
        "Daily": timedelta(days=1),
        "Weekly": timedelta(days=7),
        "Event driven": None,
    }

    @staticmethod
    def next_sync(schedule: str, from_time: datetime | None = None) -> str | None:
        interval = ConnectorScheduler.INTERVALS.get(schedule)
        if interval is None:
            return None
        base = from_time or datetime.now(timezone.utc)
        return (base + interval).isoformat()

    @staticmethod
    def describe(schedule: str) -> dict[str, str | None]:
        return {"schedule": schedule, "next_sync": ConnectorScheduler.next_sync(schedule)}
