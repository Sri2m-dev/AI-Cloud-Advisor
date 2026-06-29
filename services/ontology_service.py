from __future__ import annotations

from collections import defaultdict

from core.ontology.ontology import EnterpriseOntology, RelationshipRule
from core.ontology.relationship_types import RelationshipDefinition
from core.ontology.validators import RelationshipValidationResult, RelationshipValidator
from repositories.ontology_repository import OntologyRepository


class OntologyService:
    def __init__(self, repository: OntologyRepository | None = None):
        self.repository = repository or OntologyRepository()
        self.ontology = self.repository.load()
        self.validator = RelationshipValidator(self.ontology)

    def list_relationship_definitions(self) -> list[RelationshipDefinition]:
        return sorted(self.ontology.relationship_definitions.values(), key=lambda item: (item.group.value, item.name))

    def list_relationship_rules(self, relationship_type: str | None = None) -> list[RelationshipRule]:
        return self.ontology.get_rules(relationship_type)

    def grouped_relationships(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for definition in self.list_relationship_definitions():
            grouped[definition.group.value].append(definition.name)
        return dict(grouped)

    def validate_relationship(
        self,
        relationship_type: str,
        source_entity_type: str,
        target_entity_type: str,
    ) -> RelationshipValidationResult:
        return self.validator.validate(relationship_type, source_entity_type, target_entity_type)

    def require_valid_relationship(
        self,
        relationship_type: str,
        source_entity_type: str,
        target_entity_type: str,
    ) -> RelationshipValidationResult:
        return self.validator.require_valid(relationship_type, source_entity_type, target_entity_type)

    def allowed_relationships_for(self, source_entity_type: str, target_entity_type: str) -> list[str]:
        return self.ontology.allowed_relationships_for(source_entity_type, target_entity_type)

    def relationship_semantics(
        self,
        relationship_type: str,
        source_entity_type: str,
        target_entity_type: str,
    ) -> dict[str, str | None]:
        rule = self.ontology.get_applicable_rule(relationship_type, source_entity_type, target_entity_type)
        definition = self.ontology.get_relationship_definition(relationship_type)
        return {
            "relationship_group": definition.group.value if definition else None,
            "cardinality": rule.cardinality.label if rule else None,
            "direction": rule.direction if rule else (definition.direction if definition else None),
            "default_strength": rule.default_strength if rule else (definition.default_strength if definition else None),
            "ontology_version": rule.ontology_version if rule else (definition.ontology_version if definition else None),
        }

    def require_cardinality_allows(
        self,
        relationship_type: str,
        source_entity_type: str,
        target_entity_type: str,
        existing_targets_for_source: int,
        existing_sources_for_target: int,
        same_relationship_exists: bool = False,
    ) -> None:
        rule = self.ontology.get_applicable_rule(relationship_type, source_entity_type, target_entity_type)
        if not rule:
            return
        if not rule.cardinality.allows(
            existing_targets_for_source=existing_targets_for_source,
            existing_sources_for_target=existing_sources_for_target,
            same_relationship_exists=same_relationship_exists,
        ):
            raise ValueError(
                f"{relationship_type} violates cardinality {rule.cardinality.label} for "
                f"{source_entity_type} -> {target_entity_type}"
            )

    def save_current_ontology(self) -> EnterpriseOntology:
        return self.repository.save(self.ontology)
