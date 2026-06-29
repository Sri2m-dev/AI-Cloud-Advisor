from __future__ import annotations

from typing import Any

from observability.base.telemetry_record import TelemetryRecord


class TelemetryLog:
    @staticmethod
    def create(source: str, name: str, message: str, entity: str, severity: str = "Info", **attributes: Any) -> dict[str, Any]:
        service = attributes.pop("service", None)
        business_service = attributes.pop("business_service", None)
        return TelemetryRecord(
            source=source,
            signal_type="log",
            name=name,
            value=message,
            entity=entity,
            severity=severity,
            service=service,
            business_service=business_service,
            attributes=attributes,
        ).as_dict()
