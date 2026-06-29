from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class ConnectorExecutionStatus(str, Enum):
    QUEUED = "Queued"
    RUNNING = "Running"
    SUCCESS = "Success"
    PARTIAL = "Partial"
    FAILED = "Failed"
    RETRYING = "Retrying"
    CANCELLED = "Cancelled"


class ConnectorTriggerType(str, Enum):
    MANUAL = "Manual"
    SCHEDULED = "Scheduled"
    SYSTEM = "System"


@dataclass(slots=True)
class ConnectorExecutionRun:
    connector_id: UUID
    operation: str
    trigger_type: str = ConnectorTriggerType.MANUAL.value
    id: UUID = field(default_factory=uuid4)
    status: str = ConnectorExecutionStatus.QUEUED.value
    attempt: int = 1
    max_attempts: int = 1
    checkpoint_id: UUID | None = None
    result_id: UUID | None = None
    health_id: UUID | None = None
    started_at: str | None = None
    completed_at: str | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "connector_id", "checkpoint_id", "result_id", "health_id"):
            payload[key] = str(payload[key]) if payload.get(key) else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorExecutionRun":
        data = dict(payload)
        for key in ("id", "connector_id", "checkpoint_id", "result_id", "health_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        return cls(**data)
