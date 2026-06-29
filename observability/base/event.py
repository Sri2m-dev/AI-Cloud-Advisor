from __future__ import annotations

from typing import Any

from observability.base.telemetry_record import TelemetryRecord


class TelemetryEvent:
    @staticmethod
    def create(source: str, name: str, entity: str, event_type: str, **attributes: Any) -> dict[str, Any]:
        service = attributes.pop("service", None)
        business_service = attributes.pop("business_service", None)
        return TelemetryRecord(
            source=source,
            signal_type="event",
            name=name,
            value=event_type,
            entity=entity,
            service=service,
            business_service=business_service,
            attributes=attributes,
        ).as_dict()
