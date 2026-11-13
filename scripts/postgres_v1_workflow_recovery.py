"""Encrypted, allowlisted logical recovery for the V1 customer workflow."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import io
import json
import os
import stat
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg2
from cryptography.fernet import Fernet, InvalidToken

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATION = (
    ROOT
    / "database"
    / "contracts"
    / "v1_customer_workflow"
    / "001_customer_workflow_postgres.sql"
)
PACKAGE_FORMAT = "nexora-v1-workflow-logical-v2"
MAX_PACKAGE_BYTES = 1024 * 1024 * 1024
DATA_MEMBERS = (
    "events.jsonl",
    "evidence_objects.jsonl",
    "approvals.jsonl",
    "identity_mappings.jsonl",
)
EVENT_COLUMNS = (
    "event_id",
    "event_type",
    "organization_id",
    "tenant_id",
    "workspace_id",
    "actor_id",
    "idempotency_key",
    "payload_fingerprint",
    "payload_ciphertext",
    "occurred_at",
    "approval_id",
    "approval_action",
    "approval_state",
    "approval_stage",
    "approval_version",
    "approval_requesting_actor",
    "approval_escalated_to",
    "ask_event_id",
    "decision_event_id",
    "evidence_event_id",
)
EVIDENCE_COLUMNS = (
    "event_id",
    "organization_id",
    "tenant_id",
    "workspace_id",
    "encrypted_content",
    "ciphertext_sha256",
)
APPROVAL_COLUMNS = (
    "approval_id",
    "organization_id",
    "tenant_id",
    "workspace_id",
    "requesting_actor",
    "decision_event_id",
    "evidence_event_id",
    "state",
    "workflow_stage",
    "current_approver_role",
    "version",
    "last_event_id",
)


class WorkflowRecoveryError(RuntimeError):
    """A V1 logical recovery operation could not proceed safely."""


def _migration_digest(migration_file: Path) -> str:
    try:
        return hashlib.sha256(migration_file.read_bytes()).hexdigest()
    except OSError as exc:
        raise WorkflowRecoveryError("canonical workflow migration cannot be read") from exc


def _read_key(path: Path, label: str) -> bytes:
    try:
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise WorkflowRecoveryError(f"{label} key file permissions are too broad")
        key = path.read_bytes().strip()
    except OSError as exc:
        raise WorkflowRecoveryError(f"{label} key file cannot be read") from exc
    if not key:
        raise WorkflowRecoveryError(f"{label} key is missing")
    try:
        Fernet(key)
    except (TypeError, ValueError) as exc:
        raise WorkflowRecoveryError(f"{label} key is invalid") from exc
    return key


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    path = os.getenv(f"{name}_FILE", "").strip()
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise WorkflowRecoveryError(f"{name}_FILE cannot be read") from exc
    raise WorkflowRecoveryError(f"{name} or {name}_FILE must be configured")


def _utc(value: Any) -> str:
    if not isinstance(value, datetime):
        raise WorkflowRecoveryError("database returned an invalid timestamp")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("utf-8")
        for row in rows
    )


def _read_jsonl(data: bytes, member: str) -> list[dict[str, Any]]:
    try:
        lines = data.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowRecoveryError(f"package member {member} is not valid JSONL") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise WorkflowRecoveryError(f"package member {member} has an invalid record")
    return rows


def _write_encrypted_package(path: Path, encrypted: bytes) -> None:
    path = path.resolve()
    if path.exists():
        raise WorkflowRecoveryError("backup destination already exists")
    if len(encrypted) > MAX_PACKAGE_BYTES:
        raise WorkflowRecoveryError("encrypted package exceeds the 1 GiB limit")
    try:
        with path.open("xb") as stream:
            stream.write(encrypted)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise WorkflowRecoveryError("backup destination already exists") from exc
    except OSError as exc:
        raise WorkflowRecoveryError("encrypted package could not be written") from exc


def create_package(
    *,
    source_dsn: str,
    destination: Path,
    backup_key: bytes,
    backup_key_id: str,
    workflow_key_id: str,
    evidence_key_id: str,
    migration_file: Path = DEFAULT_MIGRATION,
) -> dict[str, Any]:
    """Capture a consistent logical snapshot of only the V1 workflow contract."""
    for label, value in (
        ("backup", backup_key_id),
        ("workflow", workflow_key_id),
        ("evidence", evidence_key_id),
    ):
        if not value.strip():
            raise WorkflowRecoveryError(f"{label} key ID is required")
    migration_digest = _migration_digest(migration_file)
    try:
        cipher = Fernet(backup_key)
    except (TypeError, ValueError) as exc:
        raise WorkflowRecoveryError("backup encryption key is invalid") from exc

    connection = None
    try:
        connection = psycopg2.connect(source_dsn, connect_timeout=5)
        connection.set_session(
            isolation_level="REPEATABLE READ", readonly=True, autocommit=False
        )
        with connection:
            with connection.cursor() as cursor:
                _verify_catalog(cursor)
                cursor.execute("SHOW server_version_num")
                source_major = int(cursor.fetchone()[0]) // 10000
                if source_major not in (17, 18):
                    raise WorkflowRecoveryError(
                        "logical recovery supports PostgreSQL 17 or 18 sources only"
                    )
                cursor.execute(
                    """
                    SELECT rolsuper, rolbypassrls
                    FROM pg_roles WHERE rolname = current_user
                    """
                )
                source_role = cursor.fetchone()
                if source_role is None or not any(source_role):
                    raise WorkflowRecoveryError(
                        "source connection must be read-capable across tenant RLS"
                    )

                cursor.execute(
                    f"""
                    SELECT {", ".join(EVENT_COLUMNS)}
                    FROM nexora_customer_workflow.events
                    ORDER BY occurred_at, event_id
                    """
                )
                events = []
                for values in cursor.fetchall():
                    event = dict(zip(EVENT_COLUMNS, values))
                    event["occurred_at"] = _utc(event["occurred_at"])
                    events.append(event)
                if not events:
                    raise WorkflowRecoveryError(
                        "refusing to create an empty V1 workflow package"
                    )

                event_ids = {row["event_id"] for row in events}
                if len(event_ids) != len(events):
                    raise WorkflowRecoveryError("source event IDs are not unique")
                for event in events:
                    for reference in (
                        "ask_event_id",
                        "decision_event_id",
                        "evidence_event_id",
                    ):
                        if event[reference] and event[reference] not in event_ids:
                            raise WorkflowRecoveryError(
                                "source workflow contains an unresolved event reference"
                            )

                cursor.execute(
                    f"""
                    SELECT {", ".join(EVIDENCE_COLUMNS)}
                    FROM nexora_customer_workflow.evidence_objects
                    ORDER BY event_id
                    """
                )
                evidence = []
                for values in cursor.fetchall():
                    row = dict(zip(EVIDENCE_COLUMNS, values))
                    row["encrypted_content"] = base64.b64encode(
                        bytes(row["encrypted_content"])
                    ).decode("ascii")
                    evidence.append(row)
                expected_evidence = {
                    row["event_id"]
                    for row in events
                    if row["event_type"] == "EVIDENCE_ADMITTED"
                }
                if {row["event_id"] for row in evidence} != expected_evidence:
                    raise WorkflowRecoveryError(
                        "source encrypted evidence does not match admitted evidence"
                    )
                for row in evidence:
                    if hashlib.sha256(
                        base64.b64decode(row["encrypted_content"], validate=True)
                    ).hexdigest() != row["ciphertext_sha256"]:
                        raise WorkflowRecoveryError(
                            "source encrypted evidence integrity check failed"
                        )

                cursor.execute(
                    f"""
                    SELECT {", ".join(APPROVAL_COLUMNS)}
                    FROM nexora_customer_workflow.approvals
                    ORDER BY approval_id
                    """
                )
                approvals = [
                    dict(zip(APPROVAL_COLUMNS, values))
                    for values in cursor.fetchall()
                ]
                actors = sorted(
                    {(row["actor_id"], row["organization_id"]) for row in events}
                )
                cursor.execute(
                    """
                    SELECT DISTINCT member.auth_user_id::text, member.org_id::text,
                           member.tenant_id::text, member.organization_name,
                           member.workspace_id, member.role, member.status
                    FROM nexora_identity.memberships AS member
                    JOIN (
                        SELECT DISTINCT actor_id, organization_id, tenant_id,
                                        workspace_id
                        FROM nexora_customer_workflow.events
                    ) AS actors
                      ON actors.actor_id = member.auth_user_id::text
                     AND actors.organization_id = member.org_id::text
                     AND actors.tenant_id = member.tenant_id::text
                     AND (member.workspace_id IS NULL
                          OR actors.workspace_id = member.workspace_id)
                    WHERE member.status = 'active'
                    ORDER BY 1, 2
                    """
                )
                profiles = [
                    {
                        "auth_user_id": row[0],
                        "org_id": row[1],
                        "tenant_id": row[2],
                        "organization_name": row[3],
                        "workspace_id": row[4],
                        "role": row[5],
                        "status": row[6],
                    }
                    for row in cursor.fetchall()
                ]
                if {(p["auth_user_id"], p["org_id"]) for p in profiles} != set(actors):
                    raise WorkflowRecoveryError(
                        "source workflow actor profiles are incomplete"
                    )

        members = {
            "events.jsonl": _jsonl(events),
            "evidence_objects.jsonl": _jsonl(evidence),
            "approvals.jsonl": _jsonl(approvals),
            "identity_mappings.jsonl": _jsonl(profiles),
        }
        manifest = {
            "format": PACKAGE_FORMAT,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_postgres_major": source_major,
            "canonical_migration_sha256": migration_digest,
            "key_ids": {
                "backup": backup_key_id,
                "workflow": workflow_key_id,
                "evidence": evidence_key_id,
            },
            "members": {
                name: {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                    "records": len(_read_jsonl(data, name)),
                }
                for name, data in members.items()
            },
        }
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as tar:
            all_members = {
                **members,
                "manifest.json": json.dumps(
                    manifest, sort_keys=True, separators=(",", ":")
                ).encode("utf-8"),
            }
            for name, data in all_members.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
        encrypted = cipher.encrypt(archive.getvalue())
        _write_encrypted_package(destination, encrypted)
        return {
            "package_sha256": hashlib.sha256(encrypted).hexdigest(),
            "encrypted_bytes": len(encrypted),
            "event_count": len(events),
            "evidence_count": len(evidence),
            "approval_count": len(approvals),
            "source_postgres_major": source_major,
        }
    except psycopg2.Error as exc:
        raise WorkflowRecoveryError(
            "source database read or catalog verification failed"
        ) from exc
    finally:
        if connection is not None:
            connection.close()


def _load_package(
    *,
    package: Path,
    backup_key: bytes,
    backup_key_id: str,
    workflow_key_id: str,
    evidence_key_id: str,
    migration_file: Path,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], str]:
    try:
        size = package.stat().st_size
        if size <= 0 or size > MAX_PACKAGE_BYTES:
            raise WorkflowRecoveryError("encrypted package size is invalid")
        encrypted = package.read_bytes()
    except OSError as exc:
        raise WorkflowRecoveryError("encrypted package cannot be read") from exc
    try:
        archive_bytes = Fernet(backup_key).decrypt(encrypted)
    except (InvalidToken, TypeError, ValueError) as exc:
        raise WorkflowRecoveryError(
            "backup key is wrong or encrypted package integrity failed"
        ) from exc
    if len(archive_bytes) > MAX_PACKAGE_BYTES:
        raise WorkflowRecoveryError("decrypted package exceeds the 1 GiB limit")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
            members = tar.getmembers()
            expected_names = {*DATA_MEMBERS, "manifest.json"}
            if (
                len(members) != len(expected_names)
                or {member.name for member in members} != expected_names
                or any(not member.isfile() for member in members)
                or sum(max(0, member.size) for member in members) > MAX_PACKAGE_BYTES
            ):
                raise WorkflowRecoveryError(
                    "package contains missing, duplicate, or unsafe members"
                )
            raw_members: dict[str, bytes] = {}
            for member in members:
                if member.size < 0 or member.size > MAX_PACKAGE_BYTES:
                    raise WorkflowRecoveryError("package member size is invalid")
                stream = tar.extractfile(member)
                if stream is None:
                    raise WorkflowRecoveryError("package member cannot be read")
                raw_members[member.name] = stream.read(member.size + 1)
                if len(raw_members[member.name]) != member.size:
                    raise WorkflowRecoveryError("package member is incomplete")
        manifest = json.loads(raw_members.pop("manifest.json").decode("utf-8"))
    except WorkflowRecoveryError:
        raise
    except (tarfile.TarError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        raise WorkflowRecoveryError("encrypted package archive is corrupt") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != PACKAGE_FORMAT:
        raise WorkflowRecoveryError("package format is unsupported")
    if manifest.get("source_postgres_major") not in (17, 18):
        raise WorkflowRecoveryError("package source PostgreSQL major is incompatible")
    expected_keys = {
        "backup": backup_key_id,
        "workflow": workflow_key_id,
        "evidence": evidence_key_id,
    }
    if manifest.get("key_ids") != expected_keys:
        raise WorkflowRecoveryError("package encryption-key IDs do not match")
    if manifest.get("canonical_migration_sha256") != _migration_digest(migration_file):
        raise WorkflowRecoveryError(
            "package was captured with an incompatible workflow migration"
        )
    expected_manifest_members = manifest.get("members")
    if not isinstance(expected_manifest_members, dict) or set(
        expected_manifest_members
    ) != set(DATA_MEMBERS):
        raise WorkflowRecoveryError("package member inventory is invalid")
    rows: dict[str, list[dict[str, Any]]] = {}
    for name in DATA_MEMBERS:
        data = raw_members[name]
        metadata = expected_manifest_members[name]
        if (
            not isinstance(metadata, dict)
            or metadata.get("size") != len(data)
            or metadata.get("sha256") != hashlib.sha256(data).hexdigest()
        ):
            raise WorkflowRecoveryError(f"package member {name} failed integrity checks")
        rows[name] = _read_jsonl(data, name)
        if metadata.get("records") != len(rows[name]):
            raise WorkflowRecoveryError(f"package member {name} record count is invalid")
    if not rows["events.jsonl"]:
        raise WorkflowRecoveryError("package contains no workflow events")
    return manifest, rows, hashlib.sha256(encrypted).hexdigest()


def _verify_catalog(cursor: Any) -> None:
    expected_columns = {
        "events": EVENT_COLUMNS,
        "evidence_objects": (*EVIDENCE_COLUMNS, "created_at"),
        "approvals": (*APPROVAL_COLUMNS, "created_at"),
        "jwt_verification_settings": (
            "singleton",
            "signing_secret",
            "issuer",
            "verification_mode",
        ),
    }
    cursor.execute(
        """
        SELECT relation.relname, attribute.attname, attribute.attnum
        FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        JOIN pg_attribute AS attribute ON attribute.attrelid = relation.oid
        WHERE namespace.nspname = 'nexora_customer_workflow'
          AND relation.relkind = 'r'
          AND attribute.attnum > 0
          AND NOT attribute.attisdropped
        ORDER BY relation.relname, attribute.attnum
        """
    )
    actual_columns: dict[str, list[str]] = {}
    for table_name, column_name, _ in cursor.fetchall():
        actual_columns.setdefault(table_name, []).append(column_name)
    if any(
        actual_columns.get(table_name) != list(columns)
        for table_name, columns in expected_columns.items()
    ):
        raise WorkflowRecoveryError("V1 workflow table columns do not match the migration")
    cursor.execute(
        """
        SELECT
            to_regclass('nexora_customer_workflow.events') IS NOT NULL,
            to_regclass('nexora_customer_workflow.evidence_objects') IS NOT NULL,
            to_regclass('nexora_customer_workflow.approvals') IS NOT NULL,
            to_regclass('nexora_customer_workflow.jwt_verification_settings') IS NOT NULL,
            to_regclass('nexora_identity.memberships') IS NOT NULL
        """
    )
    if cursor.fetchone() != (True, True, True, True, True):
        raise WorkflowRecoveryError("target lacks required V1 workflow relations")
    cursor.execute(
        """
        SELECT relation.relname, relation.relrowsecurity,
               relation.relforcerowsecurity, pg_get_userbyid(relation.relowner)
        FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'nexora_customer_workflow'
          AND relation.relname IN ('events', 'evidence_objects', 'approvals')
        ORDER BY relation.relname
        """
    )
    catalog = cursor.fetchall()
    if len(catalog) != 3 or any(
        not enabled
        or not forced
        or owner != "nxr_customer_workflow_owner"
        for _, enabled, forced, owner in catalog
    ):
        raise WorkflowRecoveryError(
            "V1 workflow table ownership or forced-RLS contract is incompatible"
        )
    cursor.execute(
        """
        SELECT count(*)
        FROM pg_policies
        WHERE (schemaname, tablename, policyname) IN (
            ('nexora_identity', 'memberships', 'customer_workflow_profile_self'),
            ('nexora_customer_workflow', 'events', 'events_runtime_scope'),
            ('nexora_customer_workflow', 'events', 'events_owner_scope'),
            ('nexora_customer_workflow', 'evidence_objects', 'evidence_runtime_scope'),
            ('nexora_customer_workflow', 'approvals', 'approvals_runtime_read'),
            ('nexora_customer_workflow', 'approvals', 'approvals_owner_scope'),
            ('nexora_identity', 'memberships', 'customer_workflow_profile_scope_guard')
        )
        """
    )
    if cursor.fetchone()[0] != 7:
        raise WorkflowRecoveryError("required tenant RLS policies are missing")
    cursor.execute(
        """
        SELECT count(*)
        FROM pg_trigger AS trigger
        JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE NOT trigger.tgisinternal
          AND namespace.nspname = 'nexora_customer_workflow'
          AND (
              (relation.relname = 'events'
               AND trigger.tgname IN (
                   'enforce_customer_workflow_event',
                   'customer_workflow_events_no_update'
               ))
              OR (relation.relname = 'events'
                  AND trigger.tgname = 'customer_workflow_evidence_object_required')
              OR (relation.relname = 'evidence_objects'
                  AND trigger.tgname = 'customer_workflow_evidence_no_update')
          )
        """
    )
    if cursor.fetchone()[0] != 4:
        raise WorkflowRecoveryError("required append-only workflow triggers are missing")
    cursor.execute(
        """
        SELECT relrowsecurity, relforcerowsecurity,
               pg_get_userbyid(relowner)
        FROM pg_class
        WHERE oid = 'nexora_identity.memberships'::regclass
        """
    )
    identity_catalog = cursor.fetchone()
    if identity_catalog != (True, True, "nxr_customer_workflow_owner"):
        raise WorkflowRecoveryError(
            "application identity mapping RLS or ownership is incompatible"
        )
    cursor.execute(
        """
        SELECT count(*)
        FROM pg_roles
        WHERE rolname IN (
            'nxr_customer_workflow_owner', 'nxr_customer_workflow_runtime'
        )
          AND NOT rolsuper
          AND NOT rolcreatedb
          AND NOT rolcreaterole
          AND NOT rolbypassrls
          AND NOT rolcanlogin
        """
    )
    if cursor.fetchone()[0] != 2:
        raise WorkflowRecoveryError("V1 workflow owner/runtime role contract is invalid")
    cursor.execute(
        """
        SELECT count(*)
        FROM pg_proc AS function
        JOIN pg_namespace AS namespace ON namespace.oid = function.pronamespace
        WHERE namespace.nspname = 'nexora_customer_workflow'
          AND function.proname IN (
              'verified_subject', 'verified_scope', 'enforce_event_contract'
          )
          AND function.prosecdef
          AND pg_get_userbyid(function.proowner) = 'nxr_customer_workflow_owner'
        """
    )
    if cursor.fetchone()[0] != 3:
        raise WorkflowRecoveryError("V1 authorization/append-only functions are incompatible")
    cursor.execute(
        """
        SELECT count(*)
        FROM pg_extension AS extension
        JOIN pg_namespace AS namespace ON namespace.oid = extension.extnamespace
        JOIN pg_proc AS procedure ON procedure.pronamespace = namespace.oid
        JOIN pg_depend AS dependency
          ON dependency.classid = 'pg_proc'::regclass
         AND dependency.objid = procedure.oid
         AND dependency.refclassid = 'pg_extension'::regclass
         AND dependency.refobjid = extension.oid
         AND dependency.deptype = 'e'
        WHERE extension.extname = 'pgcrypto'
          AND procedure.proname = 'hmac'
          AND procedure.pronargs = 3
          AND procedure.proargtypes = '17 17 25'::oidvector
          AND has_schema_privilege(
              'nxr_customer_workflow_owner', namespace.nspname, 'USAGE'
          )
          AND has_function_privilege(
              'nxr_customer_workflow_owner', procedure.oid, 'EXECUTE'
          )
        """
    )
    if cursor.fetchone()[0] != 1:
        raise WorkflowRecoveryError(
            "required pgcrypto hmac function or restricted owner grants are missing"
        )
    cursor.execute(
        """
        SELECT
            has_table_privilege(
                'nxr_customer_workflow_runtime',
                'nexora_customer_workflow.events', 'INSERT'
            ),
            has_table_privilege(
                'nxr_customer_workflow_runtime',
                'nexora_customer_workflow.evidence_objects', 'INSERT'
            ),
            has_table_privilege(
                'nxr_customer_workflow_runtime',
                'nexora_customer_workflow.approvals', 'SELECT'
            ),
            has_table_privilege(
                'nxr_customer_workflow_runtime',
                'nexora_customer_workflow.jwt_verification_settings', 'SELECT'
            ),
            has_column_privilege(
                'nxr_customer_workflow_runtime',
                'nexora_customer_workflow.jwt_verification_settings',
                'signing_secret',
                'SELECT'
            ),
            has_table_privilege(
                'nxr_customer_workflow_runtime',
                'nexora_identity.memberships', 'SELECT'
            ),
            has_table_privilege(
                'nxr_customer_workflow_runtime',
                'nexora_identity.memberships', 'INSERT'
            )
        """
    )
    if cursor.fetchone() != (True, True, True, False, False, True, False):
        raise WorkflowRecoveryError("V1 workflow grants violate least privilege")


def _check_preflight_role(cursor: Any) -> None:
    cursor.execute(
        """
        SELECT
            role.rolsuper,
            role.rolcreatedb,
            role.rolcreaterole,
            role.rolbypassrls,
            pg_has_role(current_user, 'nxr_customer_workflow_owner', 'MEMBER'),
            pg_has_role(current_user, 'nxr_customer_workflow_runtime', 'MEMBER'),
            has_table_privilege(
                current_user, 'nexora_customer_workflow.events', 'SELECT'
            ),
            has_table_privilege(
                current_user, 'nexora_customer_workflow.evidence_objects', 'SELECT'
            ),
            has_table_privilege(
                current_user, 'nexora_customer_workflow.approvals', 'SELECT'
            ),
            has_table_privilege(
                current_user, 'nexora_customer_workflow.events', 'INSERT'
            ),
            has_table_privilege(
                current_user, 'nexora_customer_workflow.events', 'UPDATE'
            ),
            has_table_privilege(
                current_user, 'nexora_customer_workflow.events', 'DELETE'
            ),
            has_table_privilege(
                current_user, 'nexora_customer_workflow.evidence_objects', 'INSERT'
            ),
            has_table_privilege(
                current_user, 'nexora_customer_workflow.approvals', 'UPDATE'
            ),
            has_column_privilege(
                current_user,
                'nexora_customer_workflow.jwt_verification_settings',
                'singleton',
                'SELECT'
            ),
            has_column_privilege(
                current_user,
                'nexora_customer_workflow.jwt_verification_settings',
                'issuer',
                'SELECT'
            ),
            has_column_privilege(
                current_user,
                'nexora_customer_workflow.jwt_verification_settings',
                'signing_secret',
                'SELECT'
            )
        FROM pg_roles AS role
        WHERE role.rolname = current_user
        """
    )
    role = cursor.fetchone()
    if (
        role is None
        or role[0]
        or role[1]
        or role[2]
        or not role[3]
        or role[4]
        or role[5]
        or role[6:9] != (True, True, True)
        or any(role[9:14])
        or role[14:16] != (True, True)
        or role[16]
    ):
        raise WorkflowRecoveryError(
            "preflight credential must be read-only BYPASSRLS without secret "
            "or owner/runtime access"
        )
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM (VALUES
                ('events'),
                ('evidence_objects'),
                ('approvals'),
                ('jwt_verification_settings')
            ) AS relation(name)
            CROSS JOIN (VALUES
                ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE'),
                ('REFERENCES'), ('TRIGGER')
            ) AS privilege(name)
            WHERE has_table_privilege(
                current_user,
                'nexora_customer_workflow.' || relation.name,
                privilege.name
            )
        )
        """
    )
    if cursor.fetchone()[0]:
        raise WorkflowRecoveryError("preflight credential has workflow write privileges")


def _check_runtime_role(cursor: Any) -> None:
    cursor.execute(
        """
        SELECT role.rolname, role.rolcanlogin, role.rolsuper,
               role.rolcreatedb, role.rolcreaterole, role.rolbypassrls,
               role.rolinherit,
               pg_has_role(current_user, 'nxr_customer_workflow_runtime', 'USAGE'),
               pg_has_role(current_user, 'nxr_customer_workflow_owner', 'MEMBER')
        FROM pg_roles AS role
        WHERE role.rolname = current_user
        """
    )
    row = cursor.fetchone()
    if (
        row is None
        or row[0] != "nxr_customer_workflow_app"
        or not row[1]
        or any(row[index] for index in (2, 3, 4, 5))
        or not row[6]
        or not row[7]
        or row[8]
    ):
        raise WorkflowRecoveryError(
            "restore credential violates the V1 least-privilege role contract"
        )


def _signing_input(
    subject: str,
    *,
    secret: str,
    issuer: str,
) -> str:
    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    header = encode(b'{"alg":"HS256","typ":"JWT"}')
    claims = encode(
        json.dumps(
            {
                "aud": "authenticated",
                "exp": int(time.time()) + 900,
                "iss": issuer,
                "role": "authenticated",
                "sub": subject,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    message = f"{header}.{claims}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("ascii"), hashlib.sha256)
    return f"{message}.{encode(signature.digest())}"


def _set_context(cursor: Any, event: dict[str, Any], profile: dict[str, Any],
                 *, jwt_secret: str, jwt_issuer: str) -> None:
    token = _signing_input(
        profile["auth_user_id"], secret=jwt_secret, issuer=jwt_issuer
    )
    cursor.execute(
        """
        SELECT
            set_config('nexora.organization_id', %s, true),
            set_config('nexora.tenant_id', %s, true),
            set_config('nexora.actor_id', %s, true),
            set_config('nexora.role', %s, true),
            set_config('nexora.access_token', %s, true)
        """,
        (
            event["organization_id"],
            event["tenant_id"],
            event["actor_id"],
            profile["role"],
            token,
        ),
    )
    cursor.execute("SELECT nexora_customer_workflow.verified_scope()")
    if cursor.fetchone() != (True,):
        raise WorkflowRecoveryError("target JWT or actor profile failed authorization")


def _insert_event(cursor: Any, event: dict[str, Any]) -> None:
    cursor.execute(
        f"""
        INSERT INTO nexora_customer_workflow.events
            ({", ".join(EVENT_COLUMNS)})
        VALUES ({", ".join(["%s"] * len(EVENT_COLUMNS))})
        """,
        tuple(event[column] for column in EVENT_COLUMNS),
    )


def _validate_package_rows(rows: dict[str, list[dict[str, Any]]]) -> None:
    events = rows["events.jsonl"]
    event_by_id = {event.get("event_id"): event for event in events}
    if len(event_by_id) != len(events) or None in event_by_id:
        raise WorkflowRecoveryError("package event IDs are invalid or duplicated")
    known: set[str] = set()
    for event in events:
        if set(event) != set(EVENT_COLUMNS):
            raise WorkflowRecoveryError("package event row shape is incompatible")
        for reference in ("ask_event_id", "decision_event_id", "evidence_event_id"):
            if event[reference] and event[reference] not in known:
                raise WorkflowRecoveryError(
                    "package event order or dependency references are invalid"
                )
        known.add(event["event_id"])
    expected_evidence = {
        event["event_id"]
        for event in events
        if event["event_type"] == "EVIDENCE_ADMITTED"
    }
    evidence = rows["evidence_objects.jsonl"]
    if {row.get("event_id") for row in evidence} != expected_evidence:
        raise WorkflowRecoveryError("package evidence rows do not match admitted events")
    if any(set(row) != set(EVIDENCE_COLUMNS) for row in evidence):
        raise WorkflowRecoveryError("package evidence row shape is incompatible")
    if any(set(row) != set(APPROVAL_COLUMNS) for row in rows["approvals.jsonl"]):
        raise WorkflowRecoveryError("package approval row shape is incompatible")
    profiles = rows["identity_mappings.jsonl"]
    profile_keys = {(row.get("auth_user_id"), row.get("org_id")) for row in profiles}
    actor_keys = {(event["actor_id"], event["organization_id"]) for event in events}
    if len(profile_keys) != len(profiles) or profile_keys != actor_keys or any(
        set(row)
        != {
            "auth_user_id",
            "org_id",
            "tenant_id",
            "organization_name",
            "workspace_id",
            "role",
            "status",
        }
        or row.get("tenant_id") != row.get("org_id")
        or row.get("status") != "active"
        or not isinstance(row.get("organization_name"), str)
        or not row["organization_name"].strip()
        or row.get("role")
        not in {
            "super_admin",
            "client_admin",
            "executive",
            "cio",
            "finance",
            "operations",
            "security",
            "technical",
            "auditor",
            "viewer",
            "sales_engineer",
        }
        for row in profiles
    ):
        raise WorkflowRecoveryError("package actor/identity mapping is invalid")
    profile_map = {
        (row["auth_user_id"], row["org_id"]): row for row in profiles
    }
    for event in events:
        mapping = profile_map[(event["actor_id"], event["organization_id"])]
        if mapping["workspace_id"] not in (None, event["workspace_id"]):
            raise WorkflowRecoveryError(
                "package actor workspace mapping does not cover its workflow"
            )
    for mapping in profiles:
        try:
            if (
                str(UUID(mapping["auth_user_id"])) != mapping["auth_user_id"]
                or str(UUID(mapping["org_id"])) != mapping["org_id"]
                or str(UUID(mapping["tenant_id"])) != mapping["tenant_id"]
            ):
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise WorkflowRecoveryError(
                "package identity mapping UUIDs are invalid"
            ) from exc
        if mapping["workspace_id"] is not None and not isinstance(
            mapping["workspace_id"], str
        ):
            raise WorkflowRecoveryError(
                "package identity workspace mapping is invalid"
            )
    for row in evidence:
        try:
            ciphertext = base64.b64decode(row["encrypted_content"], validate=True)
        except (ValueError, TypeError) as exc:
            raise WorkflowRecoveryError("package evidence ciphertext is invalid") from exc
        if hashlib.sha256(ciphertext).hexdigest() != row["ciphertext_sha256"]:
            raise WorkflowRecoveryError("package evidence checksum does not match")


def restore_package(
    *,
    package: Path,
    preflight_dsn: str,
    runtime_dsn: str,
    backup_key: bytes,
    backup_key_id: str,
    workflow_key_id: str,
    evidence_key_id: str,
    target_jwt_key_id: str,
    jwt_signing_secret: str,
    jwt_issuer: str,
    migration_file: Path = DEFAULT_MIGRATION,
) -> dict[str, Any]:
    """Restore into an empty PG17 V1 schema without restoring roles or DDL."""
    if not jwt_signing_secret or not jwt_issuer or not target_jwt_key_id.strip():
        raise WorkflowRecoveryError("target JWT key ID and signing configuration are required")
    manifest, rows, package_digest = _load_package(
        package=package,
        backup_key=backup_key,
        backup_key_id=backup_key_id,
        workflow_key_id=workflow_key_id,
        evidence_key_id=evidence_key_id,
        migration_file=migration_file,
    )
    _validate_package_rows(rows)

    preflight = runtime = None
    try:
        preflight = psycopg2.connect(preflight_dsn, connect_timeout=5)
        preflight.set_session(readonly=True, autocommit=False)
        with preflight:
            with preflight.cursor() as cursor:
                _check_preflight_role(cursor)
                _verify_catalog(cursor)
                cursor.execute("SHOW server_version_num")
                if int(cursor.fetchone()[0]) // 10000 != 17:
                    raise WorkflowRecoveryError(
                        "restore target must be PostgreSQL 17"
                    )
                cursor.execute(
                    """
                    SELECT singleton, issuer, verification_mode
                    FROM nexora_customer_workflow.jwt_verification_settings
                    WHERE singleton
                    """
                )
                settings = cursor.fetchone()
                if settings != (True, jwt_issuer, "synthetic_hs256"):
                    raise WorkflowRecoveryError(
                        "target JWT issuer or verification settings do not match"
                    )
                for mapping in rows["identity_mappings.jsonl"]:
                    cursor.execute(
                        """
                        SELECT auth_user_id::text, org_id::text, tenant_id::text,
                               organization_name, workspace_id, role, status
                        FROM nexora_identity.memberships
                        WHERE auth_user_id = %s::uuid AND org_id = %s::uuid
                        """,
                        (mapping["auth_user_id"], mapping["org_id"]),
                    )
                    if cursor.fetchone() != (
                        mapping["auth_user_id"],
                        mapping["org_id"],
                        mapping["tenant_id"],
                        mapping["organization_name"],
                        mapping["workspace_id"],
                        mapping["role"],
                        mapping["status"],
                    ):
                        raise WorkflowRecoveryError(
                            "target identity mapping does not match the recovery package"
                        )
                cursor.execute(
                    """
                    SELECT
                        (SELECT count(*) FROM nexora_customer_workflow.events),
                        (SELECT count(*) FROM nexora_customer_workflow.evidence_objects),
                        (SELECT count(*) FROM nexora_customer_workflow.approvals)
                    """
                )
                if cursor.fetchone() != (0, 0, 0):
                    raise WorkflowRecoveryError(
                        "target V1 workflow tables are not empty; refusing overwrite"
                    )

        profile_map = {
            (row["auth_user_id"], row["org_id"]): row
            for row in rows["identity_mappings.jsonl"]
        }
        event_by_id = {
            row["event_id"]: row for row in rows["events.jsonl"]
        }
        runtime = psycopg2.connect(runtime_dsn, connect_timeout=5)
        runtime.set_session(isolation_level="SERIALIZABLE", autocommit=False)
        with runtime:
            with runtime.cursor() as cursor:
                _check_runtime_role(cursor)
                _verify_catalog(cursor)
                for event in rows["events.jsonl"]:
                    profile = profile_map[
                        (event["actor_id"], event["organization_id"])
                    ]
                    _set_context(
                        cursor,
                        event,
                        profile,
                        jwt_secret=jwt_signing_secret,
                        jwt_issuer=jwt_issuer,
                    )
                    _insert_event(cursor, event)
                for evidence in rows["evidence_objects.jsonl"]:
                    event = event_by_id[evidence["event_id"]]
                    profile = profile_map[
                        (event["actor_id"], event["organization_id"])
                    ]
                    _set_context(
                        cursor,
                        event,
                        profile,
                        jwt_secret=jwt_signing_secret,
                        jwt_issuer=jwt_issuer,
                    )
                    cursor.execute(
                        """
                        INSERT INTO nexora_customer_workflow.evidence_objects
                            (event_id, organization_id, tenant_id, workspace_id,
                             encrypted_content, ciphertext_sha256)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            evidence["event_id"],
                            evidence["organization_id"],
                            evidence["tenant_id"],
                            evidence["workspace_id"],
                            psycopg2.Binary(
                                base64.b64decode(
                                    evidence["encrypted_content"], validate=True
                                )
                            ),
                            evidence["ciphertext_sha256"],
                        ),
                    )
                for approval in rows["approvals.jsonl"]:
                    profile = profile_map[
                        (approval["requesting_actor"], approval["organization_id"])
                    ]
                    event = {
                        "organization_id": approval["organization_id"],
                        "tenant_id": approval["tenant_id"],
                        "actor_id": approval["requesting_actor"],
                    }
                    _set_context(
                        cursor,
                        event,
                        profile,
                        jwt_secret=jwt_signing_secret,
                        jwt_issuer=jwt_issuer,
                    )
                    cursor.execute(
                        f"""
                        SELECT {", ".join(APPROVAL_COLUMNS)}
                        FROM nexora_customer_workflow.approvals
                        WHERE approval_id = %s
                        """,
                        (approval["approval_id"],),
                    )
                    restored = cursor.fetchone()
                    if restored != tuple(
                        approval[column] for column in APPROVAL_COLUMNS
                    ):
                        raise WorkflowRecoveryError(
                            "approval state derived from events does not match package"
                        )

        return {
            "package_sha256": package_digest,
            "source_postgres_major": manifest["source_postgres_major"],
            "target_postgres_major": 17,
            "event_count": len(rows["events.jsonl"]),
            "evidence_count": len(rows["evidence_objects.jsonl"]),
            "approval_count": len(rows["approvals.jsonl"]),
            "target_jwt_key_id": target_jwt_key_id,
        }
    except WorkflowRecoveryError:
        raise
    except psycopg2.Error as exc:
        raise WorkflowRecoveryError(
            "target preflight or transactional restore failed; no partial commit"
        ) from exc
    finally:
        if preflight is not None:
            preflight.close()
        if runtime is not None:
            runtime.close()


def _key_file(value: str, label: str) -> bytes:
    return _read_key(Path(value), label)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="create an encrypted V1 logical package")
    backup.add_argument("--destination", required=True, type=Path)
    backup.add_argument("--backup-key-file", required=True)
    backup.add_argument("--backup-key-id", required=True)
    backup.add_argument("--workflow-key-id", required=True)
    backup.add_argument("--evidence-key-id", required=True)
    backup.add_argument("--migration-file", type=Path, default=DEFAULT_MIGRATION)
    restore = commands.add_parser("restore", help="restore into an empty PG17 V1 schema")
    restore.add_argument("--package", required=True, type=Path)
    restore.add_argument("--backup-key-file", required=True)
    restore.add_argument("--backup-key-id", required=True)
    restore.add_argument("--workflow-key-id", required=True)
    restore.add_argument("--evidence-key-id", required=True)
    restore.add_argument("--target-jwt-key-id", required=True)
    restore.add_argument("--jwt-issuer", required=True)
    restore.add_argument("--jwt-signing-secret-file", required=True)
    restore.add_argument("--migration-file", type=Path, default=DEFAULT_MIGRATION)
    args = parser.parse_args(argv)
    try:
        backup_key = _key_file(args.backup_key_file, "backup")
        if args.command == "backup":
            result = create_package(
                source_dsn=_required_environment("NEXORA_V1_LOGICAL_SOURCE_DSN"),
                destination=args.destination,
                backup_key=backup_key,
                backup_key_id=args.backup_key_id,
                workflow_key_id=args.workflow_key_id,
                evidence_key_id=args.evidence_key_id,
                migration_file=args.migration_file,
            )
        else:
            jwt_secret_path = Path(args.jwt_signing_secret_file)
            try:
                if (
                    os.name != "nt"
                    and stat.S_IMODE(jwt_secret_path.stat().st_mode) & 0o077
                ):
                    raise WorkflowRecoveryError(
                        "target JWT signing secret file permissions are too broad"
                    )
                jwt_secret = jwt_secret_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise WorkflowRecoveryError(
                    "target JWT signing secret file cannot be read"
                ) from exc
            result = restore_package(
                package=args.package,
                preflight_dsn=_required_environment(
                    "NEXORA_V1_LOGICAL_PREFLIGHT_DSN"
                ),
                runtime_dsn=_required_environment(
                    "NEXORA_V1_LOGICAL_RUNTIME_DSN"
                ),
                backup_key=backup_key,
                backup_key_id=args.backup_key_id,
                workflow_key_id=args.workflow_key_id,
                evidence_key_id=args.evidence_key_id,
                target_jwt_key_id=args.target_jwt_key_id,
                jwt_signing_secret=jwt_secret,
                jwt_issuer=args.jwt_issuer,
                migration_file=args.migration_file,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except WorkflowRecoveryError as exc:
        parser.exit(2, f"recovery blocked: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
