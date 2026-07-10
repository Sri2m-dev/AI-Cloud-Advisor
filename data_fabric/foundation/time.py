"""Timezone validation helpers for Data Fabric boundaries."""

from __future__ import annotations

from datetime import datetime, timezone

from data_fabric.foundation.exceptions import DataFabricValidationError


def require_timezone_aware(value: datetime, field_name: str = "datetime") -> datetime:
    """Return a datetime only if it carries timezone information."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise DataFabricValidationError(f"{field_name} must be timezone-aware")
    return value


def normalize_to_utc(value: datetime, field_name: str = "datetime") -> datetime:
    """Normalize a timezone-aware datetime to UTC without guessing naive values."""

    return require_timezone_aware(value, field_name).astimezone(timezone.utc)


def validate_created_updated_order(created_at: datetime, updated_at: datetime) -> None:
    """Validate canonical created/updated timestamp ordering."""

    created = normalize_to_utc(created_at, "created_at")
    updated = normalize_to_utc(updated_at, "updated_at")
    if created > updated:
        raise DataFabricValidationError("created_at cannot be after updated_at")


def validate_effective_period(
    effective_from: datetime,
    effective_to: datetime | None,
) -> None:
    """Validate an effective-time interval using closed-open semantics."""

    start = normalize_to_utc(effective_from, "effective_from")
    if effective_to is None:
        return
    end = normalize_to_utc(effective_to, "effective_to")
    if end <= start:
        raise DataFabricValidationError("effective_to must be after effective_from")
