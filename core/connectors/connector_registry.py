from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

from core.connectors.connector_config import ConnectorConfig
from core.entities.entity import utc_now_iso


class ConnectorRegistryStatus(str, Enum):
    REGISTERED = "Registered"
    ACTIVE = "Active"
    DISABLED = "Disabled"
    ERROR = "Error"


@dataclass(slots=True)
class ConnectorRegistryEntry:
    config: ConnectorConfig
    status: str = ConnectorRegistryStatus.REGISTERED.value
    capabilities: list[str] = field(default_factory=list)
    last_discovered_at: str | None = None
    last_synced_at: str | None = None
    last_health_status: str = "Unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @property
    def connector_id(self) -> UUID:
        return self.config.id

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["config"] = self.config.to_dict()
        payload["connector_id"] = str(self.connector_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorRegistryEntry":
        data = dict(payload)
        data.pop("connector_id", None)
        data["config"] = ConnectorConfig.from_dict(data["config"])
        return cls(**data)
