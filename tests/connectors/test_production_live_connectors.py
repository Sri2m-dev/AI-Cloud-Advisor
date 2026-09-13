"""Comprehensive test suite for WS2: Production Data-Source Connection & Ingestion."""

import uuid
from unittest.mock import MagicMock

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from connector_adapters.live_cost import (
    AWSLiveCostConnector,
    AzureLiveCostConnector,
    ProviderFailure,
    validate_configuration,
)
from connector_orchestration.trigger import ConnectorTriggerType
from connector_registry.live_sources import LiveSourceRepository
from services.live_source_service import LiveSourceService


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
    db_path = tmp_path / "connectors.db"
    repo = LiveSourceRepository(db_path)
    service = LiveSourceService(repo)
    return service, repo


# ============================================================
# 1. Configuration Validation & Credential Security
# ============================================================

def test_validate_configuration_aws_and_azure():
    # Valid AWS
    valid_aws = {
        "account_id": "123456789012",
        "role_arn": "arn:aws:iam::123456789012:role/BillingRole",
        "region": "us-east-1",
    }
    assert validate_configuration("aws", valid_aws) == valid_aws

    # Invalid AWS Account ID
    with pytest.raises(ProviderFailure):
        validate_configuration("aws", {**valid_aws, "account_id": "123"})

    # Valid Azure
    valid_azure = {
        "tenant_id": str(uuid.uuid4()),
        "subscription_id": str(uuid.uuid4()),
        "client_id": str(uuid.uuid4()),
    }
    assert validate_configuration("azure", valid_azure) == valid_azure

    # Invalid Azure UUID
    with pytest.raises(ProviderFailure):
        validate_configuration("azure", {**valid_azure, "tenant_id": "invalid-uuid"})


def test_credential_security_no_plaintext_secrets_stored(service_and_repo, tenant_a):
    service, repo = service_and_repo
    created = service.create(
        tenant_a,
        provider="aws",
        display_name="Secure AWS Source",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/BillingRole",
            "region": "us-east-1",
        },
        secrets={"external_id": "super-secret-external-id"},
    )

    # Public representation must not include secrets or ciphertext
    assert "credential_ciphertext" not in created
    assert "external_id" not in created
    assert "config_json" not in created

    # Verify underlying DB record contains ONLY ciphertext, no plaintext secret
    with repo.transaction() as db:
        row = db.execute(
            """
            SELECT credential_ciphertext, config_json
            FROM connector_source_config WHERE source_id=?
            """,
            (created["source_id"],),
        ).fetchone()
        assert row is not None
        assert "super-secret-external-id" not in row["credential_ciphertext"]
        assert "super-secret-external-id" not in row["config_json"]


# ============================================================
# 2. Tenant Isolation
# ============================================================

def test_tenant_isolation_cannot_access_or_sync_other_tenant_sources(
    service_and_repo, tenant_a, tenant_b
):
    service, _ = service_and_repo

    # Tenant A creates source
    src_a = service.create(
        tenant_a,
        provider="aws",
        display_name="Tenant A AWS",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/RoleA",
            "region": "us-east-1",
        },
        secrets={},
    )

    # Tenant B lists sources -> empty
    sources_b = service.list_sources(tenant_b)
    assert len(sources_b) == 0

    # Tenant B tries to validate Tenant A source -> PermissionError
    with pytest.raises(PermissionError):
        service.validate_connection(tenant_b, src_a["source_id"])

    # Tenant B tries to sync Tenant A source -> PermissionError
    with pytest.raises(PermissionError):
        service.sync(tenant_b, src_a["source_id"], request_key="key-b")


# ============================================================
# 3. AWS Connector: Validation & Ingestion Mock Contract
# ============================================================

def test_aws_connector_validation_and_sync_flow(service_and_repo, tenant_a):
    service, repo = service_and_repo

    # Create mock AWS connector factory
    mock_connector = MagicMock()
    mock_connector.authenticate.return_value = True
    mock_connector.extract.return_value = [
        {
            "start": "2026-09-01",
            "end": "2026-09-02",
            "service": "Amazon Elastic Compute Cloud",
            "amount": "125.50",
            "currency": "USD",
            "estimated": False,
        },
        {
            "start": "2026-09-01",
            "end": "2026-09-02",
            "service": "Amazon Simple Storage Service",
            "amount": "45.00",
            "currency": "USD",
            "estimated": False,
        },
    ]

    real_aws = AWSLiveCostConnector(
        {
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        MagicMock(),
    )
    mock_connector.normalize = real_aws.normalize
    mock_connector.validate = real_aws.validate

    service.factories = {"aws": lambda config, creds, now: mock_connector}

    # 1. Create source in DRAFT
    src = service.create(
        tenant_a,
        provider="aws",
        display_name="AWS Cloud",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        secrets={},
    )
    assert src["status"] == "DRAFT"

    # 2. Cannot activate unvalidated source
    with pytest.raises(ProviderFailure, match="VALIDATION_REQUIRED"):
        service.set_active(tenant_a, src["source_id"], True)

    # 3. Validate connection
    val_res = service.validate_connection(tenant_a, src["source_id"])
    assert val_res["status"] == "READY"
    assert val_res["error_category"] is None

    # 4. Activate source
    service.set_active(tenant_a, src["source_id"], True)
    sources = service.list_sources(tenant_a)
    assert sources[0]["status"] == "ACTIVE"

    # 5. Manual Sync Execution
    sync_res = service.sync(
        tenant_a,
        src["source_id"],
        request_key="manual-sync-1",
        trigger=ConnectorTriggerType.MANUAL,
    )
    assert sync_res["status"] == "SUCCEEDED"
    assert sync_res["records_discovered"] == 2
    assert sync_res["records_ingested"] == 2
    assert sync_res["evidence_reference"].startswith(f"sourcefacts:{src['source_id']}:")

    # 6. Idempotent sync returns existing result
    repeat_res = service.sync(
        tenant_a,
        src["source_id"],
        request_key="manual-sync-1",
        trigger=ConnectorTriggerType.MANUAL,
    )
    assert repeat_res["execution_id"] == sync_res["execution_id"]


# ============================================================
# 4. Azure Connector: Validation & Ingestion Mock Contract
# ============================================================

def test_azure_connector_validation_and_sync_flow(service_and_repo, tenant_a):
    service, repo = service_and_repo

    mock_az_connector = MagicMock()
    mock_az_connector.authenticate.return_value = True
    mock_az_connector.extract.return_value = [
        {
            "start": "2026-09-01",
            "end": "2026-09-02",
            "service": "Virtual Machines",
            "amount": "210.00",
            "currency": "USD",
        }
    ]

    sub_id = str(uuid.uuid4())
    real_az = AzureLiveCostConnector(
        {
            "tenant_id": str(uuid.uuid4()),
            "subscription_id": sub_id,
            "client_id": str(uuid.uuid4()),
        },
        MagicMock(),
    )
    mock_az_connector.normalize = real_az.normalize
    mock_az_connector.validate = real_az.validate

    service.factories = {"azure": lambda config, creds, now: mock_az_connector}

    # 1. Create Azure source
    src = service.create(
        tenant_a,
        provider="azure",
        display_name="Enterprise Azure",
        configuration={
            "tenant_id": str(uuid.uuid4()),
            "subscription_id": sub_id,
            "client_id": str(uuid.uuid4()),
        },
        secrets={"client_secret": "my-client-secret-123"},
    )
    assert src["status"] == "DRAFT"

    # 2. Validate
    val = service.validate_connection(tenant_a, src["source_id"])
    assert val["status"] == "READY"

    # 3. Activate
    service.set_active(tenant_a, src["source_id"], True)

    # 4. Sync
    sync_res = service.sync(
        tenant_a,
        src["source_id"],
        request_key="manual-az-1",
        trigger=ConnectorTriggerType.MANUAL,
    )
    assert sync_res["status"] == "SUCCEEDED"
    assert sync_res["records_ingested"] == 1


# ============================================================
# 5. Scheduling & Run Due Contract
# ============================================================

def test_scheduling_and_run_due(service_and_repo, tenant_a):
    service, repo = service_and_repo

    mock_conn = MagicMock()
    mock_conn.authenticate.return_value = True
    mock_conn.extract.return_value = [
        {
            "start": "2026-09-01",
            "end": "2026-09-02",
            "service": "Compute",
            "amount": "50.00",
            "currency": "USD",
        }
    ]
    real_aws = AWSLiveCostConnector(
        {
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        MagicMock(),
    )
    mock_conn.normalize = real_aws.normalize
    mock_conn.validate = real_aws.validate
    service.factories = {"aws": lambda config, creds, now: mock_conn}

    src = service.create(
        tenant_a,
        provider="aws",
        display_name="Scheduled AWS",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        secrets={},
    )
    service.validate_connection(tenant_a, src["source_id"])
    service.set_active(tenant_a, src["source_id"], True)

    # Enable daily schedule (86400s)
    service.set_schedule(tenant_a, src["source_id"], enabled=True, cadence_seconds=86400)

    sources = service.list_sources(tenant_a)
    assert sources[0]["schedule_enabled"] == 1
    assert sources[0]["next_run_at"] is not None


# ============================================================
# 6. Failure Behavior & Safe Error Redaction
# ============================================================

def test_failure_behavior_and_safe_error_summary(service_and_repo, tenant_a):
    service, _ = service_and_repo

    mock_fail_conn = MagicMock()
    mock_fail_conn.authenticate.side_effect = PermissionError("AccessDenied to Cost Explorer")

    service.factories = {"aws": lambda config, creds, now: mock_fail_conn}

    src = service.create(
        tenant_a,
        provider="aws",
        display_name="Failing AWS",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        secrets={},
    )

    # Validation failure sets status to ERROR and records safe summary
    val = service.validate_connection(tenant_a, src["source_id"])
    assert val["status"] == "ERROR"
    assert val["error_category"] in {"PERMISSION_DENIED", "AUTHENTICATION", "PROVIDER_ERROR"}
    # Ensure error summary does not leak internal stack traces
    assert "Role" not in str(val["safe_error_summary"])


def test_non_admin_cannot_create_or_validate_sources(service_and_repo, tenant_a):
    service, _ = service_and_repo
    non_admin = AuthenticatedTenantContext(
        organization_id=tenant_a.organization_id,
        organization_name=tenant_a.organization_name,
        user_id="viewer@alpha.com",
        user_email="viewer@alpha.com",
        role="viewer",
        authorization_claims=frozenset(),
        tenant_id=tenant_a.tenant_id,
    )

    with pytest.raises(PermissionError, match="Tenant administrator authority"):
        service.create(
            non_admin,
            provider="aws",
            display_name="Unauthorized AWS",
            configuration={
                "account_id": "123456789012",
                "role_arn": "arn:aws:iam::123456789012:role/Role",
                "region": "us-east-1",
            },
            secrets={},
        )


def test_data_fabric_source_fact_handoff_and_persistence(service_and_repo, tenant_a):
    service, repo = service_and_repo

    mock_conn = MagicMock()
    mock_conn.authenticate.return_value = True
    mock_conn.extract.return_value = [
        {
            "start": "2026-09-01",
            "end": "2026-09-02",
            "service": "Amazon DynamoDB",
            "amount": "88.20",
            "currency": "USD",
        }
    ]
    real_aws = AWSLiveCostConnector(
        {
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        MagicMock(),
    )
    mock_conn.normalize = real_aws.normalize
    mock_conn.validate = real_aws.validate
    service.factories = {"aws": lambda config, creds, now: mock_conn}

    src = service.create(
        tenant_a,
        provider="aws",
        display_name="DynamoDB Source",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        secrets={},
    )
    service.validate_connection(tenant_a, src["source_id"])
    service.set_active(tenant_a, src["source_id"], True)

    sync_res = service.sync(
        tenant_a,
        src["source_id"],
        request_key="dynamo-sync-1",
        trigger=ConnectorTriggerType.MANUAL,
    )
    assert sync_res["status"] == "SUCCEEDED"

    # Verify Data Fabric persistence directly
    with repo.transaction() as db:
        facts = db.execute(
            "SELECT * FROM source_facts WHERE organization_id=? AND tenant_id=?",
            (tenant_a.organization_id, tenant_a.tenant_id),
        ).fetchall()
        assert len(facts) >= 1
        assert facts[0]["fact_type"] == "cloud_cost"
