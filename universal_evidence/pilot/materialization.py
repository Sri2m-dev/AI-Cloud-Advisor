"""ACT-006 governed projection into the existing canonical enterprise model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityType,
    RelationshipType,
)
from data_fabric.foundation import TenantContext
from data_fabric.identity import MatchCandidate
from enterprise_registry.canonical import canonical_enterprise_id
from universal_evidence.activation import ActivationStage, RoutingReason
from universal_evidence.governance import MappingDecisionState
from universal_evidence.normalization.fingerprints import fingerprint


class MaterializationState(str, Enum):
    OBSERVED = "OBSERVED"
    PROPOSED = "PROPOSED"
    MATCHED = "MATCHED"
    MATERIALIZED = "MATERIALIZED"
    BLOCKED = "BLOCKED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICT = "CONFLICT"
    STALE = "STALE"


class MaterializationAction(str, Enum):
    CREATE = "CREATE"
    MATCH = "MATCH"
    ENRICH = "ENRICH"
    CONFLICT = "CONFLICT"
    NO_CHANGE = "NO_CHANGE"
    BLOCK = "BLOCK"


SUPPORTED_CONCEPTS = {
    "technology.service": EntityType.TECHNOLOGY,
    "technology.provider": EntityType.TECHNOLOGY,
    "cloud.resource": EntityType.CLOUD_RESOURCE,
    "cloud.resource_id": EntityType.CLOUD_RESOURCE,
    "cloud.region": EntityType.TECHNOLOGY,
    "application.name": EntityType.APPLICATION,
    "business_service.name": EntityType.BUSINESS_SERVICE,
    "owner.name": EntityType.OWNER,
    "cost_center.name": EntityType.COST_CENTER,
    "saas.product": EntityType.SAAS_PRODUCT,
    "contract.id": EntityType.CONTRACT,
    "license.id": EntityType.LICENSE,
}


@dataclass(frozen=True, slots=True)
class MaterializationObservation:
    """Small adapter contract for normalized Universal Evidence fields."""

    semantic_concept_id: str
    normalized_value: Any
    mapping_decision_id: str
    mapping_decision_state: MappingDecisionState | str
    normalization_fingerprint: str
    source_id: str
    file_id: str
    sheet_id: str
    row_number: int
    analysis_id: str
    prospect_id: str
    organization_id: str
    tenant_id: str
    source_identifier: str | None = None
    source_system: str = "universal_evidence"
    evidence_reference: str | None = None
    stale: bool = False

    @property
    def row_reference(self) -> str:
        return f"{self.source_id}:{self.file_id}:{self.sheet_id}:row:{self.row_number}"


@dataclass(frozen=True, slots=True)
class EntityProposal:
    proposal_id: str
    proposal_fingerprint: str
    scope: tuple[str, str, str, str, str, str]
    entity_type: EntityType | None
    semantic_concept_id: str
    normalized_source_value: str
    source_observations: tuple[str, ...]
    mapping_decision_ids: tuple[str, ...]
    normalization_references: tuple[str, ...]
    identity_resolution_method: str | None
    matched_canonical_id: str | None
    state: MaterializationState
    action: MaterializationAction
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RelationshipProposal:
    proposal_id: str
    proposal_fingerprint: str
    source_canonical_id: str | None
    relationship_type: RelationshipType
    target_canonical_id: str | None
    evidence_references: tuple[str, ...]
    mapping_decision_ids: tuple[str, ...]
    scope: tuple[str, str, str, str, str, str]
    state: MaterializationState
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class MaterializationReport:
    entity_proposals: tuple[EntityProposal, ...]
    relationship_proposals: tuple[RelationshipProposal, ...]
    entities: tuple[EnterpriseEntity, ...]
    relationships: tuple[EnterpriseRelationship, ...]
    counts: dict[str, int]


class GovernedEntityMaterializationService:
    """Process-local ACT-006 adapter; canonical registries remain authoritative."""

    def __init__(self, registry, relationships, *, activation_resolver=None, audit_sink=None):
        self.registry = registry
        self.relationships = relationships
        self.activation_resolver = activation_resolver
        self.audit_sink = audit_sink

    def materialize(
        self,
        observations: Iterable[MaterializationObservation],
        *,
        context: TenantContext,
        actor_id: str = "act-006",
        allow_materialization: bool = True,
        activation=None,
    ) -> MaterializationReport:
        rows = tuple(observations)
        self._validate_scope(rows, context)
        if activation is None and self.activation_resolver is not None and rows:
            from universal_evidence.activation import ActivationScope, ScopeLevel

            first = rows[0]
            activation = self.activation_resolver.resolve(
                ActivationScope(
                    ScopeLevel.ANALYSIS,
                    organization_id=first.organization_id,
                    tenant_id=first.tenant_id,
                    prospect_id=first.prospect_id,
                    analysis_id=first.analysis_id,
                )
            )
        blocked_reason = self._blocked_reason(activation)
        grouped: dict[tuple[str, str], list[MaterializationObservation]] = {}
        for row in rows:
            grouped.setdefault(
                (row.semantic_concept_id, self._value(row.normalized_value)), []
            ).append(row)

        proposals = []
        entities = []
        for (concept, value), group in sorted(grouped.items()):
            proposal = self._propose_entity(group, context, blocked_reason, allow_materialization)
            proposals.append(proposal)
            if proposal.state in {
                MaterializationState.BLOCKED,
                MaterializationState.STALE,
                MaterializationState.UNSUPPORTED,
                MaterializationState.AMBIGUOUS,
                MaterializationState.CONFLICT,
            }:
                continue
            entity = self._entity_for(proposal, group, context)
            if entity is None:
                continue
            if (
                proposal.action is MaterializationAction.CREATE
                and allow_materialization
                and not blocked_reason
            ):
                entity = self.registry.register_entity(entity)
                self._audit("ACT006_ENTITY_MATERIALIZED", actor_id, group[0], proposal)
            elif proposal.action is MaterializationAction.MATCH:
                entity = self.registry.get_entity(proposal.matched_canonical_id)
            entities.append(entity)

        relationship_proposals = []
        relationship_rows = []
        relationship_specs = self._relationship_specs(rows, entities)
        for source, relation, target, group in relationship_specs:
            proposal = self._propose_relationship(
                source, relation, target, group, context, blocked_reason, allow_materialization
            )
            relationship_proposals.append(proposal)
            if proposal.state not in {
                MaterializationState.PROPOSED,
                MaterializationState.MATCHED,
                MaterializationState.MATERIALIZED,
            }:
                continue
            edge_id = str(uuid5(NAMESPACE_URL, "nexora://" + proposal.proposal_fingerprint))
            existing = self._existing_relationship(proposal)
            if existing is None and allow_materialization and not blocked_reason:
                edge = EnterpriseRelationship(
                    id=edge_id,
                    relationship_type=relation,
                    source_entity_id=source.id,
                    target_entity_id=target.id,
                    organization_id=context.organization_id,
                    tenant_id=context.tenant_id,
                    source_system="universal_evidence",
                    source_identifier=proposal.proposal_id,
                    evidence=proposal.evidence_references,
                    metadata={
                        "proposal_fingerprint": proposal.proposal_fingerprint,
                        "scope": proposal.scope,
                    },
                )
                edge = self.relationships.register_relationship(edge)
                self._audit("ACT006_RELATIONSHIP_MATERIALIZED", actor_id, group[0], proposal)
            else:
                edge = existing
            if edge is not None:
                relationship_rows.append(edge)

        counts = {state.value.lower(): 0 for state in MaterializationState}
        for item in (*proposals, *relationship_proposals):
            counts[item.state.value.lower()] += 1
        return MaterializationReport(
            tuple(proposals),
            tuple(relationship_proposals),
            tuple(entities),
            tuple(relationship_rows),
            counts,
        )

    def _propose_entity(self, group, context, blocked_reason, allow_materialization):
        first = group[0]
        entity_type = SUPPORTED_CONCEPTS.get(first.semantic_concept_id)
        value = self._value(first.normalized_value)
        scope = self._scope(first)
        base = (
            first.semantic_concept_id,
            value,
            scope,
            tuple(row.normalization_fingerprint for row in group),
            tuple(row.mapping_decision_id for row in group),
        )
        proposal_id = "act006-entity-" + fingerprint(base)[:24]
        proposal_fp = fingerprint(base, entity_type.value if entity_type else None)
        common = dict(
            proposal_id=proposal_id,
            proposal_fingerprint=proposal_fp,
            scope=scope,
            entity_type=entity_type,
            semantic_concept_id=first.semantic_concept_id,
            normalized_source_value=value,
            source_observations=tuple(row.row_reference for row in group),
            mapping_decision_ids=tuple(sorted({row.mapping_decision_id for row in group})),
            normalization_references=tuple(
                sorted({row.normalization_fingerprint for row in group})
            ),
            identity_resolution_method=None,
            matched_canonical_id=None,
        )
        if not value:
            return EntityProposal(
                **common,
                state=MaterializationState.BLOCKED,
                action=MaterializationAction.BLOCK,
                reason="empty normalized identity",
            )
        if entity_type is None:
            return EntityProposal(
                **common,
                state=MaterializationState.UNSUPPORTED,
                action=MaterializationAction.BLOCK,
                reason="ontology concept has no supported canonical entity type",
            )
        if blocked_reason or not allow_materialization:
            return EntityProposal(
                **common,
                state=MaterializationState.BLOCKED,
                action=MaterializationAction.BLOCK,
                reason=blocked_reason or "materialization disabled",
            )
        if any(row.stale for row in group) or any(
            self._mapping_state(row)
            not in {
                MappingDecisionState.CONFIRMED,
                MappingDecisionState.OVERRIDDEN,
                MappingDecisionState.AUTO_ACCEPTED,
            }
            for row in group
        ):
            state = (
                MaterializationState.STALE
                if any(row.stale for row in group)
                else MaterializationState.BLOCKED
            )
            return EntityProposal(
                **common,
                state=state,
                action=MaterializationAction.BLOCK,
                reason="current governed mapping and normalization are required",
            )
        source_system = first.source_system
        source_identifier = first.source_identifier or value
        candidate = MatchCandidate(
            source_system,
            source_identifier,
            value,
            context.organization_id,
            tenant_id=context.tenant_id,
        )
        matches = [
            entity
            for entity in self.registry.list_entities()
            if entity.entity_type is entity_type
            and entity.organization_id == context.organization_id
            and entity.tenant_id == context.tenant_id
            and (
                entity.canonical_id == candidate.canonical_id
                or (
                    entity.source_system == source_system
                    and entity.source_identifier == source_identifier
                )
                or self._norm(entity.name) == self._norm(value)
            )
        ]
        if len(matches) > 1:
            return EntityProposal(
                **common,
                state=MaterializationState.AMBIGUOUS,
                action=MaterializationAction.BLOCK,
                reason="multiple same-type canonical identities match",
            )
        if matches:
            method = (
                "source_identity"
                if matches[0].source_system == source_system
                and matches[0].source_identifier == source_identifier
                else "exact_governed_natural_key"
            )
            return EntityProposal(
                **{
                    **common,
                    "identity_resolution_method": method,
                    "matched_canonical_id": matches[0].canonical_id,
                },
                state=MaterializationState.MATCHED,
                action=MaterializationAction.MATCH,
            )
        return EntityProposal(
            **common, state=MaterializationState.PROPOSED, action=MaterializationAction.CREATE
        )

    def _entity_for(self, proposal, group, context):
        if proposal.action is MaterializationAction.MATCH:
            return self.registry.get_entity(proposal.matched_canonical_id)
        first = group[0]
        canonical_id = canonical_enterprise_id(
            context,
            proposal.entity_type,
            first.source_system,
            first.source_identifier or proposal.normalized_source_value,
        )
        return EnterpriseEntity(
            id=canonical_id,
            canonical_id=canonical_id,
            entity_type=proposal.entity_type,
            name=proposal.normalized_source_value,
            source_system=first.source_system,
            source_identifier=first.source_identifier or proposal.normalized_source_value,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            metadata={
                "act006": {
                    "proposal_fingerprint": proposal.proposal_fingerprint,
                    "provenance": list(proposal.source_observations),
                    "prospect_id": first.prospect_id,
                    "analysis_id": first.analysis_id,
                }
            },
            provenance_reference=proposal.proposal_fingerprint,
            lineage_reference=proposal.source_observations[0],
        )

    def _relationship_specs(self, rows, entities):
        grouped = {}
        for row in rows:
            grouped.setdefault(
                (row.semantic_concept_id, self._value(row.normalized_value)), []
            ).append(row)
        entity_by_value = {
            (entity.entity_type, self._norm(entity.name)): entity for entity in entities
        }
        specs = []
        pairs = (
            ("application.name", "business_service.name", RelationshipType.SUPPORTS),
            ("application.name", "owner.name", RelationshipType.OWNED_BY),
            ("application.name", "cost_center.name", RelationshipType.FUNDED_BY),
            (
                "cloud.resource_id",
                "technology.provider",
                RelationshipType.PROVIDED_BY
                if hasattr(RelationshipType, "PROVIDED_BY")
                else RelationshipType.SUPPLIED_BY,
            ),
        )
        for left, right, relation in pairs:
            for (concept, value), group in grouped.items():
                if concept != left:
                    continue
                target = next(
                    (
                        entity
                        for (other_concept, other_value), _ in grouped.items()
                        if other_concept == right
                        for entity in [
                            entity_by_value.get(
                                (SUPPORTED_CONCEPTS.get(right), self._norm(other_value))
                            )
                        ]
                        if entity
                    ),
                    None,
                )
                source = entity_by_value.get((SUPPORTED_CONCEPTS.get(left), self._norm(value)))
                if source and target:
                    specs.append((source, relation, target, tuple(group)))
        return specs

    def _propose_relationship(
        self, source, relation, target, group, context, blocked_reason, allow
    ):
        first = group[0]
        scope = self._scope(first)
        refs = tuple(row.evidence_reference or row.row_reference for row in group)
        fp = fingerprint(
            scope,
            source.canonical_id,
            relation.value,
            target.canonical_id,
            refs,
            tuple(row.mapping_decision_id for row in group),
        )
        common = dict(
            proposal_id="act006-rel-" + fp[:24],
            proposal_fingerprint=fp,
            source_canonical_id=source.canonical_id,
            relationship_type=relation,
            target_canonical_id=target.canonical_id,
            evidence_references=refs,
            mapping_decision_ids=tuple(sorted({row.mapping_decision_id for row in group})),
            scope=scope,
        )
        if blocked_reason or not allow:
            return RelationshipProposal(
                **common,
                state=MaterializationState.BLOCKED,
                reason=blocked_reason or "materialization disabled",
            )
        if any(row.stale for row in group) or any(
            self._mapping_state(row)
            not in {
                MappingDecisionState.CONFIRMED,
                MappingDecisionState.OVERRIDDEN,
                MappingDecisionState.AUTO_ACCEPTED,
            }
            for row in group
        ):
            return RelationshipProposal(
                **common,
                state=MaterializationState.STALE
                if any(row.stale for row in group)
                else MaterializationState.BLOCKED,
                reason="governed endpoints and relationship evidence are required",
            )
        competing = [
            row
            for row in self.relationships.search_relationships(
                organization_id=context.organization_id,
                include_inactive=False,
            )
            if row.tenant_id == context.tenant_id
            and row.source_entity_id == source.id
            and row.relationship_type is relation
            and row.target_entity_id != target.id
        ]
        if competing and relation is RelationshipType.OWNED_BY:
            return RelationshipProposal(
                **common,
                state=MaterializationState.CONFLICT,
                reason="existing governed ownership has precedence",
            )
        return RelationshipProposal(**common, state=MaterializationState.PROPOSED)

    def _existing_relationship(self, proposal):
        for row in self.relationships.search_relationships(
            organization_id=proposal.scope[1], include_inactive=False
        ):
            if (
                row.tenant_id == proposal.scope[0]
                and row.source_entity_id == proposal.source_canonical_id
                and row.target_entity_id == proposal.target_canonical_id
                and row.relationship_type is proposal.relationship_type
            ):
                return row
        return None

    def _blocked_reason(self, activation):
        if activation is None:
            return None
        if activation.stage is ActivationStage.SHADOW_ONLY:
            return "ACT-C1 shadow mode blocks materialization"
        if RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes:
            return "ACT-C1 kill switch blocks materialization"
        if activation.stage < ActivationStage.CAPABILITY_VISIBLE:
            return "ACT-C1 activation does not authorize materialization"
        return None

    @staticmethod
    def _mapping_state(row):
        return MappingDecisionState(row.mapping_decision_state)

    @staticmethod
    def _value(value):
        return str(value or "").strip()

    @staticmethod
    def _norm(value):
        return " ".join(str(value or "").casefold().split())

    @staticmethod
    def _scope(row):
        return (
            row.tenant_id,
            row.organization_id,
            row.prospect_id,
            row.analysis_id,
            row.source_id,
            row.file_id,
        )

    @staticmethod
    def _validate_scope(rows, context):
        for row in rows:
            if row.organization_id != context.organization_id or row.tenant_id != context.tenant_id:
                raise ValueError("ACT-006 observation crosses organization or tenant boundary")

    def _audit(self, event_type, actor_id, observation, subject):
        if self.audit_sink is not None:
            self.audit_sink.record(
                event_type=event_type,
                actor_id=actor_id,
                timestamp=datetime.now(timezone.utc),
                reason="ACT-006 governed materialization",
                scope_key=observation.row_reference,
                activation_id=None,
            )
