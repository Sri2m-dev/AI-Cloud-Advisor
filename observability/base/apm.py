from __future__ import annotations

from typing import Any

from observability.base.telemetry_record import TelemetryRecord


class TelemetryApmService:
    @staticmethod
    def create(source: str, service: str, health: float, entity: str, **attributes: Any) -> dict[str, Any]:
        business_service = attributes.pop("business_service", None)
        return TelemetryRecord(
            source=source,
            signal_type="apm",
            name=service,
            value=health,
            unit="health_score",
            entity=entity,
            service=service,
            business_service=business_service,
            attributes=attributes,
        ).as_dict()
