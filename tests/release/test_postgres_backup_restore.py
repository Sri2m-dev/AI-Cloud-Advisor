from pathlib import Path

import pytest

from scripts import postgres_backup_restore as backup_restore


@pytest.fixture
def database_env(monkeypatch):
    values = {
        "PGHOST": "127.0.0.1",
        "PGPORT": "55495",
        "PGDATABASE": "source",
        "PGUSER": "postgres",
        "PGPASSWORD": "runtime-only",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


def test_missing_database_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    with pytest.raises(backup_restore.BackupConfigurationError, match="PASSWORD"):
        backup_restore.DatabaseConfig.from_env()


def test_restore_rejects_source_target_collision(database_env, tmp_path):
    artifact = tmp_path / "source.dump"
    artifact.write_bytes(b"dump")
    with pytest.raises(backup_restore.BackupConfigurationError, match="isolated"):
        backup_restore._restore(
            artifact,
            backup_restore.DatabaseConfig.from_env(),
            backup_restore.DatabaseConfig.from_env(),
        )


def test_backup_uses_environment_password_without_printing_it(database_env, monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        Path(command[command.index("--file") + 1]).write_bytes(b"synthetic dump")

    monkeypatch.setattr(backup_restore.subprocess, "run", fake_run)
    artifact = backup_restore._backup(backup_restore.DatabaseConfig.from_env(), tmp_path)
    assert artifact.is_file()
    command, kwargs = calls[0]
    assert "runtime-only" not in command
    assert kwargs["env"]["PGPASSWORD"] == "runtime-only"
