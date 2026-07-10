"""Data quality and trust scoring interfaces for P3 Data Fabric."""

from data_fabric.quality.evaluator import InMemoryDataQualityEvaluator
from data_fabric.quality.exceptions import QualityScoringError, QualityValidationError
from data_fabric.quality.interfaces import (
    DataQualityEvaluator,
    QualityRule,
    TrustScoreCalculator,
)
from data_fabric.quality.scoring import (
    DEFAULT_DIMENSION_WEIGHTS,
    QUALITY_DIMENSIONS,
    QualityAssessment,
    QualityDimensionScore,
    QualityIssue,
    QualityIssueSeverity,
    QualityRuleResult,
    TrustScore,
)
from data_fabric.quality.scoring import validate_score_100, validate_weights
from data_fabric.quality.scoring import WeightedTrustScoreCalculator

__all__ = [
    "DEFAULT_DIMENSION_WEIGHTS",
    "QUALITY_DIMENSIONS",
    "DataQualityEvaluator",
    "InMemoryDataQualityEvaluator",
    "QualityAssessment",
    "QualityDimensionScore",
    "QualityIssue",
    "QualityIssueSeverity",
    "QualityRule",
    "QualityRuleResult",
    "QualityScoringError",
    "QualityValidationError",
    "TrustScore",
    "TrustScoreCalculator",
    "WeightedTrustScoreCalculator",
    "validate_score_100",
    "validate_weights",
]
