from dataclasses import dataclass
from uuid import uuid4

import pytest

from data_fabric.contracts import (
    EnterpriseRelationship,
    EntityType,
    RelationshipType,
)
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from data_fabric.persistence.mappers import (
    EntityPersistenceMapper,
    RelationshipPersistenceMapper,
)
from data_fabric.persistence.models import PageResult
from enterprise_registry.canonical import enterprise_entity_from_source
from repositories.enterprise_registry_source import CanonicalDataFabricRegistrySource
from services.demo_enterprise_topology import demo_enterprise_topology
from services.enterprise_registry_composition import (
    EnterpriseRegistryConfigurationError,
    enterprise_registry_service,
)

ORG = "11111111-1111-4111-8111-111111111111"


@dataclass
class FakePageRepository:
    records: tuple
    mapper: object
    scopes: list

    def search(self, query):
        self.scopes.append((query.tenant_context, query.page.offset, query.page.limit))
        start = query.page.offset
        end = start + query.page.limit
        return PageResult(self.records[start:end], len(self.records), query.page)


def entity(context, identifier, *, source_system="azure", name=None):
    return enterprise_entity_from_source(
        context=context,
        entity_type=EntityType.COMPUTE_RESOURCE,
        source_system=source_system,
        source_entity_id=identifier,
        canonical_name=name or identifier,
        search_attributes={"provider": "Azure"},
    )


class EmptyResponse:
    data = ()


class DomainQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.filters = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def execute(self):
        self.client.seen_filters.append((self.table_name, tuple(self.filters)))
        rows = self.client.rows.get(self.table_name, ())
        for field, value in self.filters:
            rows = tuple(row for row in rows if row.get(field) == value)
        return type("Response", (), {"data": rows})()


class DomainClient:
    def __init__(self, rows):
        self.rows = rows
        self.seen_filters = []

    def table(self, name):
        return DomainQuery(self, name)

    def rpc(self, *_args, **_kwargs):
        return type("Rpc", (), {"execute": lambda _self: EmptyResponse()})()


class CanonicalSource:
    def __init__(self, entities, relationships=()):
        self._entities = tuple(entities)
        self._relationships = tuple(relationships)
        self.entity_contexts = []
        self.relationship_contexts = []

    def entities(self, context):
        self.entity_contexts.append(context)
        return self._entities

    def relationships(self, context):
        self.relationship_contexts.append(context)
        return self._relationships


def test_canonical_data_fabric_reader_scopes_and_paginates_both_repositories():
    context = TenantContext(ORG, ORG)
    entities = (
        entity(context, "resource-1"),
        entity(context, "resource-2"),
    )
    relationships = (
        EnterpriseRelationship(
            id=str(uuid4()),
            relationship_type=RelationshipType.DEPENDS_ON,
            source_entity_id=entities[0].id,
            target_entity_id=entities[1].id,
            organization_id=ORG,
            tenant_id=ORG,
            source_system="azure",
            source_identifier="edge-1",
        ),
    )
    entity_mapper = EntityPersistenceMapper()
    relationship_mapper = RelationshipPersistenceMapper()
    entity_records = tuple(entity_mapper.domain_to_record(item, context) for item in entities)
    relationship_records = tuple(
        relationship_mapper.domain_to_record(item, context) for item in relationships
    )
    entity_repo = FakePageRepository(entity_records, entity_mapper, [])
    relationship_repo = FakePageRepository(relationship_records, relationship_mapper, [])
    reader = CanonicalDataFabricRegistrySource(
        entity_repo,
        relationship_repo,
        page_size=1,
    )

    read_entities = reader.entities(context)
    read_relationships = reader.relationships(context)
    assert [item.canonical_id for item in read_entities] == [
        item.canonical_id for item in entities
    ]
    assert [item.source_identifier for item in read_entities] == [
        item.source_identifier for item in entities
    ]
    assert [item.id for item in read_relationships] == [
        item.id for item in relationships
    ]
    assert [scope[0] for scope in entity_repo.scopes] == [context, context, context]
    assert [scope[0] for scope in relationship_repo.scopes] == [context, context]
    assert [scope[1] for scope in entity_repo.scopes] == [0, 1, 2]
    assert [scope[1] for scope in relationship_repo.scopes] == [0, 1]


def test_canonical_data_fabric_reader_fails_closed_for_missing_or_mismatched_tenant():
    context = TenantContext(ORG, ORG)
    other_org = "22222222-2222-4222-8222-222222222222"
    other = TenantContext(other_org, other_org)
    other_entity = entity(other, "foreign-resource")
    entity_mapper = EntityPersistenceMapper()
    reader = CanonicalDataFabricRegistrySource(
        FakePageRepository(
            (entity_mapper.domain_to_record(other_entity, other),),
            entity_mapper,
            [],
        ),
        FakePageRepository((), RelationshipPersistenceMapper(), []),
    )

    with pytest.raises(PermissionError, match="Explicit Data Fabric tenant context"):
        reader.entities(None)
    with pytest.raises(DataFabricTenantBoundaryError, match="tenant boundary"):
        reader.entities(context)


def test_enterprise_registry_prefers_canonical_source_and_keeps_legacy_and_demo():
    context = TenantContext(ORG, ORG)
    canonical_entity = entity(context, "azure-resource-id", name="Canonical VM")
    other_canonical = entity(context, "canonical-only-id", name="Canonical Only")
    relation = EnterpriseRelationship(
        id=str(uuid4()),
        relationship_type=RelationshipType.DEPENDS_ON,
        source_entity_id=canonical_entity.id,
        target_entity_id=other_canonical.id,
        organization_id=ORG,
        tenant_id=ORG,
        source_system="azure",
        source_identifier="azure-edge-1",
    )
    canonical_source = CanonicalSource((canonical_entity, other_canonical), (relation,))
    client = DomainClient({
        "technology_inventory": ({
            "technology_id": "AZURE-RESOURCE-ID",
            "technology_name": "Legacy VM duplicate",
                "source_system": "Azure Connector",
                "organization_id": ORG,
                "tenant_id": ORG,
        }, {
            "technology_id": "legacy-only-id",
            "technology_name": "Legacy Technology",
            "source_system": "legacy",
                "organization_id": ORG,
                "tenant_id": ORG,
        })
    })

    service = enterprise_registry_service(
        context,
        role="super_admin",
        environment="development",
        supabase_url="https://tenant.supabase.co",
        supabase_key="test-key",
        client=client,
        canonical_source=canonical_source,
    )

    duplicate_matches = service.search_entities("azure-resource-id")
    assert len(duplicate_matches) == 1
    assert duplicate_matches[0].canonical_id == canonical_entity.canonical_id
    assert service.search_entities("legacy-only-id")
    assert service.search_entities("canonical-only-id")
    assert service.get_relationships(canonical_entity.canonical_id) == (relation,)
    demo_entities, _ = demo_enterprise_topology(context)
    service_ids = {item.canonical_id for item in service.list_entities()}
    assert {item.canonical_id for item in demo_entities} <= service_ids
    assert canonical_source.entity_contexts == [context]
    assert canonical_source.relationship_contexts == [context]
    for _table, filters in client.seen_filters:
        scoped = dict(filters)
        assert scoped["organization_id"] == ORG
        assert scoped["tenant_id"] == ORG


def test_v1_enterprise_registry_uses_canonical_data_fabric_only(monkeypatch):
    context = TenantContext(ORG, ORG)
    canonical_entity = entity(context, "canonical-v1-entity")
    canonical_source = CanonicalSource((canonical_entity,))
    client = DomainClient(
        {
            "technology_inventory": (
                {
                    "technology_id": "legacy-only-id",
                    "technology_name": "Legacy Technology",
                    "source_system": "legacy",
                    "organization_id": ORG,
                    "tenant_id": ORG,
                },
            )
        }
    )
    monkeypatch.setenv("NEXORA_PRODUCT_PROFILE", "V1")

    service = enterprise_registry_service(
        context,
        role="cio",
        environment="production",
        supabase_url="https://tenant.supabase.co",
        supabase_key="test-key",
        client=client,
        canonical_source=canonical_source,
    )

    assert service.source_mode == "data_fabric"
    assert service.search_entities("canonical-v1-entity")
    assert not service.search_entities("legacy-only-id")
    assert client.seen_filters == []


def test_v1_enterprise_registry_fails_closed_without_canonical_source(monkeypatch):
    monkeypatch.setenv("NEXORA_PRODUCT_PROFILE", "v1")

    with pytest.raises(
        EnterpriseRegistryConfigurationError,
        match="canonical Data Fabric source is required",
    ):
        enterprise_registry_service(
            TenantContext(ORG, ORG),
            role="cio",
            environment="development",
            supabase_url="",
            supabase_key="",
        )


def test_enterprise_registry_composition_requires_explicit_tenant_context():
    with pytest.raises(PermissionError, match="Explicit tenant context"):
        enterprise_registry_service(None, role="auditor", environment="development")
