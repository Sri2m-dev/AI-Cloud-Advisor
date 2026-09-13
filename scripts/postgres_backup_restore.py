"""Safe local PostgreSQL backup, restore, and verification procedure.

Credentials are read from environment variables and never included in command
arguments or output. This utility is for local PostgreSQL operations only; it
does not certify hosted Supabase backups.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class BackupConfigurationError(RuntimeError):
    """Raised for missing or unsafe database configuration."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: str
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls, prefix: str = "") -> "DatabaseConfig":
        names = {name.lower(): f"{prefix}PG{name}" for name in ("HOST", "PORT", "DATABASE", "USER", "PASSWORD")}
        values = {key: os.getenv(env_name, "").strip() for key, env_name in names.items()}
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise BackupConfigurationError(
                f"missing database configuration: {', '.join(name.upper() for name in sorted(missing))}"
            )
        return cls(**values)

    def env(self) -> dict[str, str]:
        return {"PGPASSWORD": self.password}

    def connection_args(self) -> list[str]:
        return ["-h", self.host, "-p", self.port, "-U", self.user, "-d", self.database]


def _binary(name: str) -> str:
    configured = os.getenv(f"NEXORA_{name.upper()}_PATH", "").strip()
    return configured or name


def _run(command: list[str], config: DatabaseConfig, *, stdout=None) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            env={**os.environ, **config.env()},
            stdout=stdout,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise BackupConfigurationError(f"required PostgreSQL tool is unavailable: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"PostgreSQL command failed: {command[0]}") from exc


def _backup(config: DatabaseConfig, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact = destination / f"nexora-{config.database}-{stamp}.dump"
    _run(
        [_binary("pg_dump"), *config.connection_args(), "--format=custom", "--file", str(artifact)],
        config,
    )
    return artifact


def _restore(source: Path, source_config: DatabaseConfig, target_config: DatabaseConfig) -> None:
    if not source.is_file() or source.stat().st_size == 0:
        raise BackupConfigurationError("backup artifact is missing or empty")
    if (
        source_config.host == target_config.host
        and source_config.port == target_config.port
        and source_config.database == target_config.database
    ):
        raise BackupConfigurationError("restore target must be isolated from the source database")
    _run(
        [_binary("pg_restore"), *target_config.connection_args(), "--exit-on-error", str(source)],
        target_config,
    )


def _verify(config: DatabaseConfig, query: str) -> None:
    _run([_binary("psql"), *config.connection_args(), "-v", "ON_ERROR_STOP=1", "-Atc", query], config)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup = subparsers.add_parser("backup")
    backup.add_argument("--destination", type=Path, required=True)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--source", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--query", required=True)
    args = parser.parse_args(argv)
    try:
        source_config = DatabaseConfig.from_env()
        if args.command == "backup":
            print(_backup(source_config, args.destination))
        elif args.command == "restore":
            _restore(args.source, source_config, DatabaseConfig.from_env("TARGET_"))
        else:
            _verify(source_config, args.query)
        return 0
    except (BackupConfigurationError, RuntimeError) as exc:
        print(f"backup/restore failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
