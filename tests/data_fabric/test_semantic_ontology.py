from dataclasses import replace

import pytest

from data_fabric.contracts import EnterpriseEntity, EntityType
from data_fabric.semantic import (
    ConceptRelationship,
    ConceptSynonym,
    InMemoryOntologyRegistry,
    InMemorySemanticMapper,
    InMemoryTaxonomyService,
    MappingDecision,
    SemanticConcept,
    SemanticMapping,
    SemanticValidationError,
    TaxonomyNode,
)
from data_fabric.semantic.mapping import register_demo_mappings

ORG = "org-1"
TENANT = "tenant-1"


def concept(concept_id, name, concept_type="compute", **overrides):
    values = {
        "concept_id": concept_id,
        "canonical_name": name,
        "display_name": name.title(),
        "description": f"{name} concept",
        "concept_type": concept_type,
        "parent_concept_id": None,
        "synonyms": (),
        "aliases": (),
        "attributes": {},
        "organization_id": ORG,
        "tenant_id": TENANT,
    }
    values.update(overrides)
    return SemanticConcept(**values)


def seed_registry():
    registry = InMemoryOntologyRegistry()
    registry.register_concept(concept("compute", "Compute", attributes={"domain": "technology", "inherited": "parent"}))
    registry.register_concept(
        concept(
            "virtual-machine",
            "Virtual Machine",
            parent_concept_id="compute",
            synonyms=(ConceptSynonym("VM"), ConceptSynonym("Virtual Server")),
            aliases=("IaaS VM",),
            attributes={"runtime": "virtualized", "inherited": "child"},
        )
    )
    registry.register_concept(concept("object-storage", "Object Storage", "storage", synonyms=("Bucket Storage",), aliases=("Blob Store",)))
    registry.register_concept(concept("managed-relational-database", "Managed Relational Database", "database", synonyms=("Managed SQL",)))
    registry.register_concept(concept("managed-kubernetes", "Managed Kubernetes", "container_platform", synonyms=("Kubernetes Service",)))
    registry.register_concept(concept("cloud-monitoring", "Cloud Monitoring", "observability", synonyms=("Monitoring Service",)))
    return registry


def test_concept_registration_and_lookup() -> None:
    registry = InMemoryOntologyRegistry()
    item = registry.register_concept(concept("compute", "Compute"))

    assert registry.get_concept("compute", organization_id=ORG, tenant_id=TENANT) == item
    assert registry.find_by_canonical_name("Compute", organization_id=ORG, tenant_id=TENANT) == item


def test_duplicate_canonical_name_rejected_within_tenant() -> None:
    registry = InMemoryOntologyRegistry()
    registry.register_concept(concept("compute", "Compute"))

    with pytest.raises(SemanticValidationError):
        registry.register_concept(concept("compute-2", "compute"))


def test_same_canonical_name_accepted_across_tenants() -> None:
    registry = InMemoryOntologyRegistry()
    registry.register_concept(concept("compute", "Compute", tenant_id="tenant-a"))
    registry.register_concept(concept("compute", "Compute", tenant_id="tenant-b"))

    assert registry.find_by_canonical_name("Compute", organization_id=ORG, tenant_id="tenant-a") is not None
    assert registry.find_by_canonical_name("Compute", organization_id=ORG, tenant_id="tenant-b") is not None


def test_synonym_lookup_and_collision_detection() -> None:
    registry = InMemoryOntologyRegistry()
    registry.register_concept(concept("vm", "Virtual Machine", synonyms=("VM",)))

    assert registry.find_by_synonym("vm", organization_id=ORG, tenant_id=TENANT).concept_id == "vm"
    with pytest.raises(SemanticValidationError):
        registry.register_concept(concept("other", "Other", synonyms=("VM",)))


def test_concept_deactivation() -> None:
    registry = seed_registry()

    inactive = registry.deactivate_concept("virtual-machine", organization_id=ORG, tenant_id=TENANT)

    assert inactive.active is False
    assert registry.get_concept("virtual-machine", organization_id=ORG, tenant_id=TENANT).active is False


def test_parent_child_traversal_and_hierarchy_cycle_rejection() -> None:
    registry = seed_registry()

    assert [item.concept_id for item in registry.list_children("compute", organization_id=ORG, tenant_id=TENANT)] == ["virtual-machine"]
    assert [item.concept_id for item in registry.list_ancestors("virtual-machine", organization_id=ORG, tenant_id=TENANT)] == ["compute"]
    assert [item.concept_id for item in registry.list_descendants("compute", organization_id=ORG, tenant_id=TENANT)] == ["virtual-machine"]

    with pytest.raises(SemanticValidationError):
        registry.update_concept(replace(registry.get_concept("compute", organization_id=ORG, tenant_id=TENANT), parent_concept_id="virtual-machine"))


def test_relationship_endpoint_validation_and_contradiction() -> None:
    registry = seed_registry()

    with pytest.raises(SemanticValidationError):
        registry.register_concept_relationship(ConceptRelationship("bad", "virtual-machine", "missing", "related_to", ORG, TENANT))

    registry.register_concept_relationship(ConceptRelationship("rel-1", "virtual-machine", "compute", "equivalent_to", ORG, TENANT))
    with pytest.raises(SemanticValidationError):
        registry.register_concept_relationship(ConceptRelationship("rel-2", "compute", "virtual-machine", "conflicts_with", ORG, TENANT))


def test_exact_canonical_synonym_normalized_and_provider_mappings() -> None:
    registry = seed_registry()
    mapper = InMemorySemanticMapper(registry)
    mapper.register_mapping(SemanticMapping("aws-ec2", "aws", "EC2", None, None, "aws", None, "virtual-machine", ORG, TENANT, 100.0))

    canonical = mapper.map_source_term(source_system="manual", source_term="Virtual Machine", organization_id=ORG, tenant_id=TENANT)
    synonym = mapper.map_source_term(source_system="manual", source_term="VM", organization_id=ORG, tenant_id=TENANT)
    normalized = mapper.map_source_term(source_system="manual", source_term="virtual    machine", organization_id=ORG, tenant_id=TENANT)
    explicit = mapper.map_source_term(source_system="aws", source_term="EC2", provider="aws", organization_id=ORG, tenant_id=TENANT)

    assert canonical.selected.concept.concept_id == "virtual-machine"
    assert synonym.selected.concept.concept_id == "virtual-machine"
    assert normalized.selected.concept.concept_id == "virtual-machine"
    assert explicit.selected.concept.concept_id == "virtual-machine"
    assert "explicit_mapping" in explicit.selected.reasons


def test_ambiguous_mapping_no_match_and_inactive_exclusion() -> None:
    registry = InMemoryOntologyRegistry()
    registry.register_concept(concept("a", "Alpha", aliases=("Shared",)))
    registry.register_concept(concept("b", "Beta", aliases=("Shared",), concept_type="storage"))
    mapper = InMemorySemanticMapper(registry)

    ambiguous = mapper.map_source_term(source_system="manual", source_term="Shared", organization_id=ORG, tenant_id=TENANT)
    no_match = mapper.map_source_term(source_system="manual", source_term="No Such Term", organization_id=ORG, tenant_id=TENANT)
    registry.deactivate_concept("a", organization_id=ORG, tenant_id=TENANT)
    inactive = mapper.map_source_term(source_system="manual", source_term="Alpha", organization_id=ORG, tenant_id=TENANT)

    assert ambiguous.decision is MappingDecision.AMBIGUOUS
    assert no_match.decision is MappingDecision.NO_MATCH
    assert inactive.decision is MappingDecision.NO_MATCH


def test_stable_candidate_ordering_and_explanation() -> None:
    registry = InMemoryOntologyRegistry()
    registry.register_concept(concept("b", "Beta", aliases=("Shared",), concept_type="storage"))
    registry.register_concept(concept("a", "Alpha", aliases=("Shared",)))
    mapper = InMemorySemanticMapper(registry)

    result = mapper.map_source_term(source_system="manual", source_term="Shared", organization_id=ORG, tenant_id=TENANT)

    assert [candidate.concept.concept_id for candidate in result.candidates] == ["a", "b"]
    assert "reasons=" in mapper.explain_mapping(result)


def test_confidence_range_validation() -> None:
    with pytest.raises(SemanticValidationError):
        SemanticMapping("bad", "aws", "EC2", None, None, "aws", None, "virtual-machine", ORG, TENANT, 101.0)


def test_inherited_attributes_and_child_override() -> None:
    registry = seed_registry()

    attrs, explanation = registry.effective_attributes("virtual-machine", organization_id=ORG, tenant_id=TENANT)

    assert attrs["domain"] == "technology"
    assert attrs["runtime"] == "virtualized"
    assert attrs["inherited"] == "child"
    assert "inherited from virtual-machine" in explanation


def test_taxonomy_path_lookup_and_cycle_detection() -> None:
    taxonomy = InMemoryTaxonomyService()
    taxonomy.create_taxonomy("tech", organization_id=ORG, tenant_id=TENANT)
    taxonomy.add_node(TaxonomyNode("root", "tech", "compute", None, ORG, TENANT))
    taxonomy.add_node(TaxonomyNode("vm", "tech", "virtual-machine", "root", ORG, TENANT))

    path = taxonomy.get_path("vm", organization_id=ORG, tenant_id=TENANT)
    assert path.node_ids == ("root", "vm")

    with pytest.raises(SemanticValidationError):
        taxonomy.move_node("root", "vm", organization_id=ORG, tenant_id=TENANT)


def test_organization_and_tenant_isolation() -> None:
    registry = InMemoryOntologyRegistry()
    registry.register_concept(concept("vm", "Virtual Machine", tenant_id="tenant-a"))

    assert registry.find_by_canonical_name("Virtual Machine", organization_id=ORG, tenant_id="tenant-b") is None
    mapper = InMemorySemanticMapper(registry)
    result = mapper.map_source_term(source_system="manual", source_term="Virtual Machine", organization_id=ORG, tenant_id="tenant-b")
    assert result.decision is MappingDecision.NO_MATCH


def test_returned_values_cannot_mutate_internal_state() -> None:
    registry = seed_registry()
    item = registry.get_concept("virtual-machine", organization_id=ORG, tenant_id=TENANT)

    with pytest.raises(TypeError):
        item.attributes["runtime"] = "changed"

    assert registry.get_concept("virtual-machine", organization_id=ORG, tenant_id=TENANT).attributes["runtime"] == "virtualized"


def test_repeated_operations_are_deterministic() -> None:
    registry = seed_registry()
    mapper = InMemorySemanticMapper(registry)

    first = mapper.map_source_term(source_system="manual", source_term="VM", organization_id=ORG, tenant_id=TENANT)
    second = mapper.map_source_term(source_system="manual", source_term="VM", organization_id=ORG, tenant_id=TENANT)

    assert first == second


def test_demo_mappings_cover_reference_cloud_terms() -> None:
    registry = seed_registry()
    mapper = InMemorySemanticMapper(registry)
    register_demo_mappings(mapper, organization_id=ORG, tenant_id=TENANT)

    expected = {
        ("aws", "EC2", "virtual-machine"),
        ("azure", "Blob Storage", "object-storage"),
        ("gcp", "Cloud SQL", "managed-relational-database"),
        ("azure", "Kubernetes Service", "managed-kubernetes"),
        ("gcp", "Cloud Monitoring", "cloud-monitoring"),
    }
    for provider, term, concept_id in expected:
        result = mapper.map_source_term(source_system=provider, source_term=term, provider=provider, organization_id=ORG, tenant_id=TENANT)
        assert result.selected.concept.concept_id == concept_id


def test_map_entity_uses_existing_contract_fields() -> None:
    registry = seed_registry()
    mapper = InMemorySemanticMapper(registry)
    entity = EnterpriseEntity("ent-1", "application:vm", EntityType.APPLICATION, "VM", "manual", "vm-1", ORG, TENANT)

    result = mapper.map_entity(entity)

    assert result.selected.concept.concept_id == "virtual-machine"
