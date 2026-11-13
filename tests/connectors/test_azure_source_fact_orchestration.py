from uuid import uuid4

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from connectors.common.tenant_guard import resolve_organization_id
from data_fabric.source_facts.persistence import SQLiteSourceFactRepository
from data_fabric.source_facts.service import SourceFactService as RealSourceFactService
from enterprise_registry.source_fact_projection import (
    GovernedCanonicalProjectionService as RealProjectionService,
)
from services import azure_connector_service as azure_service_module
from services.azure_connector_service import AzureConnectorService
from services.demo_tenant_service import DEMO_ORGANIZATION_ID, DEMO_ORGANIZATION_NAME

SUBSCRIPTION = "11111111-2222-4333-8444-555555555555"
RESOURCE_ID = (
    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg/providers/"
    "Microsoft.Compute/virtualMachines/vm"
)


def tenant_context(organization_id=None, role="client_admin"):
    organization_id = organization_id or str(uuid4())
    return AuthenticatedTenantContext(
        organization_id=organization_id,
        organization_name="Azure Test Tenant",
        user_id="azure-admin",
        user_email="azure-admin@example.test",
        role=role,
        authorization_claims=frozenset(),
        tenant_id=organization_id,
    )


class FakeConnector:
    calls = []

    def __init__(self, *, subscription_id, auth_method):
        assert auth_method == "runtime_identity"
        self.subscription_id = subscription_id
        self.calls = []
        FakeConnector.calls.append(self.calls)

    def test_connection(self):
        self.calls.append("test_connection")
        return {"status": "CONNECTED", "checks": {"subscription_access": "PASS"}}

    def sync_accounts(self):
        self.calls.append("sync_accounts")
        return [{
            "cloud": "azure",
            "account_id": self.subscription_id,
            "account_name": f"azure-{self.subscription_id}",
            "status": "ACTIVE",
            "region": "global",
        }]

    def sync_resources(self):
        self.calls.append("sync_resources")
        return [{
            "provider": "Azure",
            "subscription_id": self.subscription_id,
            "resource_id": RESOURCE_ID,
            "resource_type": "Azure VM",
            "name": "vm",
            "region": "eastus",
            "resource_group": "rg",
            "status": "ACTIVE",
        }]


class FakeAtomicExecutor:
    def __init__(self):
        self.entity_requests = []
        self.relationship_requests = []

    def execute_entity_write(self, request):
        self.entity_requests.append(request)
        return request

    def execute_relationship_write(self, request):
        self.relationship_requests.append(request)
        return request


def test_discovery_requires_authenticated_context_and_blocks_demo():
    with pytest.raises(PermissionError, match="authenticated tenant context"):
        AzureConnectorService.discover_to_data_fabric(None, SUBSCRIPTION)

    context = AuthenticatedTenantContext(
        organization_id=DEMO_ORGANIZATION_ID,
        organization_name=DEMO_ORGANIZATION_NAME,
        user_id="ceo@company.com",
        user_email="ceo@company.com",
        role="super_admin",
        authorization_claims=frozenset(),
        tenant_id=DEMO_ORGANIZATION_ID,
    )
    with pytest.raises(PermissionError, match="synthetic demo tenant"):
        AzureConnectorService.discover_to_data_fabric(context, SUBSCRIPTION)


def test_discovery_publishes_and_projects_explicit_tenant_without_legacy_writes(
    tmp_path, monkeypatch
):
    context = tenant_context()
    source_repository = SQLiteSourceFactRepository(tmp_path / "sourcefacts.sqlite")
    atomic_executor = FakeAtomicExecutor()
    FakeConnector.calls = []
    tenant_contexts = []

    def source_service(context, repository):
        tenant_contexts.append(context)
        return RealSourceFactService(context, repository)

    def projection_service(context, executor, **kwargs):
        tenant_contexts.append(context)
        return RealProjectionService(context, executor, **kwargs)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy connector persistence must not be used")

    monkeypatch.setattr(AzureConnectorService, "sync_all", forbidden)
    monkeypatch.setattr(azure_service_module, "SourceFactService", source_service)
    monkeypatch.setattr(
        azure_service_module,
        "GovernedCanonicalProjectionService",
        projection_service,
    )
    for name in (
        "upsert_technology_inventory",
        "upsert_discovered_assets",
        "upsert_technology_relationships",
        "upsert_relationship_graph",
        "insert_rows",
        "insert_sync_history",
        "upsert_rows",
    ):
        monkeypatch.setattr(azure_service_module, name, forbidden)
    monkeypatch.setattr(
        AzureConnectorService,
        "_build_canonical_projection_executor",
        lambda: atomic_executor,
    )

    result = AzureConnectorService.discover_to_data_fabric(
        context,
        SUBSCRIPTION,
        source_fact_repository=source_repository,
        canonical_executor=atomic_executor,
        connector_factory=FakeConnector,
    )
    repeated = AzureConnectorService.discover_to_data_fabric(
        context,
        SUBSCRIPTION,
        source_fact_repository=source_repository,
        canonical_executor=atomic_executor,
        connector_factory=FakeConnector,
    )

    assert result["status"] == "SUCCESS"
    assert result["accounts"] == 1
    assert result["costs"] == 0
    assert result["resources"] == 1
    assert result["source_facts_published"] == 2
    assert result["canonical_entities_projected"] == 2
    assert result["canonical_relationships_projected"] == 0
    assert result["discovery_status"] == "SUCCESS"
    assert result["financial_ingestion_status"] == "NOT_PERFORMED"
    assert result["dashboard_readiness"] == "UNKNOWN"
    assert repeated["source_facts_published"] == 0
    assert repeated["canonical_entities_projected"] == 2
    assert FakeConnector.calls == [
        ["test_connection", "sync_accounts", "sync_resources"],
        ["test_connection", "sync_accounts", "sync_resources"],
    ]
    facts = source_repository.list_current_facts(context.organization_id, context.tenant_id)
    assert len(facts) == 2
    assert all(f.organization_id == context.organization_id for f in facts)
    assert all(f.tenant_id == context.tenant_id for f in facts)
    assert {f.value["resource_type"] for f in facts} == {"Azure Subscription", "Azure VM"}
    assert len(atomic_executor.entity_requests) == 4
    first_requests, repeated_requests = (
        atomic_executor.entity_requests[:2],
        atomic_executor.entity_requests[2:],
    )
    assert [r.idempotency_key for r in first_requests] == [
        r.idempotency_key for r in repeated_requests
    ]
    assert [r.payload_hash for r in first_requests] == [
        r.payload_hash for r in repeated_requests
    ]
    assert all(r.tenant_context == context.fabric_context for r in atomic_executor.entity_requests)
    assert all(
        r.entity_record.organization_id == context.organization_id
        and r.entity_record.tenant_id == context.tenant_id
        for r in atomic_executor.entity_requests
    )
    assert atomic_executor.relationship_requests == []
    assert len(tenant_contexts) == 4
    assert tenant_contexts[0] is tenant_contexts[1]
    assert tenant_contexts[2] is tenant_contexts[3]
    assert resolve_organization_id(context.organization_id) == context.organization_id


def test_missing_sourcefact_database_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXORA_UNIVERSAL_EVIDENCE_DB", raising=False)

    with pytest.raises(RuntimeError, match="SourceFact database is not configured"):
        AzureConnectorService._source_fact_repository()


def test_missing_server_side_data_fabric_credential_fails_closed(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="server-side Data Fabric persistence credential"):
        AzureConnectorService._build_canonical_projection_executor()
