from __future__ import annotations

from typing import Any

from observability.base.telemetry_record import TelemetryRecord


class TelemetryMetric:
    @staticmethod
    def create(source: str, name: str, value: float, entity: str, unit: str, **attributes: Any) -> dict[str, Any]:
        service = attributes.pop("service", None)
        business_service = attributes.pop("business_service", None)
        return TelemetryRecord(
            source=source,
            signal_type="metric",
            name=name,
            value=value,
            entity=entity,
            unit=unit,
            service=service,
            business_service=business_service,
            attributes=attributes,
        ).as_dict()
