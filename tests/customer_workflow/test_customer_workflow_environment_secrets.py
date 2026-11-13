import pytest

from services.customer_workflow_service import (
    CustomerWorkflowError,
    _configured_secret,
)


def test_configured_secret_reads_mounted_secret_file(monkeypatch, tmp_path):
    secret_file = tmp_path / "workflow-key"
    secret_file.write_text("synthetic-key\n", encoding="ascii")
    monkeypatch.delenv("NEXORA_CUSTOMER_WORKFLOW_KEY", raising=False)
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_KEY_FILE", str(secret_file))

    assert _configured_secret("NEXORA_CUSTOMER_WORKFLOW_KEY") == "synthetic-key"


def test_configured_secret_prefers_explicit_value_over_secret_file(
    monkeypatch, tmp_path
):
    secret_file = tmp_path / "workflow-key"
    secret_file.write_text("mounted-key\n", encoding="ascii")
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_KEY", "explicit-key")
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_KEY_FILE", str(secret_file))

    assert _configured_secret("NEXORA_CUSTOMER_WORKFLOW_KEY") == "explicit-key"


def test_configured_secret_surfaces_missing_secret_file(monkeypatch, tmp_path):
    missing_file = tmp_path / "missing-key"
    monkeypatch.delenv("NEXORA_CUSTOMER_WORKFLOW_KEY", raising=False)
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_KEY_FILE", str(missing_file))

    with pytest.raises(CustomerWorkflowError, match="could not be read"):
        _configured_secret("NEXORA_CUSTOMER_WORKFLOW_KEY")
