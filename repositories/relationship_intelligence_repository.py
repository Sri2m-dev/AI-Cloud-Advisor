"""Tenant-scoped adapters into the existing P3 canonical relationship store."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from data_fabric.contracts import EnterpriseRelationship
from data_fabric.foundation import TenantContext
from database.db import get_db


def _relationship(row: dict[str, Any]) -> EnterpriseRelationship:
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return EnterpriseRelationship(
        id=str(row["id"]),
        relationship_type=str(row["relationship_type"]),
        source_entity_id=str(row["source_entity_id"]),
        target_entity_id=str(row["target_entity_id"]),
        organization_id=str(row["organization_id"]),
        tenant_id=str(row["tenant_id"]),
        source_system=str(row.get("source_system") or "p3_relationship_registry"),
        source_identifier=str(row.get("source_identifier") or row["id"]),
        version=int(row.get("version") or 1),
        confidence_score=float(row.get("confidence_score") or 0)
        / (100 if float(row.get("confidence_score") or 0) > 1 else 1),
        quality_score=float(row.get("quality_score") or 0)
        / (100 if float(row.get("quality_score") or 0) > 1 else 1),
        metadata=dict(metadata),
        evidence=tuple(metadata.get("evidence") or ()),
        discovery_timestamp=_datetime(metadata.get("discovery_timestamp")),
        last_validation=_datetime(metadata.get("last_validation")),
        lineage_reference=metadata.get("lineage_reference"),
        provenance_reference=metadata.get("provenance_reference"),
    )


def _datetime(value):
    return datetime.fromisoformat(str(value)) if value else None


class SQLiteRelationshipIntelligenceRepository:
    """Read the governed local P3 projection; absent store is safely empty."""

    def __init__(self, connection_factory=get_db) -> None:
        self.connection_factory = connection_factory

    def list_relationships(self, context: TenantContext):
        conn = self.connection_factory()
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='enterprise_relationships'"
            ).fetchone()
            if not exists:
                return ()
            rows = conn.execute(
                "SELECT * FROM enterprise_relationships WHERE organization_id=? AND tenant_id=? "
                "AND COALESCE(active,1)=1 ORDER BY id",
                (context.organization_id, context.tenant_id),
            ).fetchall()
            return tuple(_relationship(dict(row)) for row in rows)
        finally:
            conn.close()


class SupabaseRelationshipIntelligenceRepository:
    """Read the existing P3 store with mandatory composite tenant predicates."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def list_relationships(self, context: TenantContext):
        try:
            response = (
                self.client.table("data_fabric.enterprise_relationships")
                .select("*")
                .eq("organization_id", context.organization_id)
                .eq("tenant_id", context.tenant_id)
                .eq("active", True)
                .execute()
            )
            return tuple(_relationship(dict(row)) for row in response.data or ())
        except Exception:
            return ()
