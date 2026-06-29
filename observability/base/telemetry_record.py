from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TelemetryRecord:
    source: str
    signal_type: str
    name: str
    value: Any
    entity: str
    severity: str = "Info"
    unit: str | None = None
    service: str | None = None
    business_service: str | None = None
    timestamp: str = field(default_factory=utc_now_iso)
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "signal_type": self.signal_type,
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "entity": self.entity,
            "service": self.service,
            "business_service": self.business_service,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "attributes": self.attributes,
        }
