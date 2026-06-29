from __future__ import annotations

import json
from pathlib import Path

from core.ontology.ontology import EnterpriseOntology, RelationshipCardinality, RelationshipRule
from core.ontology.relationship_types import (
    CANONICAL_RELATIONSHIP_DEFINITIONS,
    RelationshipDefinition,
    RelationshipGroup,
)


DEFAULT_ONTOLOGY_STORE = Path("data/enterprise_ontology.json")


class OntologyRepository:
    def __init__(self, store_path: str | Path = DEFAULT_ONTOLOGY_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> EnterpriseOntology:
        if not self.store_path.exists():
            return EnterpriseOntology()

        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        definitions = {
            item["name"]: RelationshipDefinition(
                name=item["name"],
                group=RelationshipGroup(item["group"]),
                description=item.get("description", ""),
                inverse_name=item.get("inverse_name"),
                direction=item.get("direction", "Forward"),
                default_strength=item.get("default_strength", "Medium"),
                ontology_version=item.get("ontology_version", "1.2.1"),
                is_canonical=bool(item.get("is_canonical", True)),
            )
            for item in payload.get("relationship_definitions", [])
        } or dict(CANONICAL_RELATIONSHIP_DEFINITIONS)

        rules = [
            RelationshipRule(
                relationship_type=item["relationship_type"],
                source_entity_types=frozenset(item.get("source_entity_types", [])),
                target_entity_types=frozenset(item.get("target_entity_types", [])),
                description=item.get("description", ""),
                cardinality=RelationshipCardinality(
                    label=item.get("cardinality", "N..N"),
                    max_targets_per_source=item.get("max_targets_per_source"),
                    max_sources_per_target=item.get("max_sources_per_target"),
                ),
                direction=item.get("direction", "Forward"),
                default_strength=item.get("default_strength", "Medium"),
                ontology_version=item.get("ontology_version", "1.2.1"),
            )
            for item in payload.get("relationship_rules", [])
        ]
        return EnterpriseOntology(relationship_definitions=definitions, relationship_rules=rules)

    def save(self, ontology: EnterpriseOntology) -> EnterpriseOntology:
        payload = {
            "relationship_definitions": [
                {
                    "name": definition.name,
                    "group": definition.group.value,
                    "description": definition.description,
                    "inverse_name": definition.inverse_name,
                    "direction": definition.direction,
                    "default_strength": definition.default_strength,
                    "ontology_version": definition.ontology_version,
                    "is_canonical": definition.is_canonical,
                }
                for definition in sorted(ontology.relationship_definitions.values(), key=lambda item: item.name)
            ],
            "relationship_rules": [
                {
                    "relationship_type": rule.relationship_type,
                    "source_entity_types": sorted(rule.source_entity_types),
                    "target_entity_types": sorted(rule.target_entity_types),
                    "description": rule.description,
                    "cardinality": rule.cardinality.label,
                    "max_targets_per_source": rule.cardinality.max_targets_per_source,
                    "max_sources_per_target": rule.cardinality.max_sources_per_target,
                    "direction": rule.direction,
                    "default_strength": rule.default_strength,
                    "ontology_version": rule.ontology_version,
                }
                for rule in sorted(ontology.relationship_rules, key=lambda item: (item.relationship_type, item.description))
            ],
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return ontology
