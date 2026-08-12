from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter

import pytest
from streamlit.testing.v1 import AppTest

import services.enterprise_registry_composition as registry_composition
from classification_engine.models import (
    ApprovalStatus,
    ClassificationResult,
    InferenceStatus,
)
from classification_engine.repository import InMemoryClassificationRepository
from data_fabric.contracts import EnterpriseRelationship, EntityType, RelationshipType
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from data_fabric.identity import InMemoryIdentityResolver, MatchCandidate, MatchDecision
from data_fabric.registry import (
    InMemoryEntityRegistry,
    InMemoryRelationshipRegistry,
    RegistryValidationError,
)
from data_fabric.versioning import InMemoryVersionStore
from enterprise_registry.adapters import (
    ApplicationEnterpriseAdapter,
    BusinessServiceEnterpriseAdapter,
    CloudAccountEnterpriseAdapter,
    SaaSEnterpriseAdapter,
    TechnologyEnterpriseAdapter,
)
from enterprise_registry.canonical import (
    ENTERPRISE_ENTITY_TAXONOMY,
    canonical_enterprise_id,
)
from enterprise_registry.canonical_service import EnterpriseRegistryService
from services.enterprise_registry_composition import (
    EnterpriseRegistryConfigurationError,
    enterprise_registry_service,
)

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"
DEV_ORG = "71cf875a-2103-47a0-8886-41a97c5750ec"


class _Financial:
    def get_financial_context(self, context, entity):
        context.assert_record_matches(entity)
        return {"total_spend": 42.0} if entity.entity_type is EntityType.CLOUD_ACCOUNT else {}


class _Response:
    def __init__(self, data):
        self.data = data


class _EmptyQuery:
    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def execute(self):
        return _Response([])


class _DevAccountClient:
    def table(self, _name):
        return _EmptyQuery()

    def rpc(self, name, params):
        assert params["requested_organization_id"] == DEV_ORG
        if name == "tenant_cloud_account_posture":
            return _RpcQuery(
                [
                    {
                        "account_id": "727482365532",
                        "mapping_status": "unknown",
                        "unblended_spend": 37143.2080151701,
                        "currency": "USD",
                    }
                ]
            )
        return _RpcQuery([])


class _RpcQuery:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return _Response(self.data)


def _service(context=None, role="super_admin", classifications=None):
    context = context or TenantContext(ORG_A, ORG_A)
    return EnterpriseRegistryService(
        context,
        role=role,
        entities=InMemoryEntityRegistry(),
        identities=InMemoryIdentityResolver(),
        relationships=InMemoryRelationshipRegistry(),
        classifications=classifications,
        financial=_Financial(),
        versions=InMemoryVersionStore(),
    )


def _account(context=None, account_id="727482365532", **values):
    return CloudAccountEnterpriseAdapter().adapt(
        context or TenantContext(ORG_A, ORG_A),
        {
            "provider": "aws",
            "source_system": "aws",
            "account_id": account_id,
            "account_name": values.pop("account_name", account_id),
            **values,
        },
    )


def test_taxonomy_contains_every_required_canonical_family():
    assert set(ENTERPRISE_ENTITY_TAXONOMY) == {
        "BUSINESS",
        "APPLICATION",
        "TECHNOLOGY",
        "SAAS_VENDOR",
        "PEOPLE_OWNERSHIP",
        "FINANCIAL",
    }
    values = {item.value for family in ENTERPRISE_ENTITY_TAXONOMY.values() for item in family}
    assert {
        "organization",
        "cloud_account",
        "ai_platform",
        "license",
        "allocation_target",
    } <= values


def test_canonical_ids_are_deterministic_tenant_and_source_aware():
    context = TenantContext(ORG_A, ORG_A)
    first = canonical_enterprise_id(context, EntityType.CLOUD_ACCOUNT, "aws", "727482365532")
    assert first == canonical_enterprise_id(context, "cloud_account", "aws", "727482365532")
    assert first != canonical_enterprise_id(
        TenantContext(ORG_B, ORG_B), "cloud_account", "aws", "727482365532"
    )
    assert first != canonical_enterprise_id(context, "cloud_account", "azure", "727482365532")


@pytest.mark.parametrize(
    ("adapter", "row", "expected"),
    [
        (
            CloudAccountEnterpriseAdapter(),
            {"account_id": "1", "account_name": "AWS"},
            "cloud_account",
        ),
        (ApplicationEnterpriseAdapter(), {"application_id": "a", "name": "App"}, "application"),
        (
            BusinessServiceEnterpriseAdapter(),
            {"service_id": "s", "name": "Service"},
            "business_service",
        ),
        (TechnologyEnterpriseAdapter(), {"technology_id": "t", "name": "Tech"}, "technology"),
        (SaaSEnterpriseAdapter(), {"tool_id": "x", "name": "SaaS"}, "saas_product"),
    ],
)
def test_cross_domain_adapters_expose_p3_contract_without_copying_domain_data(
    adapter, row, expected
):
    entity = adapter.adapt(TenantContext(ORG_A, ORG_A), row)
    assert entity.entity_type.value == expected
    assert entity.identity.canonical_id == entity.canonical_id
    assert "raw_payload" not in entity.metadata


def test_alias_resolution_duplicate_source_and_no_match():
    service = _service()
    entity = _account(aliases=("payments-prod",))
    service.register_entity(entity)
    alias = service.reconcile_identity(
        MatchCandidate("cur", "unknown", "payments-prod", ORG_A, tenant_id=ORG_A)
    )
    assert alias.decision is MatchDecision.MATCH
    unknown = service.reconcile_identity(
        MatchCandidate("cmdb", "missing", "Nothing Similar", ORG_A, tenant_id=ORG_A)
    )
    assert unknown.decision is MatchDecision.NO_MATCH
    with pytest.raises(RegistryValidationError):
        service.register_entity(_account())


def test_cross_tenant_canonical_id_cannot_be_resolved():
    entities = InMemoryEntityRegistry()
    identities = InMemoryIdentityResolver()
    entity = _account()
    entities.register_entity(entity)
    identities.register_entity(entity)
    service = EnterpriseRegistryService(
        TenantContext(ORG_B, ORG_B),
        role="auditor",
        entities=entities,
        identities=identities,
        relationships=InMemoryRelationshipRegistry(),
    )
    with pytest.raises(DataFabricTenantBoundaryError):
        service.get_entity(entity.canonical_id)


def test_read_only_persona_cannot_mutate_registry_identity():
    service = _service(role="auditor")
    with pytest.raises(PermissionError, match="mutation denied"):
        service.register_entity(_account())


def test_relationships_use_existing_p3_registry():
    service = _service()
    account = service.register_entity(_account())
    application = service.register_entity(
        ApplicationEnterpriseAdapter().adapt(
            service.context, {"application_id": "app-1", "name": "Payments"}
        )
    )
    relationship = EnterpriseRelationship(
        id="rel-1",
        relationship_type=RelationshipType.RUNS_ON,
        source_entity_id=application.id,
        target_entity_id=account.id,
        organization_id=ORG_A,
        tenant_id=ORG_A,
        source_system="cmdb",
        source_identifier="cmdb-rel-1",
    )
    service.relationships.register_relationship(relationship)
    assert service.get_relationships(account.canonical_id) == (relationship,)


def test_classification_financial_lineage_provenance_and_versions_are_exposed():
    repository = InMemoryClassificationRepository()
    context = TenantContext(ORG_A, ORG_A)
    now = datetime.now(timezone.utc)
    repository.save(
        context,
        ClassificationResult(
            id="class-1",
            organization_id=ORG_A,
            tenant_id=ORG_A,
            entity_type="cloud_account",
            entity_id="727482365532",
            field_name="business_unit",
            inferred_value="PMJAY",
            confidence_score=0.94,
            inference_method="TEST",
            inference_status=InferenceStatus.RESOLVED_INFERRED,
            policy_version=1,
            engine_version="test",
            evidence_set_hash="hash",
            source_timestamp=now,
            created_at=now,
            valid_from=now,
            valid_to=None,
            approval_status=ApprovalStatus.NEEDS_APPROVAL,
            evidence_ids=("evidence",),
        ),
    )
    service = _service(classifications=repository)
    entity = service.register_entity(_account())
    detail = service.get_detail(entity.canonical_id)
    assert detail.classifications[0]["inferred_value"] == "PMJAY"
    assert detail.financial_context["total_spend"] == 42.0
    assert detail.lineage.raw_record_id == "727482365532"
    assert detail.provenance.source_system == "aws"
    assert detail.versions[0].version == 1


def test_approved_classification_is_not_overwritten_by_later_inference():
    repository = InMemoryClassificationRepository()
    context = TenantContext(ORG_A, ORG_A)
    now = datetime.now(timezone.utc)
    base = ClassificationResult(
        id="approved",
        organization_id=ORG_A,
        tenant_id=ORG_A,
        entity_type="cloud_account",
        entity_id="727482365532",
        field_name="business_unit",
        inferred_value="PMJAY",
        confidence_score=1.0,
        inference_method="APPROVED",
        inference_status=InferenceStatus.RESOLVED_APPROVED,
        policy_version=1,
        engine_version="test",
        evidence_set_hash="first",
        source_timestamp=now,
        created_at=now,
        valid_from=now,
        valid_to=None,
        approval_status=ApprovalStatus.APPROVED,
        approved_by="owner",
        approved_at=now,
        evidence_ids=("one",),
    )
    repository.save(context, base)
    later = replace(
        base,
        id="later",
        inferred_value="OTHER",
        evidence_set_hash="second",
        inference_status=InferenceStatus.RESOLVED_INFERRED,
        approval_status=ApprovalStatus.NEEDS_APPROVAL,
        approved_by=None,
        approved_at=None,
    )
    saved = repository.save(context, later)
    assert saved.inference_status is InferenceStatus.NEEDS_REVIEW
    assert saved.review_reason == "new evidence conflicts with protected approved value"


def test_search_and_performance_envelope():
    service = _service()
    for index in range(500):
        service.register_entity(
            _account(account_id=f"{index:012d}", account_name=f"Account {index}")
        )
    target = service.search_entities("Account 499")[0]
    start = perf_counter()
    assert service.get_entity(target.canonical_id).canonical_id == target.canonical_id
    assert perf_counter() - start < 0.250
    start = perf_counter()
    assert len(service.search_entities("Account")) == 100
    assert perf_counter() - start < 1.0
    start = perf_counter()
    service.get_detail(target.canonical_id)
    assert perf_counter() - start < 2.0


def test_composition_fallback_and_production_fail_closed(tmp_path):
    path = tmp_path / "registry.db"
    sqlite3.connect(path).close()

    def connect():
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection

    selected = enterprise_registry_service(
        TenantContext(ORG_A, ORG_A),
        role="auditor",
        environment="development",
        supabase_url="",
        supabase_key="",
        connection_factory=connect,
    )
    assert selected.list_entities() == ()
    assert selected.source_mode == "sqlite"
    with pytest.raises(EnterpriseRegistryConfigurationError):
        enterprise_registry_service(
            TenantContext(ORG_A, ORG_A),
            role="auditor",
            environment="production",
            supabase_url="",
            supabase_key="",
        )


def test_configured_repository_projects_discovered_dev_account():
    selected = enterprise_registry_service(
        TenantContext(DEV_ORG, DEV_ORG),
        role="auditor",
        environment="development",
        supabase_url="https://tenant.supabase.co",
        supabase_key="valid-key",
        client=_DevAccountClient(),
    )

    matches = selected.search_entities("727482365532")
    assert selected.source_mode == "supabase"
    assert len(matches) == 1
    assert matches[0].canonical_id == ("cloud_account:e099f2ab-32d7-5f50-b03a-364c78d60098")
    assert matches[0].organization_id == DEV_ORG
    assert matches[0].tenant_id == DEV_ORG


def test_enterprise_registry_page_renders_without_supabase(monkeypatch):
    for name in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    app = AppTest.from_file("pages/enterprise_registry.py", default_timeout=30)
    for key, value in {
        "authenticated": True,
        "auth_backend": "local",
        "user": "auditor@company.com",
        "user_id": "auditor@company.com",
        "email": "auditor@company.com",
        "role": "auditor",
        "organization_id": ORG_A,
        "organization_name": "Default Org",
        "authorized_organization_ids": [ORG_A],
        "permissions": [],
    }.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    assert any("Enterprise Registry" in title.value for title in app.title)


def test_enterprise_registry_page_renders_populated_canonical_projection(monkeypatch):
    service = _service()
    entity = service.register_entity(
        _account(
            account_name="HG_AWS01",
            classification_status="NEEDS_REVIEW",
            confidence=0.84,
            financial_context_reference="tenant_cloud_account_posture:727482365532",
        )
    )
    monkeypatch.setattr(
        registry_composition,
        "enterprise_registry_service",
        lambda *args, **kwargs: service,
    )
    app = AppTest.from_file("pages/enterprise_registry.py", default_timeout=30)
    for key, value in {
        "authenticated": True,
        "auth_backend": "local",
        "user": "auditor@company.com",
        "user_id": "auditor@company.com",
        "email": "auditor@company.com",
        "role": "auditor",
        "organization_id": ORG_A,
        "organization_name": "Default Org",
        "authorized_organization_ids": [ORG_A],
        "permissions": [],
    }.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    assert any(
        metric.label == "Enterprise Entities" and metric.value == "1" for metric in app.metric
    )
    assert len(app.dataframe[0].value) == 1
    assert app.dataframe[0].value.iloc[0]["Canonical ID"] == entity.canonical_id
