"""Deterministic, type-aware natural-language literal parsing."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from universal_evidence.capability import DimensionValueType
from universal_evidence.interpretation.aliases import BOOLEAN_LITERALS

DATE_FORMATS = (
    "%B %d, %Y",
    "%B %d %Y",
    "%Y-%m-%d",
)


def parse_literal(text: str, value_type: DimensionValueType):
    value = text.strip().strip("\"'")
    if value_type is DimensionValueType.STRING:
        return value if value else None
    if value_type is DimensionValueType.BOOLEAN:
        return BOOLEAN_LITERALS.get(value.lower())
    if value_type is DimensionValueType.INTEGER:
        try:
            return int(value)
        except ValueError:
            return None
    if value_type is DimensionValueType.DECIMAL:
        try:
            parsed = Decimal(value)
            return parsed if parsed.is_finite() else None
        except InvalidOperation:
            return None
    if value_type in {DimensionValueType.DATE, DimensionValueType.DATETIME}:
        for date_format in DATE_FORMATS:
            try:
                parsed = datetime.strptime(value, date_format)
                return parsed if value_type is DimensionValueType.DATETIME else parsed.date()
            except ValueError:
                continue
    return None


def parse_date_phrase(text: str, value_type: DimensionValueType):
    if value_type not in {DimensionValueType.DATE, DimensionValueType.DATETIME}:
        return None
    return parse_literal(text, value_type)


def literal_type_matches(value, value_type):
    if value_type is DimensionValueType.STRING:
        return type(value) is str
    if value_type is DimensionValueType.INTEGER:
        return type(value) is int
    if value_type is DimensionValueType.DECIMAL:
        return type(value) is Decimal
    if value_type is DimensionValueType.BOOLEAN:
        return type(value) is bool
    if value_type is DimensionValueType.DATE:
        return type(value) is date
    if value_type is DimensionValueType.DATETIME:
        return type(value) is datetime
    return False
