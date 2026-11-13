from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet

from deploy.operations import recovery


def test_interrupted_backup_does_not_publish_partial_artifact(tmp_path, monkeypatch):
    source = tmp_path / "snapshot"
    for name in ("application", "evidence", "prospect"):
        (source / name).mkdir(parents=True)
    (source / "database.dump").write_bytes(b"synthetic database dump")

    previous = tmp_path / "prior.fernet"
    previous.write_bytes(b"last verified backup")
    destination = tmp_path / "backup.fernet"
    checkpoint = {
        "mode": "OPERATOR_QUIESCED_CAPTURE",
        "snapshot_id": "synthetic-checkpoint",
        "database_snapshot_id": "synthetic-dump",
        "file_snapshot_id": "synthetic-files",
        "operator_ref": "synthetic-operator",
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }

    def interrupt(_fd):
        raise OSError("synthetic interrupted backup")

    monkeypatch.setattr(recovery.os, "fsync", interrupt)
    with pytest.raises(OSError, match="synthetic interrupted backup"):
        recovery.package_snapshot(
            source,
            destination,
            key=Fernet.generate_key(),
            key_id="synthetic-key-id",
            checkpoint=checkpoint,
        )

    assert previous.read_bytes() == b"last verified backup"
    assert not destination.exists()
    assert list(tmp_path.glob(".backup.fernet.*.tmp")) == []
