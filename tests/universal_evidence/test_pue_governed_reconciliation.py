from __future__ import annotations

from dataclasses import dataclass

from data_fabric.contracts import EntityType
from data_fabric.foundation import TenantContext
from data_fabric.identity import InMemoryIdentityResolver
from data_fabric.registry import InMemoryEntityRegistry, InMemoryRelationshipRegistry
from enterprise_registry.canonical import enterprise_entity_from_source
from enterprise_registry.canonical_service import EnterpriseRegistryService
from enterprise_registry.knowledge_graph import EnterpriseKnowledgeGraphService
from enterprise_registry.relationship_intelligence import RelationshipIntelligenceService
from universal_evidence.activation import RoutingReason
from universal_evidence.pilot.reconciliation import (
    GovernedIdentityReconciliationService,
    ReconciliationState,
    SourceIdentityObservation,
)

ORG = "org-act007"
TENANT = "tenant-act007"


@dataclass
class Activation:
    stage: int = 2
    reason_codes: tuple = ()


def _service(context=TenantContext(ORG, TENANT)):
    relationships = InMemoryRelationshipRegistry()
    registry = EnterpriseRegistryService(
        context,
        role="operations",
        entities=InMemoryEntityRegistry(),
        identities=InMemoryIdentityResolver(),
        relationships=relationships,
    )
    return registry, relationships


def _entity(registry, context, entity_type, name, source_system, source_id, *, prospect_id=None):
    entity = enterprise_entity_from_source(
        context=context,
        entity_type=entity_type,
        source_system=source_system,
        source_entity_id=source_id,
        canonical_name=name,
    )
    if prospect_id:
        entity.metadata["act006"] = {"prospect_id": prospect_id}
    return registry.register_entity(entity)


def _observation(
    source_system,
    source_identifier,
    entity_type=EntityType.APPLICATION,
    *,
    name="Checkout",
    attributes=None,
    source_id=None,
    file_id=None,
    prospect_id="prospect-1",
    analysis_id="analysis-1",
    evidence=None,
    stale=False,
):
    return SourceIdentityObservation(
        source_system=source_system,
        source_type=source_system,
        source_identifier=source_identifier,
        entity_type=entity_type,
        normalized_attributes=attributes or {"name": name},
        organization_id=ORG,
        tenant_id=TENANT,
        prospect_id=prospect_id,
        analysis_id=analysis_id,
        source_id=source_id or source_system,
        file_id=file_id or f"{source_system}.csv",
        evidence_fingerprint=evidence or f"evidence-{source_system}-{source_identifier}",
        mapping_decision_ids=(f"mapping-{source_system}",),
        normalization_references=(f"normalization-{source_system}",),
        stale=stale,
    )


def test_three_sources_converge_to_existing_canonical_entities_and_replay_idempotently():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    resource = _entity(
        registry,
        context,
        EntityType.CLOUD_RESOURCE,
        "i-test123",
        "aws",
        "i-test123",
        prospect_id="prospect-1",
    )
    application = _entity(
        registry,
        context,
        EntityType.APPLICATION,
        "Checkout",
        "application_catalogue",
        "APP-001",
        prospect_id="prospect-1",
    )
    service = GovernedIdentityReconciliationService(registry)
    rows = (
        _observation(
            "aws", "i-test123", EntityType.CLOUD_RESOURCE, attributes={"resource_id": "i-test123"}
        ),
        _observation(
            "cmdb", "CI-10001", EntityType.CLOUD_RESOURCE, attributes={"resource_id": "i-test123"}
        ),
        _observation(
            "application_catalogue",
            "APP-001",
            attributes={"application_id": "APP-001", "name": "Checkout"},
        ),
        _observation(
            "cmdb", "CI-10001-app", attributes={"application_id": "APP-001", "name": "Checkout"}
        ),
    )
    first = service.reconcile(rows, context=context, activation=Activation())
    second = service.reconcile(rows, context=context, activation=Activation())

    assert {item.state for item in first.proposals} == {ReconciliationState.EXACT_MATCH}
    assert {item.candidate_canonical_id for item in first.proposals} == {
        resource.canonical_id,
        application.canonical_id,
    }
    assert len(first.bindings) == 4
    assert second.counts["bindings_created"] == 0
    assert second.counts["bindings_reused"] == 4
    assert len(registry.list_entities()) == 2
    assert all(item.evidence_references for item in first.bindings)

    graph = EnterpriseKnowledgeGraphService(
        registry,
        RelationshipIntelligenceService(
            context,
            role="auditor",
            entities=registry.list_entities(),
            relationships=(),
        ),
    )
    assert len(graph.search_graph("i-test123")) == 1
    assert first.bindings[0].evidence_references


def test_same_name_without_authority_is_possible_then_requires_human_confirmation():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    canonical = _entity(
        registry,
        context,
        EntityType.APPLICATION,
        "Payments",
        "application_catalogue",
        "APP-PAYMENTS",
    )
    service = GovernedIdentityReconciliationService(registry)
    rows = (
        _observation("source-a", "row-a", name="Payments"),
        _observation("source-b", "row-b", name="Payments"),
    )
    possible = service.reconcile(rows, context=context, activation=Activation())
    proposal = possible.proposals[0]
    assert proposal.state is ReconciliationState.POSSIBLE_MATCH
    decision = service.confirm_match(
        proposal,
        canonical_id=canonical.canonical_id,
        actor_id="owner-1",
        reason="Reviewed source records",
    )
    confirmed = service.reconcile(rows, context=context, activation=Activation())
    assert decision.decision_fingerprint
    assert confirmed.proposals[0].state is ReconciliationState.CONFIRMED_MATCH
    assert len(confirmed.bindings) == 2


def test_rejected_match_and_cross_entity_type_names_do_not_merge():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    payments = _entity(
        registry, context, EntityType.APPLICATION, "Payments", "catalogue", "app-payments"
    )
    service_entity = _entity(
        registry, context, EntityType.BUSINESS_SERVICE, "Payments", "catalogue", "service-payments"
    )
    reconciler = GovernedIdentityReconciliationService(registry)
    rows = (
        _observation("source-a", "a", name="Payments"),
        _observation("source-b", "b", name="Payments"),
    )
    proposal = reconciler.reconcile(rows, context=context, activation=Activation()).proposals[0]
    reconciler.reject_match(proposal, actor_id="owner-1", reason="No certified cross-reference")
    rejected = reconciler.reconcile(rows, context=context, activation=Activation())
    assert rejected.proposals[0].state is ReconciliationState.REJECTED
    assert not rejected.bindings
    assert payments.canonical_id != service_entity.canonical_id


def test_conflicting_descriptions_surface_without_overwriting_authoritative_identity():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    canonical = _entity(
        registry,
        context,
        EntityType.APPLICATION,
        "Checkout",
        "catalogue",
        "APP-001",
        prospect_id="prospect-1",
    )
    reconciler = GovernedIdentityReconciliationService(registry)
    rows = (
        _observation(
            "catalogue", "APP-001", attributes={"application_id": "APP-001", "owner": "Alice"}
        ),
        _observation(
            "finance", "finance-1", attributes={"application_id": "APP-001", "owner": "Bob"}
        ),
    )
    report = reconciler.reconcile(rows, context=context, activation=Activation())
    assert report.proposals[0].candidate_canonical_id == canonical.canonical_id
    assert report.proposals[0].state is ReconciliationState.CONFLICT
    assert report.proposals[0].conflicts == ("owner",)
    assert not report.bindings


def test_stale_evidence_and_stale_decision_cannot_bind():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    canonical = _entity(
        registry,
        context,
        EntityType.APPLICATION,
        "Payments",
        "catalogue",
        "APP-PAYMENTS",
        prospect_id="prospect-1",
    )
    reconciler = GovernedIdentityReconciliationService(registry)
    rows = (
        _observation("source-a", "a", name="Payments"),
        _observation("source-b", "b", name="Payments"),
    )
    proposal = reconciler.reconcile(rows, context=context, activation=Activation()).proposals[0]
    decision = reconciler.confirm_match(
        proposal, canonical_id=canonical.canonical_id, actor_id="owner", reason="Reviewed"
    )
    changed = (
        _observation("source-a", "a", name="Payments", evidence="changed"),
        _observation("source-b", "b", name="Payments"),
    )
    changed_proposal = reconciler.reconcile(
        changed, context=context, activation=Activation()
    ).proposals[0]
    current = reconciler.reconcile(
        changed,
        context=context,
        activation=Activation(),
        decision_overrides={changed_proposal.proposal_fingerprint: decision},
    )
    stale = reconciler.reconcile(
        (_observation("source-a", "a", name="Payments", stale=True),),
        context=context,
        activation=Activation(),
    )
    assert current.proposals[0].state is ReconciliationState.STALE
    assert stale.proposals[0].state is ReconciliationState.STALE


def test_shadow_kill_switch_and_prospect_boundaries_block_binding():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    _entity(registry, context, EntityType.APPLICATION, "Checkout", "catalogue", "APP-001")
    reconciler = GovernedIdentityReconciliationService(registry)
    row = _observation("catalogue", "APP-001")
    shadow = reconciler.reconcile((row,), context=context, activation=Activation(stage=0))
    killed = reconciler.reconcile(
        (row,),
        context=context,
        activation=Activation(reason_codes=(RoutingReason.KILL_SWITCH_ACTIVE,)),
    )
    assert shadow.proposals[0].state is ReconciliationState.BLOCKED
    assert killed.proposals[0].state is ReconciliationState.BLOCKED
    production_like = _observation("catalogue", "APP-001", prospect_id="prospect-other")
    isolated = reconciler.reconcile((production_like,), context=context, activation=Activation())
    assert isolated.proposals[0].state is ReconciliationState.UNRESOLVED
