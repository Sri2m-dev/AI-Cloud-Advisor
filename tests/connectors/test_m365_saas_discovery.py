"""Comprehensive test suite for WS3: Enterprise SaaS, License, and M365 Discovery."""

import uuid
from unittest.mock import MagicMock

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from connector_adapters.live_cost import ProviderFailure
from connector_adapters.m365_discovery import (
    M365DiscoveryConnector,
    validate_m365_configuration,
)
from connector_orchestration.trigger import ConnectorTriggerType
from connector_registry.live_sources import LiveSourceRepository
from services.live_source_service import LiveSourceService
from services.saas_discovery_intelligence_service import (
    SaaSDiscoveryIntelligenceService,
)


@pytest.fixture
def mock_fernet(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", "sJ_hQ1s36WlH-vG4eZgP8jKxTmNxqW9d0FzV1s2A3b4=")


@pytest.fixture
def tenant_a():
    org_id = str(uuid.uuid4())
    return AuthenticatedTenantContext(
        organization_id=org_id,
        organization_name="Enterprise Alpha",
        user_id="admin@alpha.com",
        user_email="admin@alpha.com",
        role="client_admin",
        authorization_claims=frozenset(["admin"]),
        tenant_id=org_id,
    )


@pytest.fixture
def tenant_b():
    org_id = str(uuid.uuid4())
    return AuthenticatedTenantContext(
        organization_id=org_id,
        organization_name="Enterprise Beta",
        user_id="admin@beta.com",
        user_email="admin@beta.com",
        role="client_admin",
        authorization_claims=frozenset(["admin"]),
        tenant_id=org_id,
    )


@pytest.fixture
def service_and_repo(tmp_path, mock_fernet):
    db_path = tmp_path / "connectors_m365.db"
    repo = LiveSourceRepository(db_path)
    service = LiveSourceService(repo)
    return service, repo


# ============================================================
# 1. M365 Configuration & Credential Validation
# ============================================================

def test_validate_m365_configuration():
    valid = {
        "tenant_id": str(uuid.uuid4()),
        "client_id": str(uuid.uuid4()),
    }
    assert validate_m365_configuration(valid) == valid

    with pytest.raises(ProviderFailure):
        validate_m365_configuration({**valid, "tenant_id": "not-a-uuid"})


def test_m365_credential_security_no_plaintext_stored(service_and_repo, tenant_a):
    service, repo = service_and_repo
    m365_tenant = str(uuid.uuid4())
    m365_client = str(uuid.uuid4())

    created = service.create(
        tenant_a,
        provider="m365",
        display_name="Enterprise M365",
        configuration={"tenant_id": m365_tenant, "client_id": m365_client},
        secrets={"client_secret": "super-secret-m365-client-secret"},
    )

    assert "credential_ciphertext" not in created
    assert "client_secret" not in created

    with repo.transaction() as db:
        row = db.execute(
            """
            SELECT credential_ciphertext, config_json
            FROM connector_source_config WHERE source_id=?
            """,
            (created["source_id"],),
        ).fetchone()
        assert "super-secret-m365-client-secret" not in row["credential_ciphertext"]
        assert "super-secret-m365-client-secret" not in row["config_json"]


# ============================================================
# 2. M365 Discovery: Users, Licenses, Assignments, Applications
# ============================================================

def test_m365_discovery_and_normalization_contract(service_and_repo, tenant_a):
    service, repo = service_and_repo

    m365_tenant = str(uuid.uuid4())
    m365_client = str(uuid.uuid4())

    mock_m365 = MagicMock()
    mock_m365.authenticate.return_value = True

    user_1_id = str(uuid.uuid4())
    sku_1_id = str(uuid.uuid4())
    sp_1_id = str(uuid.uuid4())

    mock_m365.extract.return_value = [
        {
            "entity_type": "license_sku",
            "sku_id": sku_1_id,
            "sku_part_number": "ENTERPRISEPACK",  # Office 365 E3
            "total_units": 100,
            "consumed_units": 85,
            "suspended_units": 0,
        },
        {
            "entity_type": "identity_user",
            "external_id": user_1_id,
            "user_principal_name": "jane.doe@enterprise.com",
            "display_name": "Jane Doe",
            "account_enabled": True,
        },
        {
            "entity_type": "license_assignment",
            "user_id": user_1_id,
            "user_principal_name": "jane.doe@enterprise.com",
            "sku_id": sku_1_id,
            "assigned": True,
            "actively_used": False,
        },
        {
            "entity_type": "application",
            "external_id": sp_1_id,
            "app_id": str(uuid.uuid4()),
            "display_name": "Salesforce Single Sign-On",
            "publisher": "Salesforce Inc",
            "account_enabled": True,
        },
    ]

    real_m365 = M365DiscoveryConnector(
        {"tenant_id": m365_tenant, "client_id": m365_client}, MagicMock()
    )
    mock_m365.normalize = real_m365.normalize
    mock_m365.validate = real_m365.validate
    service.factories = {"m365": lambda config, creds, now: mock_m365}

    # 1. Create source
    src = service.create(
        tenant_a,
        provider="m365",
        display_name="Corporate M365",
        configuration={"tenant_id": m365_tenant, "client_id": m365_client},
        secrets={"client_secret": "secret-key"},
    )
    assert src["status"] == "DRAFT"

    # 2. Validate connection
    val_res = service.validate_connection(tenant_a, src["source_id"])
    assert val_res["status"] == "READY"

    # 3. Activate
    service.set_active(tenant_a, src["source_id"], True)

    # 4. Sync
    sync_res = service.sync(
        tenant_a,
        src["source_id"],
        request_key="m365-sync-1",
        trigger=ConnectorTriggerType.MANUAL,
    )
    assert sync_res["status"] == "SUCCEEDED"
    assert sync_res["records_ingested"] == 4

    # 5. Query Governed SaaS Discovery Intelligence
    skus = SaaSDiscoveryIntelligenceService.get_license_skus(tenant_a, repository=repo)
    assert len(skus) == 1
    assert skus[0].sku_part_number == "ENTERPRISEPACK"
    assert skus[0].total_units == 100
    assert skus[0].consumed_units == 85
    assert skus[0].unassigned_units == 15
    # Explicit contract: Cost is UNKNOWN without financial contract evidence
    assert skus[0].cost == "UNKNOWN"

    assignments = SaaSDiscoveryIntelligenceService.get_license_assignments(
        tenant_a, repository=repo
    )
    assert len(assignments) == 1
    assert assignments[0].user_principal_name == "jane.doe@enterprise.com"
    assert assignments[0].assigned is True
    assert assignments[0].actively_used is False
    # Explicit contract: Utilization is UNKNOWN without activity logs
    assert assignments[0].utilization == "UNKNOWN"

    apps = SaaSDiscoveryIntelligenceService.get_discovered_applications(
        tenant_a, repository=repo
    )
    assert len(apps) == 1
    assert apps[0].display_name == "Salesforce Single Sign-On"
    assert apps[0].publisher == "Salesforce Inc"


# ============================================================
# 3. Tenant Isolation
# ============================================================

def test_tenant_isolation_m365_evidence(service_and_repo, tenant_a, tenant_b):
    service, repo = service_and_repo

    mock_m365 = MagicMock()
    mock_m365.authenticate.return_value = True
    mock_m365.extract.return_value = [
        {
            "entity_type": "identity_user",
            "external_id": str(uuid.uuid4()),
            "user_principal_name": "alpha.user@alpha.com",
            "display_name": "Alpha User",
            "account_enabled": True,
        }
    ]
    real_m365 = M365DiscoveryConnector(
        {"tenant_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4())}, MagicMock()
    )
    mock_m365.normalize = real_m365.normalize
    mock_m365.validate = real_m365.validate
    service.factories = {"m365": lambda config, creds, now: mock_m365}

    src_a = service.create(
        tenant_a,
        provider="m365",
        display_name="Alpha M365",
        configuration={"tenant_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4())},
        secrets={"client_secret": "alpha-secret"},
    )
    service.validate_connection(tenant_a, src_a["source_id"])
    service.set_active(tenant_a, src_a["source_id"], True)
    service.sync(tenant_a, src_a["source_id"], request_key="alpha-sync")

    # Tenant B has 0 evidence/assignments/apps
    apps_b = SaaSDiscoveryIntelligenceService.get_discovered_applications(
        tenant_b, repository=repo
    )
    assert len(apps_b) == 0

    skus_b = SaaSDiscoveryIntelligenceService.get_license_skus(tenant_b, repository=repo)
    assert len(skus_b) == 0


# ============================================================
# 4. Hardening Tests: Pagination, Permission Failure & Unknowns
# ============================================================

def test_m365_pagination_multiple_pages_and_publisher_fallback():
    mock_client = MagicMock()
    # Page 1 with nextLink, Page 2 terminal
    page1 = {
        "value": [
            {"id": "sp-1", "displayName": "Custom Internal App", "accountEnabled": True}
        ],
        "@odata.nextLink": "https://graph.microsoft.com/v1.0/servicePrincipals?$skiptoken=X",
    }
    page2 = {
        "value": [
            {
                "id": "sp-2",
                "displayName": "Partner Tool",
                "publisherName": "Partner Corp",
                "accountEnabled": True,
            }
        ]
    }

    def fake_request(method, url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "$skiptoken=X" in url:
            resp.json.return_value = page2
        else:
            resp.json.return_value = page1
        return resp

    mock_client.request.side_effect = fake_request

    connector = M365DiscoveryConnector(
        {"tenant_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4())},
        MagicMock(),
        client=mock_client,
    )
    connector.headers = {"Authorization": "Bearer token"}

    records = list(
        connector._iter_graph_collection(
            "https://graph.microsoft.com/v1.0/servicePrincipals"
        )
    )
    assert len(records) == 2
    assert records[0]["displayName"] == "Custom Internal App"
    assert records[1]["displayName"] == "Partner Tool"

    # Verify publisher fallback does NOT default to Microsoft
    normalized = connector.normalize(
        [
            {
                "entity_type": "application",
                "external_id": "sp-1",
                "display_name": "Custom Internal App",
                "publisher": records[0].get("publisherName"),
                "account_enabled": True,
            }
        ]
    )
    app_payload = normalized[0].payload["application"]
    assert app_payload["publisher"] == "UNKNOWN"
    assert app_payload["publisher"] != "Microsoft"


def test_m365_untrusted_nextlink_rejection():
    mock_client = MagicMock()
    malicious_page = {
        "value": [{"id": "u-1"}],
        "@odata.nextLink": "https://attacker.com/evil/data",
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = malicious_page
    mock_client.request.return_value = resp

    connector = M365DiscoveryConnector(
        {"tenant_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4())},
        MagicMock(),
        client=mock_client,
    )
    connector.headers = {"Authorization": "Bearer token"}

    with pytest.raises(ProviderFailure, match="MALFORMED_RESPONSE"):
        list(
            connector._iter_graph_collection(
                "https://graph.microsoft.com/v1.0/users"
            )
        )


def test_m365_service_principal_permission_denial_fails_explicitly():
    mock_client = MagicMock()
    resp = MagicMock()
    resp.status_code = 403
    mock_client.request.return_value = resp

    connector = M365DiscoveryConnector(
        {"tenant_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4())},
        MagicMock(),
        client=mock_client,
    )
    connector.headers = {"Authorization": "Bearer token"}

    with pytest.raises(ProviderFailure, match="PERMISSION_DENIED"):
        connector.extract()
