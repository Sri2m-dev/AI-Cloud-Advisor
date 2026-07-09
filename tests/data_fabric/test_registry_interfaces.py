import pytest

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship, EntityType
from data_fabric.registry import (
    DuplicateCanonicalIdError,
    EntityNotFoundError,
    InMemoryEntityRegistry,
    InMemoryRelationshipRegistry,
    RegistryValidationError,
    RelationshipNotFoundError,
)


def make_entity(**overrides):
    values = {
        "id": "ent-1",
        "canonical_id": "application:checkout",
        "entity_type": EntityType.APPLICATION,
        "name": "Checkout",
        "source_system": "servicenow",
        "source_identifier": "app-123",
        "organization_id": "org-1",
        "tenant_id": "tenant-1",
        "tags": ["tier-1", "customer"],
        "metadata": {"criticality": "high"},
    }
    values.update(overrides)
    return EnterpriseEntity(**values)


def make_relationship(**overrides):
    values = {
        "id": "rel-1",
        "relationship_type": "runs_on",
        "source_entity_id": "ent-1",
        "target_entity_id": "ent-2",
        "organization_id": "org-1",
        "source_system": "servicenow",
        "source_identifier": "rel-123",
    }
    values.update(overrides)
    return EnterpriseRelationship(**values)


def test_entity_registry_register_get_and_find_by_canonical_id() -> None:
    registry = InMemoryEntityRegistry()
    entity = make_entity()

    registered = registry.register_entity(entity)

    assert registered == entity
    assert registry.get_entity("ent-1") == entity
    assert registry.find_entity_by_canonical_id("application:checkout") == entity


def test_entity_registry_returns_copies() -> None:
    registry = InMemoryEntityRegistry()
    registry.register_entity(make_entity())

    fetched = registry.get_entity("ent-1")
    fetched.metadata["criticality"] = "low"

    assert registry.get_entity("ent-1").metadata["criticality"] == "high"


def test_entity_registry_rejects_duplicate_canonical_id() -> None:
    registry = InMemoryEntityRegistry()
    registry.register_entity(make_entity())

    with pytest.raises(DuplicateCanonicalIdError):
        registry.register_entity(make_entity(id="ent-2", source_identifier="app-456"))


def test_entity_registry_requires_source_identity_fields() -> None:
    registry = InMemoryEntityRegistry()

    with pytest.raises(RegistryValidationError):
        registry.register_entity(make_entity(canonical_id=""))

    with pytest.raises(RegistryValidationError):
        registry.register_entity(make_entity(source_system=""))

    with pytest.raises(RegistryValidationError):
        registry.register_entity(make_entity(source_identifier=""))


def test_entity_registry_search_update_and_deactivate() -> None:
    registry = InMemoryEntityRegistry()
    registry.register_entity(make_entity())
    registry.register_entity(
        make_entity(
            id="ent-2",
            canonical_id="cloud_resource:vm-1",
            entity_type="cloud_resource",
            name="VM 1",
            source_identifier="vm-1",
            tags=["infra"],
        )
    )

    assert [entity.id for entity in registry.search_entities(entity_type="application")] == [
        "ent-1"
    ]
    assert [entity.id for entity in registry.search_entities(tags=["infra"])] == ["ent-2"]

    updated = make_entity(name="Checkout API", version=2)
    registry.update_entity(updated)
    assert registry.get_entity("ent-1").name == "Checkout API"

    deactivated = registry.deactivate_entity("ent-1")
    assert deactivated.metadata["active"] is False
    assert [entity.id for entity in registry.search_entities()] == ["ent-2"]
    assert {entity.id for entity in registry.search_entities(include_inactive=True)} == {
        "ent-1",
        "ent-2",
    }


def test_entity_registry_raises_for_missing_entity() -> None:
    registry = InMemoryEntityRegistry()

    with pytest.raises(EntityNotFoundError):
        registry.get_entity("missing")

    with pytest.raises(EntityNotFoundError):
        registry.update_entity(make_entity(id="missing"))


def test_relationship_registry_register_get_search_and_deactivate() -> None:
    registry = InMemoryRelationshipRegistry()
    relationship = make_relationship()

    registered = registry.register_relationship(relationship)

    assert registered == relationship
    assert registry.get_relationship("rel-1") == relationship
    assert [item.id for item in registry.search_relationships(relationship_type="runs_on")] == [
        "rel-1"
    ]
    assert [item.id for item in registry.search_relationships(source_entity_id="ent-1")] == [
        "rel-1"
    ]

    deactivated = registry.deactivate_relationship("rel-1")
    assert deactivated.metadata["active"] is False
    assert registry.search_relationships() == []
    assert [item.id for item in registry.search_relationships(include_inactive=True)] == [
        "rel-1"
    ]


def test_relationship_registry_requires_source_and_target_fields() -> None:
    registry = InMemoryRelationshipRegistry()

    with pytest.raises(RegistryValidationError):
        registry.register_relationship(make_relationship(source_entity_id=""))

    with pytest.raises(RegistryValidationError):
        registry.register_relationship(make_relationship(target_entity_id=""))

    with pytest.raises(RegistryValidationError):
        registry.register_relationship(make_relationship(source_system=""))

    with pytest.raises(RegistryValidationError):
        registry.register_relationship(make_relationship(source_identifier=""))


def test_relationship_registry_rejects_duplicate_ids_and_missing_records() -> None:
    registry = InMemoryRelationshipRegistry()
    registry.register_relationship(make_relationship())

    with pytest.raises(RegistryValidationError):
        registry.register_relationship(make_relationship())

    with pytest.raises(RelationshipNotFoundError):
        registry.get_relationship("missing")

    with pytest.raises(RelationshipNotFoundError):
        registry.deactivate_relationship("missing")
