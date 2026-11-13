"""Operate on ACT-009 stores while the application process is stopped."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from services.customer_workflow_maintenance import (
    backup_customer_store,
    restore_customer_store,
    rotate_customer_store_keys,
    verify_customer_store,
)


def _secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    path = os.getenv(f"{name}_FILE", "").strip()
    if not path:
        raise RuntimeError(f"{name} or {name}_FILE must be configured")
    try:
        return Path(path).read_text(encoding="ascii").strip()
    except OSError as exc:
        raise RuntimeError(f"{name}_FILE could not be read") from exc


def _database_and_evidence(arguments) -> tuple[Path, Path, Path | None]:
    if arguments.store_directory:
        directory = Path(arguments.store_directory)
        return directory / "database.sqlite", directory / "evidence", directory
    if not arguments.database or not arguments.evidence_root:
        raise RuntimeError("--database and --evidence-root are required")
    return Path(arguments.database), Path(arguments.evidence_root), None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("verify", "backup", "restore", "rotate"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--store-directory")
        subparser.add_argument("--database")
        subparser.add_argument("--evidence-root")
        subparser.add_argument("--destination")
        subparser.add_argument("--backup-directory")
    arguments = parser.parse_args()
    workflow_key = _secret("NEXORA_CUSTOMER_WORKFLOW_KEY")
    evidence_key = _secret("NEXORA_CUSTOMER_EVIDENCE_KEY")
    if arguments.command == "restore":
        if not arguments.backup_directory or not arguments.destination:
            raise RuntimeError("restore requires --backup-directory and --destination")
        result = restore_customer_store(
            arguments.backup_directory,
            arguments.destination,
            workflow_key=workflow_key,
            evidence_key=evidence_key,
        )
    else:
        database, evidence_root, manifest_directory = _database_and_evidence(arguments)
        if arguments.command == "verify":
            result = verify_customer_store(
                database,
                evidence_root,
                workflow_key=workflow_key,
                evidence_key=evidence_key,
                manifest_directory=manifest_directory,
            )
        elif arguments.command == "backup":
            if not arguments.destination:
                raise RuntimeError("backup requires --destination")
            result = backup_customer_store(
                database,
                evidence_root,
                arguments.destination,
                workflow_key=workflow_key,
                evidence_key=evidence_key,
            )
        else:
            if not arguments.destination:
                raise RuntimeError("rotate requires --destination")
            result = rotate_customer_store_keys(
                database,
                evidence_root,
                arguments.destination,
                workflow_key=workflow_key,
                evidence_key=evidence_key,
                new_workflow_key=_secret("NEXORA_CUSTOMER_WORKFLOW_KEY_NEW"),
                new_evidence_key=_secret("NEXORA_CUSTOMER_EVIDENCE_KEY_NEW"),
            )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
