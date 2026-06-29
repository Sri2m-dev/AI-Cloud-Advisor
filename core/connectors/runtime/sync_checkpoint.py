from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


@dataclass(slots=True)
class ConnectorSyncCheckpoint:
    connector_id: UUID
    operation: str
    cursor: str = ""
    id: UUID = field(default_factory=uuid4)
    high_watermark: str = ""
    records_processed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["connector_id"] = str(self.connector_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorSyncCheckpoint":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["connector_id"] = UUID(str(data["connector_id"]))
        return cls(**data)
