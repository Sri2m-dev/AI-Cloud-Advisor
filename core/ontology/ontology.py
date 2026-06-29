from __future__ import annotations

from dataclasses import dataclass, field

from core.entities.entity import EntityType, RelationshipDirection, RelationshipStrength
from core.ontology.relationship_types import (
    CANONICAL_RELATIONSHIP_DEFINITIONS,
    RelationshipDefinition,
)


WILDCARD_ENTITY = "*"
ONTOLOGY_VERSION = "1.2.1"


@dataclass(frozen=True, slots=True)
class RelationshipCardinality:
    label: str
    max_targets_per_source: int | None = None
    max_sources_per_target: int | None = None

    def allows(
        self,
        *,
        existing_targets_for_source: int,
        existing_sources_for_target: int,
        same_relationship_exists: bool = False,
    ) -> bool:
        if same_relationship_exists:
            return True
        if self.max_targets_per_source is not None and existing_targets_for_source >= self.max_targets_per_source:
            return False
        if self.max_sources_per_target is not None and existing_sources_for_target >= self.max_sources_per_target:
            return False
        return True


@dataclass(frozen=True, slots=True)
class RelationshipRule:
    relationship_type: str
    source_entity_types: frozenset[str]
    target_entity_types: frozenset[str]
    description: str = ""
    cardinality: RelationshipCardinality = field(default_factory=lambda: RelationshipCardinality("N..N"))
    direction: str = RelationshipDirection.FORWARD.value
    default_strength: str = RelationshipStrength.MEDIUM.value
    ontology_version: str = ONTOLOGY_VERSION

    def allows(self, source_entity_type: str, target_entity_type: str) -> bool:
        source_allowed = WILDCARD_ENTITY in self.source_entity_types or source_entity_type in self.source_entity_types
        target_allowed = WILDCARD_ENTITY in self.target_entity_types or target_entity_type in self.target_entity_types
        return source_allowed and target_allowed


@dataclass(slots=True)
class EnterpriseOntology:
    relationship_definitions: dict[str, RelationshipDefinition] = field(
        default_factory=lambda: dict(CANONICAL_RELATIONSHIP_DEFINITIONS)
    )
    relationship_rules: list[RelationshipRule] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.relationship_rules:
            self.relationship_rules.extend(default_relationship_rules())

    def get_relationship_definition(self, relationship_type: str) -> RelationshipDefinition | None:
        return self.relationship_definitions.get(relationship_type)

    def get_rules(self, relationship_type: str | None = None) -> list[RelationshipRule]:
        if relationship_type is None:
            return list(self.relationship_rules)
        return [rule for rule in self.relationship_rules if rule.relationship_type == relationship_type]

    def get_applicable_rule(
        self,
        relationship_type: str,
        source_entity_type: str,
        target_entity_type: str,
    ) -> RelationshipRule | None:
        for rule in self.get_rules(relationship_type):
            if rule.allows(source_entity_type, target_entity_type):
                return rule
        return None

    def is_known_relationship(self, relationship_type: str) -> bool:
        return relationship_type in self.relationship_definitions

    def allowed_relationships_for(self, source_entity_type: str, target_entity_type: str) -> list[str]:
        return [
            rule.relationship_type
            for rule in self.relationship_rules
            if rule.allows(source_entity_type, target_entity_type)
        ]


def default_relationship_rules() -> list[RelationshipRule]:
    application = EntityType.APPLICATION.value
    business_service = EntityType.BUSINESS_SERVICE.value
    technology = EntityType.TECHNOLOGY.value
    cloud_account = EntityType.CLOUD_ACCOUNT.value
    vendor = EntityType.VENDOR.value
    cost_center = EntityType.COST_CENTER.value
    risk = EntityType.RISK.value
    control = EntityType.CONTROL.value
    recommendation = EntityType.RECOMMENDATION.value

    return [
        RelationshipRule(
            "RUNS_ON",
            frozenset({application}),
            frozenset({technology}),
            "Application RUNS_ON Technology",
            cardinality=RelationshipCardinality("1..N"),
            default_strength=RelationshipStrength.HIGH.value,
        ),
        RelationshipRule(
            "USES",
            frozenset({business_service}),
            frozenset({application}),
            "Business Service USES Application",
            cardinality=RelationshipCardinality("1..N"),
            default_strength=RelationshipStrength.HIGH.value,
        ),
        RelationshipRule(
            "DEPLOYED_IN",
            frozenset({technology}),
            frozenset({cloud_account}),
            "Technology DEPLOYED_IN Cloud Account",
            cardinality=RelationshipCardinality("N..1", max_targets_per_source=1),
            default_strength=RelationshipStrength.HIGH.value,
        ),
        RelationshipRule(
            "SUPPLIES",
            frozenset({vendor}),
            frozenset({technology}),
            "Vendor SUPPLIES Technology",
            cardinality=RelationshipCardinality("1..N"),
        ),
        RelationshipRule(
            "FUNDS",
            frozenset({cost_center}),
            frozenset({application}),
            "Cost Center FUNDS Application",
            cardinality=RelationshipCardinality("1..N"),
        ),
        RelationshipRule(
            "FUNDED_BY",
            frozenset({application}),
            frozenset({cost_center}),
            "Application FUNDED_BY Cost Center",
            cardinality=RelationshipCardinality("N..1", max_targets_per_source=1),
        ),
        RelationshipRule(
            "IMPACTS",
            frozenset({risk}),
            frozenset({application, technology, business_service}),
            "Risk IMPACTS Application, Technology, or Business Service",
            cardinality=RelationshipCardinality("1..N"),
            default_strength=RelationshipStrength.CRITICAL.value,
        ),
        RelationshipRule(
            "MITIGATES",
            frozenset({control}),
            frozenset({risk}),
            "Control MITIGATES Risk",
            cardinality=RelationshipCardinality("1..N"),
            default_strength=RelationshipStrength.HIGH.value,
        ),
        RelationshipRule(
            "MITIGATES",
            frozenset({recommendation}),
            frozenset({risk}),
            "Recommendation MITIGATES Risk",
            cardinality=RelationshipCardinality("1..N"),
        ),
        RelationshipRule(
            "REDUCES_COST",
            frozenset({recommendation}),
            frozenset({application, technology, business_service}),
            "Recommendation REDUCES_COST for operational entities",
            cardinality=RelationshipCardinality("1..N"),
        ),
    ]
