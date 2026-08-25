"""Bounded explainable signals derived only from PUE-001 profiles."""

from __future__ import annotations

import re

from universal_evidence.profiling import ColumnProfile, PrimitiveType

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def normalize_text(value: str) -> str:
    expanded = _CAMEL.sub(" ", str(value or "").strip())
    return " ".join(_SEPARATORS.sub(" ", expanded.casefold()).split())


def tokens(value: str) -> frozenset[str]:
    return frozenset(normalize_text(value).split())


def alias_strength(header: str, aliases: tuple[str, ...]) -> tuple[float, str | None]:
    normalized = normalize_text(header)
    header_tokens = tokens(header)
    best = 0.0
    matched: str | None = None
    for alias in aliases:
        normalized_alias = normalize_text(alias)
        alias_tokens = tokens(alias)
        if not normalized_alias:
            continue
        if normalized == normalized_alias:
            strength = 1.0
        elif alias_tokens and alias_tokens.issubset(header_tokens):
            strength = 0.90
        elif header_tokens and header_tokens.issubset(alias_tokens):
            strength = 0.20
        else:
            union = header_tokens | alias_tokens
            strength = len(header_tokens & alias_tokens) / len(union) if union else 0.0
        if strength > best:
            best, matched = strength, alias
    return best, matched


def primitive_compatibility(
    column: ColumnProfile, expected: tuple[str, ...]
) -> tuple[bool, bool]:
    dominant = column.dominant_primitive_type.value
    if dominant in {PrimitiveType.NULL.value, PrimitiveType.FORMULA.value}:
        return False, False
    return dominant in expected, dominant not in expected


def sample_shape_support(column: ColumnProfile, shape: str | None) -> bool:
    if not shape or not column.samples:
        return False
    values = [sample.display_value.strip() for sample in column.samples]
    if shape == "currency_code":
        return all(
            len(value) == 3 and value.isalpha() and value.upper() == value
            for value in values
        )
    if shape == "provider_code":
        allowed = {"aws", "azure", "gcp", "google cloud"}
        return all(value.casefold() in allowed for value in values)
    if shape == "environment_label":
        allowed = {"prod", "production", "uat", "test", "dev", "development", "staging"}
        return all(value.casefold() in allowed for value in values)
    return False
