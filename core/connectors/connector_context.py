from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from core.connectors.connector_config import ConnectorConfig


@dataclass(slots=True)
class ConnectorContext:
    config: ConnectorConfig
    actor_id: UUID | None = None
    trace_id: str = ""
    dry_run: bool = False
    services: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def organization_id(self) -> UUID:
        return self.config.organization_id

    @property
    def connector_name(self) -> str:
        return self.config.name

    def service(self, name: str) -> Any:
        return self.services.get(name)
