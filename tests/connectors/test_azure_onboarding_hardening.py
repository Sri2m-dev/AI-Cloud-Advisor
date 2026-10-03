from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from connectors.azure import azure_credential_manager as manager_module
from connectors.azure.azure_credential_manager import (
    AzureCredentialManager,
)
from connectors.azure.azure_production_connector import AzureProductionConnector
from services import azure_connector_service as service_module
from services.azure_connector_service import AzureConnectorService
from services.demo_tenant_service import DEMO_ORGANIZATION_ID, DEMO_ORGANIZATION_NAME

SUBSCRIPTION = "49ce7e88-e929-4031-b5b2-c8b557e5da2d"
OTHER_SUBSCRIPTION = "11111111-2222-4333-8444-555555555555"
ORG = "org-azure-test"


class FakeDefaultCredential:
    def __init__(self, **kwargs):
        self.kind = "default"

    def get_token(self, scope):
        return SimpleNamespace(token="redacted", expires_on=4_000_000_000)


class FakeSecretCredential:
    def __init__(self, tenant_id, client_id, client_secret):
        self.kind = "service_principal"
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret

    def get_token(self, scope):
        return SimpleNamespace(token="redacted", expires_on=4_000_000_000)


class FakeResourceClient:
    seen_subscriptions: list[str] = []

    def __init__(self, credential, subscription_id):
        FakeResourceClient.seen_subscriptions.append(subscription_id)
        allowed = subscription_id == SUBSCRIPTION
        self.resource_groups = SimpleNamespace(list=lambda: self._items(allowed))
        self.resources = SimpleNamespace(list=lambda: self._items(allowed))

    @staticmethod
    def _items(allowed):
        if not allowed:
            raise RuntimeError("SubscriptionNotFound with sensitive detail")
        return iter([SimpleNamespace(name="rg")])


@pytest.fixture(autouse=True)
def fake_azure(monkeypatch):
    FakeResourceClient.seen_subscriptions = []
    monkeypatch.setattr(manager_module, "DefaultAzureCredential", FakeDefaultCredential)
    monkeypatch.setattr(manager_module, "ClientSecretCredential", FakeSecretCredential)
    monkeypatch.setattr(manager_module, "ResourceManagementClient", FakeResourceClient)


class FakeQuery:
    def __init__(self, store, name):
        self.store = store
        self.name = name

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def upsert(self, payload, **_kwargs):
        self.store.upserts.append((self.name, payload))
        return self

    def execute(self):
        return SimpleNamespace(data=list(self.store.rows))


class FakeSupabase:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.upserts = []

    def table(self, name):
        return FakeQuery(self, name)


@pytest.fixture
def supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(service_module, "supabase", fake)
    monkeypatch.setattr(service_module, "resolve_organization_id", lambda value=None: value or ORG)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("diagnostic must not write registry or history")

    monkeypatch.setattr(AzureConnectorService, "_upsert_connector_registry", forbidden)
    monkeypatch.setattr(AzureConnectorService, "_insert_sync_history", forbidden)
    return fake


def test_runtime_identity_requires_only_subscription_id(supabase):
    result = AzureConnectorService.test_connection(
        subscription_id=SUBSCRIPTION, auth_method="runtime_identity"
    )

    assert result["status"] == "CONNECTED"
    assert result["checks"]["authentication"] == "PASS"
    assert result["checks"]["cost_management"] == "NOT_TESTED"

    missing = AzureConnectorService.test_connection(auth_method="runtime_identity")
    assert missing["status"] == "FAILED"
    assert "Subscription ID" in missing["error"]


def test_runtime_identity_never_consumes_saved_service_principal_values():
    manager = AzureCredentialManager(
        "tenant", "client", "raw-secret", SUBSCRIPTION,
        auth_method="runtime_identity", secret_ref="SOME_REF",
    )
    assert (manager.tenant_id, manager.client_id, manager.client_secret, manager.secret_ref) == (
        None, None, None, None,
    )
    assert manager.credential().kind == "default"

    saved = {
        "auth_method": "service_principal",
        "tenant_id": "saved-tenant",
        "client_id": "saved-client",
        "secret_ref": "SAVED_REF",
        "subscription_id": SUBSCRIPTION,
    }
    connector = AzureConnectorService._connector_for(
        saved, None, None, None, None, "runtime_identity", None
    )
    assert connector.credential_manager.auth_method == "runtime_identity"
    assert connector.credential_manager.tenant_id is None
    assert connector.credential_manager.secret_ref is None
    assert connector.credential.kind == "default"


def test_runtime_identity_saved_config_ignores_service_principal_fields():
    saved = {"auth_method": "runtime_identity", "tenant_id": "t", "client_id": "c",
             "secret_ref": "REF", "subscription_id": SUBSCRIPTION}
    connector = AzureConnectorService._connector_for(saved, "x", "y", "z", None, None, "R")
    assert connector.credential_manager.client_secret is None
    assert connector.credential_manager.client_id is None


def test_test_connection_does_not_mutate_registry(supabase):
    AzureConnectorService.test_connection(
        subscription_id=SUBSCRIPTION, auth_method="runtime_identity", organization_id=ORG
    )
    AzureConnectorService.test_connection(
        subscription_id=OTHER_SUBSCRIPTION, auth_method="runtime_identity", organization_id=ORG
    )

    assert supabase.upserts == []


def test_test_connection_reads_the_exact_requested_subscription(supabase):
    AzureConnectorService.test_connection(
        subscription_id=SUBSCRIPTION, auth_method="runtime_identity"
    )

    assert FakeResourceClient.seen_subscriptions == [SUBSCRIPTION]


def test_wrong_or_unreachable_subscription_fails_without_leaking_detail(supabase):
    result = AzureConnectorService.test_connection(
        subscription_id=OTHER_SUBSCRIPTION, auth_method="runtime_identity"
    )

    assert result["status"] == "FAILED"
    assert result["checks"]["authentication"] == "PASS"
    assert result["checks"]["subscription_access"] == "FAIL"
    assert "sensitive detail" not in str(result)

    malformed = AzureConnectorService.test_connection(
        subscription_id="not-a-guid", auth_method="runtime_identity"
    )
    assert malformed["status"] == "FAILED"


def test_save_config_never_persists_raw_client_secret(supabase):
    result = AzureConnectorService.save_config(
        ORG, "admin", "tenant", "client", "super-secret-value", SUBSCRIPTION,
        auth_method="service_principal", secret_ref="AZURE_SP_SECRET", connection_name="Prod",
    )

    assert result["status"] == "SAVED"
    _table, payload = supabase.upserts[-1]
    assert "client_secret" not in payload["metadata"]
    assert "super-secret-value" not in str(supabase.upserts)
    assert payload["metadata"]["secret_ref"] == "AZURE_SP_SECRET"
    assert payload["metadata"]["connection_name"] == "Prod"


def test_save_config_persists_auth_method_and_clears_sp_fields_for_runtime(supabase):
    supabase.rows = [{
        "connector_name": "Azure",
        "metadata": {"auth_method": "service_principal", "tenant_id": "t", "client_id": "c",
                     "secret_ref": "REF", "client_secret": "legacy-plaintext"},
    }]

    AzureConnectorService.save_config(
        ORG, "admin", None, None, None, SUBSCRIPTION, auth_method="runtime_identity"
    )

    metadata = supabase.upserts[-1][1]["metadata"]
    assert metadata["auth_method"] == "runtime_identity"
    assert metadata["tenant_id"] is None
    assert metadata["client_id"] is None
    assert metadata["secret_ref"] is None
    assert "client_secret" not in metadata


def test_service_principal_without_resolvable_reference_fails_closed(supabase, monkeypatch):
    monkeypatch.delenv("UNSET_AZURE_REF", raising=False)

    result = AzureConnectorService.test_connection(
        "tenant", "client", None, SUBSCRIPTION,
        auth_method="service_principal", secret_ref="UNSET_AZURE_REF",
    )
    assert result["status"] == "FAILED"
    assert result["checks"]["authentication"] == "FAIL"

    unsaved = AzureConnectorService.save_config(
        ORG, "admin", "tenant", "client", None, SUBSCRIPTION, auth_method="service_principal"
    )
    assert unsaved["status"] == "FAILED"
    assert supabase.upserts == []


def test_service_principal_resolves_reference_from_runtime_environment(supabase, monkeypatch):
    monkeypatch.setenv("AZURE_SP_REF_FOR_TEST", "resolved-value")

    result = AzureConnectorService.test_connection(
        "tenant", "client", None, SUBSCRIPTION,
        auth_method="service_principal", secret_ref="AZURE_SP_REF_FOR_TEST",
    )

    assert result["status"] == "CONNECTED"


def test_get_config_does_not_return_legacy_plaintext_secret(supabase):
    supabase.rows = [{"connector_name": "Azure", "metadata": {"client_secret": "legacy"}}]

    config = AzureConnectorService.get_config(ORG)

    assert "client_secret" not in config
    assert config["legacy_plaintext_secret_present"] is True


def test_production_connector_runtime_identity_behavior_is_unchanged():
    connector = AzureProductionConnector(subscription_id=SUBSCRIPTION)
    assert connector.credential.kind == "default"

    explicit = AzureProductionConnector("t", "c", "s", SUBSCRIPTION)
    assert explicit.credential.kind == "service_principal"


def _azure_page(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "false")
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_ROOT", str(tmp_path / "prospect"))
    app = AppTest.from_file("pages/analyze_environment.py", default_timeout=30)
    for key, value in {
        "authenticated": True, "role": "executive", "user": "ceo@company.com",
        "email": "ceo@company.com", "user_email": "ceo@company.com",
        "user_id": "ceo@company.com", "organization_id": DEMO_ORGANIZATION_ID,
        "organization_name": DEMO_ORGANIZATION_NAME, "auth_backend": "local",
        "authorized_organization_ids": [DEMO_ORGANIZATION_ID], "permissions": [],
        "analysis_start_path": "azure",
    }.items():
        app.session_state[key] = value
    app.run()
    return app


def test_azure_page_offers_both_methods_and_no_client_secret_for_runtime_identity(
    monkeypatch, tmp_path
):
    app = _azure_page(monkeypatch, tmp_path)

    assert not app.exception
    radio = app.radio(key="azure_auth_method")
    assert list(radio.options) == ["Nexora Runtime Identity", "Service Principal"]
    labels = {widget.label for widget in app.text_input}
    assert labels == {"Connection name", "Subscription ID"}
    assert not any(widget.type == "password" for widget in app.text_input)


def test_azure_page_service_principal_uses_credential_reference_not_secret(
    monkeypatch, tmp_path
):
    app = _azure_page(monkeypatch, tmp_path)
    app.radio(key="azure_auth_method").set_value("Service Principal").run()

    labels = {widget.label for widget in app.text_input}
    assert {"Tenant ID", "Client ID", "Credential reference", "Subscription ID"} <= labels
    assert "Client Secret" not in labels
