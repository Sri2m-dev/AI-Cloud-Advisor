"""Shared single-pass structural profiling helpers."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from universal_evidence.contracts import (
    EvidenceAnalysisContext,
    EvidenceColumn,
    PrimitiveProfile,
)
from universal_evidence.profiling.models import (
    ColumnProfile,
    PrimitiveType,
    ProfilerConfig,
    StructuralWarning,
    WarningCode,
)
from universal_evidence.profiling.primitive_types import observe_primitive, stable_value
from universal_evidence.profiling.sampling import select_samples
from universal_evidence.profiling.structural_flags import structural_roles


def nonempty(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def detect_header(
    rows: list[list[Any]], config: ProfilerConfig
) -> tuple[int | None, float, str]:
    """Choose a structural header candidate using density and type contrast only."""
    if not rows:
        return None, 0.0, "NO_NONEMPTY_ROWS"
    width = max((len(row) for row in rows), default=0)
    if not width:
        return None, 0.0, "NO_NONEMPTY_ROWS"
    candidates: list[tuple[float, int]] = []
    for index, row in enumerate(rows[: config.header_scan_rows]):
        padded = row + [None] * (width - len(row))
        present = [value for value in padded if nonempty(value)]
        if not present:
            continue
        density = len(present) / width
        unique_ratio = len({str(value).strip() for value in present}) / len(present)
        string_ratio = sum(
            observe_primitive(value) is PrimitiveType.STRING for value in present
        ) / len(present)
        following = [
            candidate
            for candidate in rows[index + 1 : index + 6]
            if any(nonempty(value) for value in candidate)
        ]
        following_density = 0.0
        type_contrast = 0.0
        if following:
            following_density = sum(
                sum(nonempty(value) for value in candidate) / width
                for candidate in following
            ) / len(following)
            contrasts: list[float] = []
            for ordinal, value in enumerate(padded):
                if not nonempty(value):
                    continue
                below = [
                    candidate[ordinal]
                    for candidate in following
                    if ordinal < len(candidate) and nonempty(candidate[ordinal])
                ]
                if below:
                    header_type = observe_primitive(value)
                    contrasts.append(
                        sum(observe_primitive(item) != header_type for item in below)
                        / len(below)
                    )
            type_contrast = sum(contrasts) / len(contrasts) if contrasts else 0.0
        following_support = min(len(following) / 3, 1.0)
        score = (
            density * 0.35
            + unique_ratio * 0.20
            + string_ratio * 0.15
            + min(following_density, density) * 0.15 * following_support
            + type_contrast * 0.15 * following_support
        )
        score -= index * 0.005
        if len(present) == 1 and width > 1:
            score *= 0.5
        candidates.append((score, index))
    if not candidates:
        return None, 0.0, "NO_HEADER_CANDIDATE"
    score, index = max(candidates, key=lambda item: (item[0], -item[1]))
    if score < 0.45:
        return index + 1, round(score, 4), "DENSITY_TYPE_CONTRAST_LOW_CONFIDENCE"
    return index + 1, round(score, 4), "DENSITY_TYPE_CONTRAST_V1"


def row_regions(rows: list[list[Any]]) -> tuple[tuple[int, int], ...]:
    regions: list[tuple[int, int]] = []
    start: int | None = None
    for index, row in enumerate(rows, start=1):
        populated = any(nonempty(value) for value in row)
        if populated and start is None:
            start = index
        elif not populated and start is not None:
            regions.append((start, index - 1))
            start = None
    if start is not None:
        regions.append((start, len(rows)))
    return tuple(regions)


def duplicate_header_ordinals(headers: list[Any]) -> tuple[int, ...]:
    normalized = [str(value).strip() if value is not None else "" for value in headers]
    counts = Counter(value for value in normalized if value)
    return tuple(
        index + 1
        for index, value in enumerate(normalized)
        if value and counts[value] > 1
    )


def exact_duplicate_count(rows: list[list[Any]]) -> int:
    normalized = [
        tuple(stable_value(value) for value in row)
        for row in rows
        if any(nonempty(v) for v in row)
    ]
    counts = Counter(normalized)
    return sum(count - 1 for count in counts.values() if count > 1)


def build_column_profile(
    *,
    context: EvidenceAnalysisContext,
    file_id: str,
    sheet_id: str,
    column_id: str,
    original_header: Any,
    ordinal: int,
    values: list[tuple[int, Any, bool]],
    config: ProfilerConfig,
) -> ColumnProfile:
    distribution: Counter[PrimitiveType] = Counter()
    non_null: list[Any] = []
    sample_values: list[tuple[int, Any]] = []
    unsupported = False
    formula_seen = False
    for row_number, value, formula in values:
        primitive = observe_primitive(value, formula=formula)
        distribution[primitive] += 1
        formula_seen = formula_seen or formula
        if primitive is PrimitiveType.UNKNOWN:
            unsupported = True
        if primitive not in {PrimitiveType.NULL, PrimitiveType.FORMULA}:
            non_null.append(value)
            sample_values.append((row_number, value))

    observed = len(values)
    null_count = distribution[PrimitiveType.NULL]
    non_null_count = observed - null_count
    distinct = {stable_value(value) for value in non_null}
    distinct_count = len(distinct)
    coverage = non_null_count / observed if observed else 0.0
    uniqueness = distinct_count / len(non_null) if non_null else 0.0
    non_formula_distribution = Counter(
        {
            key: value
            for key, value in distribution.items()
            if key not in {PrimitiveType.NULL, PrimitiveType.FORMULA}
        }
    )
    dominant = (
        non_formula_distribution.most_common(1)[0][0]
        if non_formula_distribution
        else (PrimitiveType.FORMULA if formula_seen else PrimitiveType.NULL)
    )
    observed_types = tuple(sorted((item.value for item in non_formula_distribution)))
    mixed = len(observed_types) > 1
    safe_min: Any | None = None
    safe_max: Any | None = None
    comparable_types = (int, float, Decimal, date, datetime, time)
    if non_null and all(isinstance(value, type(non_null[0])) for value in non_null):
        if isinstance(non_null[0], comparable_types):
            try:
                safe_min, safe_max = min(non_null), max(non_null)
            except (TypeError, ValueError):
                pass
    string_lengths = [len(value) for value in non_null if isinstance(value, str)]
    samples, suppressed = select_samples(
        sample_values,
        context=context,
        file_id=file_id,
        sheet_id=sheet_id,
        config=config,
    )
    roles = structural_roles(
        non_null_values=non_null,
        distribution=non_formula_distribution,
        distinct_count=distinct_count,
        coverage=coverage,
        uniqueness=uniqueness,
        config=config,
    )
    warnings: list[StructuralWarning] = []
    if mixed:
        warnings.append(
            StructuralWarning(
                WarningCode.MIXED_PRIMITIVE_TYPES,
                column_id,
                "multiple primitive types observed",
            )
        )
    if suppressed:
        warnings.append(
            StructuralWarning(
                WarningCode.SAMPLE_SUPPRESSED,
                column_id,
                "one or more samples suppressed by policy",
            )
        )
    if unsupported:
        warnings.append(
            StructuralWarning(
                WarningCode.UNSUPPORTED_CELL_TYPE,
                column_id,
                "unsupported primitive value observed",
            )
        )
    primitive_profile = PrimitiveProfile(
        column_id=column_id,
        primitive_type_candidates=observed_types,
        null_count=null_count,
        non_null_count=non_null_count,
        distinct_count=distinct_count,
        coverage=coverage,
        uniqueness=uniqueness,
        min_value=safe_min,
        max_value=safe_max,
        min_string_length=min(string_lengths) if string_lengths else None,
        max_string_length=max(string_lengths) if string_lengths else None,
        candidate_categorical=any(role.value == "CATEGORICAL_LIKE" for role in roles),
        candidate_identifier=any(role.value == "IDENTIFIER_LIKE" for role in roles),
        candidate_numeric_measure=any(role.value == "MEASURE_LIKE" for role in roles),
        candidate_date_field=any(role.value == "DATE_LIKE" for role in roles),
        mixed_type=mixed,
        safe_representative_samples=tuple(sample.display_value for sample in samples),
        sensitive_looking=suppressed,
        warnings=tuple(warning.code.value for warning in warnings),
    )
    return ColumnProfile(
        EvidenceColumn(
            context,
            file_id,
            sheet_id,
            column_id,
            "" if original_header is None else str(original_header),
            ordinal,
        ),
        observed,
        primitive_profile,
        tuple(sorted(distribution.items(), key=lambda item: item[0].value)),
        dominant,
        roles,
        samples,
        tuple(warnings),
    )
