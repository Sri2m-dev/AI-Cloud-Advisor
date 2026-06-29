from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class EnterpriseAssetIdentityService:
    ID_PREFIX = "EA"

    @staticmethod
    def sync_asset_identities(organization_id: str | None = None) -> dict[str, Any]:
        return EnterpriseAssetIdentityService.reconcile_assets(organization_id)

    @staticmethod
    def get_identity_coverage(organization_id: str | None = None) -> dict[str, Any]:
        return EnterpriseAssetIdentityService.get_coverage_metrics(organization_id)

    @staticmethod
    def reconcile_assets(organization_id: str | None = None) -> dict[str, Any]:
        organization_id = resolve_organization_id(organization_id)
        discovered_assets = EnterpriseAssetIdentityService._load_discovered_assets(organization_id)
        existing_identities = EnterpriseAssetIdentityService._load_existing_identities(organization_id)
        existing_by_source = EnterpriseAssetIdentityService._index_by_source(existing_identities)
        next_sequence = EnterpriseAssetIdentityService._next_asset_sequence(existing_identities)

        rows_to_upsert = []
        created = 0
        updated = 0

        for asset in discovered_assets:
            source_asset_id = str(asset.get("asset_id") or "").strip()
            provider = str(asset.get("provider") or "").strip()
            connector_name = str(asset.get("connector_name") or "").strip()
            if not source_asset_id or not provider or not connector_name:
                continue

            source_key = EnterpriseAssetIdentityService._source_key(
                organization_id,
                provider,
                connector_name,
                source_asset_id,
            )
            existing = existing_by_source.get(source_key)
            if existing:
                asset_uid = existing.get("asset_uid")
                first_seen_at = existing.get("first_seen_at") or asset.get("created_at")
                updated += 1
            else:
                asset_uid = EnterpriseAssetIdentityService._format_asset_uid(next_sequence)
                first_seen_at = asset.get("created_at") or asset.get("last_seen_at")
                next_sequence += 1
                created += 1

            rows_to_upsert.append(
                {
                    "asset_uid": asset_uid,
                    "organization_id": organization_id,
                    "provider": provider,
                    "connector_name": connector_name,
                    "source_asset_id": source_asset_id,
                    "asset_name": asset.get("asset_name") or source_asset_id,
                    "asset_type": asset.get("asset_type") or "Unknown",
                    "normalized_asset_type": EnterpriseAssetIdentityService._normalize_asset_type(
                        asset.get("asset_type")
                    ),
                    "first_seen_at": EnterpriseAssetIdentityService._coerce_timestamp(first_seen_at),
                    "last_seen_at": EnterpriseAssetIdentityService._coerce_timestamp(asset.get("last_seen_at")),
                    "status": asset.get("status") or "ACTIVE",
                }
            )

        EnterpriseAssetIdentityService._upsert_identity_rows(rows_to_upsert)
        metrics = EnterpriseAssetIdentityService.get_coverage_metrics(organization_id)
        return {
            "status": "SUCCESS",
            "created": created,
            "updated": updated,
            "processed": len(rows_to_upsert),
            "metrics": metrics,
        }

    @staticmethod
    def get_coverage_metrics(organization_id: str | None = None) -> dict[str, Any]:
        organization_id = resolve_organization_id(organization_id)
        discovered_assets = EnterpriseAssetIdentityService._load_discovered_assets(organization_id)
        identities = EnterpriseAssetIdentityService._load_existing_identities(organization_id)
        discovered_keys = {
            EnterpriseAssetIdentityService._source_key(
                organization_id,
                asset.get("provider"),
                asset.get("connector_name"),
                asset.get("asset_id"),
            )
            for asset in discovered_assets
            if asset.get("provider") and asset.get("connector_name") and asset.get("asset_id")
        }
        identity_keys = {
            EnterpriseAssetIdentityService._source_key(
                organization_id,
                identity.get("provider"),
                identity.get("connector_name"),
                identity.get("source_asset_id"),
            )
            for identity in identities
            if identity.get("provider") and identity.get("connector_name") and identity.get("source_asset_id")
        }
        identified = len(discovered_keys & identity_keys)
        total = len(discovered_keys)
        by_provider: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for identity in identities:
            provider = identity.get("provider") or "Unknown"
            asset_type = identity.get("normalized_asset_type") or "Unknown"
            by_provider[provider] = by_provider.get(provider, 0) + 1
            by_type[asset_type] = by_type.get(asset_type, 0) + 1

        return {
            "organization_id": organization_id,
            "discovered_assets": total,
            "identified_assets": identified,
            "missing_identity": max(total - identified, 0),
            "coverage_percent": round((identified / total) * 100, 1) if total else 0,
            "identity_records": len(identities),
            "by_provider": by_provider,
            "by_type": by_type,
        }

    @staticmethod
    def get_asset_identities(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        try:
            organization_id = resolve_organization_id(organization_id)
            response = (
                supabase.table("enterprise_asset_identity")
                .select("*")
                .eq("organization_id", organization_id)
                .order("asset_uid")
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            print("ENTERPRISE ASSET IDENTITY LOAD FAILED:", exc)
            return []

    @staticmethod
    def _load_discovered_assets(organization_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table("discovered_assets")
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
            )
            rows = response.data or []
            if rows:
                return rows

            unassigned_response = (
                supabase.table("discovered_assets")
                .select("*")
                .is_("organization_id", "null")
                .execute()
            )
            return unassigned_response.data or []
        except Exception as exc:
            print("DISCOVERED ASSETS LOAD FAILED:", exc)
            return []

    @staticmethod
    def _load_existing_identities(organization_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table("enterprise_asset_identity")
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            print("ENTERPRISE ASSET IDENTITY LOAD FAILED:", exc)
            return []

    @staticmethod
    def _upsert_identity_rows(rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            (
                supabase.table("enterprise_asset_identity")
                .upsert(
                    rows,
                    on_conflict="organization_id,provider,connector_name,source_asset_id",
                )
                .execute()
            )
        except Exception as exc:
            print("ENTERPRISE ASSET IDENTITY UPSERT FAILED:", exc)

    @staticmethod
    def _index_by_source(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        indexed = {}
        for row in rows:
            key = EnterpriseAssetIdentityService._source_key(
                row.get("organization_id"),
                row.get("provider"),
                row.get("connector_name"),
                row.get("source_asset_id"),
            )
            indexed[key] = row
        return indexed

    @staticmethod
    def _next_asset_sequence(rows: list[dict[str, Any]]) -> int:
        max_sequence = 0
        for row in rows:
            asset_uid = str(row.get("asset_uid") or "")
            if not asset_uid.startswith(f"{EnterpriseAssetIdentityService.ID_PREFIX}-"):
                continue
            try:
                max_sequence = max(max_sequence, int(asset_uid.split("-", 1)[1]))
            except ValueError:
                continue
        return max_sequence + 1

    @staticmethod
    def _format_asset_uid(sequence: int) -> str:
        return f"{EnterpriseAssetIdentityService.ID_PREFIX}-{sequence:06d}"

    @staticmethod
    def _source_key(
        organization_id: Any,
        provider: Any,
        connector_name: Any,
        source_asset_id: Any,
    ) -> str:
        return "|".join(
            [
                str(organization_id or "").strip().lower(),
                str(provider or "").strip().lower(),
                str(connector_name or "").strip().lower(),
                str(source_asset_id or "").strip().lower(),
            ]
        )

    @staticmethod
    def _normalize_asset_type(asset_type: Any) -> str:
        value = str(asset_type or "Unknown").strip()
        lowered = value.lower()
        if "ec2" in lowered or "vm" in lowered or "virtual machine" in lowered:
            return "Compute"
        if "s3" in lowered or "storage" in lowered:
            return "Storage"
        if "rds" in lowered or "sql" in lowered or "database" in lowered:
            return "Database"
        if "vpc" in lowered or "vnet" in lowered or "load balancer" in lowered:
            return "Network"
        if "lambda" in lowered:
            return "Serverless"
        if "eks" in lowered or "aks" in lowered or "cluster" in lowered:
            return "Container Platform"
        if "repo" in lowered or "repository" in lowered:
            return "Repository"
        return value

    @staticmethod
    def _coerce_timestamp(value: Any) -> str:
        if value:
            return str(value)
        return datetime.now(timezone.utc).isoformat()
