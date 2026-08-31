import pytest

from auth import jwt_utils


def test_production_jwt_requires_configured_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="JWT_SECRET is required"):
        jwt_utils.create_jwt("user", "viewer", "tenant")


def test_development_jwt_uses_process_local_key(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    token = jwt_utils.create_jwt("user", "viewer", "tenant")
    assert jwt_utils.verify_jwt(token)["username"] == "user"


def test_configured_secret_round_trip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-with-sufficient-entropy-123456789")
    token = jwt_utils.create_jwt("operator", "operations", "tenant")
    assert jwt_utils.verify_jwt(token)["role"] == "operations"
