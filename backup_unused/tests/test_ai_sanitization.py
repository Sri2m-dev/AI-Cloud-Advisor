"""
Tests for AI layer sanitization, gating, and fail-safe behaviour.
Run with:  pytest tests/test_ai_sanitization.py -v
"""
import os
import importlib
import sys
import types
import pytest

# ---------------------------------------------------------------------------
# Helpers to import only the pure functions from demo_ceo/app.py
# without triggering Streamlit runtime or page_config errors.
# ---------------------------------------------------------------------------

def _load_app_module():
    """
    Import demo_ceo/app.py with Streamlit stubbed out so the module-level
    st.* calls don't raise outside a running Streamlit process.
    """
    # Build a minimal stub for the `streamlit` package
    st_stub = types.ModuleType("streamlit")
    for attr in (
        "markdown", "set_page_config", "caption", "info", "warning",
        "success", "error", "columns", "expander", "button",
        "download_button", "dataframe", "radio", "sidebar",
    ):
        setattr(st_stub, attr, lambda *a, **kw: None)
    st_stub.session_state = {}

    pd_real = importlib.import_module("pandas")
    px_real = importlib.import_module("plotly.express")

    sys.modules.setdefault("streamlit", st_stub)
    sys.modules.setdefault("pandas", pd_real)
    sys.modules.setdefault("plotly.express", px_real)

    spec = importlib.util.spec_from_file_location(
        "demo_ceo_app",
        os.path.join(os.path.dirname(__file__), "..", "demo_ceo", "app.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

mock_resource = {
    # Safe fields — should be forwarded
    "type": "EC2",
    "cpu_avg": 8.5,
    "memory_avg": 22.0,
    "monthly_cost": 420.0,
    "waste_estimate": 310.0,
    "rule_triggered": "cpu_under_10_pct",
    # Sensitive fields — must NEVER appear in payload
    "instance_id": "i-0abc123def456",
    "account_id": "123456789012",
    "ip_address": "10.0.1.45",
    "private_ip": "172.16.0.5",
    "public_ip": "54.23.11.200",
    "logs": "[ERROR] timeout at 03:12",
    "tags": {"client_name": "AcmeCorp", "env": "prod"},
    "client_name": "AcmeCorp",
    "client_id": "client-99",
    "owner": "john.doe@example.com",
    "owner_id": "usr-001",
    "user_id": "usr-001",
    "username": "jdoe",
    "email": "jdoe@example.com",
    "arn": "arn:aws:iam::123456789012:role/MyRole",
    "resource_id": "res-999",
    "resource_name": "prod-web-server",
    "identifier": "some-unique-id",
    "hostname": "ip-172-16-0-5.ec2.internal",
    "dns_name": "ec2-54-23-11-200.compute-1.amazonaws.com",
    "vpc_id": "vpc-0a1b2c3d",
    "subnet_id": "subnet-0a1b2c3d",
    "security_group_id": "sg-0a1b2c3d",
    "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
    "access_key": "AKIAIOSFODNN7EXAMPLE",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSanitizeForAI:
    """sanitize_for_ai() must strip all sensitive fields when AI is disabled."""

    def setup_method(self):
        # Ensure AI is disabled during sanitization tests
        os.environ["AI_ENABLED"] = "false"
        os.environ["LLM_PROVIDER"] = "none"

    def test_returns_disabled_string_when_ai_off(self):
        app = _load_app_module()
        result = app.sanitize_for_ai(mock_resource)
        assert isinstance(result, str)
        assert "disabled" in result.lower()

    def test_no_instance_id_in_payload(self):
        """Instance IDs must never reach the AI layer."""
        os.environ["AI_ENABLED"] = "true"
        app = _load_app_module()
        payload = app.sanitize_for_ai(mock_resource)
        assert "instance_id" not in payload

    def test_no_account_id_in_payload(self):
        os.environ["AI_ENABLED"] = "true"
        app = _load_app_module()
        payload = app.sanitize_for_ai(mock_resource)
        assert "account_id" not in payload

    def test_no_ip_address_in_payload(self):
        os.environ["AI_ENABLED"] = "true"
        app = _load_app_module()
        payload = app.sanitize_for_ai(mock_resource)
        assert "ip_address" not in payload
        assert "private_ip" not in payload
        assert "public_ip" not in payload

    def test_no_logs_in_payload(self):
        os.environ["AI_ENABLED"] = "true"
        app = _load_app_module()
        payload = app.sanitize_for_ai(mock_resource)
        assert "logs" not in payload

    def test_no_client_identifiers_in_payload(self):
        os.environ["AI_ENABLED"] = "true"
        app = _load_app_module()
        payload = app.sanitize_for_ai(mock_resource)
        for sensitive in ("client_name", "client_id", "tags", "owner",
                          "username", "email", "arn", "access_key",
                          "vpc_id", "subnet_id", "security_group_id"):
            assert sensitive not in payload, f"Sensitive field leaked: {sensitive}"

    def test_only_allowed_fields_present(self):
        os.environ["AI_ENABLED"] = "true"
        app = _load_app_module()
        payload = app.sanitize_for_ai(mock_resource)
        allowed = set(app.ALLOWED_FIELDS)
        assert set(payload.keys()) == allowed, (
            f"Unexpected fields in payload: {set(payload.keys()) - allowed}"
        )

    def test_allowed_field_values_correct(self):
        os.environ["AI_ENABLED"] = "true"
        app = _load_app_module()
        payload = app.sanitize_for_ai(mock_resource)
        assert payload["resource_type"] == "EC2"
        assert payload["cpu_avg"] == 8.5
        assert payload["waste_estimate"] == 310.0
        assert payload["rule_triggered"] == "cpu_under_10_pct"

    def teardown_method(self):
        os.environ.pop("AI_ENABLED", None)
        os.environ.pop("LLM_PROVIDER", None)


class TestCallAIFailSafe:
    """call_ai() must never raise — always return a string."""

    def test_returns_deterministic_when_ai_disabled(self):
        os.environ["AI_ENABLED"] = "false"
        app = _load_app_module()
        result = app.call_ai({"resource_type": "RDS", "rule_triggered": "idle"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_deterministic_when_provider_none(self):
        os.environ["AI_ENABLED"] = "true"
        os.environ["LLM_PROVIDER"] = "none"
        app = _load_app_module()
        result = app.call_ai({"resource_type": "EBS", "waste_estimate": 120})
        assert isinstance(result, str)

    def test_fail_safe_on_provider_error(self):
        os.environ["AI_ENABLED"] = "true"
        os.environ["LLM_PROVIDER"] = "azure_openai"
        app = _load_app_module()
        # azure_openai raises NotImplementedError — must resolve to fallback string
        result = app.call_ai({"resource_type": "EC2", "rule_triggered": "test"})
        assert isinstance(result, str)
        assert "deterministic" in result.lower() or len(result) > 0

    def teardown_method(self):
        os.environ.pop("AI_ENABLED", None)
        os.environ.pop("LLM_PROVIDER", None)


class TestLLMProviderControl:
    """LLM_PROVIDER env var controls routing — no hardcoded provider."""

    def test_default_provider_is_none(self):
        os.environ.pop("LLM_PROVIDER", None)
        app = _load_app_module()
        assert app.LLM_PROVIDER == "none"

    def test_provider_reads_from_env(self):
        os.environ["LLM_PROVIDER"] = "aws_bedrock"
        app = _load_app_module()
        assert app.LLM_PROVIDER == "aws_bedrock"

    def teardown_method(self):
        os.environ.pop("LLM_PROVIDER", None)

