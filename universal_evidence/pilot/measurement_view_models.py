"""Bounded ACT-005 readiness contracts without ungoverned numerical values."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeasurementReadinessViewModel:
    visible: bool
    normalization_ready: bool
    measure_concepts: tuple[str, ...]
    dimension_concepts: tuple[str, ...]
    currency_ready: bool
    available_operations: tuple[str, ...]
    authorization_ids: tuple[str, ...]
    state: str
    reasons: tuple[str, ...]
    assessment_id: str | None
    fingerprint: str
