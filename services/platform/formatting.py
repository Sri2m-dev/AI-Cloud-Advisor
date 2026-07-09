from __future__ import annotations

from typing import Any


def safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value if value is not None else fallback)
    except (TypeError, ValueError):
        return fallback


def safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value if value is not None else fallback))
    except (TypeError, ValueError):
        return fallback


def format_currency(value: Any) -> str:
    amount = safe_float(value)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 1_000_000_000:
        return f"{sign}${amount / 1_000_000_000:.1f}B".replace(".0B", "B")
    if amount >= 1_000_000:
        return f"{sign}${amount / 1_000_000:.1f}M".replace(".0M", "M")
    if amount >= 1_000:
        value_in_k = amount / 1_000
        formatted = f"{value_in_k:,.0f}K" if value_in_k.is_integer() else f"{value_in_k:,.1f}K"
        return f"{sign}${formatted}"
    return f"{sign}${amount:,.0f}"


def format_number(value: Any) -> str:
    number = safe_float(value)
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}M".replace(".0M", "M")
    if abs(number) >= 1_000:
        return f"{number / 1_000:.1f}K".replace(".0K", "K")
    return f"{number:,.0f}"


def format_percent(value: Any, digits: int = 1) -> str:
    return f"{safe_float(value):.{digits}f}%"


def escape_markdown_currency(text: str) -> str:
    return str(text or "").replace("$", r"\$")
