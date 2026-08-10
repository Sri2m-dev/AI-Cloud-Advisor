from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import HTTPException
from streamlit.testing.v1 import AppTest

from auth.authenticated_tenant import AuthenticatedTenantContext
from auth.role_constants import normalize_role
from backend.routes import auth as api_auth
from components.sidebar_navigation import DEFAULT_ROLE_PAGE, get_role_pages
from services import audit_service, local_auth_service
from services.cloud_account_registry_service import CloudAccountRegistryService

PERSONAS = {
    "admin@company.com": ("admin123", "super_admin"),
    "ceo@company.com": ("persona123", "executive"),
    "cio@company.com": ("persona123", "cio"),
    "cto@company.com": ("persona123", "cio"),
    "finance@company.com": ("persona123", "finance"),
    "auditor@company.com": ("persona123", "auditor"),
    "operations@company.com": ("persona123", "operations"),
}


@pytest.fixture
def local_database(monkeypatch, tmp_path):
    database_path = tmp_path / "personas.db"

    def connect():
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(local_auth_service, "get_db", connect)
    monkeypatch.setattr("database.db.SQLITE_DB_PATH", str(database_path))
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    return connect


def test_all_canonical_personas_seed_and_authenticate(local_database):
    assert local_auth_service.ensure_nonproduction_personas() == len(PERSONAS)
    assert local_auth_service.ensure_nonproduction_personas() == 0
    for email, (password, expected_role) in PERSONAS.items():
        user = local_auth_service.authenticate_local_user(email.upper(), password)
        assert user is not None
        assert user.email == email
        assert user.role == expected_role
        assert user.organization_id == local_auth_service.DEFAULT_ORGANIZATION_ID
        assert user.organization_name == "Default Org"


def test_wrong_password_and_unknown_account_are_indistinguishable(local_database):
    local_auth_service.ensure_nonproduction_personas()
    assert local_auth_service.authenticate_local_user("ceo@company.com", "wrong") is None
    assert local_auth_service.authenticate_local_user("unknown@company.com", "wrong") is None


def test_persona_passwords_are_only_persisted_as_pbkdf2_hashes(local_database):
    local_auth_service.ensure_nonproduction_personas()
    conn = local_database()
    rows = conn.execute("SELECT email, password_hash FROM local_auth_users").fetchall()
    conn.close()
    assert len(rows) == len(PERSONAS)
    for row in rows:
        assert row["password_hash"].startswith("pbkdf2_sha256$")
        assert row["password_hash"] not in {"admin123", "persona123", "password123"}


def test_production_disables_seed_and_local_login(local_database):
    assert local_auth_service.ensure_nonproduction_personas(environment="production") == 0
    local_auth_service.ensure_nonproduction_personas(environment="development")
    assert (
        local_auth_service.authenticate_local_user(
            "admin@company.com", "admin123", environment="production"
        )
        is None
    )


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("CEO", "executive"),
        ("CTO", "cio"),
        ("organization_admin", "client_admin"),
        ("SuperAdmin", "super_admin"),
        ("FinOpsManager", "finance"),
    ],
)
def test_role_aliases_normalize_centrally(alias, canonical):
    assert normalize_role(alias) == canonical


def test_persona_landing_pages_are_role_specific():
    assert DEFAULT_ROLE_PAGE == {
        "super_admin": "pages/executive_dashboard.py",
        "executive": "pages/executive_dashboard.py",
        "cio": "pages/cio_dashboard.py",
        "finance": "pages/finance_dashboard.py",
        "technical": "pages/operations_workspace.py",
        "operations": "pages/operations_workspace.py",
        "auditor": "pages/audit_timeline.py",
    }


def test_sidebar_visibility_matches_persona_authority():
    assert "Executive Dashboard" in get_role_pages("CEO")
    assert "FinOps Dashboard" not in get_role_pages("CEO")
    assert "Technology Portfolio Overview" in get_role_pages("CTO")
    assert "Cloud Account Registry" in get_role_pages("finance")
    assert "Account Resolution" in get_role_pages("finance")
    assert get_role_pages("auditor") == [
        "Cloud Account Registry",
        "Account Resolution",
        "Audit Timeline",
        "Reports",
        "Enterprise Registry",
    ]
    assert "Executive Dashboard" not in get_role_pages("operations")
    assert "Operations Workspace" in get_role_pages("operations")


def _context(role: str) -> AuthenticatedTenantContext:
    return AuthenticatedTenantContext(
        organization_id=local_auth_service.DEFAULT_ORGANIZATION_ID,
        organization_name="Default Org",
        user_id=f"{role}-user",
        user_email=f"{role}@company.com",
        role=role,
        authorization_claims=frozenset(),
        tenant_id=local_auth_service.DEFAULT_ORGANIZATION_ID,
    )


def test_classification_authority_is_preserved_by_persona():
    expected = {
        "super_admin": {"read": True, "edit": True, "resolve": True, "approve": True},
        "executive": {"read": True, "edit": False, "resolve": False, "approve": False},
        "cio": {"read": True, "edit": False, "resolve": False, "approve": False},
        "finance": {"read": True, "edit": True, "resolve": True, "approve": False},
        "operations": {"read": True, "edit": True, "resolve": True, "approve": False},
        "auditor": {"read": True, "edit": False, "resolve": False, "approve": False},
    }
    for role, permissions in expected.items():
        actual = CloudAccountRegistryService.permissions(_context(role))
        assert all(actual[name] is value for name, value in permissions.items())


@pytest.mark.parametrize(
    ("role", "page"),
    [
        ("executive", "pages/finance_dashboard.py"),
        ("cio", "pages/finance_dashboard.py"),
        ("finance", "pages/executive_dashboard.py"),
        ("auditor", "pages/approval_center.py"),
        ("operations", "pages/executive_dashboard.py"),
    ],
)
def test_forbidden_direct_routes_are_server_side_denied(role, page):
    app = AppTest.from_file(page, default_timeout=30)
    app.session_state["authenticated"] = True
    app.session_state["role"] = role
    app.session_state["user"] = f"{role}@company.com"
    app.session_state["email"] = f"{role}@company.com"
    app.session_state["organization_id"] = local_auth_service.DEFAULT_ORGANIZATION_ID
    app.run()
    assert any("Unauthorized Access" in error.value for error in app.error)


def test_successful_local_login_audit_contains_no_credentials(local_database):
    local_auth_service.ensure_nonproduction_personas()
    user = local_auth_service.authenticate_local_user("ceo@company.com", "persona123")
    event = audit_service.log_user_login(
        user_id=user.email,
        organization_id=user.organization_id,
        actor_role=user.role,
    )
    assert "error" not in event
    serialized = json.dumps(event)
    assert "persona123" not in serialized
    assert "password" not in serialized.casefold()
    rows = audit_service.get_events(org_id=user.organization_id, event_type="USER_LOGIN")
    assert any(row["id"] == event["id"] for row in rows)


def test_api_login_has_no_implicit_default_credentials(monkeypatch):
    monkeypatch.delenv("API_USERS_JSON", raising=False)
    assert api_auth._load_api_users() == {}
    with pytest.raises(HTTPException) as exc:
        api_auth.login(
            api_auth.LoginRequest(username="admin", password="admin123", tenant_id="tenant")
        )
    assert exc.value.status_code == 401
