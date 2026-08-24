from __future__ import annotations

from streamlit.testing.v1 import AppTest

from classification_engine.repository import SupabaseClassificationRepository
from data_fabric.contracts import EnterpriseRelationship
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from enterprise_registry.adapters import (
    ApplicationEnterpriseAdapter,
    BusinessServiceEnterpriseAdapter,
    CloudAccountEnterpriseAdapter,
)
from enterprise_registry.knowledge_graph import EnterpriseKnowledgeGraphService
from enterprise_registry.relationship_intelligence import RelationshipIntelligenceService
from tests.enterprise_registry.test_canonical_enterprise_registry import (
    _service as registry_service,
)

ORG = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
CTX = TenantContext(ORG, ORG)


def _graph():
    registry = registry_service(context=CTX)
    account = registry.register_entity(
        CloudAccountEnterpriseAdapter().adapt(
            CTX,
            {
                "account_id": "727482365532",
                "account_name": "HG_AWS01",
                "classification_status": "NEEDS_REVIEW",
                "confidence": 0.84,
                "lineage_reference": "lineage:account",
            },
        )
    )
    application = registry.register_entity(
        ApplicationEnterpriseAdapter().adapt(CTX, {"application_id": "kordia", "name": "KordiaSoc"})
    )
    service = registry.register_entity(
        BusinessServiceEnterpriseAdapter().adapt(
            CTX, {"business_service_id": "payments", "name": "Payments"}
        )
    )
    edges = (
        EnterpriseRelationship(
            id="runs",
            relationship_type="runs_on",
            source_entity_id=application.id,
            target_entity_id=account.id,
            organization_id=ORG,
            tenant_id=ORG,
            source_system="cmdb",
            source_identifier="cmdb:runs",
            confidence_score=0.95,
            evidence=("cmdb:application-hosting",),
            lineage_reference="lineage:runs",
        ),
        EnterpriseRelationship(
            id="supports",
            relationship_type="supports",
            source_entity_id=service.id,
            target_entity_id=application.id,
            organization_id=ORG,
            tenant_id=ORG,
            source_system="service-map",
            source_identifier="service-map:supports",
            confidence_score=0.9,
            evidence=("service-catalog:payments",),
            lineage_reference="lineage:supports",
        ),
    )
    relationships = RelationshipIntelligenceService(
        CTX,
        role="auditor",
        entities=registry.list_entities(),
        relationships=edges,
    )
    return EnterpriseKnowledgeGraphService(registry, relationships), account, application, service


def test_find_and_explain_entity_preserve_canonical_evidence():
    graph, account, application, service = _graph()
    node = graph.find_entity(account.canonical_id)
    assert node.entity is not None
    assert node.evidence.source == "cloud_account_registry"
    assert node.evidence.classification_status == "NEEDS_REVIEW"
    answer = graph.explain_entity(account.canonical_id)
    assert [entity.canonical_id for entity in answer.entities] == [
        application.canonical_id,
        service.canonical_id,
    ]
    assert "2 governed path(s)" in answer.narrative
    assert {evidence.source for evidence in answer.evidence} == {"cmdb", "service-map"}


def test_graph_query_apis_are_deterministic():
    graph, account, application, service = _graph()
    assert graph.search_graph("Kordia")[0].canonical_id == application.canonical_id
    path = graph.find_path(service.canonical_id, account.canonical_id)
    assert [entity.canonical_id for entity in path.entities] == [
        service.canonical_id,
        application.canonical_id,
        account.canonical_id,
    ]
    assert [edge.relationship_type.value for edge in path.relationships] == [
        "supports",
        "runs_on",
    ]
    assert graph.find_dependencies(service.canonical_id)[-1].entities[-1].canonical_id == (
        account.canonical_id
    )
    assert graph.find_business_impact(account.canonical_id)[0].canonical_id == service.canonical_id


def test_financial_impact_deduplicates_referenced_context():
    graph, account, _, _ = _graph()
    assert graph.find_financial_impact(account.canonical_id) == 42.0


def test_performance_targets():
    graph, account, _, _ = _graph()
    measured = graph.performance_probe(account.canonical_id, "HG_AWS01")
    assert measured["entity_ms"] < 100
    assert measured["search_ms"] < 150
    assert measured["traversal_ms"] < 500


class _ClassificationResponse:
    data = [
        {"field_name": "owner", "version": 2, "inferred_value": "current"},
        {"field_name": "owner", "version": 1, "inferred_value": "old"},
        {"field_name": "application", "version": 1, "inferred_value": "KordiaSoc"},
    ]


class _ClassificationQuery:
    def __init__(self):
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def is_(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        return _ClassificationResponse()


class _ClassificationClient:
    def __init__(self):
        self.query = _ClassificationQuery()

    def table(self, name):
        assert name == "classification_result"
        return self.query


def test_classification_projection_batches_current_entity_fields_with_tenant_scope():
    client = _ClassificationClient()
    rows = SupabaseClassificationRepository(client).current_for_entity(
        CTX, "cloud_account", "727482365532"
    )
    assert [row["inferred_value"] for row in rows] == ["current", "KordiaSoc"]
    assert ("organization_id", ORG) in client.query.filters
    assert ("tenant_id", ORG) in client.query.filters


def test_cross_tenant_entities_are_rejected_by_relationship_projection():
    foreign = CloudAccountEnterpriseAdapter().adapt(
        TenantContext(OTHER, OTHER), {"account_id": "foreign", "account_name": "Foreign"}
    )
    try:
        RelationshipIntelligenceService(CTX, role="auditor", entities=(foreign,), relationships=())
    except DataFabricTenantBoundaryError:
        pass
    else:  # pragma: no cover
        raise AssertionError("cross-tenant graph projection was accepted")


def test_enterprise_graph_page_safe_empty_local_runtime(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("pages/enterprise_graph.py", default_timeout=30)
    for key, value in {
        "authenticated": True,
        "auth_backend": "local",
        "user": "auditor@company.com",
        "user_id": "auditor@company.com",
        "email": "auditor@company.com",
        "role": "auditor",
        "organization_id": ORG,
        "organization_name": "Default Org",
        "authorized_organization_ids": [ORG],
        "permissions": [],
    }.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    assert any("Enterprise Knowledge Graph" in title.value for title in app.title)
    assert any("No tenant-scoped canonical knowledge" in info.value for info in app.info)
