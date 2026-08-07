"""Tenant-scoped persistence for the authoritative cloud account registry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from auth.authenticated_tenant import AuthenticatedTenantContext
from database.db import get_db


class CloudAccountRegistryRepository:
    def __init__(self, client: Any) -> None:
        self.client = client

    @staticmethod
    def _require(context: AuthenticatedTenantContext) -> None:
        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("AuthenticatedTenantContext is required")

    def list_accounts(self, context: AuthenticatedTenantContext) -> list[dict[str, Any]]:
        self._require(context)
        response = (
            self.client.table("cloud_account_registry")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .order("provider")
            .order("account_id")
            .execute()
        )
        return list(response.data or [])

    def create(self, context: AuthenticatedTenantContext, payload: Mapping[str, Any]):
        self._require(context)
        row = {
            **payload,
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
        }
        return self.client.table("cloud_account_registry").insert(row).execute().data[0]

    def update(
        self, context: AuthenticatedTenantContext, registry_id: str, payload: Mapping[str, Any]
    ):
        self._require(context)
        response = (
            self.client.table("cloud_account_registry")
            .update(dict(payload))
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("id", registry_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def append_audit(self, context: AuthenticatedTenantContext, payload: Mapping[str, Any]):
        row = {
            **payload,
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
        }
        return self.client.table("cloud_account_registry_audit").insert(row).execute().data[0]

    def audit_history(self, context: AuthenticatedTenantContext, registry_id: str):
        response = (
            self.client.table("cloud_account_registry_audit")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("registry_id", registry_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(response.data or [])

    def resolve_account(
        self,
        context: AuthenticatedTenantContext,
        discovered: Mapping[str, Any],
        mapping: Mapping[str, Any],
        *,
        reason: str,
        confirmed: bool,
        expected_state: str = "DISCOVERED",
    ) -> dict[str, Any]:
        self._require(context)
        response = self.client.rpc(
            "fg002_resolve_cloud_account",
            {
                "requested_organization_id": context.organization_id,
                "requested_payer_account_id": discovered.get("payer_account_id"),
                "requested_account_id": discovered.get("account_id"),
                "requested_mapping": dict(mapping),
                "requested_reason": reason,
                "requested_confirmed": confirmed,
                "requested_expected_state": expected_state,
            },
        ).execute()
        return dict(response.data or {})

    def version_history(self, context: AuthenticatedTenantContext, registry_id: str):
        self._require(context)
        response = (
            self.client.table("cloud_account_registry_version")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("registry_id", registry_id)
            .order("version", desc=True)
            .execute()
        )
        return list(response.data or [])

    def bulk_resolve(
        self,
        context: AuthenticatedTenantContext,
        accounts,
        mapping: Mapping[str, Any],
        *,
        reason: str,
        confirmed: bool,
    ):
        self._require(context)
        response = self.client.rpc(
            "fg002_bulk_resolve_cloud_accounts",
            {
                "requested_organization_id": context.organization_id,
                "requested_accounts": list(accounts),
                "requested_mapping": dict(mapping),
                "requested_reason": reason,
                "requested_confirmed": confirmed,
            },
        ).execute()
        return dict(response.data or {})


class LocalCloudAccountRegistryRepository:
    """SQLite-backed registry with the same tenant-scoped contract as Supabase."""

    @staticmethod
    def _require(context: AuthenticatedTenantContext) -> None:
        CloudAccountRegistryRepository._require(context)

    @staticmethod
    def _ensure_schema(conn) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS local_cloud_account_registry (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                account_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (organization_id, tenant_id, provider, account_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS local_cloud_account_registry_audit (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                registry_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _decode(row) -> dict[str, Any]:
        payload = json.loads(row["payload"])
        return {
            **payload,
            "id": row["id"],
            "organization_id": row["organization_id"],
            "tenant_id": row["tenant_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_accounts(self, context: AuthenticatedTenantContext) -> list[dict[str, Any]]:
        self._require(context)
        conn = get_db()
        try:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT * FROM local_cloud_account_registry
                WHERE organization_id = ? AND tenant_id = ?
                ORDER BY provider, account_id
                """,
                (context.organization_id, context.tenant_id),
            ).fetchall()
            conn.commit()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def create(self, context: AuthenticatedTenantContext, payload: Mapping[str, Any]):
        self._require(context)
        row_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        data = dict(payload)
        conn = get_db()
        try:
            self._ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO local_cloud_account_registry (
                    id, organization_id, tenant_id, provider, account_id,
                    payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    context.organization_id,
                    context.tenant_id,
                    data["provider"],
                    data["account_id"],
                    json.dumps(data, default=str),
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            **data,
            "id": row_id,
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
            "created_at": now,
            "updated_at": now,
        }

    def update(
        self,
        context: AuthenticatedTenantContext,
        registry_id: str,
        payload: Mapping[str, Any],
    ):
        self._require(context)
        conn = get_db()
        try:
            self._ensure_schema(conn)
            existing = conn.execute(
                """
                SELECT * FROM local_cloud_account_registry
                WHERE id = ? AND organization_id = ? AND tenant_id = ?
                """,
                (registry_id, context.organization_id, context.tenant_id),
            ).fetchone()
            if not existing:
                return None
            merged = {**json.loads(existing["payload"]), **dict(payload)}
            now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            conn.execute(
                """
                UPDATE local_cloud_account_registry
                SET provider = ?, account_id = ?, payload = ?, updated_at = ?
                WHERE id = ? AND organization_id = ? AND tenant_id = ?
                """,
                (
                    merged["provider"],
                    merged["account_id"],
                    json.dumps(merged, default=str),
                    now,
                    registry_id,
                    context.organization_id,
                    context.tenant_id,
                ),
            )
            conn.commit()
            return {
                **merged,
                "id": registry_id,
                "organization_id": context.organization_id,
                "tenant_id": context.tenant_id,
                "created_at": existing["created_at"],
                "updated_at": now,
            }
        finally:
            conn.close()

    def append_audit(self, context: AuthenticatedTenantContext, payload: Mapping[str, Any]):
        self._require(context)
        audit_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        data = dict(payload)
        conn = get_db()
        try:
            self._ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO local_cloud_account_registry_audit (
                    id, organization_id, tenant_id, registry_id, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    context.organization_id,
                    context.tenant_id,
                    data["registry_id"],
                    json.dumps(data, default=str),
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {**data, "id": audit_id, "created_at": now}

    def audit_history(self, context: AuthenticatedTenantContext, registry_id: str):
        self._require(context)
        conn = get_db()
        try:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT payload, id, created_at
                FROM local_cloud_account_registry_audit
                WHERE organization_id = ? AND tenant_id = ? AND registry_id = ?
                ORDER BY created_at DESC
                """,
                (context.organization_id, context.tenant_id, registry_id),
            ).fetchall()
            conn.commit()
            return [
                {**json.loads(row["payload"]), "id": row["id"], "created_at": row["created_at"]}
                for row in rows
            ]
        finally:
            conn.close()
