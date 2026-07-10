"""Provider-agnostic default quality rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from data_fabric.quality.interfaces import QualityRule
from data_fabric.quality.scoring import (
    QualityIssue,
    QualityIssueSeverity,
    QualityRuleResult,
)


@dataclass(frozen=True, slots=True)
class FieldPresenceRule(QualityRule):
    """Validate that a field is present on a canonical object."""

    rule_id: str
    subject_type: str
    dimension: str
    field_name: str
    message: str
    severity: QualityIssueSeverity = QualityIssueSeverity.WARNING
    fail_score: float = 0.0

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        value = _resolve(subject, self.field_name)
        if _present(value):
            return QualityRuleResult(self.rule_id, self.dimension, 100.0)
        return _failed_result(self, self.message)


@dataclass(frozen=True, slots=True)
class RatioScoreRule(QualityRule):
    """Map an existing 0-1 contract score to a 0-100 quality dimension."""

    rule_id: str
    subject_type: str
    dimension: str
    field_name: str

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        value = _resolve(subject, self.field_name)
        try:
            score = float(value)
        except (TypeError, ValueError):
            return _issue_result(self.rule_id, self.dimension, 0.0, f"{self.field_name} must be numeric.", QualityIssueSeverity.BLOCKING)
        if score < 0.0 or score > 1.0:
            return _issue_result(self.rule_id, self.dimension, 0.0, f"{self.field_name} must be between 0 and 1.", QualityIssueSeverity.BLOCKING)
        return QualityRuleResult(self.rule_id, self.dimension, round(score * 100.0, 4))


@dataclass(frozen=True, slots=True)
class TimestampOrderRule(QualityRule):
    """Validate canonical timestamps are internally consistent."""

    rule_id: str
    subject_type: str
    dimension: str = "consistency"

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        created_at = getattr(subject, "created_at", None)
        updated_at = getattr(subject, "updated_at", None)
        if created_at is None or updated_at is None:
            return _issue_result(self.rule_id, self.dimension, 75.0, "created_at and updated_at should both be available.", QualityIssueSeverity.WARNING)
        if created_at > updated_at:
            return _issue_result(self.rule_id, self.dimension, 0.0, "created_at cannot be after updated_at.", QualityIssueSeverity.BLOCKING)
        return QualityRuleResult(self.rule_id, self.dimension, 100.0)


@dataclass(frozen=True, slots=True)
class FreshnessRule(QualityRule):
    """Assess whether update timestamps are available for freshness scoring."""

    rule_id: str
    subject_type: str
    dimension: str = "freshness"

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        if getattr(subject, "updated_at", None) is not None:
            return QualityRuleResult(self.rule_id, self.dimension, 100.0)
        return _issue_result(self.rule_id, self.dimension, 75.0, "updated_at is not available for freshness scoring.", QualityIssueSeverity.WARNING)


@dataclass(frozen=True, slots=True)
class OwnershipCompletenessRule(QualityRule):
    """Assess ownership metadata without forcing a provider-specific owner model."""

    rule_id: str = "ownership_available"
    subject_type: str = "entity"
    dimension: str = "ownership_completeness"

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        if getattr(subject, "ownership", None) is not None:
            return QualityRuleResult(self.rule_id, self.dimension, 100.0)
        quality = getattr(subject, "quality", None)
        if quality is not None and getattr(quality, "owner", None):
            return QualityRuleResult(self.rule_id, self.dimension, 100.0)
        if getattr(subject, "metadata", {}).get("ownership_missing") is True:
            return _issue_result(self.rule_id, self.dimension, 80.0, "Ownership is explicitly marked missing.", QualityIssueSeverity.WARNING)
        return _issue_result(self.rule_id, self.dimension, 60.0, "Ownership information is not available.", QualityIssueSeverity.WARNING)


@dataclass(frozen=True, slots=True)
class LineageAvailabilityRule(QualityRule):
    """Assess lineage evidence availability without requiring persistence."""

    rule_id: str
    subject_type: str
    dimension: str = "lineage_confidence"

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        if getattr(subject, "lineage", None) is not None or _has_lineage_evidence(evidence):
            return QualityRuleResult(self.rule_id, self.dimension, 100.0)
        return _issue_result(self.rule_id, self.dimension, 50.0, "Lineage evidence is not available.", QualityIssueSeverity.WARNING)


@dataclass(frozen=True, slots=True)
class ProvenanceAvailabilityRule(QualityRule):
    """Assess provenance evidence availability for source confidence."""

    rule_id: str
    subject_type: str
    dimension: str = "source_confidence"

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        if getattr(subject, "provenance", None) is not None or _has_provenance_evidence(evidence):
            return QualityRuleResult(self.rule_id, self.dimension, 100.0)
        return _issue_result(self.rule_id, self.dimension, 70.0, "Provenance evidence is not available.", QualityIssueSeverity.WARNING)


@dataclass(frozen=True, slots=True)
class UniquenessEvidenceRule(QualityRule):
    """Require explicit uniqueness evidence instead of assuming perfection."""

    rule_id: str
    subject_type: str
    dimension: str = "uniqueness"

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        duplicate_ids = set(evidence.get("duplicate_identifiers", ()))
        identifier = getattr(subject, "canonical_id", None) or getattr(subject, "id", None)
        if identifier in duplicate_ids:
            return _issue_result(self.rule_id, self.dimension, 0.0, f"Duplicate identifier detected: {identifier}.", QualityIssueSeverity.BLOCKING)
        if evidence.get("uniqueness_confirmed") is True:
            return QualityRuleResult(self.rule_id, self.dimension, 100.0)
        return _issue_result(self.rule_id, self.dimension, 80.0, "Uniqueness evidence was not provided.", QualityIssueSeverity.WARNING)


@dataclass(frozen=True, slots=True)
class RelationshipSelfReferenceRule(QualityRule):
    """Prevent accidental self-referential relationships."""

    rule_id: str = "relationship_not_self_referential"
    subject_type: str = "relationship"
    dimension: str = "validity"

    def evaluate(self, subject: Any, evidence: Mapping[str, Any]) -> QualityRuleResult:
        if getattr(subject, "source_entity_id", None) != getattr(subject, "target_entity_id", None):
            return QualityRuleResult(self.rule_id, self.dimension, 100.0)
        if getattr(subject, "metadata", {}).get("allow_self_reference") is True:
            return _issue_result(self.rule_id, self.dimension, 85.0, "Self-reference is explicitly allowed.", QualityIssueSeverity.WARNING)
        return _issue_result(self.rule_id, self.dimension, 0.0, "Relationship source and target cannot be identical unless explicitly allowed.", QualityIssueSeverity.BLOCKING)


def default_quality_rules() -> list[QualityRule]:
    """Return default provider-agnostic quality rules."""

    return [
        FieldPresenceRule("entity_canonical_id_present", "entity", "completeness", "canonical_id", "canonical_id is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("entity_type_present", "entity", "completeness", "entity_type", "entity_type is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("entity_name_present", "entity", "completeness", "name", "name is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("entity_source_system_present", "entity", "source_confidence", "source_system", "source_system is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("entity_source_identifier_present", "entity", "source_confidence", "source_identifier", "source_identifier is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("entity_organization_present", "entity", "validity", "organization_id", "organization_id is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("entity_tenant_present", "entity", "completeness", "tenant_id", "tenant_id is required.", QualityIssueSeverity.WARNING, 70.0),
        RatioScoreRule("entity_confidence_score_valid", "entity", "accuracy", "confidence_score"),
        RatioScoreRule("entity_quality_score_valid", "entity", "validity", "quality_score"),
        TimestampOrderRule("entity_timestamp_order", "entity"),
        FreshnessRule("entity_freshness_available", "entity"),
        OwnershipCompletenessRule(),
        LineageAvailabilityRule("entity_lineage_available", "entity"),
        ProvenanceAvailabilityRule("entity_provenance_available", "entity"),
        UniquenessEvidenceRule("entity_uniqueness_evidence", "entity"),
        FieldPresenceRule("relationship_source_present", "relationship", "completeness", "source_entity_id", "source_entity_id is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("relationship_target_present", "relationship", "completeness", "target_entity_id", "target_entity_id is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("relationship_type_present", "relationship", "validity", "relationship_type", "relationship_type is required.", QualityIssueSeverity.BLOCKING),
        RelationshipSelfReferenceRule(),
        FieldPresenceRule("relationship_organization_present", "relationship", "validity", "organization_id", "organization_id is required.", QualityIssueSeverity.BLOCKING),
        FieldPresenceRule("relationship_tenant_present", "relationship", "completeness", "tenant_id", "tenant_id is required.", QualityIssueSeverity.WARNING, 70.0),
        RatioScoreRule("relationship_confidence_score_valid", "relationship", "accuracy", "confidence_score"),
        RatioScoreRule("relationship_quality_score_valid", "relationship", "validity", "quality_score"),
        TimestampOrderRule("relationship_timestamp_order", "relationship"),
        FreshnessRule("relationship_freshness_available", "relationship"),
        LineageAvailabilityRule("relationship_lineage_available", "relationship"),
        ProvenanceAvailabilityRule("relationship_provenance_available", "relationship"),
        UniquenessEvidenceRule("relationship_uniqueness_evidence", "relationship"),
    ]


def _resolve(subject: Any, field_name: str) -> Any:
    value = subject
    for part in field_name.split("."):
        value = getattr(value, part, None)
        if value is None:
            return None
    return value


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _failed_result(rule: FieldPresenceRule, message: str) -> QualityRuleResult:
    return _issue_result(rule.rule_id, rule.dimension, rule.fail_score, message, rule.severity)


def _issue_result(rule_id: str, dimension: str, score: float, message: str, severity: QualityIssueSeverity) -> QualityRuleResult:
    issue = QualityIssue(rule_id=rule_id, dimension=dimension, message=message, severity=severity, deduction=100.0 - score)
    return QualityRuleResult(rule_id=rule_id, dimension=dimension, score=score, issues=(issue,))


def _has_lineage_evidence(evidence: Mapping[str, Any]) -> bool:
    lineage_path = evidence.get("lineage_path")
    if lineage_path is not None and getattr(lineage_path, "events", None):
        return True
    return bool(evidence.get("lineage_events"))


def _has_provenance_evidence(evidence: Mapping[str, Any]) -> bool:
    return bool(evidence.get("provenance_records"))

