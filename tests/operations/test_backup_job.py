import json
from pathlib import Path

from cryptography.fernet import Fernet

from deploy.operations import backup_job


def _environment(monkeypatch, tmp_path):
    storage_root = tmp_path / "snapshot"
    for name in ("application", "evidence", "prospect"):
        (storage_root / name).mkdir(parents=True)
    key_path = tmp_path / "backup.key"
    key_path.write_bytes(Fernet.generate_key())
    password_path = tmp_path / "postgres.password"
    password_path.write_text("synthetic-db-password", encoding="utf-8")
    receipt = tmp_path / "capture.json"
    receipt.write_text(
        json.dumps(
            {
                "mode": "OPERATOR_QUIESCED_CAPTURE",
                "snapshot_id": "synthetic-capture",
                "database_snapshot_id": "synthetic-db",
                "file_snapshot_id": "synthetic-storage",
                "operator_ref": "synthetic-owner",
                "captured_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    values = {
        "NEXORA_BACKUP_STATUS_FILE": str(tmp_path / "status.json"),
        "NEXORA_RECOVERY_EVENT_LOG": str(tmp_path / "events.jsonl"),
        "NEXORA_QUIESCED_SNAPSHOT_ROOT": str(storage_root),
        "NEXORA_BACKUP_ROOT": str(tmp_path / "backups"),
        "NEXORA_BACKUP_KEY_FILE": str(key_path),
        "NEXORA_BACKUP_KEY_ID": "synthetic-backup-key",
        "NEXORA_WORKFLOW_KEY_ID": "synthetic-workflow-key",
        "NEXORA_EVIDENCE_KEY_ID": "synthetic-evidence-key",
        "NEXORA_CAPTURE_RECEIPT_FILE": str(receipt),
        "PGHOST": "127.0.0.1",
        "PGPORT": "5432",
        "PGDATABASE": "synthetic",
        "PGUSER": "synthetic_backup",
        "PGPASSWORD_FILE": str(password_path),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values, key_path


def test_scheduled_job_creates_and_verifies_local_package_with_safe_status(
    monkeypatch, tmp_path, capsys
):
    environment, key_path = _environment(monkeypatch, tmp_path)
    calls = {}

    def create(config, artifact, **kwargs):
        calls["config"] = config
        calls["kwargs"] = kwargs
        artifact.write_bytes(b"synthetic encrypted package")
        return {
            "artifact_sha256": "a" * 64,
            "backup_started_at": "2026-01-01T00:00:00+00:00",
            "backup_completed_at": "2026-01-01T00:00:05+00:00",
        }

    monkeypatch.setattr(backup_job, "create_backup_package", create)
    monkeypatch.setattr(backup_job, "verify_backup_package", lambda *args, **kwargs: ({}, {}))

    assert backup_job.main() == 0
    status = json.loads(Path(environment["NEXORA_BACKUP_STATUS_FILE"]).read_text())
    events = [
        json.loads(line)
        for line in Path(environment["NEXORA_RECOVERY_EVENT_LOG"])
        .read_text()
        .splitlines()
    ]
    assert status["last_attempt_success"] is True
    assert [event["event"] for event in events] == ["backup_started", "backup_completed"]
    assert calls["config"].password == "synthetic-db-password"
    assert calls["kwargs"]["key"] == key_path.read_bytes()
    assert "offsite_verified" in capsys.readouterr().out
    assert key_path.read_text() not in Path(environment["NEXORA_RECOVERY_EVENT_LOG"]).read_text()


def test_scheduled_job_records_failure_without_claiming_success(
    monkeypatch, tmp_path, capsys
):
    environment, _ = _environment(monkeypatch, tmp_path)
    monkeypatch.setattr(
        backup_job,
        "create_backup_package",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )

    assert backup_job.main() == 1
    status = json.loads(Path(environment["NEXORA_BACKUP_STATUS_FILE"]).read_text())
    events = [
        json.loads(line)
        for line in Path(environment["NEXORA_RECOVERY_EVENT_LOG"])
        .read_text()
        .splitlines()
    ]
    assert status["last_attempt_success"] is False
    assert events[-1]["event"] == "backup_failed"
    assert "synthetic failure" in capsys.readouterr().err
