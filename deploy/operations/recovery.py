"""Bounded encrypted snapshot packaging and NEW-directory file recovery.

No database connection, pg_restore, Docker socket, scheduler or deletion. Input
must be a custodian-coordinated quiesced snapshot, never an uncoordinated live tree.
Encryption keys are supplied separately; no key bytes enter the archive/manifest.
"""

import argparse
import io
import json
import os
import tarfile
import tempfile
import time
from datetime import datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath

from cryptography.fernet import Fernet

MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000


def safe_name(name):
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or any(part in {"..", ".", ""} for part in path.parts)
        or "\\" in name
        or ":" in name
    ):
        raise ValueError("unsafe snapshot path")
    if path.parts[0] not in {"application", "evidence", "prospect", "database.dump"}:
        raise ValueError("unexpected snapshot content")
    if (path.parts[0] == "database.dump" and len(path.parts) != 1) or (
        path.parts[0] != "database.dump" and len(path.parts) < 2
    ):
        raise ValueError("invalid snapshot root entry")
    if any(
        part.lower().endswith((".key", ".pem")) or part.startswith(".env") for part in path.parts
    ):
        raise ValueError("keys/configuration must be backed up by separate custody")
    return path.as_posix()


def package_snapshot(source, destination, *, key, key_id, checkpoint):
    source, destination = Path(source), Path(destination)
    if destination.exists() or source.is_symlink() or not source.is_dir():
        raise ValueError("new artifact and existing snapshot directory required")
    # A receipt is traceability to a separately coordinated capture, not proof that
    # this utility stopped external writers or made a cross-system atomic snapshot.
    if (
        not key_id
        or not checkpoint
        or checkpoint.get("mode") != "OPERATOR_QUIESCED_CAPTURE"
        or not checkpoint.get("snapshot_id")
    ):
        raise ValueError("coordinated snapshot reference required")
    for name in ("database_snapshot_id", "file_snapshot_id", "operator_ref", "captured_at"):
        if not checkpoint.get(name):
            raise ValueError("complete capture coordination reference required")
    captured = datetime.fromisoformat(checkpoint["captured_at"].replace("Z", "+00:00"))
    if captured.tzinfo is None or not 0 <= time.time() - captured.timestamp() <= 900:
        raise ValueError(
            "fresh coordinated capture required; stale snapshots must not reset backup freshness"
        )
    roots = ["application", "evidence", "prospect"]
    if any(not (source / root).is_dir() or (source / root).is_symlink() for root in roots):
        raise ValueError("all durable storage snapshot roots are required")
    members = []
    total = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("snapshot links prohibited")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("non-regular snapshot entry")
        name = safe_name(path.relative_to(source).as_posix())
        total += path.stat().st_size
        if total > MAX_BYTES - 1048576 or len(members) >= MAX_FILES:
            raise ValueError("bounded snapshot limit exceeded")
        members.append((name, path.read_bytes()))
    if not members or "database.dump" not in {name for name, _ in members}:
        raise ValueError("coordinated database dump missing")
    manifest = {
        "version": 1,
        "key_id": key_id,
        "checkpoint": checkpoint,
        "roots": roots,
        "files": {name: sha256(data).hexdigest() for name, data in members},
    }
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, data in [
            ("manifest.json", json.dumps(manifest, sort_keys=True).encode()),
            *members,
        ]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(data))
    encrypted = Fernet(key).encrypt(stream.getvalue())
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(encrypted)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        "artifact_sha256": sha256(encrypted).hexdigest(),
        "key_id": key_id,
        "snapshot_id": checkpoint["snapshot_id"],
        "file_count": len(members),
    }


def verify_snapshot(artifact, *, key, key_id):
    artifact = Path(artifact)
    if artifact.stat().st_size > MAX_BYTES * 2:
        raise ValueError("oversized encrypted artifact")
    raw = Fernet(key).decrypt(artifact.read_bytes())
    files, total, manifest = {}, 0, None
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for item in archive:
            if (
                not item.isfile()
                or item.size < 0
                or total + item.size > MAX_BYTES
                or len(files) >= MAX_FILES
            ):
                raise ValueError("unsafe or oversized archive")
            total += item.size
            content = archive.extractfile(item).read()
            if item.name == "manifest.json":
                if manifest is not None:
                    raise ValueError("duplicate manifest")
                manifest = json.loads(content)
            else:
                name = safe_name(item.name)
                if name in files:
                    raise ValueError("duplicate member")
                files[name] = content
    if (
        not manifest
        or manifest.get("version") != 1
        or manifest.get("key_id") != key_id
        or manifest.get("roots") != ["application", "evidence", "prospect"]
    ):
        raise ValueError("manifest/key identity mismatch")
    if {name: sha256(data).hexdigest() for name, data in files.items()} != manifest.get("files"):
        raise ValueError("snapshot integrity mismatch")
    if not files.get("database.dump"):
        raise ValueError("database snapshot missing or empty")
    if any(
        parent.as_posix() in files
        for name in files
        for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    ):
        raise ValueError("conflicting archive paths")
    return manifest, files


def restore_files(artifact, destination, *, key, key_id):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("restore target must be NEW; no overwrites")
    manifest, files = verify_snapshot(artifact, key=key, key_id=key_id)
    destination.mkdir(mode=0o700)
    for root in manifest["roots"]:
        (destination / root).mkdir(mode=0o700)
    for name, content in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open("xb") as output:
            output.write(content)
    return {
        "snapshot_id": manifest["checkpoint"]["snapshot_id"],
        "files_verified": len(files),
        "database_restored": False,
    }


def record_backup_status(path, success, *, now=None):
    path = Path(path)
    now = time.time() if now is None else now
    prior = json.loads(path.read_text()) if path.exists() else {}
    status = {
        "last_attempt": now,
        "last_attempt_success": bool(success),
        "last_success": now if success else prior.get("last_success", 0),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(status))
    # Host backup user owns writes; the dedicated operations group needs only
    # read access to this non-secret status handoff. Archive/key modes stay private.
    os.chmod(temporary, 0o640)
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["package", "verify", "restore-files"])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--checkpoint-file", type=Path)
    parser.add_argument("--status-file", type=Path)
    args = parser.parse_args(argv)
    try:
        key = args.key_file.read_bytes().strip()
        if args.action == "package":
            result = package_snapshot(
                args.source,
                args.destination,
                key=key,
                key_id=args.key_id,
                checkpoint=json.loads(args.checkpoint_file.read_text()),
            )
            verify_snapshot(args.destination, key=key, key_id=args.key_id)
            if args.status_file:
                record_backup_status(args.status_file, True)
        elif args.action == "verify":
            manifest, files = verify_snapshot(args.source, key=key, key_id=args.key_id)
            result = {
                "files_verified": len(files),
                "snapshot_id": manifest["checkpoint"]["snapshot_id"],
            }
        else:
            result = restore_files(args.source, args.destination, key=key, key_id=args.key_id)
        print(json.dumps(result))
        return 0
    except Exception:
        if args.action == "package" and args.status_file:
            record_backup_status(args.status_file, False)
        print(json.dumps({"status": "RECOVERY_OPERATION_FAILED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
