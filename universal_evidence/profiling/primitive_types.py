"""Business-neutral primitive observation helpers."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from universal_evidence.profiling.models import PrimitiveType

_INTEGER = re.compile(r"^[+-]?\d+$")
_DECIMAL = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")


def observe_primitive(value: Any, *, formula: bool = False) -> PrimitiveType:
    if formula:
        return PrimitiveType.FORMULA
    if value is None or (isinstance(value, str) and not value.strip()):
        return PrimitiveType.NULL
    if isinstance(value, bool):
        return PrimitiveType.BOOLEAN
    if isinstance(value, datetime):
        return PrimitiveType.DATETIME
    if isinstance(value, date):
        return PrimitiveType.DATE
    if isinstance(value, time):
        return PrimitiveType.TIME
    if isinstance(value, int):
        return PrimitiveType.INTEGER
    if isinstance(value, (float, Decimal)):
        return PrimitiveType.DECIMAL
    if not isinstance(value, str):
        return PrimitiveType.UNKNOWN

    text = value.strip()
    if text.casefold() in {"true", "false"}:
        return PrimitiveType.BOOLEAN
    if _INTEGER.fullmatch(text):
        return PrimitiveType.INTEGER
    if _DECIMAL.fullmatch(text):
        try:
            Decimal(text)
            return PrimitiveType.DECIMAL
        except InvalidOperation:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if "T" in text or " " in text:
            return PrimitiveType.DATETIME
        if parsed.time() == time.min:
            return PrimitiveType.DATE
    except ValueError:
        pass
    try:
        date.fromisoformat(text)
        return PrimitiveType.DATE
    except ValueError:
        pass
    try:
        time.fromisoformat(text)
        return PrimitiveType.TIME
    except ValueError:
        return PrimitiveType.STRING


def stable_value(value: Any) -> tuple[str, str]:
    """Hashable deterministic representation used for structural distinctness."""
    primitive = observe_primitive(value)
    if isinstance(value, (datetime, date, time)):
        rendered = value.isoformat()
    else:
        rendered = str(value).strip()
    return primitive.value, rendered
