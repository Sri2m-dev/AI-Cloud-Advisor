"""Quality scoring result models and deterministic score calculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from data_fabric.quality.exceptions import QualityValidationError

QUALITY_DIMENSIONS: tuple[str, ...] = (
    "completeness",
    "freshness",
    "validity",
    "consistency",
    "uniqueness",
    "accuracy",
    "lineage_confidence",
    "source_confidence",
    "ownership_completeness",
)

DEFAULT_DIMENSION_WEIGHTS: dict[str, float] = {
    "completeness": 0.18,
    "freshness": 0.10,
    "validity": 0.14,
    "consistency": 0.10,
    "uniqueness": 0.08,
    "accuracy": 0.12,
    "lineage_confidence": 0.10,
    "source_confidence": 0.10,
    "ownership_completeness": 0.08,
}


class QualityIssueSeverity(str, Enum):
    """Severity used to distinguish warnings from blocking failures."""

    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """One quality issue found by a quality rule."""

    rule_id: str
    dimension: str
    message: str
    severity: QualityIssueSeverity | str = QualityIssueSeverity.WARNING
    deduction: float = 0.0

    def __post_init__(self) -> None:
        severity = QualityIssueSeverity(self.severity)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "deduction", validate_score_100(self.deduction, "deduction"))

    @property
    def is_blocking(self) -> bool:
        return self.severity is QualityIssueSeverity.BLOCKING


@dataclass(frozen=True, slots=True)
class QualityDimensionScore:
    """Score and issues for one quality dimension on a 0-100 scale."""

    dimension: str
    score: float
    issues: tuple[QualityIssue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_dimension(self.dimension)
        object.__setattr__(self, "score", validate_score_100(self.score, "score"))


@dataclass(frozen=True, slots=True)
class QualityRuleResult:
    """Result produced by a single quality rule."""

    rule_id: str
    dimension: str
    score: float
    issues: tuple[QualityIssue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_dimension(self.dimension)
        object.__setattr__(self, "score", validate_score_100(self.score, "score"))

    @property
    def has_blocking_issue(self) -> bool:
        return any(issue.is_blocking for issue in self.issues)


@dataclass(frozen=True, slots=True)
class TrustScore:
    """Weighted trust score with explainability details."""

    final_score: float
    dimension_scores: Mapping[str, QualityDimensionScore]
    weights: Mapping[str, float]
    deductions: Mapping[str, float]
    explanation: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "final_score", validate_score_100(self.final_score, "final_score"))
        object.__setattr__(self, "dimension_scores", MappingProxyType(dict(self.dimension_scores)))
        object.__setattr__(self, "weights", MappingProxyType(dict(self.weights)))
        object.__setattr__(self, "deductions", MappingProxyType(dict(self.deductions)))


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    """Complete quality assessment for one canonical object."""

    subject_id: str
    subject_type: str
    organization_id: str
    tenant_id: str | None
    source_system: str | None
    source_identifier: str | None
    dimension_scores: Mapping[str, QualityDimensionScore]
    issues: tuple[QualityIssue, ...]
    trust_score: TrustScore

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension_scores", MappingProxyType(dict(self.dimension_scores)))


class WeightedTrustScoreCalculator:
    """Deterministic weighted trust score calculator for 0-100 dimensions."""

    def __init__(self, weights: Mapping[str, float] | None = None) -> None:
        self.weights = validate_weights(weights or DEFAULT_DIMENSION_WEIGHTS)

    def calculate(
        self,
        dimension_scores: Mapping[str, QualityDimensionScore],
        issues: tuple[QualityIssue, ...] = (),
    ) -> TrustScore:
        normalized_scores = dict(dimension_scores)
        normalized_issues = list(issues)
        for dimension in QUALITY_DIMENSIONS:
            if dimension not in normalized_scores:
                issue = QualityIssue(
                    rule_id="missing_dimension",
                    dimension=dimension,
                    message=f"Dimension {dimension} was not evaluated.",
                    severity=QualityIssueSeverity.WARNING,
                    deduction=100.0,
                )
                normalized_issues.append(issue)
                normalized_scores[dimension] = QualityDimensionScore(
                    dimension=dimension,
                    score=0.0,
                    issues=(issue,),
                )

        weighted_total = sum(
            normalized_scores[dimension].score * self.weights[dimension]
            for dimension in QUALITY_DIMENSIONS
        )
        final_score = round(weighted_total, 4)
        deductions = {
            dimension: round(100.0 - normalized_scores[dimension].score, 4)
            for dimension in QUALITY_DIMENSIONS
        }
        explanation = tuple(
            f"{dimension}: score={normalized_scores[dimension].score:.2f}, "
            f"weight={self.weights[dimension]:.4f}, "
            f"deduction={deductions[dimension]:.2f}"
            for dimension in QUALITY_DIMENSIONS
        ) + (f"final_score={final_score:.2f}",)
        return TrustScore(
            final_score=final_score,
            dimension_scores=normalized_scores,
            weights=self.weights,
            deductions=deductions,
            explanation=explanation,
        )


def validate_score_100(value: float, field_name: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise QualityValidationError(f"{field_name} must be numeric") from exc
    if score < 0.0 or score > 100.0:
        raise QualityValidationError(f"{field_name} must be between 0 and 100")
    return score


def validate_weights(weights: Mapping[str, float]) -> dict[str, float]:
    missing = set(QUALITY_DIMENSIONS) - set(weights)
    extra = set(weights) - set(QUALITY_DIMENSIONS)
    if missing:
        raise QualityValidationError(f"Missing weight(s): {', '.join(sorted(missing))}")
    if extra:
        raise QualityValidationError(f"Unknown weight(s): {', '.join(sorted(extra))}")
    normalized = {dimension: float(weights[dimension]) for dimension in QUALITY_DIMENSIONS}
    if any(weight < 0.0 for weight in normalized.values()):
        raise QualityValidationError("Weights cannot be negative")
    if round(sum(normalized.values()), 8) != 1.0:
        raise QualityValidationError("Weights must total 1.0")
    return normalized


def _validate_dimension(dimension: str) -> None:
    if dimension not in QUALITY_DIMENSIONS:
        raise QualityValidationError(f"Unknown quality dimension: {dimension}")
