import time
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend import supabase_auth
from backend.middleware.tenant_isolation import TenantIsolationMiddleware
from backend.security import get_current_user

SIGNING_KEY = "local-test-signing-key-that-is-at-least-32-bytes"
USER_ID = str(uuid4())
ORG_ID = str(uuid4())
SESSION_ID = str(uuid4())


def _token(**overrides):
    claims = {
        "aud": "authenticated",
        "exp": int(time.time()) + 600,
        "iat": int(time.time()),
        "iss": "supabase",
        "role": "authenticated",
        "session_id": SESSION_ID,
        "sub": USER_ID,
    }
    claims.update(overrides)
    return jwt.encode(claims, SIGNING_KEY, algorithm="HS256")


def _configure(monkeypatch):
    monkeypatch.setenv("SUPABASE_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://auth-gateway.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "synthetic-anon-key")
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setenv("JWT_SECRET", SIGNING_KEY)
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_JWT_MODE", "synthetic_hs256")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(supabase_auth, "is_token_revoked", lambda _session: False)


def test_resolves_signed_token_to_authoritative_active_membership(monkeypatch):
    _configure(monkeypatch)
    calls = []

    def request_json(method, path, **kwargs):
        calls.append((method, path, kwargs.get("access_token")))
        if path == "auth/v1/user":
            return {"id": USER_ID, "email": "user-a@example.test"}
        pytest.fail(f"Unexpected provider request: {method} {path}")

    monkeypatch.setattr(supabase_auth, "_request_json", request_json)
    membership_calls = []

    def identity_membership(token, subject):
        membership_calls.append((token, subject))
        return {
            "auth_user_id": USER_ID,
            "org_id": ORG_ID,
            "tenant_id": ORG_ID,
            "organization_name": "Synthetic A",
            "role": "viewer",
            "permissions": [],
        }

    monkeypatch.setattr(supabase_auth, "_identity_membership", identity_membership)
    access_token = _token()

    principal = supabase_auth.resolve_access_token(access_token)

    assert principal["sub"] == USER_ID
    assert principal["username"] == "user-a@example.test"
    assert principal["tenant_id"] == ORG_ID
    assert principal["role"] == "viewer"
    assert principal["jti"] == SESSION_ID
    assert [call[1] for call in calls] == ["auth/v1/user"]
    assert all(call[2] == access_token for call in calls)
    assert membership_calls == [(access_token, USER_ID)]


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://untrusted.example.test"},
        {"aud": "service_role"},
        {"exp": int(time.time()) - 1},
    ],
    ids=["wrong-issuer", "wrong-audience", "expired"],
)
def test_rejects_invalid_supabase_claims_before_provider_lookup(monkeypatch, overrides):
    _configure(monkeypatch)
    monkeypatch.setattr(
        supabase_auth,
        "_request_json",
        lambda *args, **kwargs: pytest.fail("Invalid claims must be rejected locally"),
    )

    with pytest.raises(supabase_auth.SupabaseTokenRejected):
        supabase_auth.resolve_access_token(_token(**overrides))


def test_rejects_membership_not_bound_to_authenticated_uid(monkeypatch):
    _configure(monkeypatch)

    def request_json(_method, path, **_kwargs):
        if path == "auth/v1/user":
            return {"id": USER_ID, "email": "user-a@example.test"}
        pytest.fail(f"Unexpected provider request: {path}")

    monkeypatch.setattr(supabase_auth, "_request_json", request_json)
    monkeypatch.setattr(
        supabase_auth,
        "_identity_membership",
        lambda *_args: (_ for _ in ()).throw(
            supabase_auth.SupabaseMembershipRejected()
        ),
    )

    with pytest.raises(supabase_auth.SupabaseMembershipRejected):
        supabase_auth.resolve_access_token(_token())


def test_production_jwt_contract_fails_closed(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(
        supabase_auth.SupabaseAuthUnavailable,
        match="production JWT verification contract is not qualified",
    ):
        supabase_auth.resolve_access_token(_token())


def test_middleware_denies_forged_tenant_header(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        supabase_auth,
        "resolve_access_token",
        lambda _token: {"tenant_id": ORG_ID, "token_type": "access"},
    )
    app = FastAPI()
    app.add_middleware(TenantIsolationMiddleware)

    @app.get("/protected")
    def protected(_user=Depends(get_current_user)):
        return {"ok": True}

    response = TestClient(app).get(
        "/protected",
        headers={
            "Authorization": f"Bearer {_token()}",
            "X-Tenant-Id": str(uuid4()),
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Tenant mismatch"}
