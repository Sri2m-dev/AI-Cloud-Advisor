"""Abstract interfaces for data quality evaluation and trust scoring."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Mapping

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.quality.scoring import (
    QualityAssessment,
    QualityRuleResult,
    TrustScore,
)


class QualityRule(ABC):
    """Extensible provider-agnostic quality rule interface."""

    rule_id: str
    subject_type: str
    dimension: str

    @abstractmethod
    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        """Evaluate a canonical entity or relationship."""


class TrustScoreCalculator(ABC):
    """Interface for calculating deterministic trust scores."""

    @abstractmethod
    def calculate(self, dimension_scores: Mapping[str, Any], issues: tuple[Any, ...]) -> TrustScore:
        """Calculate a weighted trust score from dimension scores."""


class DataQualityEvaluator(ABC):
    """Interface for assessing canonical entity and relationship quality."""

    @abstractmethod
    def evaluate_entity(self, entity: EnterpriseEntity, **evidence: Any) -> QualityAssessment:
        """Evaluate one canonical entity."""

    @abstractmethod
    def evaluate_relationship(
        self,
        relationship: EnterpriseRelationship,
        **evidence: Any,
    ) -> QualityAssessment:
        """Evaluate one canonical relationship."""

    @abstractmethod
    def evaluate_batch(self, subjects: Iterable[Any], **evidence: Any) -> dict[str, QualityAssessment]:
        """Evaluate entities and relationships while preserving subject traceability."""

    @abstractmethod
    def register_rule(self, rule: QualityRule) -> None:
        """Register an additional provider-agnostic or injected domain rule."""

    @abstractmethod
    def list_rules(self) -> list[QualityRule]:
        """List active quality rules."""

    @abstractmethod
    def calculate_trust_score(self, assessment: QualityAssessment) -> TrustScore:
        """Recalculate a trust score for an assessment."""

    @abstractmethod
    def explain_score(self, assessment: QualityAssessment) -> str:
        """Explain dimension scores, weights, deductions, and final score."""

    @abstractmethod
    def identify_failed_dimensions(self, assessment: QualityAssessment) -> list[str]:
        """Return dimensions with less than perfect scores."""

    @abstractmethod
    def identify_blocking_issues(self, assessment: QualityAssessment) -> list[Any]:
        """Return blocking issues from an assessment."""
