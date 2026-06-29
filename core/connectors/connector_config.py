from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class ConnectorType(str, Enum):
    CLOUD = "Cloud"
    SAAS = "SaaS"
    ITSM = "ITSM"
    OBSERVABILITY = "Observability"
    SECURITY = "Security"
    FINANCE = "Finance"
    DEVOPS = "DevOps"
    CUSTOM = "Custom"


@dataclass(slots=True)
class ConnectorConfig:
    name: str
    provider: str
    connector_type: str
    organization_id: UUID
    id: UUID = field(default_factory=uuid4)
    enabled: bool = True
    auth_type: str = "api_key"
    settings: dict[str, Any] = field(default_factory=dict)
    sync_interval_minutes: int = 60
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["organization_id"] = str(self.organization_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorConfig":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["organization_id"] = UUID(str(data["organization_id"]))
        return cls(**data)
