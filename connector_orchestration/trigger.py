"""Connector trigger contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class ConnectorTriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    API = "api"
    DEPENDENCY_COMPLETE = "dependency_complete"
    STARTUP = "startup"
    EVENT = "event"
    ON_DEMAND = "on_demand"


@dataclass(frozen=True)
class ConnectorTrigger:
    """Describes why a connector run was requested."""

    trigger_id: str = field(default_factory=lambda: str(uuid4()))
    trigger_type: ConnectorTriggerType = ConnectorTriggerType.MANUAL
    requested_by: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
