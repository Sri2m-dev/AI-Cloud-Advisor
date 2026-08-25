"""Configurable, business-neutral structural role observations."""

from __future__ import annotations

from collections import Counter
from typing import Any

from universal_evidence.profiling.models import (
    PrimitiveType,
    ProfilerConfig,
    StructuralRole,
)


def structural_roles(
    *,
    non_null_values: list[Any],
    distribution: Counter[PrimitiveType],
    distinct_count: int,
    coverage: float,
    uniqueness: float,
    config: ProfilerConfig,
) -> tuple[StructuralRole, ...]:
    roles: set[StructuralRole] = set()
    count = len(non_null_values)
    if not count:
        return ()
    dominant, dominant_count = distribution.most_common(1)[0]
    dominance = dominant_count / count
    if coverage < config.mostly_null_coverage:
        roles.add(StructuralRole.MOSTLY_NULL)
    if distinct_count == 1:
        roles.add(StructuralRole.CONSTANT_VALUE)
    if uniqueness >= config.high_cardinality_ratio:
        roles.add(StructuralRole.HIGH_CARDINALITY)
    if uniqueness <= config.low_cardinality_ratio:
        roles.add(StructuralRole.LOW_CARDINALITY)
    if count >= 3 and uniqueness >= config.high_cardinality_ratio and dominance >= 0.8:
        if dominant in {PrimitiveType.STRING, PrimitiveType.INTEGER}:
            roles.add(StructuralRole.IDENTIFIER_LIKE)
    if dominance >= 0.8 and dominant in {PrimitiveType.INTEGER, PrimitiveType.DECIMAL}:
        if distinct_count > 1:
            roles.add(StructuralRole.MEASURE_LIKE)
    if dominance >= 0.8 and dominant in {
        PrimitiveType.DATE,
        PrimitiveType.DATETIME,
        PrimitiveType.TIME,
    }:
        roles.add(StructuralRole.DATE_LIKE)
    if dominance >= 0.8 and dominant is PrimitiveType.BOOLEAN:
        roles.add(StructuralRole.BOOLEAN_LIKE)
    if 1 < distinct_count <= 20 and uniqueness <= 0.5 and dominance >= 0.8:
        roles.add(StructuralRole.CATEGORICAL_LIKE)
    string_lengths = [
        len(str(value)) for value in non_null_values if isinstance(value, str)
    ]
    if string_lengths and sum(string_lengths) / len(string_lengths) > 50:
        roles.add(StructuralRole.FREE_TEXT_LIKE)
    return tuple(sorted(roles, key=lambda item: item.value))
