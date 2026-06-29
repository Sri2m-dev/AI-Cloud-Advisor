from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class ConnectorLogLevel(str, Enum):
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"
    DEBUG = "Debug"


@dataclass(slots=True)
class ConnectorRunLog:
    run_id: UUID
    connector_id: UUID
    message: str
    level: str = ConnectorLogLevel.INFO.value
    id: UUID = field(default_factory=uuid4)
    operation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "run_id", "connector_id"):
            payload[key] = str(payload[key])
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorRunLog":
        data = dict(payload)
        for key in ("id", "run_id", "connector_id"):
            data[key] = UUID(str(data[key]))
        return cls(**data)
