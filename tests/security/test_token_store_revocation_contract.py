import time
from threading import Barrier, Lock, Thread

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from backend import token_store
from backend.middleware import tenant_isolation
from backend.routes import auth
from backend.security import get_current_user


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lock = Lock()

    def set(self, key, value, ex, nx=False):
        with self.lock:
            self._purge(key)
            if nx and key in self.values:
                return None
            self.values[key] = (value, time.time() + ex)
            return True

    def exists(self, key):
        with self.lock:
            self._purge(key)
            return key in self.values

    def _purge(self, key):
        value = self.values.get(key)
        if value is not None and value[1] <= time.time():
            del self.values[key]


def _refresh_claims(**overrides):
    return {
        "username": "test_operator",
        "role": "Viewer",
        "tenant_id": "tenant-a",
        "token_type": "refresh",
        "jti": "refresh-jti",
        "exp": int(time.time()) + 300,
        **overrides,
    }


def _authorized_api_user():
    return {
        "test_operator": {
            "password": "test-password",
            "role": "Viewer",
            "tenant_id": "tenant-a",
        }
    }


def test_rotated_refresh_token_cannot_be_reused(monkeypatch):
    monkeypatch.setattr(token_store, "_redis_client", FakeRedis())
    monkeypatch.setattr(auth, "verify_jwt", lambda token: _refresh_claims())
    monkeypatch.setattr(auth, "_load_api_users", _authorized_api_user)
    monkeypatch.setattr(
        auth,
        "create_jwt",
        lambda **claims: f"{claims['token_type']}-replacement",
    )
    request = auth.RefreshRequest(refresh_token="original-refresh-token")

    auth.refresh(request)

    with pytest.raises(HTTPException) as error:
        auth.refresh(request)

    assert error.value.status_code == 401


def test_revoked_access_token_is_rejected(monkeypatch):
    monkeypatch.setattr(token_store, "_redis_client", FakeRedis())
    token_store.revoke_token("revoked-access-jti", int(time.time()) + 300)

    monkeypatch.setattr(
        tenant_isolation,
        "verify_jwt",
        lambda token: {
            "username": "test_operator",
            "role": "Viewer",
            "tenant_id": "tenant-a",
            "token_type": "access",
            "jti": "revoked-access-jti",
            "exp": int(time.time()) + 300,
        },
    )
    app = FastAPI()
    app.add_middleware(tenant_isolation.TenantIsolationMiddleware)

    @app.get("/protected")
    def protected(_user=Depends(get_current_user)):
        return {"ok": True}

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer revoked-access-token"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("jti", [None, "", [], {}], ids=["missing", "empty", "list", "object"])
def test_access_token_with_missing_or_malformed_jti_is_rejected(monkeypatch, jti):
    monkeypatch.setattr(token_store, "_redis_client", FakeRedis())
    import backend.security as security

    monkeypatch.setattr(
        security,
        "verify_jwt",
        lambda token: {
            "username": "test_operator",
            "role": "Viewer",
            "tenant_id": "tenant-a",
            "token_type": "access",
            "jti": jti,
            "exp": int(time.time()) + 300,
        },
    )
    app = FastAPI()

    @app.get("/protected")
    def protected(_user=Depends(get_current_user)):
        return {"ok": True}

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("jti", [None, "", [], {}], ids=["missing", "empty", "list", "object"])
def test_refresh_rejects_missing_or_malformed_jti(monkeypatch, jti):
    monkeypatch.setattr(auth, "consume_token", lambda *args: pytest.fail("Invalid JTI consumed"))
    monkeypatch.setattr(auth, "verify_jwt", lambda token: _refresh_claims(jti=jti))
    monkeypatch.setattr(auth, "_load_api_users", _authorized_api_user)
    monkeypatch.setattr(
        auth,
        "create_jwt",
        lambda **claims: pytest.fail("Invalid-JTI token must not be refreshed"),
    )

    with pytest.raises(HTTPException) as error:
        auth.refresh(auth.RefreshRequest(refresh_token="invalid-jti-refresh-token"))

    assert error.value.status_code == 401


def test_expired_refresh_token_is_rejected_without_rotation(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(token_store, "_redis_client", fake_redis)
    monkeypatch.setattr(auth, "verify_jwt", lambda token: "expired")
    monkeypatch.setattr(
        auth,
        "create_jwt",
        lambda **claims: pytest.fail("Expired token must not be rotated"),
    )

    with pytest.raises(HTTPException) as error:
        auth.refresh(auth.RefreshRequest(refresh_token="expired-refresh-token"))

    assert error.value.status_code == 401
    assert fake_redis.values == {}


def test_expired_token_revocation_has_no_positive_ttl():
    assert token_store._ttl_seconds(int(time.time()) - 30) == 0


def test_refresh_token_consumption_is_atomic_under_concurrency(monkeypatch):
    monkeypatch.setattr(token_store, "_redis_client", FakeRedis())
    barrier = Barrier(8)
    results = []

    def consume():
        barrier.wait()
        results.append(token_store.consume_token("one-use-jti", int(time.time()) + 300))

    threads = [Thread(target=consume) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_revocation_ttl_tracks_token_expiry(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(token_store, "_redis_client", fake_redis)
    expiry = int(time.time()) + 300

    token_store.revoke_token("expiring-jti", expiry)

    stored_expiry = fake_redis.values[token_store._key("expiring-jti")][1]
    assert 298 <= stored_expiry - time.time() <= 300


@pytest.mark.parametrize("jti", [None, "", [], {}], ids=["missing", "empty", "list", "object"])
def test_revocation_rejects_malformed_jti(jti):
    with pytest.raises(ValueError):
        token_store.revoke_token(jti, int(time.time()) + 300)

    with pytest.raises(ValueError):
        token_store.is_token_revoked(jti)


def test_expired_tokens_are_not_added_to_revocation_store(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(token_store, "_redis_client", fake_redis)

    assert token_store.revoke_token("expired-jti", int(time.time()) - 30) is False
    assert fake_redis.values == {}


def test_redis_failure_is_explicit_and_fail_closed(monkeypatch):
    class UnavailableRedis:
        def exists(self, key):
            raise RedisConnectionError("unavailable")

    monkeypatch.setattr(token_store, "_redis_client", UnavailableRedis())

    with pytest.raises(token_store.TokenStoreUnavailable):
        token_store.is_token_revoked("access-jti")


def test_redis_failure_while_revoking_is_explicit(monkeypatch):
    class UnavailableRedis:
        def set(self, key, value, ex, nx=False):
            raise RedisConnectionError("unavailable")

    monkeypatch.setattr(token_store, "_redis_client", UnavailableRedis())

    with pytest.raises(token_store.TokenStoreUnavailable):
        token_store.revoke_token("access-jti", int(time.time()) + 300)

    with pytest.raises(token_store.TokenStoreUnavailable):
        token_store.consume_token("refresh-jti", int(time.time()) + 300)


def test_refresh_returns_503_when_redis_is_unavailable(monkeypatch):
    class UnavailableRedis:
        def set(self, key, value, ex, nx=False):
            raise RedisConnectionError("unavailable")

    monkeypatch.setattr(token_store, "_redis_client", UnavailableRedis())
    monkeypatch.setattr(auth, "verify_jwt", lambda token: _refresh_claims())
    monkeypatch.setattr(auth, "_load_api_users", _authorized_api_user)
    monkeypatch.setattr(
        auth,
        "create_jwt",
        lambda **claims: pytest.fail("Token issuance must fail closed"),
    )

    with pytest.raises(HTTPException) as error:
        auth.refresh(auth.RefreshRequest(refresh_token="refresh-token"))

    assert error.value.status_code == 503


def test_logout_returns_503_when_redis_is_unavailable(monkeypatch):
    class UnavailableRedis:
        def set(self, key, value, ex, nx=False):
            raise RedisConnectionError("unavailable")

    monkeypatch.setattr(token_store, "_redis_client", UnavailableRedis())
    monkeypatch.setattr(
        auth,
        "verify_jwt",
        lambda token: {
            "username": "test_operator",
            "role": "Viewer",
            "tenant_id": "tenant-a",
            "token_type": "access",
            "jti": "access-jti",
            "exp": int(time.time()) + 300,
        },
    )

    with pytest.raises(HTTPException) as error:
        auth.logout(
            auth.LogoutRequest(),
            user={"username": "test_operator", "tenant_id": "tenant-a"},
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="access-token",
            ),
        )

    assert error.value.status_code == 503


def test_protected_route_returns_503_when_redis_is_unavailable(monkeypatch):
    class UnavailableRedis:
        def exists(self, key):
            raise RedisConnectionError("unavailable")

    monkeypatch.setattr(token_store, "_redis_client", UnavailableRedis())
    import backend.security as security

    monkeypatch.setattr(
        security,
        "verify_jwt",
        lambda token: {
            "username": "test_operator",
            "role": "Viewer",
            "tenant_id": "tenant-a",
            "token_type": "access",
            "jti": "access-jti",
            "exp": int(time.time()) + 300,
        },
    )
    app = FastAPI()

    @app.get("/protected")
    def protected(_user=Depends(get_current_user)):
        return {"ok": True}

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 503


def test_middleware_returns_503_when_redis_is_unavailable(monkeypatch):
    class UnavailableRedis:
        def exists(self, key):
            raise RedisConnectionError("unavailable")

    monkeypatch.setattr(token_store, "_redis_client", UnavailableRedis())
    monkeypatch.setattr(
        tenant_isolation,
        "verify_jwt",
        lambda token: {
            "username": "test_operator",
            "role": "Viewer",
            "tenant_id": "tenant-a",
            "token_type": "access",
            "jti": "access-jti",
            "exp": int(time.time()) + 300,
        },
    )
    app = FastAPI()
    app.add_middleware(tenant_isolation.TenantIsolationMiddleware)

    @app.get("/protected")
    def protected():
        return {"ok": True}

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 503
