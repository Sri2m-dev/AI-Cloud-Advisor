from datetime import datetime, timedelta, timezone

import pytest

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityLineage,
    EntityOwnership,
    EntityProvenance,
    EntityType,
)
from data_fabric.lineage import LineageEvent, LineagePath, ProvenanceRecord
from data_fabric.quality import (
    DEFAULT_DIMENSION_WEIGHTS,
    InMemoryDataQualityEvaluator,
    QualityIssue,
    QualityIssueSeverity,
    QualityRule,
    QualityRuleResult,
    QualityValidationError,
    WeightedTrustScoreCalculator,
)


def make_entity(**overrides):
    values = {
        "id": "ent-1",
        "canonical_id": "application:checkout",
        "entity_type": EntityType.APPLICATION,
        "name": "Checkout",
        "source_system": "servicenow",
        "source_identifier": "app-123",
        "organization_id": "org-1",
        "tenant_id": "tenant-1",
        "confidence_score": 1.0,
        "quality_score": 1.0,
        "ownership": EntityOwnership(owner_id="owner-1", owner_name="Platform"),
        "lineage": EntityLineage(connector="servicenow", raw_record_id="raw-1"),
        "provenance": EntityProvenance(
            source_system="servicenow",
            source_identifier="app-123",
            collection_method="connector_sync",
        ),
    }
    values.update(overrides)
    return EnterpriseEntity(**values)


def make_relationship(**overrides):
    values = {
        "id": "rel-1",
        "relationship_type": "runs_on",
        "source_entity_id": "ent-1",
        "target_entity_id": "ent-2",
        "organization_id": "org-1",
        "tenant_id": "tenant-1",
        "source_system": "servicenow",
        "source_identifier": "rel-123",
        "confidence_score": 1.0,
        "quality_score": 1.0,
        "lineage": EntityLineage(connector="servicenow", raw_record_id="raw-rel-1"),
        "provenance": EntityProvenance(
            source_system="servicenow",
            source_identifier="rel-123",
            collection_method="connector_sync",
        ),
    }
    values.update(overrides)
    return EnterpriseRelationship(**values)


def lineage_path() -> LineagePath:
    return LineagePath(
        subject_id="ent-1",
        events=(
            LineageEvent(
                id="lin-1",
                event_type="source",
                source_system="servicenow",
                source_identifier="app-123",
                organization_id="org-1",
                entity_id="ent-1",
            ),
        ),
    )


def provenance_records() -> list[ProvenanceRecord]:
    return [
        ProvenanceRecord(
            id="prov-1",
            source_system="servicenow",
            source_identifier="app-123",
            organization_id="org-1",
            collection_method="connector_sync",
            entity_id="ent-1",
        )
    ]


def test_valid_entity_receives_expected_deterministic_score() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    entity = make_entity()

    assessment = evaluator.evaluate_entity(
        entity,
        lineage_path=lineage_path(),
        provenance_records=provenance_records(),
        uniqueness_confirmed=True,
    )

    assert assessment.trust_score.final_score == 100.0
    assert evaluator.identify_failed_dimensions(assessment) == []
    assert evaluator.identify_blocking_issues(assessment) == []


def test_incomplete_entity_receives_deductions() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    entity = make_entity(tenant_id=None, ownership=None, lineage=None, provenance=None)

    assessment = evaluator.evaluate_entity(entity)

    assert assessment.dimension_scores["completeness"].score == 70.0
    assert assessment.dimension_scores["ownership_completeness"].score == 60.0
    assert assessment.trust_score.final_score < 100.0


def test_invalid_timestamps_produce_blocking_issue() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    entity = make_entity()
    entity.created_at = datetime.now(timezone.utc) + timedelta(days=1)
    entity.updated_at = datetime.now(timezone.utc)

    assessment = evaluator.evaluate_entity(entity, uniqueness_confirmed=True)

    blocking = evaluator.identify_blocking_issues(assessment)
    assert any(issue.rule_id == "entity_timestamp_order" for issue in blocking)
    assert assessment.dimension_scores["consistency"].score == 0.0


def test_invalid_score_ranges_are_handled_explicitly() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    entity = make_entity()
    entity.confidence_score = 1.4

    assessment = evaluator.evaluate_entity(entity, uniqueness_confirmed=True)

    assert assessment.dimension_scores["accuracy"].score == 0.0
    assert any(issue.rule_id == "entity_confidence_score_valid" for issue in evaluator.identify_blocking_issues(assessment))


def test_relationship_self_reference_rule_blocks_invalid_relationship() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    relationship = make_relationship(target_entity_id="ent-1")

    assessment = evaluator.evaluate_relationship(relationship, uniqueness_confirmed=True)

    assert assessment.dimension_scores["validity"].score == 0.0
    assert any(issue.rule_id == "relationship_not_self_referential" for issue in evaluator.identify_blocking_issues(assessment))


def test_custom_weights_are_accepted_when_valid() -> None:
    weights = dict(DEFAULT_DIMENSION_WEIGHTS)
    weights["completeness"] = 0.20
    weights["freshness"] = 0.08

    calculator = WeightedTrustScoreCalculator(weights)

    assert calculator.weights["completeness"] == 0.20
    assert round(sum(calculator.weights.values()), 8) == 1.0


def test_invalid_custom_weights_are_rejected() -> None:
    weights = dict(DEFAULT_DIMENSION_WEIGHTS)
    weights["completeness"] = 0.50

    with pytest.raises(QualityValidationError):
        WeightedTrustScoreCalculator(weights)


def test_explanation_includes_dimensions_and_deductions() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    assessment = evaluator.evaluate_entity(make_entity(lineage=None), uniqueness_confirmed=True)
    explanation = evaluator.explain_score(assessment)

    assert "completeness: score=" in explanation
    assert "lineage_confidence: score=" in explanation
    assert "deduction=" in explanation
    assert "final_score=" in explanation


def test_missing_lineage_does_not_silently_score_as_perfect() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    assessment = evaluator.evaluate_entity(make_entity(lineage=None), uniqueness_confirmed=True)

    assert assessment.dimension_scores["lineage_confidence"].score == 50.0
    assert any(issue.rule_id == "entity_lineage_available" for issue in assessment.issues)


def test_organization_and_tenant_context_are_preserved() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    assessment = evaluator.evaluate_entity(make_entity(organization_id="org-2", tenant_id="tenant-2"))

    assert assessment.organization_id == "org-2"
    assert assessment.tenant_id == "tenant-2"


def test_batch_results_remain_associated_and_org_isolated() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    first = make_entity(id="shared", organization_id="org-1")
    second = make_entity(id="shared", canonical_id="application:billing", organization_id="org-2")

    results = evaluator.evaluate_batch([first, second], uniqueness_confirmed=True)

    assert set(results) == {"org-1:shared", "org-2:shared"}
    assert results["org-1:shared"].organization_id == "org-1"
    assert results["org-2:shared"].organization_id == "org-2"


def test_repeated_evaluation_returns_same_result() -> None:
    evaluator = InMemoryDataQualityEvaluator()
    entity = make_entity()

    first = evaluator.evaluate_entity(entity, uniqueness_confirmed=True)
    second = evaluator.evaluate_entity(entity, uniqueness_confirmed=True)

    assert first.trust_score.final_score == second.trust_score.final_score
    assert first.dimension_scores == second.dimension_scores


def test_custom_rule_registration_works() -> None:
    class AccuracyPenaltyRule(QualityRule):
        rule_id = "custom_accuracy_penalty"
        subject_type = "entity"
        dimension = "accuracy"

        def evaluate(self, subject, evidence):
            issue = QualityIssue(
                rule_id=self.rule_id,
                dimension=self.dimension,
                message="Custom accuracy warning.",
                severity=QualityIssueSeverity.WARNING,
                deduction=50.0,
            )
            return QualityRuleResult(self.rule_id, self.dimension, 50.0, (issue,))

    evaluator = InMemoryDataQualityEvaluator()
    evaluator.register_rule(AccuracyPenaltyRule())

    assessment = evaluator.evaluate_entity(make_entity(), uniqueness_confirmed=True)

    assert any(rule.rule_id == "custom_accuracy_penalty" for rule in evaluator.list_rules())
    assert assessment.dimension_scores["accuracy"].score == 50.0


def test_entity_and_relationship_evaluations_remain_separate() -> None:
    evaluator = InMemoryDataQualityEvaluator()

    entity_assessment = evaluator.evaluate_entity(make_entity(), uniqueness_confirmed=True)
    relationship_assessment = evaluator.evaluate_relationship(make_relationship(), uniqueness_confirmed=True)

    assert entity_assessment.subject_type == "entity"
    assert relationship_assessment.subject_type == "relationship"
    assert entity_assessment.subject_id == "ent-1"
    assert relationship_assessment.subject_id == "rel-1"
