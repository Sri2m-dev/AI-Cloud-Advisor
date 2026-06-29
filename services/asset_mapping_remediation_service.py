from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.enterprise_relationship_intelligence_service import EnterpriseRelationshipIntelligenceService
from services.supabase_client import supabase


class AssetMappingRemediationService:
    @staticmethod
    def get_unmapped_asset_queue(organization_id: str | None = None) -> list[dict[str, Any]]:
        dashboard = EnterpriseRelationshipIntelligenceService.get_dashboard(organization_id)
        quality_by_asset: dict[tuple[str, str], dict[str, Any]] = {}
        for row in dashboard["remediation"]:
            key = (row.get("Enterprise Asset ID") or "-", row.get("Asset") or "-")
            item = quality_by_asset.setdefault(
                key,
                {
                    "Enterprise Asset ID": row.get("Enterprise Asset ID") or "-",
                    "Asset": row.get("Asset") or "-",
                    "Provider": row.get("Provider") or "-",
                    "Asset Type": row.get("Asset Type") or "-",
                    "Issues": [],
                    "Recommended Actions": [],
                },
            )
            item["Issues"].append(row.get("Issue") or "Review Required")
            item["Recommended Actions"].append(row.get("Recommended Action") or "Review mapping")

        return [
            {
                **row,
                "Issues": ", ".join(dict.fromkeys(row["Issues"])),
                "Recommended Actions": "; ".join(dict.fromkeys(row["Recommended Actions"])),
            }
            for row in quality_by_asset.values()
        ]

    @staticmethod
    def assign_asset_to_application(
        asset_uid: str,
        application_name: str,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        asset = AssetMappingRemediationService._get_asset(asset_uid, organization_id)
        if not asset:
            return AssetMappingRemediationService._result("FAILED", "Asset not found", organization_id)

        organization_id = asset["organization_id"]
        asset_name = asset["asset_name"]
        asset_type = asset.get("normalized_asset_type") or asset.get("asset_type") or "Technology"
        now = AssetMappingRemediationService._now()
        edge = {
            "source_type": asset_type,
            "source_name": asset_name,
            "relationship_type": "MAPS_TO_APPLICATION",
            "target_type": "Application",
            "target_name": application_name,
            "organization_id": organization_id,
            "source_system": "Asset Mapping Remediation",
            "metadata": {
                "asset_uid": asset.get("asset_uid"),
                "source_asset_id": asset.get("source_asset_id"),
                "remediated_at": now,
            },
        }
        AssetMappingRemediationService._upsert_relationship("technology_relationships", edge)
        AssetMappingRemediationService._upsert_relationship("relationship_graph", edge)
        AssetMappingRemediationService._ensure_application_spend_mapping(asset_name, application_name)
        AssetMappingRemediationService._update_discovered_payload(
            asset,
            {
                "application": application_name,
                "registry_app_name": application_name,
                "mapping_reviewed_at": now,
            },
        )
        return AssetMappingRemediationService._result(
            "SUCCESS",
            f"{asset_name} assigned to {application_name}",
            organization_id,
        )

    @staticmethod
    def assign_asset_to_cost_center(
        asset_uid: str,
        cost_center: str,
        organization_id: str | None = None,
        application_name: str | None = None,
    ) -> dict[str, Any]:
        asset = AssetMappingRemediationService._get_asset(asset_uid, organization_id)
        if not asset:
            return AssetMappingRemediationService._result("FAILED", "Asset not found", organization_id)

        now = AssetMappingRemediationService._now()
        AssetMappingRemediationService._update_discovered_payload(
            asset,
            {
                "cost_center": cost_center,
                "mapping_reviewed_at": now,
            },
        )
        if application_name:
            AssetMappingRemediationService._update_application(application_name, {"cost_center": cost_center})

        return AssetMappingRemediationService._result(
            "SUCCESS",
            f"{asset['asset_name']} assigned to cost center {cost_center}",
            asset["organization_id"],
        )

    @staticmethod
    def assign_owner(
        asset_uid: str,
        owner_name: str,
        organization_id: str | None = None,
        owner_email: str | None = None,
        owner_department: str | None = None,
    ) -> dict[str, Any]:
        asset = AssetMappingRemediationService._get_asset(asset_uid, organization_id)
        if not asset:
            return AssetMappingRemediationService._result("FAILED", "Asset not found", organization_id)

        now = AssetMappingRemediationService._now()
        owner_payload = {
            "business_owner": owner_name,
            "technical_owner": owner_name,
            "owner_name": owner_name,
            "owner_email": owner_email,
            "owner_department": owner_department,
            "mapping_reviewed_at": now,
        }
        AssetMappingRemediationService._update_discovered_payload(asset, owner_payload)
        AssetMappingRemediationService._upsert_technology_owner(asset, owner_payload)
        return AssetMappingRemediationService._result(
            "SUCCESS",
            f"{asset['asset_name']} owner assigned to {owner_name}",
            asset["organization_id"],
        )

    @staticmethod
    def mark_reviewed(asset_uid: str, organization_id: str | None = None) -> dict[str, Any]:
        asset = AssetMappingRemediationService._get_asset(asset_uid, organization_id)
        if not asset:
            return AssetMappingRemediationService._result("FAILED", "Asset not found", organization_id)

        now = AssetMappingRemediationService._now()
        AssetMappingRemediationService._update_discovered_payload(
            asset,
            {
                "mapping_reviewed": True,
                "mapping_reviewed_at": now,
            },
        )
        try:
            supabase.table("enterprise_asset_identity").update({"last_seen_at": now}).eq(
                "asset_uid",
                asset_uid,
            ).execute()
        except Exception as exc:
            print("ASSET IDENTITY REVIEW UPDATE FAILED:", exc)

        return AssetMappingRemediationService._result(
            "SUCCESS",
            f"{asset['asset_name']} marked reviewed",
            asset["organization_id"],
        )

    @staticmethod
    def get_quality_score(organization_id: str | None = None) -> dict[str, Any]:
        return EnterpriseRelationshipIntelligenceService.get_relationship_quality_score(organization_id)

    @staticmethod
    def get_applications() -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table("application_registry")
                .select("app_name,owner_name,owner_email,cost_center")
                .order("app_name")
                .execute()
            )
            return response.data or []
        except Exception as exc:
            print("APPLICATION OPTIONS LOAD FAILED:", exc)
            return []

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        quality_dashboard = EnterpriseRelationshipIntelligenceService.get_dashboard(organization_id)
        return {
            "queue": AssetMappingRemediationService.get_unmapped_asset_queue(
                quality_dashboard["coverage"]["organization_id"]
            ),
            "quality": quality_dashboard["quality"],
            "coverage": quality_dashboard["coverage"],
            "applications": AssetMappingRemediationService.get_applications(),
        }

    @staticmethod
    def _get_asset(asset_uid: str, organization_id: str | None = None) -> dict[str, Any] | None:
        resolved_org = resolve_organization_id(organization_id)
        identities = AssetMappingRemediationService._fetch_identities(resolved_org)
        if organization_id and not identities:
            resolved_org = resolve_organization_id()
            identities = AssetMappingRemediationService._fetch_identities(resolved_org)

        asset = None
        for row in identities:
            if row.get("asset_uid") == asset_uid or row.get("source_asset_id") == asset_uid:
                asset = row
                break
        if not asset:
            return None

        discovered = AssetMappingRemediationService._fetch_discovered(asset.get("source_asset_id"), resolved_org)
        return {
            **asset,
            "organization_id": asset.get("organization_id") or resolved_org,
            "asset_name": asset.get("asset_name") or asset.get("source_asset_id") or asset_uid,
            "discovered": discovered or {},
        }

    @staticmethod
    def _fetch_identities(organization_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table("enterprise_asset_identity")
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            print("ASSET IDENTITY LOAD FAILED:", exc)
            return []

    @staticmethod
    def _fetch_discovered(asset_id: Any, organization_id: str) -> dict[str, Any] | None:
        if not asset_id:
            return None
        try:
            response = (
                supabase.table("discovered_assets")
                .select("*")
                .eq("asset_id", asset_id)
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            if rows:
                return rows[0]

            response = (
                supabase.table("discovered_assets")
                .select("*")
                .eq("asset_id", asset_id)
                .is_("organization_id", "null")
                .limit(1)
                .execute()
            )
            rows = response.data or []
            return rows[0] if rows else None
        except Exception as exc:
            print("DISCOVERED ASSET LOAD FAILED:", exc)
            return None

    @staticmethod
    def _upsert_relationship(table_name: str, edge: dict[str, Any]) -> None:
        try:
            supabase.table(table_name).upsert(
                edge,
                on_conflict="organization_id,source_type,source_name,relationship_type,target_type,target_name",
            ).execute()
        except Exception as exc:
            print(f"{table_name.upper()} REMEDIATION UPSERT FAILED:", exc)

    @staticmethod
    def _ensure_application_spend_mapping(asset_name: str, application_name: str) -> None:
        try:
            existing = (
                supabase.table("application_spend_mapping")
                .select("*")
                .eq("spend_application_name", asset_name)
                .eq("registry_app_name", application_name)
                .limit(1)
                .execute()
            )
            if existing.data:
                return
            supabase.table("application_spend_mapping").insert(
                {
                    "spend_application_name": asset_name,
                    "registry_app_name": application_name,
                }
            ).execute()
        except Exception as exc:
            print("APPLICATION SPEND MAPPING REMEDIATION FAILED:", exc)

    @staticmethod
    def _update_discovered_payload(asset: dict[str, Any], updates: dict[str, Any]) -> None:
        discovered = asset.get("discovered") or {}
        asset_id = discovered.get("asset_id") or asset.get("source_asset_id")
        if not asset_id:
            return

        raw_payload = discovered.get("raw_payload") or {}
        if not isinstance(raw_payload, dict):
            raw_payload = {}
        clean_updates = {key: value for key, value in updates.items() if value not in (None, "")}
        raw_payload.update(clean_updates)

        try:
            supabase.table("discovered_assets").update({"raw_payload": raw_payload}).eq(
                "asset_id",
                asset_id,
            ).execute()
        except Exception as exc:
            print("DISCOVERED ASSET REMEDIATION UPDATE FAILED:", exc)

    @staticmethod
    def _upsert_technology_owner(asset: dict[str, Any], owner_payload: dict[str, Any]) -> None:
        technology_name = asset.get("asset_name") or asset.get("source_asset_id")
        if not technology_name:
            return

        payload = {
            "technology_name": technology_name,
            "technology_type": asset.get("asset_type") or "Cloud Resource",
            "vendor_name": asset.get("provider") or "Unknown",
            "category": asset.get("asset_type") or "Cloud Resource",
            "cloud_provider": asset.get("provider"),
            "owner_department": owner_payload.get("owner_department"),
            "business_owner": owner_payload.get("business_owner"),
            "technical_owner": owner_payload.get("technical_owner"),
            "status": "ACTIVE",
            "source_system": "Asset Mapping Remediation",
            "organization_id": asset.get("organization_id"),
            "updated_at": AssetMappingRemediationService._now(),
        }
        payload = {key: value for key, value in payload.items() if value not in (None, "")}

        try:
            existing = (
                supabase.table("technology_inventory")
                .select("technology_name")
                .eq("technology_name", technology_name)
                .limit(1)
                .execute()
            )
            if existing.data:
                supabase.table("technology_inventory").update(payload).eq(
                    "technology_name",
                    technology_name,
                ).execute()
            else:
                supabase.table("technology_inventory").insert(payload).execute()
        except Exception as exc:
            print("TECHNOLOGY OWNER REMEDIATION UPSERT FAILED:", exc)

    @staticmethod
    def _update_application(application_name: str, updates: dict[str, Any]) -> None:
        try:
            supabase.table("application_registry").update(updates).eq("app_name", application_name).execute()
        except Exception as exc:
            print("APPLICATION REMEDIATION UPDATE FAILED:", exc)

    @staticmethod
    def _result(status: str, message: str, organization_id: str | None = None) -> dict[str, Any]:
        quality = EnterpriseRelationshipIntelligenceService.get_relationship_quality_score(organization_id)
        return {
            "status": status,
            "message": message,
            "quality": quality,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
