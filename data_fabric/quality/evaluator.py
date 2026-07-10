"""In-memory data quality evaluator implementation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.quality.interfaces import DataQualityEvaluator, QualityRule
from data_fabric.quality.rules import default_quality_rules
from data_fabric.quality.scoring import (
    QUALITY_DIMENSIONS,
    QualityAssessment,
    QualityDimensionScore,
    QualityIssue,
    TrustScore,
    WeightedTrustScoreCalculator,
)


class InMemoryDataQualityEvaluator(DataQualityEvaluator):
    """Provider-agnostic, non-persistent quality evaluator."""

    def __init__(
        self,
        rules: Iterable[QualityRule] | None = None,
        trust_calculator: WeightedTrustScoreCalculator | None = None,
    ) -> None:
        self._rules = list(rules or default_quality_rules())
        self._trust_calculator = trust_calculator or WeightedTrustScoreCalculator()

    def evaluate_entity(self, entity: EnterpriseEntity, **evidence: Any) -> QualityAssessment:
        return self._evaluate(entity, subject_type="entity", evidence=evidence)

    def evaluate_relationship(
        self,
        relationship: EnterpriseRelationship,
        **evidence: Any,
    ) -> QualityAssessment:
        return self._evaluate(relationship, subject_type="relationship", evidence=evidence)

    def evaluate_batch(self, subjects: Iterable[Any], **evidence: Any) -> dict[str, QualityAssessment]:
        results: dict[str, QualityAssessment] = {}
        for subject in subjects:
            if isinstance(subject, EnterpriseEntity):
                assessment = self.evaluate_entity(subject, **evidence)
            elif isinstance(subject, EnterpriseRelationship):
                assessment = self.evaluate_relationship(subject, **evidence)
            else:
                raise TypeError(f"Unsupported quality subject: {type(subject).__name__}")
            results[f"{assessment.organization_id}:{assessment.subject_id}"] = assessment
        return results

    def register_rule(self, rule: QualityRule) -> None:
        self._rules.append(rule)

    def list_rules(self) -> list[QualityRule]:
        return list(self._rules)

    def calculate_trust_score(self, assessment: QualityAssessment) -> TrustScore:
        return self._trust_calculator.calculate(assessment.dimension_scores, assessment.issues)

    def explain_score(self, assessment: QualityAssessment) -> str:
        return "\n".join(assessment.trust_score.explanation)

    def identify_failed_dimensions(self, assessment: QualityAssessment) -> list[str]:
        return [
            dimension
            for dimension in QUALITY_DIMENSIONS
            if assessment.dimension_scores[dimension].score < 100.0
        ]

    def identify_blocking_issues(self, assessment: QualityAssessment) -> list[QualityIssue]:
        return [issue for issue in assessment.issues if issue.is_blocking]

    def _evaluate(self, subject: Any, *, subject_type: str, evidence: dict[str, Any]) -> QualityAssessment:
        rule_results = [
            rule.evaluate(subject, evidence)
            for rule in self._rules
            if rule.subject_type == subject_type
        ]
        dimension_scores: dict[str, QualityDimensionScore] = {}
        all_issues: list[QualityIssue] = []
        for dimension in QUALITY_DIMENSIONS:
            results = [result for result in rule_results if result.dimension == dimension]
            if results:
                score = min(result.score for result in results)
                issues = tuple(issue for result in results for issue in result.issues)
            else:
                score = 0.0
                issue = QualityIssue(
                    rule_id="missing_dimension_rule",
                    dimension=dimension,
                    message=f"No rule evaluated dimension {dimension}.",
                    deduction=100.0,
                )
                issues = (issue,)
            all_issues.extend(issues)
            dimension_scores[dimension] = QualityDimensionScore(
                dimension=dimension,
                score=score,
                issues=issues,
            )
        trust_score = self._trust_calculator.calculate(dimension_scores, tuple(all_issues))
        return QualityAssessment(
            subject_id=getattr(subject, "id"),
            subject_type=subject_type,
            organization_id=getattr(subject, "organization_id"),
            tenant_id=getattr(subject, "tenant_id", None),
            source_system=getattr(subject, "source_system", None),
            source_identifier=getattr(subject, "source_identifier", None),
            dimension_scores=dimension_scores,
            issues=tuple(all_issues),
            trust_score=trust_score,
        )

