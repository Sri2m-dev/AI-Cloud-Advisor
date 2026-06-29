from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class EnterpriseRelationshipIntelligenceService:
    @staticmethod
    def get_relationship_coverage(organization_id: str | None = None) -> dict[str, Any]:
        context = EnterpriseRelationshipIntelligenceService._load_context(organization_id)
        assets = context["assets"]
        relationship_index = context["relationship_index"]
        related = [
            asset
            for asset in assets
            if EnterpriseRelationshipIntelligenceService._asset_has_relationship(asset, relationship_index)
        ]
        total = len(assets)
        return {
            "organization_id": context["organization_id"],
            "total_assets": total,
            "related_assets": len(related),
            "orphan_assets": max(total - len(related), 0),
            "relationship_edges": len(context["relationships"]),
            "coverage_percent": EnterpriseRelationshipIntelligenceService._percent(len(related), total),
        }

    @staticmethod
    def get_orphan_assets(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = EnterpriseRelationshipIntelligenceService._load_context(organization_id)
        relationship_index = context["relationship_index"]
        return [
            EnterpriseRelationshipIntelligenceService._remediation_row(
                asset,
                "Orphan Asset",
                "Create technology/application relationship in relationship graph",
            )
            for asset in context["assets"]
            if not EnterpriseRelationshipIntelligenceService._asset_has_relationship(asset, relationship_index)
        ]

    @staticmethod
    def get_assets_without_owners(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = EnterpriseRelationshipIntelligenceService._load_context(organization_id)
        return [
            EnterpriseRelationshipIntelligenceService._remediation_row(
                asset,
                "Missing Owner",
                "Assign business or technical owner",
            )
            for asset in context["assets"]
            if not EnterpriseRelationshipIntelligenceService._asset_has_owner(asset, context["inventory_by_name"])
        ]

    @staticmethod
    def get_assets_without_application_mapping(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = EnterpriseRelationshipIntelligenceService._load_context(organization_id)
        return [
            EnterpriseRelationshipIntelligenceService._remediation_row(
                asset,
                "Missing Application Mapping",
                "Map asset to application registry or application spend mapping",
            )
            for asset in context["assets"]
            if not EnterpriseRelationshipIntelligenceService._asset_has_application_mapping(asset, context)
        ]

    @staticmethod
    def get_assets_without_cost_mapping(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = EnterpriseRelationshipIntelligenceService._load_context(organization_id)
        return [
            EnterpriseRelationshipIntelligenceService._remediation_row(
                asset,
                "Missing Cost Mapping",
                "Connect asset identity to unified cloud cost resource or application spend",
            )
            for asset in context["assets"]
            if not EnterpriseRelationshipIntelligenceService._asset_has_cost_mapping(asset, context)
        ]

    @staticmethod
    def get_relationship_quality_score(organization_id: str | None = None) -> dict[str, Any]:
        context = EnterpriseRelationshipIntelligenceService._load_context(organization_id)
        assets = context["assets"]
        total = len(assets)
        relationship_count = sum(
            1
            for asset in assets
            if EnterpriseRelationshipIntelligenceService._asset_has_relationship(asset, context["relationship_index"])
        )
        owner_count = sum(
            1
            for asset in assets
            if EnterpriseRelationshipIntelligenceService._asset_has_owner(asset, context["inventory_by_name"])
        )
        app_count = sum(
            1
            for asset in assets
            if EnterpriseRelationshipIntelligenceService._asset_has_application_mapping(asset, context)
        )
        cost_count = sum(
            1
            for asset in assets
            if EnterpriseRelationshipIntelligenceService._asset_has_cost_mapping(asset, context)
        )
        relationship_score = EnterpriseRelationshipIntelligenceService._percent(relationship_count, total)
        owner_score = EnterpriseRelationshipIntelligenceService._percent(owner_count, total)
        app_score = EnterpriseRelationshipIntelligenceService._percent(app_count, total)
        cost_score = EnterpriseRelationshipIntelligenceService._percent(cost_count, total)
        quality_score = round(
            (relationship_score * 0.4)
            + (owner_score * 0.2)
            + (app_score * 0.2)
            + (cost_score * 0.2),
            1,
        )
        return {
            "organization_id": context["organization_id"],
            "score": quality_score,
            "relationship_score": relationship_score,
            "owner_score": owner_score,
            "application_mapping_score": app_score,
            "cost_mapping_score": cost_score,
            "total_assets": total,
        }

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        coverage = EnterpriseRelationshipIntelligenceService.get_relationship_coverage(organization_id)
        orphan_assets = EnterpriseRelationshipIntelligenceService.get_orphan_assets(coverage["organization_id"])
        missing_owners = EnterpriseRelationshipIntelligenceService.get_assets_without_owners(
            coverage["organization_id"]
        )
        missing_apps = EnterpriseRelationshipIntelligenceService.get_assets_without_application_mapping(
            coverage["organization_id"]
        )
        missing_costs = EnterpriseRelationshipIntelligenceService.get_assets_without_cost_mapping(
            coverage["organization_id"]
        )
        quality = EnterpriseRelationshipIntelligenceService.get_relationship_quality_score(
            coverage["organization_id"]
        )
        remediation = EnterpriseRelationshipIntelligenceService._dedupe_remediation(
            orphan_assets + missing_owners + missing_apps + missing_costs
        )
        return {
            "coverage": coverage,
            "orphan_assets": orphan_assets,
            "assets_without_owners": missing_owners,
            "assets_without_application_mapping": missing_apps,
            "assets_without_cost_mapping": missing_costs,
            "quality": quality,
            "remediation": remediation,
        }

    @staticmethod
    def _load_context(organization_id: str | None = None) -> dict[str, Any]:
        requested_org_id = str(organization_id or "").strip() or None
        resolved_org_id = resolve_organization_id(requested_org_id)
        identities = EnterpriseRelationshipIntelligenceService._fetch_org_rows(
            "enterprise_asset_identity",
            resolved_org_id,
        )
        discovered = EnterpriseRelationshipIntelligenceService._fetch_org_rows("discovered_assets", resolved_org_id)

        if requested_org_id and not identities and not discovered:
            resolved_org_id = resolve_organization_id()
            identities = EnterpriseRelationshipIntelligenceService._fetch_org_rows(
                "enterprise_asset_identity",
                resolved_org_id,
            )
            discovered = EnterpriseRelationshipIntelligenceService._fetch_org_rows(
                "discovered_assets",
                resolved_org_id,
            )

        inventory = EnterpriseRelationshipIntelligenceService._fetch_org_rows("technology_inventory", resolved_org_id)
        technology_relationships = EnterpriseRelationshipIntelligenceService._fetch_org_rows(
            "technology_relationships",
            resolved_org_id,
        )
        graph_relationships = EnterpriseRelationshipIntelligenceService._fetch_org_rows(
            "relationship_graph",
            resolved_org_id,
        )
        costs = EnterpriseRelationshipIntelligenceService._fetch_rows("unified_cloud_costs")
        spend_mapping = EnterpriseRelationshipIntelligenceService._fetch_rows("application_spend_mapping")
        applications = EnterpriseRelationshipIntelligenceService._fetch_rows("application_registry")

        relationships = technology_relationships + graph_relationships
        assets = EnterpriseRelationshipIntelligenceService._build_assets(identities, discovered)

        return {
            "organization_id": resolved_org_id,
            "assets": assets,
            "identities": identities,
            "discovered": discovered,
            "inventory": inventory,
            "relationships": relationships,
            "relationship_index": EnterpriseRelationshipIntelligenceService._relationship_index(relationships),
            "inventory_by_name": EnterpriseRelationshipIntelligenceService._index_by_names(
                inventory,
                ["technology_name", "vendor_name"],
            ),
            "cost_keys": EnterpriseRelationshipIntelligenceService._cost_keys(costs),
            "application_names": EnterpriseRelationshipIntelligenceService._application_names(applications),
            "application_spend_names": EnterpriseRelationshipIntelligenceService._application_spend_names(
                spend_mapping
            ),
        }

    @staticmethod
    def _fetch_org_rows(table_name: str, organization_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", organization_id)
                .limit(limit)
                .execute()
            )
            rows = response.data or []
            if rows:
                return rows

            response = (
                supabase.table(table_name)
                .select("*")
                .is_("organization_id", "null")
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            print(f"RELATIONSHIP INTELLIGENCE {table_name} LOAD FAILED:", exc)
            return EnterpriseRelationshipIntelligenceService._fetch_rows(table_name, limit)

    @staticmethod
    def _fetch_rows(table_name: str, limit: int = 1000) -> list[dict[str, Any]]:
        try:
            response = supabase.table(table_name).select("*").limit(limit).execute()
            return response.data or []
        except Exception as exc:
            print(f"RELATIONSHIP INTELLIGENCE {table_name} LOAD FAILED:", exc)
            return []

    @staticmethod
    def _build_assets(
        identities: list[dict[str, Any]],
        discovered: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        assets_by_key: dict[str, dict[str, Any]] = {}
        discovered_by_source = {
            EnterpriseRelationshipIntelligenceService._normalize(row.get("asset_id")): row
            for row in discovered
            if row.get("asset_id")
        }

        for row in identities:
            source_id = row.get("source_asset_id")
            discovered_row = discovered_by_source.get(EnterpriseRelationshipIntelligenceService._normalize(source_id), {})
            raw_payload = discovered_row.get("raw_payload") or {}
            asset = {
                "asset_uid": row.get("asset_uid"),
                "source_asset_id": source_id,
                "asset_name": row.get("asset_name") or discovered_row.get("asset_name") or source_id,
                "provider": row.get("provider") or discovered_row.get("provider"),
                "connector_name": row.get("connector_name") or discovered_row.get("connector_name"),
                "asset_type": row.get("normalized_asset_type") or row.get("asset_type") or discovered_row.get("asset_type"),
                "raw_payload": raw_payload if isinstance(raw_payload, dict) else {},
                "discovered": discovered_row,
            }
            assets_by_key[EnterpriseRelationshipIntelligenceService._asset_key(asset)] = asset

        for row in discovered:
            raw_payload = row.get("raw_payload") or {}
            asset = {
                "asset_uid": None,
                "source_asset_id": row.get("asset_id"),
                "asset_name": row.get("asset_name") or row.get("asset_id"),
                "provider": row.get("provider"),
                "connector_name": row.get("connector_name"),
                "asset_type": row.get("asset_type"),
                "raw_payload": raw_payload if isinstance(raw_payload, dict) else {},
                "discovered": row,
            }
            assets_by_key.setdefault(EnterpriseRelationshipIntelligenceService._asset_key(asset), asset)

        return sorted(assets_by_key.values(), key=lambda row: str(row.get("asset_uid") or row.get("asset_name") or ""))

    @staticmethod
    def _relationship_index(rows: list[dict[str, Any]]) -> set[str]:
        values: set[str] = set()
        for row in rows:
            values.add(EnterpriseRelationshipIntelligenceService._normalize(row.get("source_name")))
            values.add(EnterpriseRelationshipIntelligenceService._normalize(row.get("target_name")))
        values.discard("")
        return values

    @staticmethod
    def _asset_has_relationship(asset: dict[str, Any], relationship_index: set[str]) -> bool:
        return any(alias in relationship_index for alias in EnterpriseRelationshipIntelligenceService._asset_aliases(asset))

    @staticmethod
    def _asset_has_owner(asset: dict[str, Any], inventory_by_name: dict[str, dict[str, Any]]) -> bool:
        owner_fields = ["owner_name", "owner_email", "business_owner", "technical_owner", "owner_department"]
        sources = [asset.get("discovered") or {}, asset.get("raw_payload") or {}]
        for alias in EnterpriseRelationshipIntelligenceService._asset_aliases(asset):
            if alias in inventory_by_name:
                sources.append(inventory_by_name[alias])
        return any(any(source.get(field) for field in owner_fields) for source in sources)

    @staticmethod
    def _asset_has_application_mapping(asset: dict[str, Any], context: dict[str, Any]) -> bool:
        aliases = EnterpriseRelationshipIntelligenceService._asset_aliases(asset)
        application_names = context["application_names"]
        spend_names = context["application_spend_names"]
        raw_payload = asset.get("raw_payload") or {}
        discovered = asset.get("discovered") or {}
        direct_values = {
            EnterpriseRelationshipIntelligenceService._normalize(raw_payload.get("application")),
            EnterpriseRelationshipIntelligenceService._normalize(raw_payload.get("app_name")),
            EnterpriseRelationshipIntelligenceService._normalize(discovered.get("application")),
        }
        if direct_values & application_names or direct_values & spend_names:
            return True

        for row in context["relationships"]:
            source_type = EnterpriseRelationshipIntelligenceService._normalize(row.get("source_type"))
            target_type = EnterpriseRelationshipIntelligenceService._normalize(row.get("target_type"))
            source_name = EnterpriseRelationshipIntelligenceService._normalize(row.get("source_name"))
            target_name = EnterpriseRelationshipIntelligenceService._normalize(row.get("target_name"))
            if source_name in aliases and target_type == "application":
                return True
            if target_name in aliases and source_type == "application":
                return True
        return False

    @staticmethod
    def _asset_has_cost_mapping(asset: dict[str, Any], context: dict[str, Any]) -> bool:
        aliases = EnterpriseRelationshipIntelligenceService._asset_aliases(asset)
        if aliases & context["cost_keys"]:
            return True
        raw_payload = asset.get("raw_payload") or {}
        if EnterpriseRelationshipIntelligenceService._normalize(raw_payload.get("annual_cost")) not in {"", "0", "0.0"}:
            return True
        return EnterpriseRelationshipIntelligenceService._asset_has_application_mapping(asset, context)

    @staticmethod
    def _index_by_names(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
        indexed = {}
        for row in rows:
            for field in fields:
                key = EnterpriseRelationshipIntelligenceService._normalize(row.get(field))
                if key:
                    indexed[key] = row
        return indexed

    @staticmethod
    def _cost_keys(rows: list[dict[str, Any]]) -> set[str]:
        keys: set[str] = set()
        for row in rows:
            for field in ["resource_id", "service_name", "application", "account_name"]:
                key = EnterpriseRelationshipIntelligenceService._normalize(row.get(field))
                if key:
                    keys.add(key)
        return keys

    @staticmethod
    def _application_names(rows: list[dict[str, Any]]) -> set[str]:
        return {
            EnterpriseRelationshipIntelligenceService._normalize(row.get("app_name") or row.get("app_code"))
            for row in rows
            if row.get("app_name") or row.get("app_code")
        }

    @staticmethod
    def _application_spend_names(rows: list[dict[str, Any]]) -> set[str]:
        names: set[str] = set()
        for row in rows:
            for field in ["spend_application_name", "registry_app_name"]:
                name = EnterpriseRelationshipIntelligenceService._normalize(row.get(field))
                if name:
                    names.add(name)
        return names

    @staticmethod
    def _asset_aliases(asset: dict[str, Any]) -> set[str]:
        raw_payload = asset.get("raw_payload") or {}
        discovered = asset.get("discovered") or {}
        values = {
            asset.get("asset_uid"),
            asset.get("source_asset_id"),
            asset.get("asset_name"),
            raw_payload.get("technology_name"),
            raw_payload.get("resource_id"),
            discovered.get("asset_id"),
            discovered.get("asset_name"),
        }
        return {EnterpriseRelationshipIntelligenceService._normalize(value) for value in values if value}

    @staticmethod
    def _asset_key(asset: dict[str, Any]) -> str:
        return (
            EnterpriseRelationshipIntelligenceService._normalize(asset.get("source_asset_id"))
            or EnterpriseRelationshipIntelligenceService._normalize(asset.get("asset_uid"))
            or EnterpriseRelationshipIntelligenceService._normalize(asset.get("asset_name"))
        )

    @staticmethod
    def _remediation_row(asset: dict[str, Any], issue: str, action: str) -> dict[str, Any]:
        return {
            "Enterprise Asset ID": asset.get("asset_uid") or "-",
            "Asset": asset.get("asset_name") or asset.get("source_asset_id") or "-",
            "Provider": asset.get("provider") or "-",
            "Asset Type": asset.get("asset_type") or "-",
            "Issue": issue,
            "Recommended Action": action,
        }

    @staticmethod
    def _dedupe_remediation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        deduped = []
        for row in rows:
            key = (row["Enterprise Asset ID"], row["Asset"], row["Issue"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    @staticmethod
    def _percent(numerator: int, denominator: int) -> float:
        return round((numerator / denominator) * 100, 1) if denominator else 0.0

    @staticmethod
    def _normalize(value: Any) -> str:
        return str(value or "").strip().lower()
