"""Create and restore encrypted, verifiable PostgreSQL recovery packages."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from psycopg2 import Error as PsycopgError
from psycopg2 import connect, sql
from psycopg2.extensions import make_dsn

MAX_PACKAGE_BYTES = 1024 * 1024 * 1024
MAX_PACKAGE_FILES = 20000
PACKAGE_FORMAT = "nexora-postgres-recovery-v1"
STORAGE_ROOTS = ("application", "evidence", "prospect")
DATABASE_FILES = ("database.dump", "database_globals.sql", "database_metadata.json")
CHECKPOINT_FIELDS = (
    "database_snapshot_id",
    "file_snapshot_id",
    "operator_ref",
    "captured_at",
)


class RecoveryPackageError(RuntimeError):
    """Raised when a PostgreSQL recovery package cannot be safely used."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: str
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls, prefix: str = "") -> DatabaseConfig:
        names = {
            name.lower(): f"{prefix}PG{name}"
            for name in ("HOST", "PORT", "DATABASE", "USER", "PASSWORD")
        }
        values = {key: os.getenv(name, "").strip() for key, name in names.items()}
        password_file = os.getenv(f"{prefix}PGPASSWORD_FILE", "").strip()
        if password_file:
            path = Path(password_file)
            if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise RecoveryPackageError("database password file permissions are too broad")
            try:
                values["password"] = path.read_text(encoding="utf-8").rstrip("\r\n")
            except OSError as error:
                raise RecoveryPackageError("database password file cannot be read") from error
        missing = [key.upper() for key, value in values.items() if not value]
        if missing:
            raise RecoveryPackageError(
                f"missing database configuration: {', '.join(sorted(missing))}"
            )
        return cls(**values)

    def libpq_env(self) -> dict[str, str]:
        return {"PGPASSWORD": self.password}

    def args(self, *, database: str | None = None) -> list[str]:
        return [
            "--host",
            self.host,
            "--port",
            self.port,
            "--username",
            self.user,
            "--dbname",
            database or self.database,
        ]


def _binary(name: str) -> str:
    return os.getenv(f"NEXORA_{name.upper()}_PATH", "").strip() or name


def _run(
    name: str,
    args: list[str],
    config: DatabaseConfig,
    *,
    stdout: Any = subprocess.PIPE,
) -> str:
    command = [_binary(name), *args]
    try:
        options = {
            "check": True,
            "text": True,
            "timeout": 900,
            "env": {**os.environ, **config.libpq_env()},
        }
        if stdout == subprocess.PIPE:
            result = subprocess.run(command, capture_output=True, **options)
        else:
            result = subprocess.run(command, stdout=stdout, stderr=subprocess.PIPE, **options)
    except FileNotFoundError as error:
        raise RecoveryPackageError(f"required PostgreSQL tool is unavailable: {name}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr or ""
        if config.password:
            detail = detail.replace(config.password, "[REDACTED]")
        raise RecoveryPackageError(
            f"{name} failed: {detail.strip()[-2000:] or 'no diagnostic output'}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise RecoveryPackageError(f"{name} timed out after 900 seconds") from error
    return result.stdout or ""


def _json_rows(cursor) -> list[dict[str, Any]]:
    names = [column.name for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _hash_rows(cursor, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    cursor.execute(query, params)
    digest = hashlib.sha256()
    count = 0
    for (row,) in cursor:
        digest.update(row.encode("utf-8"))
        digest.update(b"\n")
        count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def _migration_inventory(paths: tuple[Path, ...]) -> list[dict[str, str]]:
    if not paths:
        raise RecoveryPackageError("at least one required migration file is required")
    result = []
    for path in sorted(Path(item).resolve() for item in paths):
        if not path.is_file():
            raise RecoveryPackageError(f"required migration file is missing: {path.name}")
        result.append(
            {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    return result


def _database_metadata(
    config: DatabaseConfig,
    migrations: list[dict[str, str]],
    workflow_key_id: str,
    evidence_key_id: str,
) -> dict[str, Any]:
    try:
        connection = connect(
            host=config.host,
            port=int(config.port),
            dbname=config.database,
            user=config.user,
            password=config.password,
            connect_timeout=5,
            application_name="nexora-recovery-qualification",
        )
    except PsycopgError as error:
        raise RecoveryPackageError(
            f"source PostgreSQL connection failed: {str(error).strip()[-1000:]}"
        ) from error
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            server_version_num = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT pg_encoding_to_char(database.encoding), database.datcollate,
                       database.datctype, owner.rolname
                FROM pg_database AS database
                JOIN pg_roles AS owner ON owner.oid = database.datdba
                WHERE database.datname = current_database()
                """
            )
            database = cursor.fetchone()
            if database is None:
                raise RecoveryPackageError("connected database metadata is unavailable")
            cursor.execute(
                """
                SELECT grantor.rolname AS grantor,
                       CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END AS grantee,
                       acl.privilege_type AS privilege,
                       acl.is_grantable AS grantable
                FROM pg_database AS database
                CROSS JOIN LATERAL aclexplode(
                    COALESCE(database.datacl, acldefault('d', database.datdba))
                ) AS acl
                LEFT JOIN pg_roles AS grantor ON grantor.oid = acl.grantor
                LEFT JOIN pg_roles AS grantee ON grantee.oid = acl.grantee
                WHERE database.datname = current_database()
                ORDER BY grantor, grantee, privilege
                """
            )
            database_acl = _json_rows(cursor)
            cursor.execute(
                """
                SELECT role.rolname, role.rolcanlogin, role.rolsuper,
                       role.rolcreatedb, role.rolcreaterole, role.rolinherit,
                       role.rolreplication, role.rolbypassrls, role.rolconnlimit,
                COALESCE(role.rolvaliduntil::text, '') AS rolvaliduntil
                FROM pg_roles AS role
                WHERE role.rolname !~ '^pg_'
                ORDER BY role.rolname
                """
            )
            roles = _json_rows(cursor)
            cursor.execute(
                """
                SELECT granted.rolname AS granted_role, member.rolname AS member,
                       grantor.rolname AS grantor, membership.admin_option,
                       membership.inherit_option, membership.set_option
                FROM pg_auth_members AS membership
                JOIN pg_roles AS granted ON granted.oid = membership.roleid
                JOIN pg_roles AS member ON member.oid = membership.member
                JOIN pg_roles AS grantor ON grantor.oid = membership.grantor
                ORDER BY granted_role, member, grantor
                """
            )
            memberships = _json_rows(cursor)
            cursor.execute(
                """
                SELECT namespace.nspname AS name, owner.rolname AS owner,
                       COALESCE((
                           SELECT json_agg(
                               json_build_object(
                                   'grantee',
                                   CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                                        ELSE acl_grantee.rolname END,
                                   'privilege', acl.privilege_type,
                                   'grantable', acl.is_grantable
                               )
                               ORDER BY CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                                             ELSE acl_grantee.rolname END,
                                        acl.privilege_type
                           )
                           FROM aclexplode(COALESCE(
                               namespace.nspacl,
                               acldefault('n', namespace.nspowner)
                           )) AS acl
                           LEFT JOIN pg_roles AS acl_grantee
                               ON acl_grantee.oid = acl.grantee
                       ), '[]'::json) AS acl
                FROM pg_namespace AS namespace
                JOIN pg_roles AS owner ON owner.oid = namespace.nspowner
                WHERE namespace.nspname !~ '^(pg_|information_schema$)'
                ORDER BY namespace.nspname
                """
            )
            schemas = _json_rows(cursor)
            cursor.execute(
                """
                SELECT namespace.nspname AS schema, relation.relname AS name,
                       relation.relkind AS kind, owner.rolname AS owner,
                       relation.relrowsecurity AS rls,
                       relation.relforcerowsecurity AS force_rls,
                       COALESCE((
                           SELECT json_agg(
                               json_build_object(
                                   'grantee',
                                   CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                                        ELSE acl_grantee.rolname END,
                                   'privilege', acl.privilege_type,
                                   'grantable', acl.is_grantable
                               )
                               ORDER BY CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                                             ELSE acl_grantee.rolname END,
                                        acl.privilege_type
                           )
                           FROM aclexplode(COALESCE(
                               relation.relacl,
                               acldefault(
                                   CASE WHEN relation.relkind = 'S'
                                        THEN 'S'::"char" ELSE 'r'::"char" END,
                                   relation.relowner
                               )
                           )) AS acl
                           LEFT JOIN pg_roles AS acl_grantee
                               ON acl_grantee.oid = acl.grantee
                       ), '[]'::json) AS acl
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                JOIN pg_roles AS owner ON owner.oid = relation.relowner
                WHERE namespace.nspname !~ '^(pg_|information_schema$)'
                  AND relation.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
                ORDER BY namespace.nspname, relation.relname
                """
            )
            relations = _json_rows(cursor)
            cursor.execute(
                """
                SELECT schemaname AS schema, tablename AS table, policyname AS name,
                       permissive, roles::text AS roles, cmd, COALESCE(qual, '') AS using,
                       COALESCE(with_check, '') AS with_check
                FROM pg_policies
                ORDER BY schemaname, tablename, policyname
                """
            )
            policies = _json_rows(cursor)
            cursor.execute(
                """
                SELECT namespace.nspname AS schema, procedure.proname AS name,
                       pg_get_function_identity_arguments(procedure.oid) AS arguments,
                       owner.rolname AS owner, procedure.prosecdef AS security_definer,
                       COALESCE(procedure.proconfig::text, '') AS config,
                       COALESCE((
                           SELECT json_agg(
                               json_build_object(
                                   'grantee',
                                   CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                                        ELSE acl_grantee.rolname END,
                                   'privilege', acl.privilege_type,
                                   'grantable', acl.is_grantable
                               )
                               ORDER BY CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                                             ELSE acl_grantee.rolname END,
                                        acl.privilege_type
                           )
                           FROM aclexplode(COALESCE(
                               procedure.proacl,
                               acldefault('f', procedure.proowner)
                           )) AS acl
                           LEFT JOIN pg_roles AS acl_grantee
                               ON acl_grantee.oid = acl.grantee
                       ), '[]'::json) AS acl,
                       encode(public.digest(pg_get_functiondef(procedure.oid), 'sha256'), 'hex')
                           AS definition_sha256
                FROM pg_proc AS procedure
                JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
                JOIN pg_roles AS owner ON owner.oid = procedure.proowner
                WHERE namespace.nspname !~ '^(pg_|information_schema$)'
                ORDER BY namespace.nspname, procedure.proname,
                         pg_get_function_identity_arguments(procedure.oid)
                """
            )
            functions = _json_rows(cursor)
            cursor.execute(
                """
                SELECT extension.extname AS name, extension.extversion AS version,
                       namespace.nspname AS schema
                FROM pg_extension AS extension
                JOIN pg_namespace AS namespace ON namespace.oid = extension.extnamespace
                ORDER BY extension.extname
                """
            )
            extensions = _json_rows(cursor)

            workflow = {}
            for table, order in (
                ("events", "event_id"),
                ("evidence_objects", "event_id"),
            ):
                if table not in {
                    item["name"]
                    for item in relations
                    if item["schema"] == "nexora_customer_workflow"
                }:
                    continue
                query = sql.SQL(
                    "SELECT to_jsonb(record)::text FROM {}.{} AS record ORDER BY record.{}"
                ).format(
                    sql.Identifier("nexora_customer_workflow"),
                    sql.Identifier(table),
                    sql.Identifier(order),
                )
                workflow[table] = _hash_rows(cursor, query.as_string(connection))
        return {
            "database": {
                "encoding": database[0],
                "collation": database[1],
                "ctype": database[2],
                "owner": database[3],
                "acl_entries": database_acl,
            },
            "server_version_num": server_version_num,
            "roles": roles,
            "memberships": memberships,
            "schemas": schemas,
            "relations": relations,
            "policies": policies,
            "functions": functions,
            "extensions": extensions,
            "migration_versions": migrations,
            "workflow_tables": workflow,
            "required_key_ids": {
                "workflow": workflow_key_id,
                "evidence": evidence_key_id,
            },
            "role_passwords_included": False,
        }
    except PsycopgError as error:
        raise RecoveryPackageError(
            f"PostgreSQL metadata inventory failed: {str(error).strip()[-1000:]}"
        ) from error
    finally:
        connection.close()


def _safe_member(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not path.parts
        or path.is_absolute()
        or "\\" in name
        or ":" in name
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.parts[0] not in {*DATABASE_FILES, *STORAGE_ROOTS}
    ):
        raise RecoveryPackageError("unsafe recovery package path")
    if path.parts[0] in DATABASE_FILES and len(path.parts) != 1:
        raise RecoveryPackageError("invalid database package path")
    if path.parts[0] in STORAGE_ROOTS and len(path.parts) < 2:
        raise RecoveryPackageError("storage package path must name a file")
    if any(
        part.lower().endswith((".key", ".pem")) or part.startswith(".env")
        for part in path.parts
    ):
        raise RecoveryPackageError("secrets must be recovered through separate custody")
    return path.as_posix()


def _validate_checkpoint(checkpoint: dict[str, Any]) -> None:
    if checkpoint.get("mode") != "OPERATOR_QUIESCED_CAPTURE" or not checkpoint.get(
        "snapshot_id"
    ):
        raise RecoveryPackageError("operator-quiesced capture receipt is required")
    if any(not checkpoint.get(field) for field in CHECKPOINT_FIELDS):
        raise RecoveryPackageError("capture receipt is incomplete")
    captured = datetime.fromisoformat(checkpoint["captured_at"].replace("Z", "+00:00"))
    if captured.tzinfo is None or not 0 <= time.time() - captured.timestamp() <= 900:
        raise RecoveryPackageError("capture receipt is stale or has an invalid timestamp")


def _collect_storage(root: Path) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    total = 0
    for storage_root in STORAGE_ROOTS:
        directory = root / storage_root
        if not directory.is_dir() or directory.is_symlink():
            raise RecoveryPackageError(f"required storage snapshot is missing: {storage_root}")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise RecoveryPackageError("symbolic links are not permitted in backups")
            if path.is_dir():
                continue
            if not path.is_file():
                raise RecoveryPackageError("non-regular storage entry in backup")
            name = _safe_member(path.relative_to(root).as_posix())
            content = path.read_bytes()
            members[name] = content
            total += len(content)
            if len(members) > MAX_PACKAGE_FILES or total > MAX_PACKAGE_BYTES:
                raise RecoveryPackageError("backup exceeds the configured size limit")
    return members


def _atomic_publish(destination: Path, encrypted: bytes) -> None:
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


def _seal_package(
    members: dict[str, bytes],
    *,
    key: bytes,
    key_id: str,
    checkpoint: dict[str, Any],
    source: dict[str, str],
    metadata: dict[str, Any],
    backup_started_at: datetime,
    destination: Path,
) -> dict[str, Any]:
    if destination.exists():
        raise RecoveryPackageError("backup destination already exists")
    for required in DATABASE_FILES:
        if not members.get(required):
            raise RecoveryPackageError(f"incomplete PostgreSQL backup: {required} missing")
    if not metadata.get("roles") or metadata.get("role_passwords_included") is not False:
        raise RecoveryPackageError("global role inventory is missing or includes credentials")
    if not metadata.get("migration_versions") or not key_id:
        raise RecoveryPackageError("backup key identity and migrations are required")
    _validate_checkpoint(checkpoint)
    if re.search(rb"\bPASSWORD\b", members["database_globals.sql"], re.IGNORECASE):
        raise RecoveryPackageError("global role dump unexpectedly contains password material")
    for name in members:
        _safe_member(name)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in members.items()}
    manifest = {
        "format": PACKAGE_FORMAT,
        "key_id": key_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backup_started_at": backup_started_at.isoformat(),
        "backup_completed_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint": checkpoint,
        "storage_roots": list(STORAGE_ROOTS),
        "source": source,
        "database": metadata,
        "files": hashes,
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    if len(members) + 1 > MAX_PACKAGE_FILES or (
        sum(len(content) for content in members.values()) + len(manifest_bytes)
        > MAX_PACKAGE_BYTES
    ):
        raise RecoveryPackageError("backup exceeds the configured size limit")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        entries = [
            ("manifest.json", manifest_bytes),
            *members.items(),
        ]
        for name, content in entries:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(content))
    encrypted = Fernet(key).encrypt(stream.getvalue())
    _atomic_publish(destination, encrypted)
    return {
        "artifact_sha256": hashlib.sha256(encrypted).hexdigest(),
        "backup_started_at": manifest["backup_started_at"],
        "backup_completed_at": manifest["backup_completed_at"],
        "key_id": key_id,
        "snapshot_id": checkpoint["snapshot_id"],
        "file_count": len(members),
    }


def create_backup_package(
    source_config: DatabaseConfig,
    destination: Path,
    *,
    storage_root: Path,
    key: bytes,
    key_id: str,
    checkpoint: dict[str, Any],
    migration_files: tuple[Path, ...],
    workflow_key_id: str,
    evidence_key_id: str,
) -> dict[str, Any]:
    destination = Path(destination)
    backup_started_at = datetime.now(timezone.utc)
    migration_versions = _migration_inventory(migration_files)
    if not workflow_key_id or not evidence_key_id:
        raise RecoveryPackageError("workflow and evidence key references are required")
    metadata = _database_metadata(
        source_config, migration_versions, workflow_key_id, evidence_key_id
    )
    with tempfile.TemporaryDirectory(prefix="nexora-pg-backup-") as directory:
        staging = Path(directory)
        database_dump = staging / "database.dump"
        globals_dump = staging / "database_globals.sql"
        _run(
            "pg_dump",
            [
                *source_config.args(),
                "--format=custom",
                "--file",
                str(database_dump),
            ],
            source_config,
        )
        _run(
            "pg_dumpall",
            [
                "--dbname",
                make_dsn(
                    host=source_config.host,
                    port=source_config.port,
                    dbname=source_config.database,
                    user=source_config.user,
                ),
                "--roles-only",
                "--no-role-passwords",
                "--file",
                str(globals_dump),
            ],
            source_config,
        )
        _run("pg_restore", ["--list", str(database_dump)], source_config)
        members = {
            "database.dump": database_dump.read_bytes(),
            "database_globals.sql": globals_dump.read_bytes(),
            "database_metadata.json": json.dumps(metadata, sort_keys=True).encode(),
            **_collect_storage(Path(storage_root)),
        }
    return _seal_package(
        members,
        key=key,
        key_id=key_id,
        checkpoint=checkpoint,
        source={
            "host": source_config.host,
            "port": source_config.port,
            "database": source_config.database,
        },
        metadata=metadata,
        backup_started_at=backup_started_at,
        destination=destination,
    )


def _validate_metadata_contract(metadata: dict[str, Any]) -> None:
    roles = metadata.get("roles")
    if not isinstance(roles, list):
        raise RecoveryPackageError("backup role inventory is invalid")
    role_names = {role.get("rolname") for role in roles if isinstance(role, dict)}
    if None in role_names or not role_names:
        raise RecoveryPackageError("backup role inventory is incomplete")
    required = {metadata.get("database", {}).get("owner")}
    for collection, fields in (
        ("schemas", ("owner",)),
        ("relations", ("owner",)),
        ("functions", ("owner",)),
        ("memberships", ("granted_role", "member", "grantor")),
    ):
        for item in metadata.get(collection, []):
            required.update(item.get(field) for field in fields)
    for grant in metadata.get("database", {}).get("acl_entries", []):
        required.add(grant.get("grantor"))
        if grant.get("grantee") != "PUBLIC":
            required.add(grant.get("grantee"))
    required.discard(None)
    required = {role for role in required if not role.startswith("pg_")}
    if not required <= role_names:
        raise RecoveryPackageError("backup ownership or grants reference missing roles")


def verify_backup_package(
    artifact: Path,
    *,
    key: bytes,
    key_id: str,
    migration_files: tuple[Path, ...] | None = None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    artifact = Path(artifact)
    if not artifact.is_file() or artifact.stat().st_size > MAX_PACKAGE_BYTES * 2:
        raise RecoveryPackageError("backup package is missing or oversized")
    try:
        raw = Fernet(key).decrypt(artifact.read_bytes())
    except (InvalidToken, ValueError) as error:
        raise RecoveryPackageError(
            "backup encryption key is invalid or package is corrupt"
        ) from error
    files: dict[str, bytes] = {}
    manifest = None
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            for item in archive:
                if (
                    not item.isfile()
                    or item.size < 0
                    or total + item.size > MAX_PACKAGE_BYTES
                    or len(files) >= MAX_PACKAGE_FILES
                ):
                    raise RecoveryPackageError("unsafe or oversized recovery package")
                total += item.size
                content_file = archive.extractfile(item)
                if content_file is None:
                    raise RecoveryPackageError("unreadable package member")
                content = content_file.read()
                if item.name == "manifest.json":
                    if manifest is not None:
                        raise RecoveryPackageError("duplicate package manifest")
                    manifest = json.loads(content)
                else:
                    name = _safe_member(item.name)
                    if name in files:
                        raise RecoveryPackageError("duplicate package member")
                    files[name] = content
    except (tarfile.TarError, json.JSONDecodeError) as error:
        raise RecoveryPackageError("package archive or manifest is corrupted") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != PACKAGE_FORMAT
        or manifest.get("key_id") != key_id
        or manifest.get("storage_roots") != list(STORAGE_ROOTS)
    ):
        raise RecoveryPackageError("package format or key identity mismatch")
    if {name: hashlib.sha256(data).hexdigest() for name, data in files.items()} != manifest.get(
        "files"
    ):
        raise RecoveryPackageError("package member checksum mismatch")
    if any(not files.get(name) for name in DATABASE_FILES):
        raise RecoveryPackageError("incomplete PostgreSQL backup package")
    metadata = json.loads(files["database_metadata.json"])
    if metadata != manifest.get("database") or metadata.get("role_passwords_included") is not False:
        raise RecoveryPackageError("database metadata or role-password policy mismatch")
    if re.search(rb"\bPASSWORD\b", files["database_globals.sql"], re.IGNORECASE):
        raise RecoveryPackageError("global role dump contains unexpected password material")
    _validate_metadata_contract(metadata)
    if migration_files is not None and _migration_inventory(migration_files) != metadata.get(
        "migration_versions"
    ):
        raise RecoveryPackageError("recovery migration versions do not match the backup")
    return manifest, files


def _create_database(
    target: DatabaseConfig, target_database: str, metadata: dict[str, Any]
) -> None:
    connection = connect(
        host=target.host,
        port=int(target.port),
        dbname=target.database,
        user=target.user,
        password=target.password,
        connect_timeout=5,
    )
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_database,))
            if cursor.fetchone():
                raise RecoveryPackageError("restore target database already exists")
            cursor.execute(
                sql.SQL(
                    "CREATE DATABASE {} OWNER {} ENCODING {} "
                    "LC_COLLATE {} LC_CTYPE {} TEMPLATE template0"
                ).format(
                    sql.Identifier(target_database),
                    sql.Identifier(metadata["database"]["owner"]),
                    sql.Literal(metadata["database"]["encoding"]),
                    sql.Literal(metadata["database"]["collation"]),
                    sql.Literal(metadata["database"]["ctype"]),
                )
            )
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(target_database)
                )
            )
            allowed_privileges = {"CONNECT", "CREATE", "TEMPORARY"}
            for grant in metadata["database"]["acl_entries"]:
                if grant["privilege"] not in allowed_privileges:
                    raise RecoveryPackageError("unsupported database privilege in backup manifest")
                cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(grant["grantor"])))
                grantee = (
                    sql.SQL("PUBLIC")
                    if grant["grantee"] == "PUBLIC"
                    else sql.Identifier(grant["grantee"])
                )
                grant_sql = sql.SQL("GRANT {} ON DATABASE {} TO {}{}").format(
                    sql.SQL(grant["privilege"]),
                    sql.Identifier(target_database),
                    grantee,
                    sql.SQL(" WITH GRANT OPTION") if grant["grantable"] else sql.SQL(""),
                )
                cursor.execute(grant_sql)
                cursor.execute("RESET ROLE")
    except PsycopgError as error:
        raise RecoveryPackageError(
            f"database creation or ACL restoration failed: {str(error).strip()[-1000:]}"
        ) from error
    finally:
        connection.close()


def _assert_target_database_absent(
    target: DatabaseConfig, target_database: str
) -> None:
    if not target_database or "\x00" in target_database:
        raise RecoveryPackageError("a valid new restore database name is required")
    connection = connect(
        host=target.host,
        port=int(target.port),
        dbname=target.database,
        user=target.user,
        password=target.password,
        connect_timeout=5,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_database,))
            if cursor.fetchone():
                raise RecoveryPackageError("restore target database already exists")
    except PsycopgError as error:
        raise RecoveryPackageError(
            f"cannot validate recovery target credentials/database: {str(error).strip()[-1000:]}"
        ) from error
    finally:
        connection.close()


def _restore_global_roles(target: DatabaseConfig, metadata: dict[str, Any]) -> None:
    connection = connect(
        host=target.host,
        port=int(target.port),
        dbname=target.database,
        user=target.user,
        password=target.password,
        connect_timeout=5,
    )
    try:
        with connection:
            with connection.cursor() as cursor:
                role_names = [role["rolname"] for role in metadata["roles"]]
                cursor.execute(
                    "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                    (role_names,),
                )
                conflicts = [row[0] for row in cursor.fetchall()]
                if conflicts:
                    raise RecoveryPackageError(
                        "recovery target already contains captured roles"
                    )
                for role in metadata["roles"]:
                    options = [
                        "SUPERUSER" if role["rolsuper"] else "NOSUPERUSER",
                        "CREATEDB" if role["rolcreatedb"] else "NOCREATEDB",
                        "CREATEROLE" if role["rolcreaterole"] else "NOCREATEROLE",
                        "INHERIT" if role["rolinherit"] else "NOINHERIT",
                        "LOGIN" if role["rolcanlogin"] else "NOLOGIN",
                        "REPLICATION" if role["rolreplication"] else "NOREPLICATION",
                        "BYPASSRLS" if role["rolbypassrls"] else "NOBYPASSRLS",
                        f"CONNECTION LIMIT {int(role['rolconnlimit'])}",
                    ]
                    statement = sql.SQL("CREATE ROLE {} WITH {}").format(
                        sql.Identifier(role["rolname"]),
                        sql.SQL(" ").join(sql.SQL(option) for option in options),
                    )
                    cursor.execute(statement)
                    if role["rolvaliduntil"]:
                        cursor.execute(
                            sql.SQL("ALTER ROLE {} VALID UNTIL {}").format(
                                sql.Identifier(role["rolname"]),
                                sql.Literal(role["rolvaliduntil"]),
                            )
                        )
                for membership in metadata["memberships"]:
                    options = []
                    if membership["admin_option"]:
                        options.append("ADMIN OPTION")
                    options.extend(
                        (
                            "INHERIT TRUE"
                            if membership["inherit_option"]
                            else "INHERIT FALSE",
                            "SET TRUE" if membership["set_option"] else "SET FALSE",
                        )
                    )
                    cursor.execute(
                        sql.SQL("GRANT {} TO {} WITH {}").format(
                            sql.Identifier(membership["granted_role"]),
                            sql.Identifier(membership["member"]),
                            sql.SQL(", ").join(sql.SQL(option) for option in options),
                        )
                    )
    except PsycopgError as error:
        raise RecoveryPackageError(
            f"global role restoration failed: {str(error).strip()[-1000:]}"
        ) from error
    finally:
        connection.close()


def _publish_storage_files(
    files: dict[str, bytes], destination: Path, storage_roots: list[str]
) -> None:
    destination = Path(destination)
    if destination.exists():
        raise RecoveryPackageError("storage recovery target already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        for root in storage_roots:
            (temporary / root).mkdir(mode=0o700)
        for name, content in files.items():
            path = PurePosixPath(name)
            if path.parts[0] not in storage_roots:
                continue
            target = temporary.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open("xb") as output:
                output.write(content)
        temporary.rename(destination)
    finally:
        if temporary.exists():
            for path in sorted(temporary.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            temporary.rmdir()


def _assert_metadata_matches(
    expected: dict[str, Any], actual: dict[str, Any], *, bootstrap_role: str
) -> None:
    comparable = ("database", "schemas", "relations", "policies", "functions", "extensions",
                  "migration_versions", "workflow_tables", "required_key_ids")
    for field in comparable:
        if expected.get(field) != actual.get(field):
            expected_rows = expected.get(field)
            actual_rows = actual.get(field)
            if isinstance(expected_rows, list) and isinstance(actual_rows, list):
                key_fields = {
                    "schemas": ("name",),
                    "relations": ("schema", "name"),
                    "policies": ("schema", "table", "name"),
                    "functions": ("schema", "name", "arguments"),
                    "extensions": ("name",),
                }.get(field, ())
                expected_by_key = {
                    tuple(row.get(key) for key in key_fields): row
                    for row in expected_rows
                }
                actual_by_key = {
                    tuple(row.get(key) for key in key_fields): row
                    for row in actual_rows
                }
                differing_keys = sorted(
                    set(expected_by_key) | set(actual_by_key), key=str
                )
                for key in differing_keys:
                    old = expected_by_key.get(key)
                    new = actual_by_key.get(key)
                    if old != new:
                        different_fields = (
                            sorted(
                                name
                                for name in set(old or {}) | set(new or {})
                                if (old or {}).get(name) != (new or {}).get(name)
                            )
                            if old is not None and new is not None
                            else ["object_missing"]
                        )
                        raise RecoveryPackageError(
                            f"restored PostgreSQL {field} verification failed "
                            f"for {key}: {', '.join(different_fields)}"
                        )
            raise RecoveryPackageError(f"restored PostgreSQL {field} verification failed")
    expected_roles = [item for item in expected["roles"] if item["rolname"] != bootstrap_role]
    actual_roles = [item for item in actual["roles"] if item["rolname"] != bootstrap_role]
    if expected_roles != actual_roles:
        raise RecoveryPackageError("restored PostgreSQL roles or ownership attributes mismatch")
    membership_fields = (
        "granted_role",
        "member",
        "admin_option",
        "inherit_option",
        "set_option",
    )
    expected_memberships = sorted(
        tuple(item[field] for field in membership_fields)
        for item in expected["memberships"]
        if item["member"] != bootstrap_role and item["granted_role"] != bootstrap_role
    )
    actual_memberships = sorted(
        tuple(item[field] for field in membership_fields)
        for item in actual["memberships"]
        if item["member"] != bootstrap_role and item["granted_role"] != bootstrap_role
    )
    if expected_memberships != actual_memberships:
        raise RecoveryPackageError("restored PostgreSQL role memberships mismatch")
    if _major(expected["server_version_num"]) != _major(actual["server_version_num"]):
        raise RecoveryPackageError("recovery PostgreSQL major version is incompatible")


def _major(version_num: int) -> int:
    return version_num // 10000 if version_num >= 100000 else version_num // 10000


def restore_backup_package(
    artifact: Path,
    target: DatabaseConfig,
    *,
    target_database: str,
    storage_destination: Path,
    key: bytes,
    key_id: str,
    migration_files: tuple[Path, ...],
) -> dict[str, Any]:
    manifest, files = verify_backup_package(
        artifact, key=key, key_id=key_id, migration_files=migration_files
    )
    source = manifest["source"]
    if target.host == source["host"] and target.port == source["port"]:
        raise RecoveryPackageError("recovery PostgreSQL endpoint must differ from the source")
    if target.user in {role["rolname"] for role in manifest["database"]["roles"]}:
        raise RecoveryPackageError("recovery administrator must be distinct from captured roles")
    if Path(storage_destination).exists():
        raise RecoveryPackageError("storage recovery target already exists")
    target_major = int(
        _run("psql", [*target.args(), "-X", "-Atc", "SHOW server_version_num"], target).strip()
    )
    if _major(target_major) != _major(manifest["database"]["server_version_num"]):
        raise RecoveryPackageError("recovery PostgreSQL major version is incompatible")
    _assert_target_database_absent(target, target_database)
    with tempfile.TemporaryDirectory(prefix="nexora-pg-restore-") as directory:
        root = Path(directory)
        dump = root / "database.dump"
        dump.write_bytes(files["database.dump"])
        metadata = manifest["database"]
        _restore_global_roles(target, metadata)
        _create_database(target, target_database, metadata)
        database_target = DatabaseConfig(
            target.host, target.port, target_database, target.user, target.password
        )
        _run(
            "pg_restore",
            [
                *database_target.args(),
                "--exit-on-error",
                "--role",
                metadata["database"]["owner"],
                str(dump),
            ],
            database_target,
        )
        actual = _database_metadata(
            database_target,
            _migration_inventory(migration_files),
            metadata["required_key_ids"]["workflow"],
            metadata["required_key_ids"]["evidence"],
        )
        _assert_metadata_matches(
            metadata, actual, bootstrap_role=target.user
        )
        _publish_storage_files(files, storage_destination, manifest["storage_roots"])
    return {
        "status": "RESTORE_VERIFIED",
        "target_database": target_database,
        "roles_verified": len(manifest["database"]["roles"]),
        "extensions_verified": len(manifest["database"]["extensions"]),
        "schema_objects_verified": len(manifest["database"]["relations"]),
        "workflow_tables_verified": manifest["database"]["workflow_tables"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--destination", type=Path, required=True)
    backup.add_argument("--storage-root", type=Path, required=True)
    backup.add_argument("--key-file", type=Path, required=True)
    backup.add_argument("--key-id", required=True)
    backup.add_argument("--workflow-key-id", required=True)
    backup.add_argument("--evidence-key-id", required=True)
    backup.add_argument("--checkpoint-file", type=Path, required=True)
    backup.add_argument("--migration-file", type=Path, action="append", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--source", type=Path, required=True)
    verify.add_argument("--key-file", type=Path, required=True)
    verify.add_argument("--key-id", required=True)
    verify.add_argument("--migration-file", type=Path, action="append", required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--key-file", type=Path, required=True)
    restore.add_argument("--key-id", required=True)
    restore.add_argument("--migration-file", type=Path, action="append", required=True)
    restore.add_argument("--target-database", required=True)
    restore.add_argument("--storage-destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        key = args.key_file.read_bytes().strip()
        migrations = tuple(args.migration_file)
        if args.command == "backup":
            result = create_backup_package(
                DatabaseConfig.from_env(),
                args.destination,
                storage_root=args.storage_root,
                key=key,
                key_id=args.key_id,
                checkpoint=json.loads(args.checkpoint_file.read_text()),
                migration_files=migrations,
                workflow_key_id=args.workflow_key_id,
                evidence_key_id=args.evidence_key_id,
            )
        elif args.command == "verify":
            manifest, files = verify_backup_package(
                args.source, key=key, key_id=args.key_id, migration_files=migrations
            )
            result = {
                "status": "PACKAGE_VERIFIED",
                "snapshot_id": manifest["checkpoint"]["snapshot_id"],
                "files_verified": len(files),
            }
        else:
            result = restore_backup_package(
                args.source,
                DatabaseConfig.from_env("TARGET_"),
                target_database=args.target_database,
                storage_destination=args.storage_destination,
                key=key,
                key_id=args.key_id,
                migration_files=migrations,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, RecoveryPackageError, subprocess.SubprocessError) as error:
        print(f"PostgreSQL recovery failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
