"""Validation helpers for canonical enterprise model contracts."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

EnumT = TypeVar("EnumT", bound=Enum)


def normalize_enum(enum_cls: type[EnumT], value: EnumT | str, field_name: str) -> EnumT:
    """Normalize strings into enum values while preserving enum inputs."""

    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_cls)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


def validate_score(value: float, field_name: str) -> float:
    """Validate a confidence or quality score as a 0.0 to 1.0 float."""

    numeric = float(value)
    if numeric < 0.0 or numeric > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")
    return numeric
