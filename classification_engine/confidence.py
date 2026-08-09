"""Deterministic, explainable confidence scoring."""

from __future__ import annotations

from dataclasses import dataclass

ENGINE_VERSION = "p4.2-rules-v1"


@dataclass(frozen=True, slots=True)
class ConfidenceDimensions:
    source_reliability: float
    consistency: float
    freshness: float
    coverage: float
    corroboration: float
    contradiction_penalty: float = 0
    tenant_policy_modifier: float = 0


@dataclass(frozen=True, slots=True)
class ConfidenceExplanation:
    score: float
    dimensions: ConfidenceDimensions
    formula: str


def calculate_confidence(dimensions: ConfidenceDimensions) -> ConfidenceExplanation:
    """Return a reproducible 0..1 score using a documented weighted model."""
    values = (
        dimensions.source_reliability,
        dimensions.consistency,
        dimensions.freshness,
        dimensions.coverage,
        dimensions.corroboration,
        dimensions.contradiction_penalty,
    )
    if any(not 0 <= value <= 1 for value in values):
        raise ValueError("confidence dimensions must be between 0 and 1")
    base = (
        0.30 * dimensions.source_reliability
        + 0.20 * dimensions.consistency
        + 0.15 * dimensions.freshness
        + 0.15 * dimensions.coverage
        + 0.20 * dimensions.corroboration
    )
    score = max(
        0.0,
        min(
            1.0, base - 0.35 * dimensions.contradiction_penalty + dimensions.tenant_policy_modifier
        ),
    )
    return ConfidenceExplanation(
        score=round(score, 6),
        dimensions=dimensions,
        formula=(
            ".30 reliability + .20 consistency + .15 freshness + .15 coverage "
            "+ .20 corroboration - .35 contradiction + policy modifier"
        ),
    )
