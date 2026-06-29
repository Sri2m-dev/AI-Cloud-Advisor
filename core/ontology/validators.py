from __future__ import annotations

from dataclasses import dataclass

from core.ontology.ontology import EnterpriseOntology


@dataclass(frozen=True, slots=True)
class RelationshipValidationResult:
    is_valid: bool
    relationship_type: str
    source_entity_type: str
    target_entity_type: str
    message: str
    cardinality: str | None = None
    direction: str | None = None
    default_strength: str | None = None
    ontology_version: str | None = None


class RelationshipValidator:
    def __init__(self, ontology: EnterpriseOntology | None = None):
        self.ontology = ontology or EnterpriseOntology()

    def validate(
        self,
        relationship_type: str,
        source_entity_type: str,
        target_entity_type: str,
    ) -> RelationshipValidationResult:
        if not self.ontology.is_known_relationship(relationship_type):
            return RelationshipValidationResult(
                is_valid=False,
                relationship_type=relationship_type,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
                message=f"Unknown relationship type: {relationship_type}",
            )

        rules = self.ontology.get_rules(relationship_type)
        if not rules:
            return RelationshipValidationResult(
                is_valid=True,
                relationship_type=relationship_type,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
                message="Relationship type is known and has no restricted source/target rule.",
            )

        matched_rule = self.ontology.get_applicable_rule(relationship_type, source_entity_type, target_entity_type)
        if matched_rule:
            return RelationshipValidationResult(
                is_valid=True,
                relationship_type=relationship_type,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
                message="Relationship source and target are allowed by ontology.",
                cardinality=matched_rule.cardinality.label,
                direction=matched_rule.direction,
                default_strength=matched_rule.default_strength,
                ontology_version=matched_rule.ontology_version,
            )

        allowed = "; ".join(
            f"{sorted(rule.source_entity_types)} -> {sorted(rule.target_entity_types)}"
            for rule in rules
        )
        return RelationshipValidationResult(
            is_valid=False,
            relationship_type=relationship_type,
            source_entity_type=source_entity_type,
            target_entity_type=target_entity_type,
            message=f"{source_entity_type} {relationship_type} {target_entity_type} is not allowed. Allowed patterns: {allowed}",
        )

    def require_valid(
        self,
        relationship_type: str,
        source_entity_type: str,
        target_entity_type: str,
    ) -> RelationshipValidationResult:
        result = self.validate(relationship_type, source_entity_type, target_entity_type)
        if not result.is_valid:
            raise ValueError(result.message)
        return result
