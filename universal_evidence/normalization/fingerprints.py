"""Deterministic fingerprints without floating-point coercion."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Any


def canonical_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, datetime):
        return {"datetime": value.isoformat()}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return canonical_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return {"type": type(value).__name__, "repr": repr(value)}


def fingerprint(*values: Any) -> str:
    payload = json.dumps(
        canonical_value(values), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256(payload.encode("utf-8")).hexdigest()
