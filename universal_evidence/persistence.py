"""ACT-009 durable lifecycle metadata repository with strict scope binding."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from universal_evidence.normalization.fingerprints import fingerprint

LIFECYCLE_STATES = frozenset({"ACTIVE", "EXPIRED", "PURGE_PENDING", "PURGED"})
_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "universal_evidence"
    / "0001_create_lifecycle_state.sql"
)


@dataclass(frozen=True, slots=True)
class LifecycleScope:
    organization_id: str
    tenant_id: str
    prospect_id: str | None = None
    analysis_id: str | None = None

    def __post_init__(self) -> None:
        if not self.organization_id or not self.tenant_id:
            raise ValueError("organization_id and tenant_id are required")

    @property
    def values(self) -> tuple[str, str, str | None, str | None]:
        return (self.organization_id, self.tenant_id, self.prospect_id, self.analysis_id)


@dataclass(frozen=True, slots=True)
class LifecycleRecord:
    object_type: str
    object_key: str
    scope: LifecycleScope
    state: str
    fingerprint: str
    payload: Mapping[str, Any] | None
    version: int
    created_at: str
    updated_at: str


class LifecyclePersistenceError(RuntimeError):
    pass


def run_universal_evidence_migrations(database, *, connection_factory=None) -> None:
    """Normal deployment/startup migration entry point; replay-safe and fail-closed."""
    if database is None or not str(database).strip():
        raise LifecyclePersistenceError("durable lifecycle database is required")
    factory = connection_factory or (lambda: sqlite3.connect(str(database)))
    try:
        connection = factory()
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(_MIGRATION.read_text(encoding="utf-8"))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except Exception as exc:
        raise LifecyclePersistenceError("universal evidence migration failed") from exc


class SQLiteLifecycleRepository:
    """SQLite adapter; every lookup and mutation requires the complete scope."""

    def __init__(self, database, *, connection_factory=None, migrate=True):
        self.database = str(database)
        self.connection_factory = connection_factory or (lambda: sqlite3.connect(self.database))
        if migrate:
            self.migrate()

    def migrate(self) -> None:
        run_universal_evidence_migrations(self.database, connection_factory=self.connection_factory)

    def put(
        self,
        object_type: str,
        object_key: str,
        scope: LifecycleScope,
        *,
        state: str = "ACTIVE",
        payload: Mapping[str, Any] | None = None,
        fingerprint_value: str | None = None,
        actor_id: str = "system",
        reason: str = "lifecycle upsert",
    ) -> LifecycleRecord:
        state = str(state).upper()
        if state not in LIFECYCLE_STATES:
            raise ValueError(f"unsupported lifecycle state: {state}")
        if not object_type or not object_key:
            raise ValueError("object_type and object_key are required")
        if payload is not None:
            self._json_payload(payload)
        now = datetime.now(timezone.utc).isoformat()
        value_fingerprint = fingerprint_value or fingerprint(
            object_type, object_key, scope.values, payload, state
        )
        payload_json = (
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if payload is not None
            else None
        )
        connection = self.connection_factory()
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            db_scope = self._db_scope(scope)
            connection.execute(
                """INSERT INTO universal_evidence_lifecycle
                (object_type, object_key, organization_id, tenant_id, prospect_id, analysis_id,
                 state, fingerprint, payload_json, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(
                    object_type, object_key, organization_id, tenant_id,
                    prospect_id, analysis_id
                )
                DO UPDATE SET state=excluded.state, fingerprint=excluded.fingerprint,
                        payload_json=excluded.payload_json,
                        version=CASE WHEN universal_evidence_lifecycle.state = excluded.state
                            AND universal_evidence_lifecycle.fingerprint = excluded.fingerprint
                            AND universal_evidence_lifecycle.payload_json IS excluded.payload_json
                            THEN universal_evidence_lifecycle.version
                            ELSE universal_evidence_lifecycle.version + 1 END,
                        updated_at=CASE WHEN universal_evidence_lifecycle.state = excluded.state
                            AND universal_evidence_lifecycle.fingerprint = excluded.fingerprint
                            AND universal_evidence_lifecycle.payload_json IS excluded.payload_json
                            THEN universal_evidence_lifecycle.updated_at
                            ELSE excluded.updated_at END""",
                (
                    object_type,
                    object_key,
                    *db_scope,
                    state,
                    value_fingerprint,
                    payload_json,
                    now,
                    now,
                ),
            )
            self._audit(
                connection,
                "LIFECYCLE_UPSERT",
                object_type,
                object_key,
                scope,
                value_fingerprint,
                actor_id,
                reason,
                now,
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise LifecyclePersistenceError("lifecycle write failed") from exc
        finally:
            connection.close()
        return self.get(object_type, object_key, scope, include_purged=True)

    def get(
        self,
        object_type: str,
        object_key: str,
        scope: LifecycleScope,
        *,
        include_purged: bool = False,
    ) -> LifecycleRecord:
        connection = self.connection_factory()
        try:
            row = connection.execute(
                """SELECT object_type, object_key, organization_id, tenant_id,
                         prospect_id, analysis_id,
                   state, fingerprint, payload_json, version, created_at, updated_at
                   FROM universal_evidence_lifecycle
                   WHERE object_type=? AND object_key=? AND organization_id=? AND tenant_id=?
                     AND prospect_id = ? AND analysis_id = ?""",
                (object_type, object_key, *self._db_scope(scope)),
            ).fetchone()
        finally:
            connection.close()
        if row is None or (not include_purged and row[6] == "PURGED"):
            raise LifecyclePersistenceError("lifecycle record not found in scope")
        return self._record(row)

    def list_scope(
        self, scope: LifecycleScope, *, include_purged: bool = False
    ) -> tuple[LifecycleRecord, ...]:
        connection = self.connection_factory()
        try:
            rows = connection.execute(
                """SELECT object_type, object_key, organization_id, tenant_id,
                         prospect_id, analysis_id,
                   state, fingerprint, payload_json, version, created_at, updated_at
                   FROM universal_evidence_lifecycle
                   WHERE organization_id=? AND tenant_id=? AND prospect_id = ? AND analysis_id = ?
                   ORDER BY object_type, object_key""",
                self._db_scope(scope),
            ).fetchall()
        finally:
            connection.close()
        records = tuple(self._record(row) for row in rows)
        return (
            records if include_purged else tuple(item for item in records if item.state != "PURGED")
        )

    def list_type(
        self, object_type: str, *, include_purged: bool = False
    ) -> tuple[LifecycleRecord, ...]:
        """Load a typed envelope set for a reconstruction adapter."""
        connection = self.connection_factory()
        try:
            rows = connection.execute(
                """SELECT object_type, object_key, organization_id, tenant_id,
                   prospect_id, analysis_id, state, fingerprint, payload_json,
                   version, created_at, updated_at
                   FROM universal_evidence_lifecycle
                   WHERE object_type = ? ORDER BY organization_id, tenant_id,
                   prospect_id, analysis_id, object_key""",
                (object_type,),
            ).fetchall()
        finally:
            connection.close()
        records = tuple(self._record(row) for row in rows)
        return (
            records if include_purged else tuple(item for item in records if item.state != "PURGED")
        )

    def mark_state(
        self,
        object_type: str,
        object_key: str,
        scope: LifecycleScope,
        state: str,
        *,
        actor_id: str = "system",
        reason: str = "lifecycle transition",
    ) -> LifecycleRecord:
        current = self.get(object_type, object_key, scope, include_purged=True)
        return self.put(
            object_type,
            object_key,
            scope,
            state=state,
            payload=current.payload,
            fingerprint_value=current.fingerprint,
            actor_id=actor_id,
            reason=reason,
        )

    def purge_scope(self, scope: LifecycleScope, *, actor_id: str, reason: str) -> int:
        records = tuple(
            item
            for item in self.list_scope(scope, include_purged=False)
            if item.object_type != "governed_operation_event"
        )
        connection = self.connection_factory()
        now = datetime.now(timezone.utc).isoformat()
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """DELETE FROM universal_evidence_lifecycle
                                     WHERE organization_id=? AND tenant_id=?
                                         AND prospect_id = ? AND analysis_id = ?
                                         AND object_type != 'governed_operation_event'""",
                self._db_scope(scope),
            )
            for record in records:
                tombstone_key = f"{record.object_type}:{record.object_key}"
                tombstone_fp = fingerprint("PURGED", record.fingerprint, scope.values)
                connection.execute(
                    """INSERT INTO universal_evidence_lifecycle
                    (object_type, object_key, organization_id, tenant_id, prospect_id, analysis_id,
                     state, fingerprint, payload_json, version, created_at, updated_at)
                    VALUES ('tombstone', ?, ?, ?, ?, ?, 'PURGED', ?, NULL, 1, ?, ?)""",
                    (tombstone_key, *self._db_scope(scope), tombstone_fp, now, now),
                )
                self._audit(
                    connection,
                    "LIFECYCLE_PURGED",
                    record.object_type,
                    record.object_key,
                    scope,
                    tombstone_fp,
                    actor_id,
                    reason,
                    now,
                )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise LifecyclePersistenceError("scoped purge failed") from exc
        finally:
            connection.close()
        return len(records)

    def audit_events(self, scope: LifecycleScope) -> tuple[dict[str, Any], ...]:
        connection = self.connection_factory()
        try:
            rows = connection.execute(
                """SELECT audit_id, event_type, object_type, object_key,
                                     fingerprint, actor_id, reason, occurred_at
                                     FROM universal_evidence_audit
                                     WHERE organization_id=? AND tenant_id=?
                                         AND prospect_id = ? AND analysis_id = ?
                                     ORDER BY occurred_at, audit_id""",
                self._db_scope(scope),
            ).fetchall()
        finally:
            connection.close()
        return tuple(
            dict(
                zip(
                    (
                        "audit_id",
                        "event_type",
                        "object_type",
                        "object_key",
                        "fingerprint",
                        "actor_id",
                        "reason",
                        "occurred_at",
                    ),
                    row,
                    strict=True,
                )
            )
            for row in rows
        )

    @staticmethod
    def _json_payload(payload):
        if any(isinstance(value, (bytes, bytearray, memoryview)) for value in payload.values()):
            raise ValueError("raw evidence bytes cannot be persisted in lifecycle metadata")
        try:
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("lifecycle payload must be JSON serializable") from exc

    @staticmethod
    def _record(row):
        return LifecycleRecord(
            row[0],
            row[1],
            LifecycleScope(row[2], row[3], row[4] or None, row[5] or None),
            row[6],
            row[7],
            json.loads(row[8]) if row[8] else None,
            row[9],
            row[10],
            row[11],
        )

    @staticmethod
    def _db_scope(scope):
        return tuple(value or "" for value in scope.values)

    @staticmethod
    def _audit(
        connection,
        event_type,
        object_type,
        object_key,
        scope,
        value_fingerprint,
        actor_id,
        reason,
        occurred_at,
    ):
        connection.execute(
            """INSERT INTO universal_evidence_audit
                    (audit_id, event_type, object_type, object_key,
                     organization_id, tenant_id, prospect_id, analysis_id,
                     fingerprint, actor_id, reason, occurred_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid4()),
                event_type,
                object_type,
                object_key,
                *SQLiteLifecycleRepository._db_scope(scope),
                value_fingerprint,
                actor_id,
                reason,
                occurred_at,
            ),
        )
