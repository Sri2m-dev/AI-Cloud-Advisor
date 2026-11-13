from uuid import uuid4

from services.aws_connector_service import AWSConnectorService
from services.demo_tenant_service import DEMO_ORGANIZATION_ID


def _tenant_id():
    return str(uuid4())


def test_demo_tenant_sync_is_rejected_before_configuration_or_cloud_access(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("demo sync must stop before database or cloud access")

    monkeypatch.setattr(AWSConnectorService, "get_config", forbidden)
    monkeypatch.setattr(AWSConnectorService, "_build_connector", forbidden)

    result = AWSConnectorService.sync_all(organization_id=DEMO_ORGANIZATION_ID)

    assert result["status"] == "REJECTED"
    assert result["discovery_status"] == "NOT_STARTED"
    assert result["persistence_status"] == "NOT_ATTEMPTED"
    assert result["dashboard_readiness"] == "UNKNOWN"


def test_non_demo_discovery_counts_are_not_reported_as_persisted(monkeypatch):
    organization_id = _tenant_id()
    calls = []

    class FakeConnector:
        def sync_accounts(self):
            calls.append("accounts")
            return [{"account_id": "aws-account"}]

        def sync_costs(self):
            calls.append("costs")
            return [{"cost": 42}]

        def sync_resources(self):
            calls.append("resources")
            return [{"resource_id": "aws-resource"}]

        def sync_recommendations(self):
            calls.append("recommendations")
            return [{"title": "recommendation"}]

    def forbidden_persistence(*_args, **_kwargs):
        raise AssertionError("legacy persistence must not be attempted")

    monkeypatch.setattr(AWSConnectorService, "get_config", lambda _org: {})
    monkeypatch.setattr(
        AWSConnectorService, "_build_connector", lambda *_args, **_kwargs: FakeConnector()
    )
    for method in (
        "_upsert_cloud_accounts",
        "_upsert_rows",
        "_upsert_relationships",
        "_upsert_relationship_graph",
        "_insert_rows",
        "_upsert_discovered_assets",
        "_insert_sync_history",
        "_upsert_connector_registry",
    ):
        monkeypatch.setattr(AWSConnectorService, method, forbidden_persistence)

    result = AWSConnectorService.sync_all(organization_id=organization_id)

    assert calls == ["accounts", "costs", "resources", "recommendations"]
    assert result["status"] == "PARTIAL"
    assert result["discovery_status"] == "SUCCESS"
    assert result["retrieved_counts"] == {
        "accounts": 1,
        "costs": 1,
        "resources": 1,
        "recommendations": 1,
    }
    assert result["financial_ingestion_status"] == "BLOCKED"
    assert result["persistence_status"] == "NOT_ATTEMPTED"
    assert result["persistence_reason"] == "TENANT_SCOPED_LEGACY_WRITE_UNAVAILABLE"
    assert result["dashboard_readiness"] == "UNKNOWN"
    assert "persisted_counts" not in result
    assert "objects_synced" not in result


def test_aws_discovery_failure_does_not_return_success_or_claim_persistence(monkeypatch):
    def fail_discovery(*_args, **_kwargs):
        raise RuntimeError("contains secret or provider detail")

    monkeypatch.setattr(AWSConnectorService, "get_config", lambda _org: {})
    monkeypatch.setattr(AWSConnectorService, "_build_connector", fail_discovery)

    result = AWSConnectorService.sync_all(organization_id=_tenant_id())

    assert result["status"] == "FAILED"
    assert result["discovery_status"] == "FAILED"
    assert result["persistence_status"] == "NOT_ATTEMPTED"
    assert result["dashboard_readiness"] == "UNKNOWN"
    assert "secret" not in result["error"]


def test_partial_discovery_failure_preserves_retrieved_counts(monkeypatch):
    class FakeConnector:
        def sync_accounts(self):
            return [{"account_id": "aws-account"}]

        def sync_costs(self):
            raise RuntimeError("provider error")

    monkeypatch.setattr(AWSConnectorService, "get_config", lambda _org: {})
    monkeypatch.setattr(
        AWSConnectorService, "_build_connector", lambda *_args, **_kwargs: FakeConnector()
    )

    result = AWSConnectorService.sync_all(organization_id=_tenant_id())

    assert result["status"] == "PARTIAL"
    assert result["discovery_status"] == "PARTIAL"
    assert result["retrieved_counts"] == {
        "accounts": 1,
        "costs": 0,
        "resources": 0,
        "recommendations": 0,
    }
    assert result["financial_ingestion_status"] == "BLOCKED"
    assert result["persistence_status"] == "NOT_ATTEMPTED"
    assert "provider error" not in result["error"]
