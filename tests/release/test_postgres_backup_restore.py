import io
import json
import os
import subprocess
import tarfile
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

from scripts import postgres_recovery_package as recovery
from scripts.enforce_backup_retention import enforce_retention
from scripts.recovery_measurement import EVENTS, record_event, summarize


def _rewrite_manifest(artifact, key, update):
    encrypted = Fernet(key).decrypt(artifact.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(encrypted), mode="r:gz") as archive:
        entries = [
            (item.name, archive.extractfile(item).read())
            for item in archive
        ]
    rewritten = []
    for name, content in entries:
        if name == "manifest.json":
            manifest = json.loads(content)
            update(manifest)
            content = json.dumps(manifest, sort_keys=True).encode()
        rewritten.append((name, content))
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, content in rewritten:
            item = tarfile.TarInfo(name)
            item.size = len(content)
            archive.addfile(item, io.BytesIO(content))
    artifact.write_bytes(Fernet(key).encrypt(stream.getvalue()))


@pytest.fixture
def database_env(monkeypatch):
    values = {
        "PGHOST": "127.0.0.1",
        "PGPORT": "55495",
        "PGDATABASE": "source",
        "PGUSER": "qualification_backup",
        "PGPASSWORD": "runtime-only",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


def _checkpoint():
    return {
        "mode": "OPERATOR_QUIESCED_CAPTURE",
        "snapshot_id": "synthetic-checkpoint",
        "database_snapshot_id": "synthetic-database-snapshot",
        "file_snapshot_id": "synthetic-file-snapshot",
        "operator_ref": "synthetic-operator",
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def _metadata(owner="synthetic_owner"):
    return {
        "database": {
            "owner": owner,
            "acl_entries": [
                {
                    "grantor": owner,
                    "grantee": "PUBLIC",
                    "privilege": "CONNECT",
                    "grantable": False,
                }
            ],
        },
        "roles": [{"rolname": "synthetic_owner"}],
        "memberships": [],
        "schemas": [],
        "relations": [],
        "functions": [],
        "migration_versions": [{"name": "001.sql", "sha256": "a" * 64}],
        "role_passwords_included": False,
        "required_key_ids": {
            "workflow": "synthetic-workflow-key",
            "evidence": "synthetic-evidence-key",
        },
    }


def _package(tmp_path, *, metadata=None, members=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    migration = tmp_path / "001.sql"
    migration.write_text("synthetic migration", encoding="utf-8")
    default_metadata = _metadata() if metadata is None else metadata
    default_metadata["migration_versions"] = recovery._migration_inventory((migration,))
    default_members = {
        "database.dump": b"synthetic database archive",
        "database_globals.sql": b"CREATE ROLE synthetic_owner NOLOGIN;",
        "database_metadata.json": json.dumps(default_metadata, sort_keys=True).encode(),
        "evidence/synthetic.enc": Fernet(Fernet.generate_key()).encrypt(b"ciphertext"),
    }
    artifact = tmp_path / "backup.fernet"
    recovery._seal_package(
        default_members if members is None else members,
        key=key,
        key_id="synthetic-backup-key",
        checkpoint=_checkpoint(),
        source={"host": "source", "port": "55432", "database": "source"},
        metadata=default_metadata,
        backup_started_at=datetime.now(timezone.utc),
        destination=artifact,
    )
    return key, migration, artifact, default_members


def test_missing_database_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    with pytest.raises(recovery.RecoveryPackageError, match="PASSWORD"):
        recovery.DatabaseConfig.from_env()


def test_password_file_is_loaded_without_exposing_it(tmp_path, monkeypatch, database_env):
    password_file = tmp_path / "password"
    password_file.write_text("synthetic-file-secret\n", encoding="utf-8")
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setenv("PGPASSWORD_FILE", str(password_file))
    config = recovery.DatabaseConfig.from_env()
    assert config.password == "synthetic-file-secret"
    assert config.password not in config.args()


def test_pg_tools_receive_password_only_through_environment(database_env, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(recovery.subprocess, "run", fake_run)
    config = recovery.DatabaseConfig.from_env()
    recovery._run("pg_dump", config.args(), config)
    command, kwargs = calls[0]
    assert "runtime-only" not in command
    assert kwargs["env"]["PGPASSWORD"] == "runtime-only"


def test_package_encrypts_manifest_and_verifies_global_roles_and_hashes(tmp_path):
    key, migration, artifact, members = _package(tmp_path)
    assert b"synthetic database archive" not in artifact.read_bytes()
    manifest, verified = recovery.verify_backup_package(
        artifact,
        key=key,
        key_id="synthetic-backup-key",
        migration_files=(migration,),
    )
    assert manifest["database"]["roles"] == [{"rolname": "synthetic_owner"}]
    assert manifest["database"]["role_passwords_included"] is False
    assert manifest["files"]["database_globals.sql"]
    assert verified == members


def test_invalid_key_corruption_and_wrong_key_id_fail_closed(tmp_path):
    key, _, artifact, _ = _package(tmp_path)
    with pytest.raises(recovery.RecoveryPackageError, match="key is invalid"):
        recovery.verify_backup_package(
            artifact, key=Fernet.generate_key(), key_id="synthetic-backup-key"
        )
    with pytest.raises(recovery.RecoveryPackageError, match="identity mismatch"):
        recovery.verify_backup_package(
            artifact, key=key, key_id="incorrect-key-id"
        )
    damaged = artifact.read_bytes()
    artifact.write_bytes(damaged[:-1] + bytes([damaged[-1] ^ 1]))
    with pytest.raises(recovery.RecoveryPackageError, match="key is invalid"):
        recovery.verify_backup_package(
            artifact, key=key, key_id="synthetic-backup-key"
        )


def test_corrupted_authenticated_manifest_is_rejected(tmp_path):
    key, _, artifact, _ = _package(tmp_path)
    _rewrite_manifest(artifact, key, lambda manifest: manifest.update(format="unknown"))
    with pytest.raises(recovery.RecoveryPackageError, match="format or key identity mismatch"):
        recovery.verify_backup_package(
            artifact, key=key, key_id="synthetic-backup-key"
        )


def test_missing_globals_and_incomplete_packages_are_rejected(tmp_path):
    key = Fernet.generate_key()
    metadata = _metadata()
    incomplete = {
        "database.dump": b"synthetic dump",
        "database_metadata.json": json.dumps(metadata, sort_keys=True).encode(),
    }
    with pytest.raises(recovery.RecoveryPackageError, match="database_globals.sql missing"):
        recovery._seal_package(
            incomplete,
            key=key,
            key_id="synthetic-backup-key",
            checkpoint=_checkpoint(),
            source={"host": "source", "port": "55432", "database": "source"},
            metadata=metadata,
            backup_started_at=datetime.now(timezone.utc),
            destination=tmp_path / "incomplete.fernet",
        )


def test_interrupted_postgres_package_is_never_published(tmp_path, monkeypatch):
    key, _, artifact, members = _package(tmp_path / "source")
    destination = tmp_path / "interrupted.fernet"
    prior = tmp_path / "prior.fernet"
    prior.write_bytes(b"previous verified package")

    def interrupt(_descriptor):
        raise OSError("synthetic interrupted package write")

    monkeypatch.setattr(recovery.os, "fsync", interrupt)
    with pytest.raises(OSError, match="synthetic interrupted"):
        recovery._seal_package(
            members,
            key=key,
            key_id="synthetic-backup-key",
            checkpoint=_checkpoint(),
            source={"host": "source", "port": "55432", "database": "source"},
            metadata=_metadata(),
            backup_started_at=datetime.now(timezone.utc),
            destination=destination,
        )
    assert not destination.exists()
    assert prior.read_bytes() == b"previous verified package"
    assert list(tmp_path.glob(".interrupted.fernet.*.tmp")) == []


def test_manifest_rejects_missing_role_owner_and_incompatible_migration(tmp_path):
    key, migration, artifact, _ = _package(tmp_path, metadata=_metadata("missing_owner"))
    with pytest.raises(recovery.RecoveryPackageError, match="reference missing roles"):
        recovery.verify_backup_package(
            artifact, key=key, key_id="synthetic-backup-key"
        )

    key, migration, artifact, _ = _package(tmp_path / "other")
    incompatible = tmp_path / "different.sql"
    incompatible.write_text("different migration", encoding="utf-8")
    with pytest.raises(recovery.RecoveryPackageError, match="migration versions"):
        recovery.verify_backup_package(
            artifact,
            key=key,
            key_id="synthetic-backup-key",
            migration_files=(incompatible,),
        )


def test_restore_metadata_rejects_wrong_database_and_role_ownership():
    expected = {
        "database": {"owner": "synthetic_owner"},
        "schemas": [],
        "relations": [],
        "policies": [],
        "functions": [],
        "extensions": [],
        "migration_versions": [],
        "workflow_tables": [],
        "required_key_ids": {},
        "roles": [{"rolname": "synthetic_owner", "rolsuper": True}],
        "memberships": [],
    }
    wrong_database_owner = {
        **expected,
        "database": {"owner": "different_owner"},
    }
    with pytest.raises(recovery.RecoveryPackageError, match="database verification failed"):
        recovery._assert_metadata_matches(
            expected, wrong_database_owner, bootstrap_role="recovery_admin"
        )

    wrong_role_attributes = {
        **expected,
        "roles": [{"rolname": "synthetic_owner", "rolsuper": False}],
    }
    with pytest.raises(
        recovery.RecoveryPackageError, match="roles or ownership attributes mismatch"
    ):
        recovery._assert_metadata_matches(
            expected, wrong_role_attributes, bootstrap_role="recovery_admin"
        )


def test_restore_rejects_same_host_endpoint_before_connecting(tmp_path):
    key, migration, artifact, _ = _package(tmp_path)
    config = recovery.DatabaseConfig("source", "55432", "postgres", "recovery_admin", "")
    with pytest.raises(recovery.RecoveryPackageError, match="endpoint must differ"):
        recovery.restore_backup_package(
            artifact,
            config,
            target_database="restored",
            storage_destination=tmp_path / "restored-files",
            key=key,
            key_id="synthetic-backup-key",
            migration_files=(migration,),
        )


def test_retention_defaults_to_dry_run_and_preserves_two_latest(tmp_path):
    now = 40 * 86400
    backups = []
    for index in range(4):
        artifact = tmp_path / f"backup-{index}.fernet"
        artifact.write_bytes(b"synthetic ciphertext")
        artifact.touch()
        timestamp = now - (index + 35) * 86400
        os.utime(artifact, (timestamp, timestamp))
        backups.append(artifact)
    unrelated = tmp_path / "do-not-delete.txt"
    unrelated.write_text("synthetic", encoding="utf-8")

    dry_run = enforce_retention(
        tmp_path, older_than_days=30, keep_newest=2, now=now
    )
    assert dry_run["mode"] == "DRY_RUN"
    assert dry_run["candidate_count"] == 2
    assert all(path.exists() for path in backups)
    applied = enforce_retention(
        tmp_path, older_than_days=30, keep_newest=2, apply=True, now=now
    )
    assert applied["deleted_names"] == dry_run["candidate_names"]
    assert sum(path.exists() for path in backups) == 2
    assert unrelated.exists()


def test_recovery_measurement_separates_database_restore_and_full_service_rto(tmp_path):
    evidence_file = tmp_path / "recovery.jsonl"
    baseline = datetime(2026, 1, 1, tzinfo=timezone.utc)
    offsets = (0, 60, 120, 180, 240, 360, 480, 540)
    for event, offset in zip(EVENTS, offsets):
        occurred_at = (baseline + timedelta(seconds=offset)).isoformat()
        record_event(evidence_file, event, occurred_at=occurred_at)

    report = summarize(evidence_file)
    assert report["backup_seconds"] == 60
    assert report["rpo_seconds"] == 60
    assert report["database_restore_seconds"] == 120
    assert report["rto_seconds"] == 300
    assert report["customer_validation_seconds"] == 360
