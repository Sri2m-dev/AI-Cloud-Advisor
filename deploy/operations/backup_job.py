"""Scheduled local PostgreSQL package creation after coordinated storage capture."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from deploy.operations.recovery import record_backup_status
from scripts.postgres_recovery_package import (
    DatabaseConfig,
    create_backup_package,
    verify_backup_package,
)


def _record(path: Path, event: str, **details: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        **details,
    }
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> int:
    status_path = Path(os.environ["NEXORA_BACKUP_STATUS_FILE"])
    event_path = Path(os.environ["NEXORA_RECOVERY_EVENT_LOG"])
    artifact = None
    try:
        storage_root = Path(os.environ["NEXORA_QUIESCED_SNAPSHOT_ROOT"])
        backup_root = Path(os.environ["NEXORA_BACKUP_ROOT"])
        backup_root.mkdir(parents=True, exist_ok=True)
        key_path = Path(os.environ["NEXORA_BACKUP_KEY_FILE"])
        if os.name != "nt" and key_path.stat().st_mode & 0o077:
            raise PermissionError("backup encryption key file permissions are too broad")
        key = key_path.read_bytes().strip()
        key_id = os.environ["NEXORA_BACKUP_KEY_ID"]
        checkpoint = json.loads(
            Path(os.environ["NEXORA_CAPTURE_RECEIPT_FILE"]).read_text(encoding="utf-8")
        )
        root = Path(__file__).resolve().parents[2]
        migration_files = (
            root
            / "database"
            / "contracts"
            / "v1_customer_workflow"
            / "001_customer_workflow_postgres.sql",
        )
        artifact = backup_root / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid4().hex
            + ".fernet"
        )
        _record(event_path, "backup_started", snapshot_id=checkpoint.get("snapshot_id"))
        result = create_backup_package(
            DatabaseConfig.from_env(),
            artifact,
            storage_root=storage_root,
            key=key,
            key_id=key_id,
            checkpoint=checkpoint,
            migration_files=migration_files,
            workflow_key_id=os.environ["NEXORA_WORKFLOW_KEY_ID"],
            evidence_key_id=os.environ["NEXORA_EVIDENCE_KEY_ID"],
        )
        verify_backup_package(
            artifact,
            key=key,
            key_id=key_id,
            migration_files=migration_files,
        )
        record_backup_status(status_path, True)
        _record(
            event_path,
            "backup_completed",
            artifact_name=artifact.name,
            artifact_sha256=result["artifact_sha256"],
            key_id=key_id,
            backup_started_at=result["backup_started_at"],
            backup_completed_at=result["backup_completed_at"],
        )
        print(
            json.dumps(
                {
                    "status": "BACKUP_VERIFIED",
                    "artifact_name": artifact.name,
                    "artifact_sha256": result["artifact_sha256"],
                    "offsite_verified": False,
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        record_backup_status(status_path, False)
        _record(
            event_path,
            "backup_failed",
            error_type=type(error).__name__,
            diagnostic=str(error)[:1000],
        )
        print(f"PostgreSQL backup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
