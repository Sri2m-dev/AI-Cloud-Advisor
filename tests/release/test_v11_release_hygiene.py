"""Offline release guards: no live SDK client or credential is used."""

import runpy
import sys
from pathlib import Path
from types import ModuleType

import pytest


class ConfiguredClientReached(Exception):
    pass


@pytest.fixture
def isolated_ingestion(monkeypatch):
    configured = {
        "SUPABASE_URL": "https://synthetic.example.invalid",
        "SUPABASE_SERVICE_ROLE_KEY": "synthetic-backend-placeholder",
        "AZURE_TENANT_ID": "synthetic-tenant",
        "AZURE_CLIENT_ID": "synthetic-client",
        "AZURE_CLIENT_SECRET": "synthetic-client-placeholder",
        "AZURE_SUBSCRIPTION_ID": "synthetic-subscription",
    }
    for name, value in configured.items():
        monkeypatch.setenv(name, value)

    calls = []

    def configured_client(url, key):
        calls.append((url, key))
        raise ConfiguredClientReached

    def forbidden(*args, **kwargs):
        pytest.fail("No provider client or network operation is permitted")

    for name, attributes in {
        "config": {"DEFAULT_ORG_ID": "synthetic-org"},
        "supabase": {"create_client": configured_client},
        "boto3": {"client": forbidden},
        "azure.identity": {"ClientSecretCredential": forbidden},
        "azure.mgmt.costmanagement": {"CostManagementClient": forbidden},
    }.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    return configured, calls


@pytest.mark.parametrize("missing", ("", "   "))
@pytest.mark.parametrize(
    "script,variable",
    [("aws_athena_ingest.py", name) for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")]
    + [
        ("azure_cost_sync.py", name)
        for name in (
            "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "AZURE_TENANT_ID",
            "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID",
        )
    ],
)
def test_missing_configuration_stops_before_any_client(
    isolated_ingestion, monkeypatch, capsys, script, variable, missing
):
    configured, calls = isolated_ingestion
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(variable, missing)
    with pytest.raises(RuntimeError) as error:
        runpy.run_path(script)
    assert variable in str(error.value)
    assert not calls
    output = capsys.readouterr()
    for value in configured.values():
        assert value not in str(error.value) + output.out + output.err


@pytest.mark.parametrize("script", ("aws_athena_ingest.py", "azure_cost_sync.py"))
def test_configured_backend_credential_is_forwarded_without_output(
    isolated_ingestion, capsys, script
):
    configured, calls = isolated_ingestion
    with pytest.raises(ConfiguredClientReached):
        runpy.run_path(script)
    assert calls == [(configured["SUPABASE_URL"], configured["SUPABASE_SERVICE_ROLE_KEY"])]
    output = capsys.readouterr()
    assert not output.out and not output.err


@pytest.mark.parametrize("script", ("aws_athena_ingest.py", "azure_cost_sync.py"))
def test_publishable_key_cannot_start_backend_ingestion(
    isolated_ingestion, monkeypatch, script
):
    _, calls = isolated_ingestion
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sb_publishable_synthetic-placeholder")
    with pytest.raises(RuntimeError, match="backend credential"):
        runpy.run_path(script)
    assert not calls


def test_secondary_api_uses_release_authority():
    import ast

    tree = ast.parse(Path("api/v1/endpoints.py").read_text(encoding="utf-8"))
    versions = [
        keyword.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "FastAPI"
        for keyword in node.keywords if keyword.arg == "version"
    ]
    assert len(versions) == 1
    assert isinstance(versions[0], ast.Name) and versions[0].id == "RELEASE_VERSION"
