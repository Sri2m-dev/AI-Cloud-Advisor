from pathlib import Path

import pytest

from services import db


def test_legacy_postgres_uses_only_configured_password(monkeypatch):
    captured = {}
    monkeypatch.setenv("PGPASSWORD", "configured-at-runtime")
    monkeypatch.setenv("PGHOST", "db.internal")
    monkeypatch.setenv("PGPORT", "5433")
    monkeypatch.setenv("PGDATABASE", "nexora")
    monkeypatch.setenv("PGUSER", "nexora-service")
    monkeypatch.setattr(db.psycopg2, "connect", lambda **kwargs: captured.update(kwargs))

    db.get_connection()

    assert captured == {
        "host": "db.internal",
        "port": "5433",
        "database": "nexora",
        "user": "nexora-service",
        "password": "configured-at-runtime",
    }


@pytest.mark.parametrize("environment", ("development", "production"))
def test_missing_postgres_password_fails_clearly_without_disclosure(monkeypatch, environment):
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setattr(
        db.psycopg2,
        "connect",
        lambda **_kwargs: pytest.fail("connection must not be attempted"),
    )

    with pytest.raises(db.DatabaseConfigurationError) as error:
        db.get_connection()

    assert "PGPASSWORD is required" in str(error.value)
    assert "password=" not in str(error.value).casefold()


def test_no_static_postgres_password_or_credential_logging_remains():
    source = Path("services/db.py").read_text(encoding="utf-8")
    assert 'password="' not in source
    assert "logger" not in source and "print(" not in source


def test_sqlite_local_path_remains_independent():
    source = Path("database/db.py").read_text(encoding="utf-8")
    assert "sqlite3.connect" in source
