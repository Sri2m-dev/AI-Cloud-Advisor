from __future__ import annotations

from typing import Any

from observability.base.telemetry_record import TelemetryRecord


class TelemetryAlert:
    @staticmethod
    def create(source: str, name: str, entity: str, severity: str, **attributes: Any) -> dict[str, Any]:
        service = attributes.pop("service", None)
        business_service = attributes.pop("business_service", None)
        return TelemetryRecord(
            source=source,
            signal_type="alert",
            name=name,
            value=severity,
            entity=entity,
            severity=severity,
            service=service,
            business_service=business_service,
            attributes=attributes,
        ).as_dict()
