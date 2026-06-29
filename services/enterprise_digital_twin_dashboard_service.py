from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.business_capability_service import BusinessCapabilityService
from services.enterprise_correlation_service import EnterpriseCorrelationService
from services.enterprise_cost_attribution_service import EnterpriseCostAttributionService
from services.enterprise_ownership_service import EnterpriseOwnershipService
from services.enterprise_relationship_intelligence_service import EnterpriseRelationshipIntelligenceService
from services.supabase_client import supabase


class EnterpriseDigitalTwinDashboardService:
    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        context = EnterpriseDigitalTwinDashboardService._load_context(organization_id)
        capability_twin = EnterpriseDigitalTwinDashboardService.get_capability_twin(context)
        application_twin = EnterpriseDigitalTwinDashboardService.get_application_twin(context)
        asset_twin = EnterpriseDigitalTwinDashboardService.get_asset_twin(context)
        summary = EnterpriseDigitalTwinDashboardService.get_enterprise_twin_summary(
            context,
            capability_twin,
            application_twin,
            asset_twin,
        )
        gaps = EnterpriseDigitalTwinDashboardService.get_risk_governance_gaps(context)
        return {
            "organization_id": context["organization_id"],
            "summary": summary,
            "capability_twin": capability_twin,
            "application_twin": application_twin,
            "asset_twin": asset_twin,
            "impact_paths": [row.get("Impact Path") for row in asset_twin if row.get("Impact Path")],
            "risk_governance_gaps": gaps,
            "executive_narrative": EnterpriseDigitalTwinDashboardService.get_executive_narrative(
                capability_twin,
                application_twin,
                asset_twin,
                summary,
            ),
            "connector_registry": context["connector_registry"],
            "connector_sync_history": context["connector_sync_history"],
            "technology_relationships": context["technology_relationships"],
            "relationship_graph": context["relationship_graph"],
        }

    @staticmethod
    def get_enterprise_twin_summary(
        context: dict[str, Any],
        capability_twin: list[dict[str, Any]],
        application_twin: list[dict[str, Any]],
        asset_twin: list[dict[str, Any]],
    ) -> dict[str, Any]:
        cost_summary = context["cost_dashboard"]["summary"]
        capability_summary = context["capability_dashboard"]["summary"]
        ownership_summary = context["ownership_summary"]
        relationship_quality = context["relationship_quality"]
        return {
            "Total Capabilities": len(capability_twin),
            "Applications": len(application_twin),
            "Enterprise Assets": len(asset_twin),
            "Attributed Cost": round(float(cost_summary.get("attributed_cost") or 0), 2),
            "Cost Coverage %": float(cost_summary.get("attribution_coverage_percent") or 0),
            "Average Capability Health": float(capability_summary.get("average_health") or 0),
            "Ownership Quality": float(ownership_summary.get("ownership_quality_score") or 0),
            "Relationship Quality": float(relationship_quality.get("score") or 0),
        }

    @staticmethod
    def get_capability_twin(context: dict[str, Any]) -> list[dict[str, Any]]:
        capabilities = context["capabilities"]
        ownership_rows = context["ownership_rows"]
        cost_by_capability = EnterpriseDigitalTwinDashboardService._cost_index(
            context["cost_dashboard"]["cost_by_business_capability"],
            "Business Capability",
        )
        health_by_capability = {
            EnterpriseDigitalTwinDashboardService._norm(row.get("Business Capability")): row
            for row in context["capability_dashboard"].get("health", [])
        }
        capability_names = {
            row.get("capability_name") or row.get("business_capability")
            for row in capabilities
            if row.get("capability_name") or row.get("business_capability")
        }
        capability_names.update(row.get("business_capability") for row in ownership_rows if row.get("business_capability"))

        output = []
        for name in sorted({item for item in capability_names if item}):
            key = EnterpriseDigitalTwinDashboardService._norm(name)
            registry = EnterpriseDigitalTwinDashboardService._first_matching(
                capabilities,
                "capability_name",
                name,
            )
            related_ownership = [
                row
                for row in ownership_rows
                if EnterpriseDigitalTwinDashboardService._norm(row.get("business_capability")) == key
            ]
            applications = {row.get("application") for row in related_ownership if row.get("application")}
            assets = {row.get("enterprise_asset_id") for row in related_ownership if row.get("enterprise_asset_id")}
            health = health_by_capability.get(key, {})
            output.append(
                {
                    "Capability": name,
                    "Business Unit": registry.get("business_unit") or health.get("Business Unit") or "Unassigned",
                    "Owner": registry.get("executive_owner") or EnterpriseDigitalTwinDashboardService._first_value(
                        related_ownership,
                        ["executive_owner", "business_owner", "technical_owner"],
                    ),
                    "Health": float(health.get("Health Score") or 0),
                    "Cost": float(cost_by_capability.get(key, {}).get("Cost") or 0),
                    "Applications": len(applications),
                    "Assets": len(assets),
                    "Risk": health.get("Risk") or EnterpriseDigitalTwinDashboardService._risk_from_health(
                        float(health.get("Health Score") or 0),
                        registry.get("criticality"),
                    ),
                }
            )
        return sorted(output, key=lambda row: row["Cost"], reverse=True)

    @staticmethod
    def get_application_twin(context: dict[str, Any]) -> list[dict[str, Any]]:
        ownership_rows = context["ownership_rows"]
        correlation_rows = context["correlation_rows"]
        cost_by_application = EnterpriseDigitalTwinDashboardService._cost_index(
            context["cost_dashboard"]["cost_by_application"],
            "Application",
        )
        app_names = {row.get("application") for row in ownership_rows + correlation_rows if row.get("application")}
        output = []
        for app in sorted({item for item in app_names if item}):
            key = EnterpriseDigitalTwinDashboardService._norm(app)
            ownership = [
                row
                for row in ownership_rows
                if EnterpriseDigitalTwinDashboardService._norm(row.get("application")) == key
            ]
            correlation = EnterpriseDigitalTwinDashboardService._first_matching(correlation_rows, "application", app)
            assets = {row.get("enterprise_asset_id") for row in ownership if row.get("enterprise_asset_id")}
            output.append(
                {
                    "Application": app,
                    "Business Service": correlation.get("business_service")
                    or EnterpriseDigitalTwinDashboardService._first_value(ownership, ["business_service"]),
                    "Capability": correlation.get("business_capability")
                    or EnterpriseDigitalTwinDashboardService._first_value(ownership, ["business_capability"]),
                    "Owner": EnterpriseDigitalTwinDashboardService._first_value(
                        ownership,
                        ["technical_owner", "business_owner", "executive_owner"],
                    )
                    or correlation.get("owner"),
                    "Cost": float(cost_by_application.get(key, {}).get("Cost") or 0),
                    "Assets": len(assets),
                    "Criticality": EnterpriseDigitalTwinDashboardService._first_value(ownership, ["criticality"]),
                }
            )
        return sorted(output, key=lambda row: row["Cost"], reverse=True)

    @staticmethod
    def get_asset_twin(context: dict[str, Any]) -> list[dict[str, Any]]:
        cost_by_asset = EnterpriseDigitalTwinDashboardService._cost_by_field(context["cost_rows"], "enterprise_asset_id")
        output = []
        for asset in context["assets"]:
            asset_id = asset.get("asset_uid")
            correlation = context["correlation_by_asset"].get(EnterpriseDigitalTwinDashboardService._norm(asset_id), {})
            ownership = context["ownership_by_asset"].get(EnterpriseDigitalTwinDashboardService._norm(asset_id), {})
            application = correlation.get("application") or ownership.get("application")
            business_service = correlation.get("business_service") or ownership.get("business_service")
            capability = correlation.get("business_capability") or ownership.get("business_capability")
            provider = asset.get("provider") or asset.get("connector_name") or correlation.get("vendor")
            asset_type = asset.get("asset_type") or asset.get("normalized_asset_type") or "Cloud Resource"
            impact_path = EnterpriseDigitalTwinDashboardService._impact_path(
                capability,
                business_service,
                application,
                asset_id,
                provider,
                asset_type,
            )
            output.append(
                {
                    "Enterprise Asset ID": asset_id,
                    "Asset Name": asset.get("asset_name") or asset.get("source_asset_id"),
                    "Provider": provider,
                    "Application": application,
                    "Owner": ownership.get("technical_owner") or ownership.get("business_owner") or correlation.get("owner"),
                    "Cost": float(cost_by_asset.get(EnterpriseDigitalTwinDashboardService._norm(asset_id), 0)),
                    "Environment": ownership.get("environment") or correlation.get("environment"),
                    "Criticality": ownership.get("criticality"),
                    "Impact Path": impact_path,
                }
            )
        return sorted(output, key=lambda row: row["Cost"], reverse=True)

    @staticmethod
    def get_risk_governance_gaps(context: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        unattributed = context["cost_dashboard"].get("unattributed_costs", [])
        low_confidence = context["low_confidence_correlations"]
        return {
            "missing_owners": context["assets_without_owner"],
            "unattributed_cost": unattributed,
            "low_confidence_correlations": low_confidence,
            "unmapped_assets": context["assets_without_application_mapping"] + context["orphan_assets"],
        }

    @staticmethod
    def get_executive_narrative(
        capability_twin: list[dict[str, Any]],
        application_twin: list[dict[str, Any]],
        asset_twin: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> str:
        if not capability_twin:
            return "No business capability twin is available yet. Run discovery, correlation, and ownership sync to populate it."

        primary = capability_twin[0]
        capability = primary.get("Capability") or "The primary capability"
        related_apps = [
            row
            for row in application_twin
            if EnterpriseDigitalTwinDashboardService._norm(row.get("Capability"))
            == EnterpriseDigitalTwinDashboardService._norm(capability)
        ]
        app_names = ", ".join(row.get("Application") for row in related_apps if row.get("Application")) or "mapped applications"
        ownership_quality = float(summary.get("Ownership Quality") or 0)
        return (
            f"{capability} is supported by {app_names} and {int(primary.get('Assets') or len(asset_twin))} "
            f"enterprise asset, with ${float(primary.get('Cost') or 0):,.2f} attributed cost and "
            f"{ownership_quality:.1f}% ownership coverage."
        )

    @staticmethod
    def _load_context(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        assets = EnterpriseDigitalTwinDashboardService._fetch_org_rows("enterprise_asset_identity", org_id)
        correlation_summary = EnterpriseCorrelationService.get_correlation_summary(org_id)
        ownership_summary = EnterpriseOwnershipService.get_ownership_summary(org_id)
        capability_dashboard = BusinessCapabilityService.get_dashboard(org_id)
        cost_dashboard = EnterpriseCostAttributionService.get_dashboard(org_id)
        relationship_quality = EnterpriseRelationshipIntelligenceService.get_relationship_quality_score(org_id)

        correlation_rows = correlation_summary.get("correlations", [])
        ownership_rows = ownership_summary.get("ownership", [])
        cost_rows = cost_dashboard.get("attributions", [])
        return {
            "organization_id": org_id,
            "assets": assets,
            "correlation_summary": correlation_summary,
            "correlation_rows": correlation_rows,
            "correlation_by_asset": EnterpriseDigitalTwinDashboardService._index_rows(correlation_rows, ["enterprise_asset_id"]),
            "ownership_summary": ownership_summary,
            "ownership_rows": ownership_rows,
            "ownership_by_asset": EnterpriseDigitalTwinDashboardService._index_rows(ownership_rows, ["enterprise_asset_id"]),
            "capability_dashboard": capability_dashboard,
            "capabilities": EnterpriseDigitalTwinDashboardService._fetch_org_rows("business_capability_registry", org_id),
            "cost_dashboard": cost_dashboard,
            "cost_rows": cost_rows,
            "relationship_quality": relationship_quality,
            "technology_relationships": EnterpriseDigitalTwinDashboardService._fetch_org_rows("technology_relationships", org_id),
            "relationship_graph": EnterpriseDigitalTwinDashboardService._fetch_org_rows("relationship_graph", org_id),
            "connector_registry": EnterpriseDigitalTwinDashboardService._fetch_rows("connector_registry"),
            "connector_sync_history": EnterpriseDigitalTwinDashboardService._fetch_org_rows("connector_sync_history", org_id),
            "assets_without_owner": EnterpriseOwnershipService.get_assets_without_owner(org_id),
            "assets_without_application_mapping": EnterpriseRelationshipIntelligenceService.get_assets_without_application_mapping(org_id),
            "orphan_assets": EnterpriseRelationshipIntelligenceService.get_orphan_assets(org_id),
            "low_confidence_correlations": EnterpriseCorrelationService.get_low_confidence_correlations(org_id),
        }

    @staticmethod
    def _impact_path(
        capability: str | None,
        business_service: str | None,
        application: str | None,
        asset_id: str | None,
        provider: str | None,
        asset_type: str | None,
    ) -> str:
        resource = " ".join(part for part in [provider, asset_type] if part)
        return " -> ".join(
            part
            for part in [capability, business_service, application, asset_id, resource]
            if part
        )

    @staticmethod
    def _risk_from_health(health: float, criticality: str | None) -> str:
        if str(criticality or "").lower() in {"critical", "high"} and health < 80:
            return "High"
        if health >= 90:
            return "Low"
        if health >= 75:
            return "Medium"
        return "High"

    @staticmethod
    def _cost_index(rows: list[dict[str, Any]], key_name: str) -> dict[str, dict[str, Any]]:
        return {
            EnterpriseDigitalTwinDashboardService._norm(row.get(key_name)): row
            for row in rows
            if row.get(key_name)
        }

    @staticmethod
    def _cost_by_field(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
        grouped: dict[str, float] = {}
        for row in rows:
            key = EnterpriseDigitalTwinDashboardService._norm(row.get(field))
            if key:
                grouped[key] = grouped.get(key, 0.0) + float(row.get("cost") or 0)
        return grouped

    @staticmethod
    def _fetch_rows(table_name: str) -> list[dict[str, Any]]:
        try:
            return supabase.table(table_name).select("*").limit(1000).execute().data or []
        except Exception as exc:
            print(f"ENTERPRISE DIGITAL TWIN DASHBOARD LOAD FAILED: {table_name}: {exc}")
            return []

    @staticmethod
    def _fetch_org_rows(table_name: str, organization_id: str) -> list[dict[str, Any]]:
        try:
            rows = (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", organization_id)
                .limit(1000)
                .execute()
                .data
                or []
            )
            if rows:
                return rows
        except Exception as exc:
            print(f"ENTERPRISE DIGITAL TWIN DASHBOARD ORG LOAD FAILED: {table_name}: {exc}")
        return EnterpriseDigitalTwinDashboardService._fetch_rows(table_name)

    @staticmethod
    def _index_rows(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
        index = {}
        for row in rows:
            for field in fields:
                key = EnterpriseDigitalTwinDashboardService._norm(row.get(field))
                if key:
                    index[key] = row
        return index

    @staticmethod
    def _first_matching(rows: list[dict[str, Any]], field: str, value: Any) -> dict[str, Any]:
        normalized = EnterpriseDigitalTwinDashboardService._norm(value)
        for row in rows:
            if EnterpriseDigitalTwinDashboardService._norm(row.get(field)) == normalized:
                return row
        return {}

    @staticmethod
    def _first_value(rows: list[dict[str, Any]], fields: list[str]) -> Any:
        for row in rows:
            for field in fields:
                value = row.get(field)
                if value not in (None, ""):
                    return value
        return None

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()
