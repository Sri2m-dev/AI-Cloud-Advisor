"""Offline backup, verification, restore, and key rotation for ACT-009 stores."""

from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from services.customer_workflow_service import CustomerWorkflowError

_MANIFEST = "store-manifest.json"
_MANIFEST_SCHEMA = "nexora.customer-workflow-store.v1"


def _cipher(key: str | bytes, name: str) -> Fernet:
    material = key.encode("ascii") if isinstance(key, str) else key
    try:
        return Fernet(material)
    except (TypeError, ValueError) as exc:
        raise CustomerWorkflowError(f"{name} encryption key is invalid") from exc


def _key_fingerprint(key: str | bytes) -> str:
    material = key.encode("ascii") if isinstance(key, str) else key
    return hashlib.sha256(material).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_backup(source_path: Path, destination_path: Path) -> None:
    source = sqlite3.connect(str(source_path))
    destination = sqlite3.connect(str(destination_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def _event_fingerprint(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _evidence_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if not root.is_dir():
        raise CustomerWorkflowError("customer evidence root is not a directory")
    files = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise CustomerWorkflowError("customer evidence store cannot contain symlinks")
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _write_manifest(
    directory: Path,
    *,
    database: Path,
    evidence_root: Path,
    workflow_key: str | bytes,
    evidence_key: str | bytes,
) -> None:
    manifest = {
        "schema": _MANIFEST_SCHEMA,
        "database_sha256": _file_sha256(database),
        "evidence_files": {
            path.relative_to(evidence_root).as_posix(): _file_sha256(path)
            for path in _evidence_files(evidence_root)
        },
        "workflow_key_sha256": _key_fingerprint(workflow_key),
        "evidence_key_sha256": _key_fingerprint(evidence_key),
    }
    (directory / _MANIFEST).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def verify_customer_store(
    database: str | Path,
    evidence_root: str | Path,
    *,
    workflow_key: str | bytes,
    evidence_key: str | bytes,
    manifest_directory: str | Path | None = None,
) -> dict[str, int]:
    database_path = Path(database).resolve()
    evidence_path = Path(evidence_root).resolve()
    if not database_path.is_file():
        raise CustomerWorkflowError("customer workflow database is unavailable")
    workflow_cipher = _cipher(workflow_key, "customer workflow")
    evidence_cipher = _cipher(evidence_key, "customer evidence")
    files = _evidence_files(evidence_path)
    all_files = {
        path.relative_to(evidence_path).as_posix(): path
        for path in files
    }
    encrypted_files = {
        name: path for name, path in all_files.items() if path.suffix == ".enc"
    }

    manifest_root = Path(manifest_directory).resolve() if manifest_directory else None
    if manifest_root is not None:
        try:
            manifest = json.loads((manifest_root / _MANIFEST).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CustomerWorkflowError(
                "customer store manifest is unavailable or invalid"
            ) from exc
        if manifest.get("schema") != _MANIFEST_SCHEMA:
            raise CustomerWorkflowError("customer store manifest schema is unsupported")
        if manifest.get("database_sha256") != _file_sha256(database_path):
            raise CustomerWorkflowError("customer store database failed its manifest digest check")
        if manifest.get("workflow_key_sha256") != _key_fingerprint(workflow_key):
            raise CustomerWorkflowError("customer workflow key does not match the backup")
        if manifest.get("evidence_key_sha256") != _key_fingerprint(evidence_key):
            raise CustomerWorkflowError("customer evidence key does not match the backup")
        expected_files = manifest.get("evidence_files")
        actual_files = {name: _file_sha256(path) for name, path in all_files.items()}
        if expected_files != actual_files:
            raise CustomerWorkflowError("customer evidence files failed their manifest checks")

    try:
        connection = sqlite3.connect(str(database_path))
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise CustomerWorkflowError(
                    "customer workflow database failed SQLite integrity_check"
                )
            rows = connection.execute(
                """SELECT event_type, payload_fingerprint, payload_ciphertext
                   FROM customer_workflow_events"""
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise CustomerWorkflowError("customer workflow database could not be verified") from exc

    referenced_files: set[str] = set()
    for path in encrypted_files.values():
        try:
            evidence_cipher.decrypt(path.read_bytes())
        except (InvalidToken, OSError) as exc:
            raise CustomerWorkflowError("encrypted customer evidence is unavailable") from exc
    for event_type, payload_digest, ciphertext in rows:
        try:
            plaintext = workflow_cipher.decrypt(ciphertext.encode("ascii"))
            payload = json.loads(plaintext)
        except (AttributeError, InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CustomerWorkflowError("customer workflow record failed integrity checks") from exc
        if not hmac.compare_digest(_event_fingerprint(payload), payload_digest):
            raise CustomerWorkflowError("customer workflow record failed integrity checks")
        if event_type != "EVIDENCE_ADMITTED":
            continue
        relative = Path(str(payload.get("encrypted_source") or ""))
        source = (evidence_path / relative).resolve()
        if not source.is_relative_to(evidence_path):
            raise CustomerWorkflowError("customer evidence locator is outside the configured root")
        relative_name = source.relative_to(evidence_path).as_posix()
        referenced_files.add(relative_name)
        try:
            content = evidence_cipher.decrypt(source.read_bytes())
        except (InvalidToken, OSError) as exc:
            raise CustomerWorkflowError("encrypted customer evidence is unavailable") from exc
        if not hmac.compare_digest(
            hashlib.sha256(content).hexdigest(),
            str(payload.get("source_sha256") or ""),
        ):
            raise CustomerWorkflowError("customer evidence failed its stored digest check")
    if not referenced_files.issubset(encrypted_files):
        raise CustomerWorkflowError("customer evidence references are incomplete")
    return {"events": len(rows), "evidence_files": len(encrypted_files)}


def backup_customer_store(
    database: str | Path,
    evidence_root: str | Path,
    destination: str | Path,
    *,
    workflow_key: str | bytes,
    evidence_key: str | bytes,
) -> dict[str, int]:
    source_db = Path(database).resolve()
    source_evidence = Path(evidence_root).resolve()
    target = Path(destination).resolve()
    if not source_db.is_file():
        raise CustomerWorkflowError("customer workflow database is unavailable")
    if target.exists():
        raise CustomerWorkflowError("backup destination already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    staging.mkdir()
    try:
        staged_db = staging / "database.sqlite"
        _sqlite_backup(source_db, staged_db)
        staged_evidence = staging / "evidence"
        if source_evidence.exists():
            shutil.copytree(source_evidence, staged_evidence)
        else:
            staged_evidence.mkdir()
        _write_manifest(
            staging,
            database=staged_db,
            evidence_root=staged_evidence,
            workflow_key=workflow_key,
            evidence_key=evidence_key,
        )
        result = verify_customer_store(
            staged_db,
            staged_evidence,
            workflow_key=workflow_key,
            evidence_key=evidence_key,
            manifest_directory=staging,
        )
        staging.rename(target)
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def restore_customer_store(
    backup_directory: str | Path,
    destination: str | Path,
    *,
    workflow_key: str | bytes,
    evidence_key: str | bytes,
) -> dict[str, int]:
    source = Path(backup_directory).resolve()
    target = Path(destination).resolve()
    if target.exists():
        raise CustomerWorkflowError("restore destination already exists")
    verify_customer_store(
        source / "database.sqlite",
        source / "evidence",
        workflow_key=workflow_key,
        evidence_key=evidence_key,
        manifest_directory=source,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copytree(source, staging)
        result = verify_customer_store(
            staging / "database.sqlite",
            staging / "evidence",
            workflow_key=workflow_key,
            evidence_key=evidence_key,
            manifest_directory=staging,
        )
        staging.rename(target)
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def rotate_customer_store_keys(
    database: str | Path,
    evidence_root: str | Path,
    destination: str | Path,
    *,
    workflow_key: str | bytes,
    evidence_key: str | bytes,
    new_workflow_key: str | bytes,
    new_evidence_key: str | bytes,
) -> dict[str, int]:
    if _key_fingerprint(workflow_key) == _key_fingerprint(new_workflow_key):
        raise CustomerWorkflowError("new customer workflow key must differ from the current key")
    if _key_fingerprint(evidence_key) == _key_fingerprint(new_evidence_key):
        raise CustomerWorkflowError("new customer evidence key must differ from the current key")
    source_db = Path(database).resolve()
    source_evidence = Path(evidence_root).resolve()
    target = Path(destination).resolve()
    if target.exists():
        raise CustomerWorkflowError("rotation destination already exists")
    verify_customer_store(
        source_db,
        source_evidence,
        workflow_key=workflow_key,
        evidence_key=evidence_key,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    staging.mkdir()
    try:
        staged_db = staging / "database.sqlite"
        _sqlite_backup(source_db, staged_db)
        old_cipher = _cipher(workflow_key, "customer workflow")
        new_cipher = _cipher(new_workflow_key, "new customer workflow")
        connection = sqlite3.connect(str(staged_db))
        try:
            connection.execute("DROP TRIGGER IF EXISTS customer_workflow_events_no_update")
            connection.execute("DROP TRIGGER IF EXISTS customer_workflow_events_no_delete")
            rows = connection.execute(
                """SELECT event_id, payload_fingerprint, payload_ciphertext
                   FROM customer_workflow_events"""
            ).fetchall()
            for event_id, payload_digest, ciphertext in rows:
                try:
                    plaintext = old_cipher.decrypt(ciphertext.encode("ascii"))
                    payload = json.loads(plaintext)
                except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise CustomerWorkflowError(
                        "customer workflow record failed integrity checks during rotation"
                    ) from exc
                if not hmac.compare_digest(_event_fingerprint(payload), payload_digest):
                    raise CustomerWorkflowError(
                        "customer workflow record failed integrity checks during rotation"
                    )
                connection.execute(
                    """UPDATE customer_workflow_events SET payload_ciphertext=?
                       WHERE event_id=?""",
                    (new_cipher.encrypt(plaintext).decode("ascii"), event_id),
                )
            connection.executescript(
                """
                CREATE TRIGGER customer_workflow_events_no_update
                BEFORE UPDATE ON customer_workflow_events
                BEGIN
                    SELECT RAISE(ABORT, 'customer workflow events are append-only');
                END;
                CREATE TRIGGER customer_workflow_events_no_delete
                BEFORE DELETE ON customer_workflow_events
                BEGIN
                    SELECT RAISE(ABORT, 'customer workflow events are append-only');
                END;
                """
            )
            connection.commit()
        finally:
            connection.close()
        old_evidence_cipher = _cipher(evidence_key, "customer evidence")
        new_evidence_cipher = _cipher(new_evidence_key, "new customer evidence")
        staged_evidence = staging / "evidence"
        for source in _evidence_files(source_evidence):
            relative = source.relative_to(source_evidence)
            destination_file = staged_evidence / relative
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if source.suffix == ".enc":
                try:
                    data = new_evidence_cipher.encrypt(old_evidence_cipher.decrypt(data))
                except InvalidToken as exc:
                    raise CustomerWorkflowError(
                        "encrypted customer evidence is unavailable during rotation"
                    ) from exc
            destination_file.write_bytes(data)
        _write_manifest(
            staging,
            database=staged_db,
            evidence_root=staged_evidence,
            workflow_key=new_workflow_key,
            evidence_key=new_evidence_key,
        )
        result = verify_customer_store(
            staged_db,
            staged_evidence,
            workflow_key=new_workflow_key,
            evidence_key=new_evidence_key,
            manifest_directory=staging,
        )
        staging.rename(target)
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging)
