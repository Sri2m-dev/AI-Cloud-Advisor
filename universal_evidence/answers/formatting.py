"""Faithful PUE-009 formatting without numeric derivation."""

from decimal import Decimal

from shared.currency import normalize_currency

CURRENCY_SYMBOLS = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}


def format_number(value: Decimal | int) -> str:
    if isinstance(value, Decimal):
        rendered = format(value, "f")
        integer, separator, fraction = rendered.partition(".")
        integer = f"{int(integer):,}"
        fraction = fraction.rstrip("0")
        return f"{integer}.{fraction}" if separator and fraction else integer
    return f"{value:,}"


def format_governed_value(value: Decimal | int, unit: str | None) -> str:
    rendered = format_number(value)
    if unit is None:
        return rendered
    code = normalize_currency(unit) or str(unit).strip().upper()
    symbol = CURRENCY_SYMBOLS.get(code)
    if symbol is not None:
        return f"{symbol}{rendered}"
    return f"{code} {rendered}"
