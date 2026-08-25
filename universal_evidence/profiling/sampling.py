"""Bounded deterministic sampling with conservative disclosure controls."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from universal_evidence.contracts import EvidenceAnalysisContext, EvidenceRowReference
from universal_evidence.profiling.models import ProfilerConfig, StructuralSample


def _high_entropy_token(text: str) -> bool:
    compact = "".join(text.split())
    if len(compact) < 24:
        return False
    counts = Counter(compact)
    entropy = -sum(
        (count / len(compact)) * math.log2(count / len(compact))
        for count in counts.values()
    )
    return entropy >= 4.0 and not any(character.isspace() for character in text)


def safe_display(value: Any, config: ProfilerConfig) -> tuple[str | None, bool]:
    if value is None or isinstance(value, (bytes, bytearray, memoryview)):
        return None, False
    text = str(value)
    if any(ord(character) < 32 and character not in "\t\r\n" for character in text):
        return None, False
    if len(text) > config.max_string_sample_length * 4 or _high_entropy_token(text):
        return None, False
    if len(text) > config.max_string_sample_length:
        return text[: config.max_string_sample_length] + "…", True
    return text, False


def select_samples(
    values: list[tuple[int, Any]],
    *,
    context: EvidenceAnalysisContext,
    file_id: str,
    sheet_id: str,
    config: ProfilerConfig,
) -> tuple[tuple[StructuralSample, ...], bool]:
    samples: list[StructuralSample] = []
    seen: set[str] = set()
    suppressed = False
    for row_number, value in values:
        display, truncated = safe_display(value, config)
        if display is None:
            if value not in (None, ""):
                suppressed = True
            continue
        if display in seen:
            continue
        seen.add(display)
        samples.append(
            StructuralSample(
                display,
                EvidenceRowReference(
                    context, file_id, sheet_id, row_numbers=(row_number,)
                ),
                truncated,
            )
        )
        if len(samples) >= config.max_sample_values:
            break
    return tuple(samples), suppressed
