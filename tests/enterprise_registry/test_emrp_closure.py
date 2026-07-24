from __future__ import annotations

from dataclasses import replace

import pytest

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityIdentity,
    EntityOwnership,
    EntityType,
    RelationshipType,
)
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from data_fabric.identity import (
    InMemoryIdentityResolver,
    MatchCandidate,
    MatchDecision,
)
from data_fabric.quality import InMemoryDataQualityEvaluator
from data_fabric.registry import InMemoryEntityRegistry, InMemoryRelationshipRegistry
from data_fabric.semantic import (
    InMemoryOntologyRegistry,
    InMemoryTaxonomyService,
    SemanticConcept,
    TaxonomyNode,
)
from enterprise_registry import (
    AcceptanceThresholds,
    EMRPAcceptanceReport,
    EMRPRelationshipError,
    EMRPTaxonomyError,
    EnterpriseMetadataRegistry,
    EnterpriseMetadataRegistryService,
    RelationshipTopologyRule,
    TaxonomyValidation,
)


@pytest.fixture
def context() -> TenantContext:
    return TenantContext("org-1", "tenant-a")


@pytest.fixture
def emrp(context: TenantContext) -> EnterpriseMetadataRegistryService:
    return EnterpriseMetadataRegistryService(
        context,
        entities=InMemoryEntityRegistry(),
        identities=InMemoryIdentityResolver(),
        relationships=InMemoryRelationshipRegistry(),
        taxonomy=InMemoryTaxonomyService(),
        ontology=InMemoryOntologyRegistry(),
        quality=InMemoryDataQualityEvaluator(),
    )


def entity(
    context: TenantContext,
    entity_id: str,
    *,
    entity_type: EntityType = EntityType.APPLICATION,
    name: str | None = None,
    source_system: str = "catalog",
    source_identifier: str | None = None,
    aliases: tuple[str, ...] = (),
    owner: bool = True,
) -> EnterpriseEntity:
    canonical_id = f"{entity_type.value}:{entity_id}"
    source_id = source_identifier or entity_id
    return EnterpriseEntity(
        id=entity_id,
        canonical_id=canonical_id,
        entity_type=entity_type,
        name=name if name is not None else entity_id.replace("-", " ").title(),
        source_system=source_system,
        source_identifier=source_id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        identity=EntityIdentity(
            id=canonical_id,
            canonical_id=canonical_id,
            source_system=source_system,
            source_identifier=source_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            aliases=list(aliases),
        ),
        ownership=EntityOwnership(owner_id="owner-1") if owner else None,
    )


def candidate(
    context: TenantContext,
    *,
    canonical_id: str | None = None,
    source_identifier: str = "candidate",
    name: str = "Candidate",
    aliases: tuple[str, ...] = (),
) -> MatchCandidate:
    return MatchCandidate(
        source_system="catalog",
        source_identifier=source_identifier,
        name=name,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        canonical_id=canonical_id,
        aliases=aliases,
    )


def relationship(
    context: TenantContext,
    relationship_id: str,
    source_id: str,
    target_id: str,
    *,
    relationship_type: RelationshipType = RelationshipType.DEPENDS_ON,
) -> EnterpriseRelationship:
    return EnterpriseRelationship(
        id=relationship_id,
        relationship_type=relationship_type,
        source_entity_id=source_id,
        target_entity_id=target_id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        source_system="catalog",
        source_identifier=relationship_id,
    )


def application_dependency_rule(
    *,
    max_targets: int | None = None,
) -> RelationshipTopologyRule:
    return RelationshipTopologyRule(
        relationship_type=RelationshipType.DEPENDS_ON,
        source_types=frozenset({EntityType.APPLICATION}),
        target_types=frozenset({EntityType.APPLICATION}),
        max_targets_per_source=max_targets,
    )


def taxonomy_setup(
    emrp: EnterpriseMetadataRegistryService,
    context: TenantContext,
) -> tuple[EnterpriseEntity, TaxonomyNode]:
    application = entity(context, "payments-app")
    emrp.register_entity(application)
    emrp.ontology.register_concept(
        SemanticConcept(
            concept_id="payments-domain",
            canonical_name="Payments",
            display_name="Payments",
            description="Payments business domain",
            concept_type="capability",
            parent_concept_id=None,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            attributes={"business_domains": ("payments",)},
        )
    )
    emrp.taxonomy.create_taxonomy(
        "business-domains",
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
    )
    node = TaxonomyNode(
        node_id="payments-node",
        taxonomy_id="business-domains",
        concept_id="payments-domain",
        parent_node_id=None,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
    )
    emrp.taxonomy.add_node(node)
    return application, node


def test_emrp_implements_bounded_orchestration_interface(
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    interface: EnterpriseMetadataRegistry = emrp
    assert interface.context == emrp.context


@pytest.mark.parametrize(
    ("match_candidate", "reason", "confidence"),
    [
        (
            lambda ctx, item: candidate(ctx, canonical_id=item.canonical_id),
            "canonical_id",
            1.0,
        ),
        (
            lambda ctx, item: candidate(
                ctx,
                source_identifier=item.source_identifier,
            ),
            "source_identity",
            0.98,
        ),
        (
            lambda ctx, item: candidate(ctx, name="Payments API"),
            "candidate_name_entity_alias",
            0.82,
        ),
    ],
)
def test_identity_reconciliation_is_deterministic(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
    match_candidate,
    reason: str,
    confidence: float,
) -> None:
    registered = emrp.register_entity(
        entity(context, "payments", aliases=("Payments API",))
    )

    result = emrp.reconcile_identity(match_candidate(context, registered))

    assert result.decision is MatchDecision.MATCH
    assert result.matched_entity == registered
    assert result.match_reason == reason
    assert result.confidence_score == confidence


def test_identity_duplicate_candidates_and_no_match_are_explicit(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    emrp.register_entity(entity(context, "payments", aliases=("shared-alias",)))
    emrp.register_entity(entity(context, "billing", aliases=("shared-alias",)))

    duplicate = emrp.reconcile_identity(
        candidate(context, name="Unknown", aliases=("shared-alias",))
    )
    no_match = emrp.reconcile_identity(
        candidate(context, name="No Such Entity", source_identifier="missing")
    )

    assert duplicate.decision is MatchDecision.DUPLICATE
    assert [item.id for item in duplicate.matched_entities] == [
        "billing",
        "payments",
    ]
    assert duplicate.confidence_score == 0.8
    assert no_match.decision is MatchDecision.NO_MATCH
    assert no_match.confidence_score == 0.0


def test_identity_reconciliation_rejects_cross_tenant_candidates_and_matches(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    other_context = TenantContext("org-1", "tenant-b")
    with pytest.raises(DataFabricTenantBoundaryError):
        emrp.reconcile_identity(candidate(other_context))

    other = entity(
        other_context,
        "foreign",
        source_identifier="foreign-source",
    )
    emrp.identities.register_entity(other)
    with pytest.raises(DataFabricTenantBoundaryError):
        emrp.reconcile_identity(
            candidate(
                context,
                source_identifier="foreign-source",
                name=other.name,
            )
        )


def test_taxonomy_membership_type_and_domain_are_validated(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    application, node = taxonomy_setup(emrp, context)

    result = emrp.validate_taxonomy_assignment(
        application,
        node,
        taxonomy_id="business-domains",
        approved_concept_types=frozenset({"capability"}),
        business_domain="payments",
    )

    assert result.valid is True
    assert result.reason == "approved_membership"
    with pytest.raises(EMRPTaxonomyError):
        emrp.validate_taxonomy_assignment(
            application,
            node,
            taxonomy_id="business-domains",
            approved_concept_types=frozenset({"technology"}),
        )
    with pytest.raises(EMRPTaxonomyError):
        emrp.validate_taxonomy_assignment(
            application,
            node,
            taxonomy_id="business-domains",
            approved_concept_types=frozenset({"capability"}),
            business_domain="unapproved-domain",
        )


def test_taxonomy_rejects_unsupported_and_cross_tenant_nodes(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    application, node = taxonomy_setup(emrp, context)
    unsupported = replace(node, node_id="not-registered")
    with pytest.raises(EMRPTaxonomyError):
        emrp.validate_taxonomy_assignment(
            application,
            unsupported,
            taxonomy_id="business-domains",
            approved_concept_types=frozenset({"capability"}),
        )

    cross_tenant = replace(node, tenant_id="tenant-b")
    with pytest.raises(DataFabricTenantBoundaryError):
        emrp.validate_taxonomy_assignment(
            application,
            cross_tenant,
            taxonomy_id="business-domains",
            approved_concept_types=frozenset({"capability"}),
        )


def test_relationship_validation_rejects_broken_references_and_invalid_types(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    source = emrp.register_entity(entity(context, "source"))
    technology = emrp.register_entity(
        entity(context, "technology", entity_type=EntityType.TECHNOLOGY)
    )
    rule = application_dependency_rule()

    with pytest.raises(EMRPRelationshipError, match="not registered"):
        emrp.validate_relationship(
            relationship(context, "broken", source.id, "missing"),
            rule=rule,
        )
    with pytest.raises(EMRPRelationshipError, match="target type"):
        emrp.validate_relationship(
            relationship(context, "invalid-target", source.id, technology.id),
            rule=rule,
        )
    with pytest.raises(EMRPRelationshipError, match="source type"):
        emrp.validate_relationship(
            relationship(context, "invalid-source", technology.id, source.id),
            rule=rule,
        )


def test_relationship_direction_cardinality_duplicates_and_self_reference(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    first = emrp.register_entity(entity(context, "first"))
    second = emrp.register_entity(entity(context, "second"))
    third = emrp.register_entity(entity(context, "third"))
    rule = application_dependency_rule(max_targets=1)
    stored = emrp.register_relationship(
        relationship(context, "first-second", first.id, second.id),
        rule=rule,
    )
    assert stored.source_entity_id == first.id

    with pytest.raises(EMRPRelationshipError, match="duplicate"):
        emrp.validate_relationship(
            relationship(
                context,
                "duplicate",
                first.canonical_id,
                second.canonical_id,
            ),
            rule=rule,
        )
    with pytest.raises(EMRPRelationshipError, match="cardinality"):
        emrp.validate_relationship(
            relationship(context, "too-many", first.id, third.id),
            rule=rule,
        )
    with pytest.raises(EMRPRelationshipError, match="self-referential"):
        emrp.validate_relationship(
            relationship(context, "self", second.id, second.id),
            rule=rule,
        )


def test_relationship_cycle_detection_is_deterministic(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    first = emrp.register_entity(entity(context, "first"))
    second = emrp.register_entity(entity(context, "second"))
    third = emrp.register_entity(entity(context, "third"))
    rule = application_dependency_rule()
    emrp.register_relationship(
        relationship(context, "first-second", first.id, second.id),
        rule=rule,
    )
    emrp.register_relationship(
        relationship(context, "second-third", second.id, third.id),
        rule=rule,
    )

    with pytest.raises(EMRPRelationshipError, match="circular"):
        emrp.validate_relationship(
            relationship(context, "third-first", third.id, first.id),
            rule=rule,
        )


def test_relationship_validation_rejects_cross_tenant_endpoints(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    source = emrp.register_entity(entity(context, "source"))
    foreign = entity(TenantContext("org-1", "tenant-b"), "foreign")
    emrp.entities.register_entity(foreign)

    with pytest.raises(DataFabricTenantBoundaryError):
        emrp.validate_relationship(
            relationship(context, "cross-tenant", source.id, foreign.id),
            rule=application_dependency_rule(),
        )


def test_acceptance_thresholds_produce_explicit_pass_evidence(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    application, node = taxonomy_setup(emrp, context)
    target = emrp.register_entity(entity(context, "ledger"))
    identity = emrp.reconcile_identity(
        candidate(context, canonical_id=application.canonical_id)
    )
    relation = relationship(context, "payments-ledger", application.id, target.id)
    emrp.validate_relationship(relation, rule=application_dependency_rule())
    taxonomy = emrp.validate_taxonomy_assignment(
        application,
        node,
        taxonomy_id="business-domains",
        approved_concept_types=frozenset({"capability"}),
        business_domain="payments",
    )

    report = emrp.evaluate_acceptance(
        identity=identity,
        entity=application,
        relationship=relation,
        relationship_rule=application_dependency_rule(),
        taxonomy=taxonomy,
    )

    assert isinstance(report, EMRPAcceptanceReport)
    assert report.accepted is True
    assert report.failed_checks == ()
    assert report.checks["identity_confidence"].required == 0.8
    assert report.checks["metadata_completeness"].required == 100.0


def test_acceptance_thresholds_fail_deterministically(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    incomplete = entity(context, "incomplete", name="", owner=False)
    no_match = emrp.reconcile_identity(
        candidate(context, name="Missing", source_identifier="missing")
    )
    relation = relationship(context, "incomplete-rel", "incomplete", "target")

    report = emrp.evaluate_acceptance(
        identity=no_match,
        entity=incomplete,
        relationship=relation,
        relationship_rule=application_dependency_rule(),
        taxonomy=TaxonomyValidation(
            valid=False,
            taxonomy_id="business-domains",
            node_id="missing",
            concept_id="missing",
            reason="unsupported",
        ),
        thresholds=AcceptanceThresholds(),
    )

    assert report.accepted is False
    assert report.failed_checks == (
        "identity_confidence",
        "metadata_completeness",
        "ownership_completeness",
        "relationship_topology",
        "taxonomy_validity",
    )


def test_metadata_acceptance_rejects_cross_tenant_records(
    context: TenantContext,
    emrp: EnterpriseMetadataRegistryService,
) -> None:
    other_context = TenantContext("org-1", "tenant-b")
    foreign = entity(other_context, "foreign")
    foreign_candidate = candidate(other_context, canonical_id=foreign.canonical_id)
    identity = InMemoryIdentityResolver([foreign]).resolve(foreign_candidate)

    with pytest.raises(DataFabricTenantBoundaryError):
        emrp.evaluate_acceptance(
            identity=identity,
            entity=foreign,
            relationship=relationship(
                other_context,
                "foreign-rel",
                "foreign",
                "other",
            ),
            relationship_rule=application_dependency_rule(),
            taxonomy=TaxonomyValidation(
                valid=True,
                taxonomy_id="domains",
                node_id="foreign",
                concept_id="foreign",
                reason="approved_membership",
            ),
        )
