from __future__ import annotations

from typing import Any

from observability.base.telemetry_record import TelemetryRecord


class TelemetrySlo:
    @staticmethod
    def create(source: str, name: str, score: float, entity: str, **attributes: Any) -> dict[str, Any]:
        service = attributes.pop("service", None)
        business_service = attributes.pop("business_service", None)
        return TelemetryRecord(
            source=source,
            signal_type="slo",
            name=name,
            value=score,
            entity=entity,
            unit="%",
            service=service,
            business_service=business_service,
            attributes=attributes,
        ).as_dict()
