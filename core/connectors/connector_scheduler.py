from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class ConnectorScheduleStatus(str, Enum):
    ENABLED = "Enabled"
    PAUSED = "Paused"
    DISABLED = "Disabled"


@dataclass(slots=True)
class ConnectorSchedule:
    connector_id: UUID
    operation: str
    interval_minutes: int
    id: UUID = field(default_factory=uuid4)
    status: str = ConnectorScheduleStatus.ENABLED.value
    next_run_at: str | None = None
    last_run_at: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["connector_id"] = str(self.connector_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "ConnectorSchedule":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["connector_id"] = UUID(str(data["connector_id"]))
        return cls(**data)
