import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend import security
from backend.api_user_store import APIUserStoreUnavailable
from backend.middleware import tenant_isolation
from backend.routes import auth
from backend.security import get_current_user, require_role


def _access_app(monkeypatch, claims, users):
    monkeypatch.setattr(security, "verify_jwt", lambda token: dict(claims))
    monkeypatch.setattr(tenant_isolation, "verify_jwt", lambda token: dict(claims))
    monkeypatch.setattr(security, "_load_api_users", lambda: users, raising=False)
    monkeypatch.setattr(security, "is_token_revoked", lambda jti: False)
    monkeypatch.setattr(tenant_isolation, "is_token_revoked", lambda jti: False)

    app = FastAPI()
    app.add_middleware(tenant_isolation.TenantIsolationMiddleware)

    @app.get("/protected")
    def protected(user=Depends(get_current_user)):
        return {
            "role": user["role"],
            "tenant_id": user["tenant_id"],
        }

    @app.get("/admin", dependencies=[Depends(require_role("super_admin"))])
    def admin():
        return {"ok": True}

    return app


def _access_claims(**overrides):
    return {
        "username": "test_operator",
        "role": "SuperAdmin",
        "tenant_id": "tenant-a",
        "org_id": "tenant-a",
        "token_type": "access",
        "jti": "test-access-jti",
        "exp": 9999999999,
        **overrides,
    }


def _refresh_payload(**overrides):
    return {
        "username": "test_operator",
        "role": "Auditor",
        "tenant_id": "tenant-a",
        "token_type": "refresh",
        "jti": "test-refresh-jti",
        "exp": 9999999999,
        **overrides,
    }


def test_api_login_rejects_unauthorized_tenant(monkeypatch):
    monkeypatch.setattr(
        auth,
        "_load_api_users",
        lambda: {
            "test_operator": {
                "password": "test-password",
                "role": "Viewer",
                "tenant_id": "tenant-a",
            }
        },
    )

    payload = auth.LoginRequest(
        username="test_operator",
        password="test-password",
        tenant_id="tenant-b",
    )

    with pytest.raises(HTTPException) as error:
        auth.login(payload)

    assert error.value.status_code == 403


def test_api_login_rejects_missing_tenant_assignment(monkeypatch):
    monkeypatch.setattr(
        auth,
        "_load_api_users",
        lambda: {
            "test_operator": {
                "password": "test-password",
                "role": "Viewer",
            }
        },
    )

    payload = auth.LoginRequest(
        username="test_operator",
        password="test-password",
        tenant_id="tenant-a",
    )

    with pytest.raises(HTTPException) as error:
        auth.login(payload)

    assert error.value.status_code == 403


def test_api_login_allows_assigned_tenant(monkeypatch):
    monkeypatch.setattr(
        auth,
        "_load_api_users",
        lambda: {
            "test_operator": {
                "password": "test-password",
                "role": "Viewer",
                "tenant_id": "tenant-a",
            }
        },
    )
    issued = []
    monkeypatch.setattr(
        auth,
        "create_jwt",
        lambda **claims: issued.append(claims) or "test-token",
    )

    result = auth.login(
        auth.LoginRequest(
            username="test_operator",
            password="test-password",
            tenant_id="tenant-a",
        )
    )

    assert result["tenant_id"] == "tenant-a"
    assert [token["token_type"] for token in issued] == ["access", "refresh"]
    assert all(token["tenant_id"] == "tenant-a" for token in issued)


def test_refresh_rejects_removed_tenant_membership(monkeypatch):
    monkeypatch.setattr(auth, "verify_jwt", lambda token: _refresh_payload())
    monkeypatch.setattr(
        auth,
        "_load_api_users",
        lambda: {
            "test_operator": {
                "password": "test-password",
                "role": "Viewer",
                "tenant_id": "tenant-b",
            }
        },
    )

    def unexpected_revoke(*args, **kwargs):
        pytest.fail("Refresh token must not be rotated before authorization")

    monkeypatch.setattr(auth, "consume_token", unexpected_revoke)

    with pytest.raises(HTTPException) as error:
        auth.refresh(auth.RefreshRequest(refresh_token="test-refresh-token"))

    assert error.value.status_code == 403


@pytest.mark.parametrize(
    "users",
    [
        {},
        {
            "test_operator": {
                "password": "test-password",
                "role": "Viewer",
                "tenant_id": "tenant-a",
                "disabled": True,
            }
        },
    ],
    ids=["removed-user", "disabled-user"],
)
def test_refresh_rejects_removed_or_disabled_user(monkeypatch, users):
    monkeypatch.setattr(auth, "verify_jwt", lambda token: _refresh_payload())
    monkeypatch.setattr(auth, "_load_api_users", lambda: users)
    monkeypatch.setattr(
        auth,
        "consume_token",
        lambda *args, **kwargs: pytest.fail("Rejected refresh tokens must not be rotated"),
    )

    with pytest.raises(HTTPException) as error:
        auth.refresh(auth.RefreshRequest(refresh_token="test-refresh-token"))

    assert error.value.status_code == 401


def test_refresh_uses_current_authorized_role(monkeypatch):
    monkeypatch.setattr(auth, "verify_jwt", lambda token: _refresh_payload())
    monkeypatch.setattr(
        auth,
        "_load_api_users",
        lambda: {
            "test_operator": {
                "password": "test-password",
                "role": "Finance",
                "tenant_id": "tenant-a",
            }
        },
    )
    consumed = []
    issued = []
    monkeypatch.setattr(auth, "consume_token", lambda *args: consumed.append(args) or True)
    monkeypatch.setattr(
        auth,
        "create_jwt",
        lambda **claims: issued.append(claims) or f"test-{claims['token_type']}",
    )

    result = auth.refresh(auth.RefreshRequest(refresh_token="test-refresh-token"))

    assert result["access_token"] == "test-access"
    assert result["refresh_token"] == "test-refresh"
    assert [token["role"] for token in issued] == ["finance", "finance"]
    assert [token["tenant_id"] for token in issued] == ["tenant-a", "tenant-a"]
    assert len(consumed) == 1


def test_refresh_token_is_rejected_as_api_bearer(monkeypatch):
    monkeypatch.setattr(tenant_isolation, "verify_jwt", lambda token: _refresh_payload())
    app = FastAPI()
    app.add_middleware(tenant_isolation.TenantIsolationMiddleware)

    @app.get("/protected")
    def protected(_user=Depends(get_current_user)):
        return {"ok": True}

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer test-refresh-token"},
    )

    assert response.status_code == 401


def test_access_token_for_disabled_user_is_rejected(monkeypatch):
    app = _access_app(
        monkeypatch,
        _access_claims(),
        {
            "test_operator": {
                "role": "SuperAdmin",
                "tenant_id": "tenant-a",
                "disabled": True,
            }
        },
    )

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 401


def test_access_token_for_removed_user_is_rejected(monkeypatch):
    app = _access_app(monkeypatch, _access_claims(), {})

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 401


def test_access_token_does_not_preserve_demoted_role(monkeypatch):
    app = _access_app(
        monkeypatch,
        _access_claims(),
        {
            "test_operator": {
                "role": "Finance",
                "tenant_id": "tenant-a",
            }
        },
    )
    client = TestClient(app)

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )
    privileged_response = client.get(
        "/admin",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "finance"
    assert privileged_response.status_code == 403


def test_access_token_is_rejected_after_tenant_membership_changes(monkeypatch):
    app = _access_app(
        monkeypatch,
        _access_claims(),
        {
            "test_operator": {
                "role": "Finance",
                "tenant_id": "tenant-b",
            }
        },
    )

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 403


def test_profile_lookup_failure_cannot_restore_stale_jwt_role(monkeypatch):
    def unavailable_profile(*args, **kwargs):
        raise RuntimeError("profile lookup unavailable")

    monkeypatch.setattr(security, "get_user_profile", unavailable_profile, raising=False)
    app = _access_app(
        monkeypatch,
        _access_claims(),
        {
            "test_operator": {
                "role": "Finance",
                "tenant_id": "tenant-a",
            }
        },
    )

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "finance"


def test_authoritative_user_store_failure_returns_503(monkeypatch):
    def unavailable_store():
        raise APIUserStoreUnavailable("unavailable")

    app = _access_app(monkeypatch, _access_claims(), {})
    monkeypatch.setattr(security, "_load_api_users", unavailable_store)

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 503


def test_access_token_uses_current_role_for_valid_active_member(monkeypatch):
    app = _access_app(
        monkeypatch,
        _access_claims(role="Viewer"),
        {
            "test_operator": {
                "role": "Auditor",
                "tenant_id": "tenant-a",
                "is_active": True,
            }
        },
    )

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "role": "auditor",
        "tenant_id": "tenant-a",
    }
