from types import SimpleNamespace

import pytest

from auth import connector_context

AUTH_USER = "11111111-1111-4111-8111-111111111111"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def test_unauthenticated_session_cannot_fall_back_to_default_tenant(monkeypatch):
    monkeypatch.setattr(connector_context.st, "session_state", {})

    with pytest.raises(PermissionError, match="authenticated session"):
        connector_context.get_current_organization_id()


def test_supabase_tenant_context_requires_matching_auth_profile_and_membership(monkeypatch):
    session = {
        "authenticated": True,
        "auth_backend": "supabase",
        "user": SimpleNamespace(id=AUTH_USER, email="user@example.com"),
        "user_id": AUTH_USER,
        "profile": {
            "auth_user_id": AUTH_USER,
            "org_id": ORG_A,
            "role": "client_admin",
        },
        "organization_id": ORG_A,
        "authorized_organization_ids": [ORG_A],
    }
    monkeypatch.setattr(connector_context.st, "session_state", session)

    assert connector_context.get_current_organization_id() == ORG_A
    assert connector_context.get_current_user_id() == AUTH_USER
    assert connector_context.is_client_admin()

    session["organization_id"] = ORG_B
    with pytest.raises(PermissionError, match="tenant membership"):
        connector_context.get_current_organization_id()


def test_supabase_connector_context_rejects_unbound_or_missing_identity(monkeypatch):
    session = {
        "authenticated": True,
        "auth_backend": "supabase",
        "user": SimpleNamespace(id=AUTH_USER, email="user@example.com"),
        "user_id": AUTH_USER,
        "profile": {"auth_user_id": ORG_A, "org_id": ORG_A},
        "organization_id": ORG_A,
        "authorized_organization_ids": [ORG_A],
    }
    monkeypatch.setattr(connector_context.st, "session_state", session)

    with pytest.raises(PermissionError, match="identity"):
        connector_context.get_current_user_id()

    session["profile"]["auth_user_id"] = AUTH_USER
    session["user"] = None
    with pytest.raises(PermissionError, match="identity"):
        connector_context.get_current_user_id()


def test_local_connector_context_requires_explicit_authorized_tenant(monkeypatch):
    session = {
        "authenticated": True,
        "auth_backend": "local",
        "user_id": "developer@example.com",
        "organization_id": ORG_A,
        "authorized_organization_ids": [ORG_A],
        "role": "client_admin",
    }
    monkeypatch.setattr(connector_context.st, "session_state", session)

    assert connector_context.get_current_organization_id() == ORG_A
    assert connector_context.get_current_user_id() == "developer@example.com"

    session["authorized_organization_ids"] = []
    with pytest.raises(PermissionError, match="membership"):
        connector_context.get_current_organization_id()
