from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from time import perf_counter

import pytest
from streamlit.testing.v1 import AppTest

from data_fabric.contracts import EnterpriseRelationship, RelationshipType
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from enterprise_registry.adapters import (
    ApplicationEnterpriseAdapter,
    BusinessServiceEnterpriseAdapter,
    CloudAccountEnterpriseAdapter,
)
from enterprise_registry.relationship_intelligence import (
    RelationshipDirection,
    RelationshipIntelligenceService,
)
from repositories.relationship_intelligence_repository import (
    SQLiteRelationshipIntelligenceRepository,
    SupabaseRelationshipIntelligenceRepository,
)
from services.relationship_intelligence_composition import (
    RelationshipIntelligenceConfigurationError,
    relationship_intelligence_service,
)

ORG = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
CTX = TenantContext(ORG, ORG)
NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


def _entities(context=CTX):
    account = CloudAccountEnterpriseAdapter().adapt(
        context, {"account_id": "727482365532", "account_name": "HG_AWS01"}
    )
    application = ApplicationEnterpriseAdapter().adapt(
        context, {"application_id": "kordia", "name": "KordiaSoc"}
    )
    service = BusinessServiceEnterpriseAdapter().adapt(
        context, {"business_service_id": "payments", "name": "Payments"}
    )
    return account, application, service


def _edge(identifier, relationship_type, source, target, context=CTX, evidence=("cmdb:1",)):
    return EnterpriseRelationship(
        id=identifier,
        relationship_type=relationship_type,
        source_entity_id=source.id,
        target_entity_id=target.id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        source_system="cmdb",
        source_identifier=identifier,
        evidence=evidence,
        discovery_timestamp=NOW,
        last_validation=NOW,
        lineage_reference=f"lineage:{identifier}",
        provenance_reference=f"provenance:{identifier}",
    )


def _service(role="auditor"):
    account, application, service = _entities()
    edges = (
        _edge("1", "runs_on", application, account),
        _edge("2", "supports", service, application),
    )
    return RelationshipIntelligenceService(
        CTX, role=role, entities=(account, application, service), relationships=edges
    )


def test_relationship_taxonomy_includes_authorized_additive_types():
    values = {item.value for item in RelationshipType}
    assert {
        "owns",
        "hosted_on",
        "depends_on",
        "communicates_with",
        "secured_by",
        "monitored_by",
        "consumes",
        "belongs_to",
        "supports",
        "part_of",
        "runs_on",
        "provides",
        "managed_by",
        "funded_by",
        "allocated_to",
        "backed_up_by",
        "protected_by",
        "integrates_with",
    } <= values


def test_relationship_requires_evidence_and_tenant_scope():
    account, application, _ = _entities()
    with pytest.raises(ValueError, match="evidence is required"):
        RelationshipIntelligenceService(
            CTX,
            role="auditor",
            entities=(account, application),
            relationships=(_edge("missing", "runs_on", application, account, evidence=()),),
        )
    other_account, other_application, _ = _entities(TenantContext(OTHER, OTHER))
    with pytest.raises(DataFabricTenantBoundaryError):
        RelationshipIntelligenceService(
            CTX,
            role="auditor",
            entities=(account, application),
            relationships=(
                _edge(
                    "cross",
                    "runs_on",
                    other_application,
                    other_account,
                    TenantContext(OTHER, OTHER),
                ),
            ),
        )


def test_directional_queries_multihop_dependencies_and_impact_narrative():
    intelligence = _service()
    account, application, service = _entities()
    inbound = intelligence.get_relationships(
        account.canonical_id, direction=RelationshipDirection.INBOUND
    )
    assert [row.relationship_type.value for row in inbound] == ["runs_on"]
    paths = intelligence.traverse(
        account.canonical_id, max_hops=2, direction=RelationshipDirection.INBOUND
    )
    assert [path.entities[-1].display_name for path in paths] == ["KordiaSoc", "Payments"]
    assert [path.hops for path in paths] == [1, 2]
    dependencies = intelligence.get_dependencies(service.canonical_id, max_hops=None)
    assert [path.entities[-1].display_name for path in dependencies] == ["KordiaSoc", "HG_AWS01"]
    impact = intelligence.get_blast_radius(account.canonical_id)
    assert [entity.canonical_id for entity in impact.impacted] == [
        application.canonical_id,
        service.canonical_id,
    ]
    assert "1 application(s)" in impact.narrative
    assert "1 business service(s)" in impact.narrative


def test_search_and_performance_targets():
    intelligence = _service()
    account = _entities()[0]
    start = perf_counter()
    assert intelligence.get_relationships(account.canonical_id)
    lookup = perf_counter() - start
    start = perf_counter()
    assert intelligence.traverse(account.canonical_id, max_hops=None)
    traversal = perf_counter() - start
    start = perf_counter()
    assert intelligence.search("HG_AWS01")
    search = perf_counter() - start
    assert lookup < 0.100
    assert traversal < 0.300
    assert search < 0.150


def test_sqlite_repository_is_tenant_scoped(tmp_path):
    path = tmp_path / "relationships.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE enterprise_relationships (id TEXT, relationship_type TEXT, "
        "source_entity_id TEXT, target_entity_id TEXT, organization_id TEXT, tenant_id TEXT, "
        "source_system TEXT, source_identifier TEXT, confidence_score REAL, quality_score REAL, "
        "metadata TEXT, version INTEGER, active INTEGER)"
    )
    for identifier, organization in (("mine", ORG), ("other", OTHER)):
        conn.execute(
            "INSERT INTO enterprise_relationships VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                "runs_on",
                f"{identifier}-source",
                f"{identifier}-target",
                organization,
                organization,
                "cmdb",
                identifier,
                90,
                90,
                '{"evidence":["cmdb:1"]}',
                1,
                1,
            ),
        )
    conn.commit()
    conn.close()

    def connect():
        value = sqlite3.connect(path)
        value.row_factory = sqlite3.Row
        return value

    rows = SQLiteRelationshipIntelligenceRepository(connect).list_relationships(CTX)
    assert [row.id for row in rows] == ["mine"]


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        return _Response(self.rows)


class _Client:
    def __init__(self):
        self.query = _Query([])

    def table(self, name):
        assert name == "data_fabric.enterprise_relationships"
        return self.query


def test_supabase_repository_applies_composite_tenant_scope():
    client = _Client()
    assert SupabaseRelationshipIntelligenceRepository(client).list_relationships(CTX) == ()
    assert ("organization_id", ORG) in client.query.filters
    assert ("tenant_id", ORG) in client.query.filters
    assert ("active", True) in client.query.filters


def test_production_invalid_configuration_fails_closed():
    with pytest.raises(RelationshipIntelligenceConfigurationError):
        relationship_intelligence_service(
            CTX,
            role="auditor",
            environment="production",
            supabase_url="",
            supabase_key="",
        )


def test_relationship_explorer_safe_empty_local_runtime(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("pages/relationship_explorer.py", default_timeout=30)
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
    assert any("Relationship Explorer" in title.value for title in app.title)
    assert any("No tenant-scoped" in info.value for info in app.info)
