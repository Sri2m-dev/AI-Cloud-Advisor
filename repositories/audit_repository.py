"""Repository boundary for the platform's central audit event stream."""

from __future__ import annotations

import json
from typing import Any, Mapping, Protocol
from uuid import uuid4

from database.db import get_db

PRIMARY_AUDIT_TABLE = "audit_events"


def organization_scope(org_id: str | None) -> str:
    return str(org_id or "1")


def legacy_organization_id(org_id: str | None) -> int:
    return int(org_id) if str(org_id).isdigit() else 1


def event_org_matches(row: Mapping[str, Any], org_id: str | None) -> bool:
    requested = organization_scope(org_id)
    event_data = row.get("event_data") or {}
    recorded = str(event_data.get("org_id") or row.get("organization_id") or "1")
    return recorded == requested


class AuditRepository(Protocol):
    def insert_event(self, event: Mapping[str, Any]) -> dict[str, Any]: ...

    def list_events(
        self,
        *,
        org_id: str | None,
        event_type: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    def get_event(self, *, org_id: str | None, event_id: str) -> dict[str, Any] | None: ...


class SupabaseAuditRepository:
    """Preserve the existing public.audit_events shape and tenant filtering."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def insert_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        response = self.client.table(PRIMARY_AUDIT_TABLE).insert(dict(event)).execute()
        return dict(response.data[0]) if response.data else {"error": "No data returned"}

    def list_events(
        self, *, org_id, event_type=None, resource_type=None, resource_id=None, limit=100
    ) -> list[dict[str, Any]]:
        query = self.client.table(PRIMARY_AUDIT_TABLE).select("*")
        if str(org_id).isdigit():
            query = query.eq("organization_id", legacy_organization_id(org_id))
        if event_type:
            query = query.eq("event_type", event_type)
        if resource_type:
            query = query.eq("event_source", resource_type)
        if resource_id:
            query = query.eq("entity_id", str(resource_id))
        rows = query.order("created_at", desc=True).limit(limit).execute().data or []
        return [dict(row) for row in rows if event_org_matches(row, org_id)]

    def get_event(self, *, org_id, event_id):
        rows = self.list_events(org_id=org_id, limit=1000)
        return next((row for row in rows if str(row.get("id")) == str(event_id)), None)


class SQLiteAuditRepository:
    """Append-only, tenant-scoped local audit persistence."""

    def __init__(self, connection_factory=get_db) -> None:
        self.connection_factory = connection_factory

    @staticmethod
    def _ensure_schema(conn) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS local_audit_events (
                id TEXT PRIMARY KEY,
                organization_scope TEXT NOT NULL,
                organization_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_source TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                event_data TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS local_audit_events_tenant_timeline_idx
                ON local_audit_events (organization_scope, created_at DESC, id DESC);
            CREATE TRIGGER IF NOT EXISTS local_audit_events_no_update
                BEFORE UPDATE ON local_audit_events
                BEGIN SELECT RAISE(ABORT, 'local audit events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS local_audit_events_no_delete
                BEFORE DELETE ON local_audit_events
                BEGIN SELECT RAISE(ABORT, 'local audit events are append-only'); END;
            """
        )

    @staticmethod
    def _decode(row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "organization_id": row["organization_id"],
            "event_type": row["event_type"],
            "event_source": row["event_source"],
            "entity_id": row["entity_id"],
            "actor_id": row["actor_id"],
            "event_data": json.loads(row["event_data"]),
            "created_at": row["created_at"],
        }

    def insert_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(event)
        row["id"] = str(row.get("id") or uuid4())
        scope = organization_scope((row.get("event_data") or {}).get("org_id"))
        conn = self.connection_factory()
        try:
            self._ensure_schema(conn)
            conn.execute(
                """INSERT INTO local_audit_events
                   (id, organization_scope, organization_id, event_type, event_source,
                    entity_id, actor_id, event_data, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["id"],
                    scope,
                    row["organization_id"],
                    row["event_type"],
                    row["event_source"],
                    str(row["entity_id"]),
                    str(row["actor_id"]),
                    json.dumps(row.get("event_data") or {}, default=str, sort_keys=True),
                    row["created_at"],
                ),
            )
            conn.commit()
            return row
        finally:
            conn.close()

    def list_events(
        self, *, org_id, event_type=None, resource_type=None, resource_id=None, limit=100
    ) -> list[dict[str, Any]]:
        clauses = ["organization_scope = ?"]
        values: list[Any] = [organization_scope(org_id)]
        for column, value in (
            ("event_type", event_type),
            ("event_source", resource_type),
            ("entity_id", str(resource_id) if resource_id is not None else None),
        ):
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        values.append(max(0, int(limit)))
        conn = self.connection_factory()
        try:
            self._ensure_schema(conn)
            rows = conn.execute(
                f"SELECT * FROM local_audit_events WHERE {' AND '.join(clauses)} "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                values,
            ).fetchall()
            conn.commit()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def get_event(self, *, org_id, event_id):
        conn = self.connection_factory()
        try:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM local_audit_events WHERE organization_scope = ? AND id = ?",
                (organization_scope(org_id), str(event_id)),
            ).fetchone()
            conn.commit()
            return self._decode(row) if row else None
        finally:
            conn.close()
