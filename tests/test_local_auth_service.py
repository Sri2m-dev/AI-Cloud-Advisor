import sqlite3

import pytest

from auth.authenticated_tenant import AuthenticatedTenantError
from services import enterprise_spend_composition, local_auth_service


def test_default_admin_is_seeded_once_with_hashed_password(monkeypatch, tmp_path):
    database_path = tmp_path / "auth.db"

    def get_test_db():
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(local_auth_service, "get_db", get_test_db)

    assert local_auth_service.ensure_default_tenant_administrator() is True
    assert local_auth_service.ensure_default_tenant_administrator() is False

    conn = get_test_db()
    row = conn.execute(
        "SELECT password_hash, role, organization_name FROM local_auth_users"
    ).fetchone()
    conn.close()
    assert row["password_hash"] != "admin123"
    assert row["password_hash"].startswith("pbkdf2_sha256$")
    assert row["role"] == "super_admin"
    assert row["organization_name"] == "Default Org"


def test_default_admin_authentication_is_tenant_bound(monkeypatch, tmp_path):
    database_path = tmp_path / "auth.db"

    def get_test_db():
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(local_auth_service, "get_db", get_test_db)
    local_auth_service.ensure_default_tenant_administrator()

    assert local_auth_service.authenticate_local_user("admin@company.com", "wrong") is None
    user = local_auth_service.authenticate_local_user("ADMIN@COMPANY.COM", "admin123")
    assert user is not None
    assert user.role == "super_admin"
    assert user.organization_id == local_auth_service.DEFAULT_ORGANIZATION_ID
    assert user.organization_name == "Default Org"


def test_local_tenant_context_does_not_require_supabase(monkeypatch):
    monkeypatch.setattr(
        enterprise_spend_composition,
        "_organization_name",
        lambda _: pytest.fail("Supabase resolver must not be used for local auth"),
    )
    organization_id = local_auth_service.DEFAULT_ORGANIZATION_ID
    context = enterprise_spend_composition.authenticated_tenant_context(
        {
            "authenticated": True,
            "auth_backend": "local",
            "organization_id": organization_id,
            "authorized_organization_ids": [organization_id],
            "organization_name": "Default Org",
            "email": "admin@company.com",
            "role": "super_admin",
        }
    )
    assert context.organization_id == organization_id
    assert context.organization_name == "Default Org"


def test_local_tenant_context_rejects_unapproved_organization():
    with pytest.raises(AuthenticatedTenantError, match="not an authorized membership"):
        enterprise_spend_composition.authenticated_tenant_context(
            {
                "authenticated": True,
                "auth_backend": "local",
                "organization_id": local_auth_service.DEFAULT_ORGANIZATION_ID,
                "authorized_organization_ids": ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
                "organization_name": "Default Org",
                "email": "admin@company.com",
                "role": "super_admin",
            }
        )


def test_local_spend_service_returns_tenant_scoped_empty_posture(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    organization_id = local_auth_service.DEFAULT_ORGANIZATION_ID
    context = enterprise_spend_composition.authenticated_tenant_context(
        {
            "authenticated": True,
            "auth_backend": "local",
            "organization_id": organization_id,
            "authorized_organization_ids": [organization_id],
            "organization_name": "Default Org",
            "email": "admin@company.com",
            "role": "super_admin",
        }
    )
    posture = enterprise_spend_composition.enterprise_spend_service().get_financial_posture(context)
    assert posture.organization_id == organization_id
    assert posture.has_data is False
