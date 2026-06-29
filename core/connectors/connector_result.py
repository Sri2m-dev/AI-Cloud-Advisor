from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class ConnectorRunStatus(str, Enum):
    SUCCESS = "Success"
    PARTIAL = "Partial"
    FAILED = "Failed"
    SKIPPED = "Skipped"


@dataclass(slots=True)
class ConnectorResult:
    connector_id: UUID
    operation: str
    status: str = ConnectorRunStatus.SUCCESS.value
    id: UUID = field(default_factory=uuid4)
    message: str = ""
    entities_synced: int = 0
    relationships_synced: int = 0
    metadata_records: int = 0
    events_published: int = 0
    errors: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str = field(default_factory=utc_now_iso)

    @property
    def ok(self) -> bool:
        return self.status in {ConnectorRunStatus.SUCCESS.value, ConnectorRunStatus.PARTIAL.value}

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["connector_id"] = str(self.connector_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorResult":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["connector_id"] = UUID(str(data["connector_id"]))
        return cls(**data)
