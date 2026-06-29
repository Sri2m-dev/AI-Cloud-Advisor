from __future__ import annotations

from typing import Any

from observability.base.telemetry_record import TelemetryRecord


class TelemetryTrace:
    @staticmethod
    def create(source: str, service: str, latency_ms: float, entity: str, **attributes: Any) -> dict[str, Any]:
        business_service = attributes.pop("business_service", None)
        return TelemetryRecord(
            source=source,
            signal_type="trace",
            name=f"{service} latency",
            value=latency_ms,
            unit="ms",
            entity=entity,
            service=service,
            business_service=business_service,
            attributes=attributes,
        ).as_dict()
