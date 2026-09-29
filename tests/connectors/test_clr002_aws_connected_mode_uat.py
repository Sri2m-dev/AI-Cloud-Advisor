from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGE = Path("pages/aws_connector_setup.py")
TEST_ORG_ID = "00000000-0000-4000-8000-000000000002"


def run_page(monkeypatch):
    monkeypatch.setenv(
        "NEXORA_AWS_PRINCIPAL_ARN",
        "arn:aws:iam::111111111111:role/NexoraConnectorPrincipal",
    )

    app = AppTest.from_file(
        str(PAGE),
        default_timeout=30,
    )

    app.session_state["authenticated"] = True
    app.session_state["role"] = "super_admin"
    app.session_state["organization_id"] = TEST_ORG_ID
    app.session_state["user"] = {
        "id": "clr002-uat-admin",
        "email": "clr002-uat@nexora.invalid",
        "role": "super_admin",
        "organization_id": TEST_ORG_ID,
    }

    app.run()

    return app


def test_connected_mode_page_renders(monkeypatch):
    app = run_page(monkeypatch)

    assert not app.exception

    titles = [
        str(getattr(item, "value", ""))
        for item in app.title
    ]

    assert "AWS Connector Setup" in titles


def test_external_id_is_generated_and_disabled(monkeypatch):
    app = run_page(monkeypatch)

    assert not app.exception

    fields = [
        item
        for item in app.text_input
        if getattr(item, "label", "") == "External ID"
    ]

    assert len(fields) == 1
    assert fields[0].disabled is True
    assert str(fields[0].value).startswith("nexora-")


def test_role_arn_remains_customer_configurable(monkeypatch):
    app = run_page(monkeypatch)

    assert not app.exception

    fields = [
        item
        for item in app.text_input
        if getattr(item, "label", "") == "Role ARN"
    ]

    assert len(fields) == 1
    assert fields[0].disabled is False


def test_no_customer_access_key_fields(monkeypatch):
    app = run_page(monkeypatch)

    assert not app.exception

    labels = " ".join(
        str(getattr(item, "label", "")).lower()
        for item in app.text_input
    )

    assert "access key" not in labels
    assert "secret access" not in labels
    assert "secret key" not in labels


def test_trust_policy_contains_assume_role_and_external_id(
    monkeypatch,
):
    app = run_page(monkeypatch)

    assert not app.exception

    rendered = "\n".join(
        str(getattr(item, "value", ""))
        for item in app.code
    )

    assert "sts:AssumeRole" in rendered
    assert "sts:ExternalId" in rendered
    assert "NexoraConnectorPrincipal" in rendered


def test_unauthenticated_user_is_still_blocked(monkeypatch):
    monkeypatch.setenv(
        "NEXORA_AWS_PRINCIPAL_ARN",
        "arn:aws:iam::111111111111:role/NexoraConnectorPrincipal",
    )

    app = AppTest.from_file(
        str(PAGE),
        default_timeout=30,
    )

    app.run()

    assert not app.exception

    errors = [
        str(getattr(item, "value", ""))
        for item in app.error
    ]

    assert "Please log in" in errors

    role_fields = [
        item
        for item in app.text_input
        if getattr(item, "label", "") == "Role ARN"
    ]

    assert not role_fields


def test_non_connector_admin_is_still_blocked(monkeypatch):
    monkeypatch.setenv(
        "NEXORA_AWS_PRINCIPAL_ARN",
        "arn:aws:iam::111111111111:role/NexoraConnectorPrincipal",
    )

    app = AppTest.from_file(
        str(PAGE),
        default_timeout=30,
    )

    app.session_state["authenticated"] = True
    app.session_state["role"] = "executive"
    app.session_state["organization_id"] = TEST_ORG_ID
    app.session_state["user"] = {
        "id": "clr002-uat-executive",
        "email": "clr002-executive@nexora.invalid",
        "role": "executive",
        "organization_id": TEST_ORG_ID,
    }

    app.run()

    assert not app.exception

    errors = " ".join(
        str(getattr(item, "value", ""))
        for item in app.error
    )

    assert "Connector setup is restricted" in errors

    role_fields = [
        item
        for item in app.text_input
        if getattr(item, "label", "") == "Role ARN"
    ]

    assert not role_fields
