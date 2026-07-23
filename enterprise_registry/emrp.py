"""Tenant-bound orchestration over existing Enterprise Data Fabric contracts."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityType,
    RelationshipType,
)
from data_fabric.foundation import TenantContext
from data_fabric.identity import (
    IdentityResolver,
    MatchCandidate,
    MatchDecision,
    MatchResult,
)
from data_fabric.quality import DataQualityEvaluator, QualityAssessment
from data_fabric.registry import (
    EntityNotFoundError,
    EntityRegistry,
    RelationshipRegistry,
)
from data_fabric.semantic import OntologyRegistry, TaxonomyNode, TaxonomyService
from enterprise_registry.exceptions import EMRPRelationshipError, EMRPTaxonomyError


@dataclass(frozen=True, slots=True)
class RelationshipTopologyRule:
    """Explicit deterministic constraints for one canonical relationship type."""

    relationship_type: RelationshipType
    source_types: frozenset[EntityType]
    target_types: frozenset[EntityType]
    max_targets_per_source: int | None = None
    allow_cycles: bool = False
    allow_self_reference: bool = False

    def __post_init__(self) -> None:
        if self.max_targets_per_source is not None and self.max_targets_per_source < 1:
            raise ValueError("max_targets_per_source must be positive")


@dataclass(frozen=True, slots=True)
class TaxonomyValidation:
    """Deterministic evidence for one taxonomy assignment."""

    valid: bool
    taxonomy_id: str
    node_id: str
    concept_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class AcceptanceThresholds:
    """Explicit non-probabilistic WP-006 acceptance thresholds."""

    identity_confidence: float = 0.80
    metadata_completeness: float = 100.0
    ownership_completeness: float = 100.0
    relationship_completeness: float = 100.0
    relationship_validity: float = 100.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.identity_confidence <= 1.0:
            raise ValueError("identity_confidence must be between 0 and 1")
        for field_name in (
            "metadata_completeness",
            "ownership_completeness",
            "relationship_completeness",
            "relationship_validity",
        ):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{field_name} must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    """One named deterministic acceptance decision."""

    name: str
    passed: bool
    actual: float | bool
    required: float | bool


@dataclass(frozen=True, slots=True)
class EMRPAcceptanceReport:
    """Combined quality/trust and semantic acceptance evidence."""

    checks: Mapping[str, AcceptanceCheck]

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", MappingProxyType(dict(self.checks)))

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks.values())

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(
            name for name, check in self.checks.items() if not check.passed
        )


class EnterpriseMetadataRegistry(Protocol):
    """Bounded orchestration interface; injected contracts retain authority."""

    context: TenantContext

    def reconcile_identity(self, candidate: MatchCandidate) -> MatchResult: ...

    def validate_taxonomy_assignment(
        self,
        entity: EnterpriseEntity,
        node: TaxonomyNode,
        *,
        taxonomy_id: str,
        approved_concept_types: frozenset[str],
        business_domain: str | None = None,
    ) -> TaxonomyValidation: ...

    def validate_relationship(
        self,
        relationship: EnterpriseRelationship,
        *,
        rule: RelationshipTopologyRule,
    ) -> tuple[EnterpriseEntity, EnterpriseEntity]: ...


class EnterpriseMetadataRegistryService:
    """Coordinate existing P3 interfaces without owning persistence or authority."""

    def __init__(
        self,
        context: TenantContext,
        *,
        entities: EntityRegistry,
        identities: IdentityResolver,
        relationships: RelationshipRegistry,
        taxonomy: TaxonomyService,
        ontology: OntologyRegistry,
        quality: DataQualityEvaluator,
    ) -> None:
        self.context = context
        self.entities = entities
        self.identities = identities
        self.relationships = relationships
        self.taxonomy = taxonomy
        self.ontology = ontology
        self.quality = quality

    def register_entity(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        """Register through existing entity and identity contracts."""

        self.context.assert_record_matches(entity, "entity")
        registered = self.entities.register_entity(entity)
        self.identities.register_entity(registered)
        return registered

    def reconcile_identity(self, candidate: MatchCandidate) -> MatchResult:
        """Resolve canonical, source, alias, duplicate, and no-match identities."""

        self.context.assert_record_matches(candidate, "identity candidate")
        result = self.identities.detect_duplicates(candidate)
        for entity in result.matched_entities:
            self.context.assert_record_matches(entity, "identity match")
        if result.matched_entity is not None:
            self.context.assert_record_matches(result.matched_entity, "identity match")
        return result

    def validate_taxonomy_assignment(
        self,
        entity: EnterpriseEntity,
        node: TaxonomyNode,
        *,
        taxonomy_id: str,
        approved_concept_types: frozenset[str],
        business_domain: str | None = None,
    ) -> TaxonomyValidation:
        """Validate membership and ontology compatibility in this tenant."""

        self.context.assert_record_matches(entity, "taxonomy entity")
        self.context.assert_record_matches(node, "taxonomy node")
        stored = self.taxonomy.get_node(
            node.node_id,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
        )
        if stored is None or stored != node or node.taxonomy_id != taxonomy_id:
            raise EMRPTaxonomyError("taxonomy node is not an approved membership")
        concept = self.ontology.get_concept(
            node.concept_id,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
        )
        if concept is None or not concept.active:
            raise EMRPTaxonomyError("taxonomy concept is missing or inactive")
        if concept.concept_type not in approved_concept_types:
            raise EMRPTaxonomyError("taxonomy concept type is not approved")
        if business_domain is not None:
            compatible_domains = {
                str(value) for value in concept.attributes.get("business_domains", ())
            }
            direct_match = business_domain in {
                concept.concept_id,
                concept.canonical_name,
            }
            if not direct_match and business_domain not in compatible_domains:
                raise EMRPTaxonomyError(
                    "taxonomy concept is incompatible with the business domain"
                )
        return TaxonomyValidation(
            valid=True,
            taxonomy_id=taxonomy_id,
            node_id=node.node_id,
            concept_id=node.concept_id,
            reason="approved_membership",
        )

    def validate_relationship(
        self,
        relationship: EnterpriseRelationship,
        *,
        rule: RelationshipTopologyRule,
    ) -> tuple[EnterpriseEntity, EnterpriseEntity]:
        """Validate endpoints, direction, cardinality, duplicates, and cycles."""

        self.context.assert_record_matches(relationship, "relationship")
        if relationship.relationship_type != rule.relationship_type:
            raise EMRPRelationshipError("relationship type has no matching topology rule")
        source = self._resolve_entity(relationship.source_entity_id)
        target = self._resolve_entity(relationship.target_entity_id)
        if source.entity_type not in rule.source_types:
            raise EMRPRelationshipError("relationship source type is invalid")
        if target.entity_type not in rule.target_types:
            raise EMRPRelationshipError("relationship direction or target type is invalid")
        if (
            source.canonical_id == target.canonical_id
            and not rule.allow_self_reference
        ):
            raise EMRPRelationshipError("self-referential relationship is prohibited")

        source_key = source.canonical_id
        target_key = target.canonical_id
        existing = [
            (
                item,
                self._resolve_entity(item.source_entity_id).canonical_id,
                self._resolve_entity(item.target_entity_id).canonical_id,
            )
            for item in self._scoped_relationships(rule.relationship_type)
        ]
        if any(
            existing_source == source_key and existing_target == target_key
            for _, existing_source, existing_target in existing
        ):
            raise EMRPRelationshipError("duplicate relationship is prohibited")
        outgoing = [
            item
            for item, existing_source, _ in existing
            if existing_source == source_key
        ]
        if (
            rule.max_targets_per_source is not None
            and len(outgoing) >= rule.max_targets_per_source
        ):
            raise EMRPRelationshipError("relationship cardinality is exceeded")
        if not rule.allow_cycles and self._would_create_cycle(
            source_key,
            target_key,
            [
                (existing_source, existing_target)
                for _, existing_source, existing_target in existing
            ],
        ):
            raise EMRPRelationshipError("circular relationship is prohibited")
        return source, target

    def register_relationship(
        self,
        relationship: EnterpriseRelationship,
        *,
        rule: RelationshipTopologyRule,
    ) -> EnterpriseRelationship:
        self.validate_relationship(relationship, rule=rule)
        return self.relationships.register_relationship(relationship)

    def evaluate_acceptance(
        self,
        *,
        identity: MatchResult,
        entity: EnterpriseEntity,
        relationship: EnterpriseRelationship,
        relationship_rule: RelationshipTopologyRule,
        taxonomy: TaxonomyValidation,
        thresholds: AcceptanceThresholds = AcceptanceThresholds(),
    ) -> EMRPAcceptanceReport:
        """Produce explicit pass/fail evidence from existing quality contracts."""

        self.context.assert_record_matches(identity.candidate, "identity candidate")
        for matched in identity.matched_entities:
            self.context.assert_record_matches(matched, "identity match")
        self.context.assert_record_matches(entity, "metadata entity")
        self.context.assert_record_matches(relationship, "metadata relationship")
        try:
            self.validate_relationship(relationship, rule=relationship_rule)
            topology_valid = True
        except EMRPRelationshipError:
            topology_valid = False
        entity_quality = self.quality.evaluate_entity(
            entity,
            uniqueness_confirmed=identity.decision is MatchDecision.MATCH,
        )
        relationship_quality = self.quality.evaluate_relationship(
            relationship,
            uniqueness_confirmed=True,
        )
        checks = {
            "identity_confidence": self._check(
                "identity_confidence",
                identity.confidence_score,
                thresholds.identity_confidence,
                identity.decision is MatchDecision.MATCH,
            ),
            "metadata_completeness": self._quality_check(
                "metadata_completeness",
                entity_quality,
                "completeness",
                thresholds.metadata_completeness,
            ),
            "ownership_completeness": self._quality_check(
                "ownership_completeness",
                entity_quality,
                "ownership_completeness",
                thresholds.ownership_completeness,
            ),
            "relationship_completeness": self._quality_check(
                "relationship_completeness",
                relationship_quality,
                "completeness",
                thresholds.relationship_completeness,
            ),
            "relationship_topology": AcceptanceCheck(
                name="relationship_topology",
                passed=topology_valid,
                actual=topology_valid,
                required=True,
            ),
            "relationship_validity": self._quality_check(
                "relationship_validity",
                relationship_quality,
                "validity",
                thresholds.relationship_validity,
            ),
            "taxonomy_validity": AcceptanceCheck(
                name="taxonomy_validity",
                passed=taxonomy.valid,
                actual=taxonomy.valid,
                required=True,
            ),
        }
        return EMRPAcceptanceReport(checks)

    def _resolve_entity(self, identifier: str) -> EnterpriseEntity:
        try:
            entity = self.entities.get_entity(identifier)
        except EntityNotFoundError:
            entity = self.entities.find_entity_by_canonical_id(identifier)
            if entity is None:
                raise EMRPRelationshipError(
                    f"relationship endpoint is not registered: {identifier}"
                ) from None
        self.context.assert_record_matches(entity, "relationship endpoint")
        return entity

    def _scoped_relationships(
        self,
        relationship_type: RelationshipType,
    ) -> list[EnterpriseRelationship]:
        candidates = self.relationships.search_relationships(
            relationship_type=relationship_type.value,
            organization_id=self.context.organization_id,
            include_inactive=False,
        )
        return [
            item
            for item in candidates
            if item.tenant_id == self.context.tenant_id
        ]

    @staticmethod
    def _would_create_cycle(
        source_id: str,
        target_id: str,
        relationships: list[tuple[str, str]],
    ) -> bool:
        adjacency: dict[str, set[str]] = {}
        for existing_source, existing_target in relationships:
            adjacency.setdefault(existing_source, set()).add(existing_target)
        stack = [target_id]
        visited: set[str] = set()
        while stack:
            current = stack.pop()
            if current == source_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(sorted(adjacency.get(current, ()), reverse=True))
        return False

    @staticmethod
    def _check(
        name: str,
        actual: float,
        required: float,
        prerequisite: bool = True,
    ) -> AcceptanceCheck:
        return AcceptanceCheck(
            name=name,
            passed=prerequisite and actual >= required,
            actual=actual,
            required=required,
        )

    @classmethod
    def _quality_check(
        cls,
        name: str,
        assessment: QualityAssessment,
        dimension: str,
        required: float,
    ) -> AcceptanceCheck:
        return cls._check(
            name,
            assessment.dimension_scores[dimension].score,
            required,
        )
