from __future__ import annotations

from typing import Any


SUPPORTED_CURRENCIES = ("USD", "INR", "EUR", "GBP", "AUD", "CAD", "JPY", "SGD", "AED")

_CURRENCY_SYMBOLS = {
    "USD": "$",
    "INR": "₹",
    "EUR": "€",
    "GBP": "£",
}


def normalize_currency(value: Any) -> str | None:
    currency = str(value or "").strip().upper()
    return currency if currency in SUPPORTED_CURRENCIES else None


def format_currency_amount(value: Any, currency: str | None) -> str:
    """Format an amount only when a governed ISO currency is available."""
    normalized = normalize_currency(currency)
    if normalized is None:
        return "Currency resolution required"
    amount = float(value or 0)
    symbol = _CURRENCY_SYMBOLS.get(normalized)
    formatted = f"{amount:,.0f}"
    return f"{symbol}{formatted}" if symbol else f"{normalized} {formatted}"
