from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.business_capability_service import BusinessCapabilityService
from services.connector_operations_service import ConnectorOperationsService
from services.enterprise_correlation_service import EnterpriseCorrelationService
from services.enterprise_cost_attribution_service import EnterpriseCostAttributionService
from services.enterprise_ownership_service import EnterpriseOwnershipService
from services.supabase_client import supabase


class AIContextService:
    _ENTERPRISE_CONTEXT_CACHE: dict[str, dict[str, Any]] = {}

    @staticmethod
    def build_enterprise_context(organization_id: str | None = None) -> dict[str, Any]:
        resolved_org = resolve_organization_id(organization_id)
        if resolved_org in AIContextService._ENTERPRISE_CONTEXT_CACHE:
            return AIContextService._ENTERPRISE_CONTEXT_CACHE[resolved_org]
        context = AIContextService._load_context(resolved_org)
        assets = AIContextService._build_assets(context)
        applications = AIContextService._build_applications(context, assets)
        capabilities = AIContextService._build_capabilities(context, applications, assets)
        ownership = AIContextService._build_ownership_context(context)
        cost = AIContextService._build_cost_context(context)
        quality = AIContextService._build_quality_context(context)
        connector_health = AIContextService._build_connector_context(context)
        enterprise_context = {
            "organization": {
                "organization_id": context["organization_id"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_assets": len(assets),
                "total_applications": len(applications),
                "total_capabilities": len(capabilities),
            },
            "capabilities": capabilities,
            "applications": applications,
            "assets": assets,
            "ownership": ownership,
            "cost": cost,
            "quality": quality,
            "relationships": AIContextService._build_relationships(context),
            "connector_health": connector_health,
        }
        AIContextService._ENTERPRISE_CONTEXT_CACHE[resolved_org] = enterprise_context
        return enterprise_context

    @staticmethod
    def build_capability_context(capability: str, organization_id: str | None = None) -> dict[str, Any]:
        enterprise = AIContextService.build_enterprise_context(organization_id)
        key = AIContextService._norm(capability)
        return {
            **enterprise["organization"],
            "capability": next((row for row in enterprise["capabilities"] if AIContextService._norm(row.get("name")) == key), {}),
            "applications": [row for row in enterprise["applications"] if AIContextService._norm(row.get("business_capability")) == key],
            "assets": [row for row in enterprise["assets"] if AIContextService._norm(row.get("business_capability")) == key],
            "relationships": [row for row in enterprise["relationships"] if key in AIContextService._norm(row)],
            "quality": enterprise["quality"],
        }

    @staticmethod
    def build_application_context(application: str, organization_id: str | None = None) -> dict[str, Any]:
        enterprise = AIContextService.build_enterprise_context(organization_id)
        key = AIContextService._norm(application)
        return {
            **enterprise["organization"],
            "application": next((row for row in enterprise["applications"] if AIContextService._norm(row.get("name")) == key), {}),
            "assets": [row for row in enterprise["assets"] if AIContextService._norm(row.get("application")) == key],
            "cost": AIContextService._filter_cost_distribution(enterprise["cost"], key),
            "quality": enterprise["quality"],
        }

    @staticmethod
    def build_asset_context(asset_id: str, organization_id: str | None = None) -> dict[str, Any]:
        enterprise = AIContextService.build_enterprise_context(organization_id)
        key = AIContextService._norm(asset_id)
        asset = next((row for row in enterprise["assets"] if AIContextService._norm(row.get("enterprise_asset_id")) == key), {})
        return {
            **enterprise["organization"],
            "asset": asset,
            "relationships": [
                row
                for row in enterprise["relationships"]
                if key in {AIContextService._norm(row.get("source")), AIContextService._norm(row.get("target"))}
            ],
            "quality": enterprise["quality"],
        }

    @staticmethod
    def build_owner_context(owner: str, organization_id: str | None = None) -> dict[str, Any]:
        enterprise = AIContextService.build_enterprise_context(organization_id)
        key = AIContextService._norm(owner)
        assets = [
            row
            for row in enterprise["assets"]
            if key
            in {
                AIContextService._norm(row.get("technical_owner")),
                AIContextService._norm(row.get("business_owner")),
                AIContextService._norm(row.get("executive_owner")),
                AIContextService._norm(row.get("owner")),
            }
        ]
        return {
            **enterprise["organization"],
            "owner": owner,
            "assets": assets,
            "applications": sorted({row.get("application") for row in assets if row.get("application")}),
            "capabilities": sorted({row.get("business_capability") for row in assets if row.get("business_capability")}),
            "total_cost": round(sum(float(row.get("cost") or 0) for row in assets), 2),
        }

    @staticmethod
    def build_cost_context(organization_id: str | None = None) -> dict[str, Any]:
        return AIContextService.build_enterprise_context(organization_id)["cost"]

    @staticmethod
    def build_quality_context(organization_id: str | None = None) -> dict[str, Any]:
        return AIContextService.build_enterprise_context(organization_id)["quality"]

    @staticmethod
    def build_connector_context(organization_id: str | None = None) -> dict[str, Any]:
        return AIContextService.build_enterprise_context(organization_id)["connector_health"]

    @staticmethod
    def _load_context(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        assets = AIContextService._fetch_org_rows("enterprise_asset_identity", org_id)
        correlation_summary = EnterpriseCorrelationService.get_correlation_summary(org_id)
        ownership_summary = EnterpriseOwnershipService.get_ownership_summary(org_id)
        capability_dashboard = BusinessCapabilityService.get_dashboard(org_id)
        cost_dashboard = EnterpriseCostAttributionService.get_dashboard(org_id)
        persisted_cost_rows = AIContextService._fetch_org_rows("enterprise_cost_attribution", org_id)
        connector_operations = ConnectorOperationsService.get_connector_operations(org_id)
        connector_kpis = AIContextService._connector_kpis(connector_operations)
        quality_history = AIContextService._fetch_org_rows("digital_twin_quality_history", org_id)
        relationships = (
            AIContextService._fetch_org_rows("technology_relationships", org_id)
            + AIContextService._fetch_org_rows("relationship_graph", org_id)
        )
        correlation_rows = correlation_summary.get("correlations", [])
        ownership_rows = ownership_summary.get("ownership", [])
        cost_rows = persisted_cost_rows or [
            row for row in cost_dashboard.get("attributions", []) if row.get("attributed")
        ]
        return {
            "organization_id": org_id,
            "assets": assets,
            "correlation_summary": correlation_summary,
            "correlation_rows": correlation_rows,
            "correlation_by_asset": AIContextService._index_rows(correlation_rows, ["enterprise_asset_id"]),
            "ownership_summary": ownership_summary,
            "ownership_rows": ownership_rows,
            "ownership_by_asset": AIContextService._index_rows(ownership_rows, ["enterprise_asset_id"]),
            "capability_dashboard": capability_dashboard,
            "capability_registry": AIContextService._fetch_org_rows("business_capability_registry", org_id),
            "cost_dashboard": cost_dashboard,
            "cost_rows": cost_rows,
            "quality_history": quality_history,
            "connector_operations": connector_operations,
            "connector_kpis": connector_kpis,
            "relationships": relationships,
        }

    @staticmethod
    def _build_assets(context: dict[str, Any]) -> list[dict[str, Any]]:
        cost_by_asset = AIContextService._sum_by(context["cost_rows"], "enterprise_asset_id")
        output = []
        for asset in context["assets"]:
            asset_id = asset.get("asset_uid")
            correlation = context["correlation_by_asset"].get(AIContextService._norm(asset_id), {})
            ownership = context["ownership_by_asset"].get(AIContextService._norm(asset_id), {})
            output.append(
                {
                    "enterprise_asset_id": asset_id,
                    "cloud_provider": asset.get("provider") or asset.get("connector_name"),
                    "resource_type": asset.get("normalized_asset_type") or asset.get("asset_type"),
                    "resource_name": asset.get("asset_name") or asset.get("source_asset_id"),
                    "source_asset_id": asset.get("source_asset_id"),
                    "environment": ownership.get("environment") or correlation.get("environment"),
                    "region": asset.get("region"),
                    "last_seen": asset.get("last_seen_at") or asset.get("first_seen_at"),
                    "application": correlation.get("application") or ownership.get("application"),
                    "business_service": correlation.get("business_service") or ownership.get("business_service"),
                    "business_capability": correlation.get("business_capability") or ownership.get("business_capability"),
                    "correlation_confidence": correlation.get("confidence"),
                    "relationship_path": AIContextService._impact_path(asset, correlation, ownership),
                    "technical_owner": ownership.get("technical_owner"),
                    "business_owner": ownership.get("business_owner"),
                    "executive_owner": ownership.get("executive_owner"),
                    "owner": ownership.get("technical_owner") or ownership.get("business_owner") or correlation.get("owner"),
                    "department": ownership.get("department") or correlation.get("department"),
                    "team": ownership.get("team") or correlation.get("team"),
                    "cost_center": ownership.get("cost_center") or correlation.get("cost_center"),
                    "criticality": ownership.get("criticality"),
                    "lifecycle": ownership.get("lifecycle"),
                    "cost": round(float(cost_by_asset.get(AIContextService._norm(asset_id), 0)), 2),
                }
            )
        return output

    @staticmethod
    def _build_applications(context: dict[str, Any], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cost_by_application = AIContextService._sum_by(context["cost_rows"], "application")
        applications = sorted({row.get("application") for row in assets if row.get("application")})
        output = []
        for application in applications:
            key = AIContextService._norm(application)
            app_assets = [row for row in assets if AIContextService._norm(row.get("application")) == key]
            correlation = next((row for row in context["correlation_rows"] if AIContextService._norm(row.get("application")) == key), {})
            output.append(
                {
                    "name": application,
                    "business_service": correlation.get("business_service") or AIContextService._first_value(app_assets, "business_service"),
                    "business_capability": correlation.get("business_capability") or AIContextService._first_value(app_assets, "business_capability"),
                    "owner": AIContextService._first_value(app_assets, "owner"),
                    "cost": round(float(cost_by_application.get(key, 0)), 2),
                    "asset_count": len(app_assets),
                    "criticality": AIContextService._first_value(app_assets, "criticality"),
                    "correlation_confidence": correlation.get("confidence"),
                }
            )
        return output

    @staticmethod
    def _build_capabilities(
        context: dict[str, Any],
        applications: list[dict[str, Any]],
        assets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        cost_by_capability = AIContextService._sum_by(context["cost_rows"], "business_capability")
        health_by_capability = {
            AIContextService._norm(row.get("Business Capability")): row
            for row in context["capability_dashboard"].get("health", [])
        }
        names = {row.get("capability_name") for row in context["capability_registry"] if row.get("capability_name")}
        names.update(row.get("business_capability") for row in assets if row.get("business_capability"))
        output = []
        for name in sorted({item for item in names if item}):
            key = AIContextService._norm(name)
            registry = next((row for row in context["capability_registry"] if AIContextService._norm(row.get("capability_name")) == key), {})
            health = health_by_capability.get(key, {})
            capability_apps = [row for row in applications if AIContextService._norm(row.get("business_capability")) == key]
            capability_assets = [row for row in assets if AIContextService._norm(row.get("business_capability")) == key]
            output.append(
                {
                    "name": name,
                    "business_unit": registry.get("business_unit"),
                    "business_domain": registry.get("business_domain"),
                    "executive_owner": registry.get("executive_owner") or AIContextService._first_value(capability_assets, "executive_owner"),
                    "health": health.get("Health Score"),
                    "governance_score": health.get("Governance Score"),
                    "risk": health.get("Risk"),
                    "maturity": registry.get("maturity"),
                    "criticality": registry.get("criticality"),
                    "cost": round(float(cost_by_capability.get(key, 0)), 2),
                    "application_count": len(capability_apps),
                    "asset_count": len(capability_assets),
                    "applications": [row.get("name") for row in capability_apps],
                }
            )
        return output

    @staticmethod
    def _build_ownership_context(context: dict[str, Any]) -> dict[str, Any]:
        ownership_rows = context["ownership_rows"]
        return {
            "summary": context["ownership_summary"],
            "total_records": len(ownership_rows),
            "technical_owners": AIContextService._count_by(ownership_rows, "technical_owner"),
            "business_owners": AIContextService._count_by(ownership_rows, "business_owner"),
            "executive_owners": AIContextService._count_by(ownership_rows, "executive_owner"),
            "departments": AIContextService._count_by(ownership_rows, "department"),
            "teams": AIContextService._count_by(ownership_rows, "team"),
            "cost_centers": AIContextService._count_by(ownership_rows, "cost_center"),
            "criticality": AIContextService._count_by(ownership_rows, "criticality"),
            "lifecycle": AIContextService._count_by(ownership_rows, "lifecycle"),
        }

    @staticmethod
    def _build_cost_context(context: dict[str, Any]) -> dict[str, Any]:
        rows = context["cost_rows"]
        summary = context["cost_dashboard"].get("summary", {})
        return {
            "summary": {
                **summary,
                "persisted_attribution_rows": len(rows),
                "average_attribution_confidence": AIContextService._average([row.get("confidence") for row in rows]),
            },
            "total_cost": round(sum(float(row.get("cost") or 0) for row in rows), 2),
            "monthly_cost": AIContextService._sum_by_month(rows),
            "application_spend": AIContextService._distribution(rows, "application"),
            "capability_spend": AIContextService._distribution(rows, "business_capability"),
            "cost_center_spend": AIContextService._distribution(rows, "cost_center"),
            "department_spend": AIContextService._distribution(rows, "department"),
            "attribution_rows": len(rows),
        }

    @staticmethod
    def _build_quality_context(context: dict[str, Any]) -> dict[str, Any]:
        history = context["quality_history"]
        scores = AIContextService._current_quality_scores(context)
        return {
            "scores": scores,
            "health": {
                "score": scores.get("overall_quality"),
                "stars": max(1, min(5, round(float(scores.get("overall_quality") or 0) / 20))),
            },
            "trend": AIContextService._quality_trend(history, scores),
            "top_issues": AIContextService._quality_issues(context),
            "auto_fix_recommendations": AIContextService._auto_fix_recommendations(context),
        }

    @staticmethod
    def _build_relationships(context: dict[str, Any]) -> list[dict[str, Any]]:
        output = AIContextService._relationship_confidence(context)
        for row in context["relationships"]:
            source = row.get("source_name") or row.get("source")
            target = row.get("target_name") or row.get("target")
            if source and target:
                output.append(
                    {
                        "source": source,
                        "target": target,
                        "confidence": row.get("confidence"),
                        "source_systems": row.get("source_system") or row.get("source"),
                        "relationship_type": row.get("relationship_type") or row.get("relationship"),
                    }
                )
        return AIContextService._dedupe(output, ("source", "target", "relationship_type"))

    @staticmethod
    def _build_connector_context(context: dict[str, Any]) -> dict[str, Any]:
        rows = context["connector_operations"]
        by_connector = {
            row.get("Connector"): {
                "health": row.get("Health Score"),
                "status": row.get("Status"),
                "last_sync": row.get("Last Sync"),
                "failures": 1 if row.get("Status") == "Failed" else 0,
                "coverage": row.get("Assets Discovered"),
                "last_error": row.get("Last Error"),
                "recommended_action": row.get("Recommended Action"),
            }
            for row in rows
            if row.get("Connector")
        }
        saas_names = {"GitHub", "GitHub Copilot", "Microsoft 365", "OpenAI", "Slack", "Zoom"}
        saas_rows = [row for row in rows if row.get("Connector") in saas_names]
        if saas_rows:
            by_connector["SaaS"] = {
                "health": round(sum(int(row.get("Health Score") or 0) for row in saas_rows) / len(saas_rows)),
                "status": "Connected" if any(row.get("Status") == "Connected" for row in saas_rows) else "Not Configured",
                "last_sync": max((row.get("Last Sync") or "" for row in saas_rows), default=""),
                "failures": sum(1 for row in saas_rows if row.get("Status") == "Failed"),
                "coverage": sum(int(row.get("Assets Discovered") or 0) for row in saas_rows),
                "last_error": "; ".join(row.get("Last Error") for row in saas_rows if row.get("Last Error")),
                "recommended_action": "Review SaaS connector onboarding and sync health.",
            }
        return {
            "summary": context["connector_kpis"],
            "connectors": by_connector,
        }

    @staticmethod
    def _current_quality_scores(context: dict[str, Any]) -> dict[str, Any]:
        assets = context["assets"]
        correlation_rows = context["correlation_rows"]
        connector_rows = context["connector_operations"]
        mapped_assets = [
            row
            for row in assets
            if context["correlation_by_asset"].get(AIContextService._norm(row.get("asset_uid")), {}).get("application")
        ]
        capability_mapped = [row for row in correlation_rows if row.get("business_capability")]
        cost_summary = context["cost_dashboard"].get("summary", {})
        relationship = AIContextService._percent(len(mapped_assets), len(assets))
        ownership = float(context["ownership_summary"].get("ownership_quality_score") or 0)
        mapping = AIContextService._percent(len(mapped_assets), len(assets))
        capability = AIContextService._percent(len(capability_mapped), len(correlation_rows))
        cost = float(cost_summary.get("attribution_coverage_percent") or 0)
        freshness = AIContextService._percent(
            len([row for row in connector_rows if row.get("Status") == "Connected"]),
            len(connector_rows),
        )
        overall = round(
            (relationship * 0.30)
            + (ownership * 0.20)
            + (mapping * 0.15)
            + (cost * 0.20)
            + (capability * 0.10)
            + (freshness * 0.05),
            1,
        )
        return {
            "overall_quality": overall,
            "relationship": round(relationship, 1),
            "ownership": round(ownership, 1),
            "cost": round(cost, 1),
            "mapping": round(mapping, 1),
            "capability": round(capability, 1),
            "freshness": round(freshness, 1),
        }

    @staticmethod
    def _quality_issues(context: dict[str, Any]) -> list[dict[str, Any]]:
        issues = []
        for row in context["cost_dashboard"].get("unattributed_costs", [])[:10]:
            issues.append(
                {
                    "severity": "High" if float(row.get("cost") or 0) > 0 else "Low",
                    "issue": "Unattributed Cost",
                    "entity": row.get("cost_id") or row.get("service_name"),
                    "impact": "Cost is not connected to business ownership.",
                    "recommendation": "Map provider, account, or service category to an enterprise asset.",
                }
            )
        return issues[:10]

    @staticmethod
    def _auto_fix_recommendations(context: dict[str, Any]) -> list[dict[str, Any]]:
        unattributed = context["cost_dashboard"].get("unattributed_costs", [])
        primary = next((row for row in context["correlation_rows"] if row.get("application")), {})
        if not unattributed or not primary:
            return []
        return [
            {
                "entity": "Unattributed cost queue",
                "suggestion": f"Map {len(unattributed)} cost rows to {primary.get('application')} after finance approval.",
                "application": primary.get("application"),
                "business_capability": primary.get("business_capability"),
                "confidence": 88,
                "reason": "Rows contain provider, account, or service category signals but no resource-level asset id.",
            }
        ]

    @staticmethod
    def _relationship_confidence(context: dict[str, Any]) -> list[dict[str, Any]]:
        output = []
        for asset in context["assets"]:
            asset_id = asset.get("asset_uid")
            correlation = context["correlation_by_asset"].get(AIContextService._norm(asset_id), {})
            ownership = context["ownership_by_asset"].get(AIContextService._norm(asset_id), {})
            parts = [
                correlation.get("business_capability") or ownership.get("business_capability"),
                correlation.get("business_service") or ownership.get("business_service"),
                correlation.get("application") or ownership.get("application"),
                asset_id,
                " ".join(
                    item
                    for item in [
                        asset.get("provider") or asset.get("connector_name") or correlation.get("vendor"),
                        asset.get("asset_type") or asset.get("normalized_asset_type"),
                    ]
                    if item
                ),
            ]
            parts = [part for part in parts if part]
            for source, target in zip(parts, parts[1:]):
                output.append(
                    {
                        "source": source,
                        "target": target,
                        "confidence": 98 if correlation.get("application") and ownership else 90,
                        "source_systems": "Enterprise Asset Identity, Correlation, Ownership, Cost Attribution",
                        "relationship_type": "INFERRED_IMPACT_PATH",
                    }
                )
        return output

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
        except Exception:
            pass
        try:
            return supabase.table(table_name).select("*").limit(1000).execute().data or []
        except Exception:
            return []

    @staticmethod
    def _connector_kpis(rows: list[dict[str, Any]]) -> dict[str, Any]:
        connected = sum(1 for row in rows if row.get("Status") == "Connected")
        failed = sum(1 for row in rows if row.get("Status") == "Failed")
        not_configured = sum(1 for row in rows if row.get("Status") == "Not Configured")
        assets = sum(int(row.get("Assets Discovered") or 0) for row in rows)
        average_health = round(sum(int(row.get("Health Score") or 0) for row in rows) / len(rows)) if rows else 0
        return {
            "Total Connectors": len(rows),
            "Connected": connected,
            "Failed": failed,
            "Not Configured": not_configured,
            "Assets Discovered": assets,
            "Average Health": average_health,
        }

    @staticmethod
    def _index_rows(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
        index = {}
        for row in rows:
            for field in fields:
                key = AIContextService._norm(row.get(field))
                if key:
                    index[key] = row
        return index

    @staticmethod
    def _impact_path(asset: dict[str, Any], correlation: dict[str, Any], ownership: dict[str, Any]) -> str:
        provider = asset.get("provider") or asset.get("connector_name") or correlation.get("vendor")
        resource_type = asset.get("asset_type") or asset.get("normalized_asset_type")
        return " -> ".join(
            part
            for part in [
                correlation.get("business_capability") or ownership.get("business_capability"),
                correlation.get("business_service") or ownership.get("business_service"),
                correlation.get("application") or ownership.get("application"),
                asset.get("asset_uid"),
                " ".join(item for item in [provider, resource_type] if item),
            ]
            if part
        )

    @staticmethod
    def _sum_by(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
        grouped: dict[str, float] = {}
        for row in rows:
            key = AIContextService._norm(row.get(field))
            if key:
                grouped[key] = grouped.get(key, 0.0) + float(row.get("cost") or 0)
        return grouped

    @staticmethod
    def _sum_by_month(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, float] = {}
        for row in rows:
            usage_date = str(row.get("usage_date") or "")[:7]
            if usage_date:
                grouped[usage_date] = grouped.get(usage_date, 0.0) + float(row.get("cost") or 0)
        return [{"month": month, "cost": round(cost, 2)} for month, cost in sorted(grouped.items())]

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        grouped: dict[str, float] = {}
        for row in rows:
            value = row.get(field) or "Unassigned"
            grouped[str(value)] = grouped.get(str(value), 0.0) + float(row.get("cost") or 0)
        return [
            {"name": name, "cost": round(cost, 2)}
            for name, cost in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
        ]

    @staticmethod
    def _count_by(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get(field) or "Unassigned"
            counts[str(value)] = counts.get(str(value), 0) + 1
        return [{"name": name, "count": count} for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)]

    @staticmethod
    def _quality_trend(history: list[dict[str, Any]], scores: dict[str, Any]) -> list[dict[str, Any]]:
        if history:
            return [
                {
                    "date": str(row.get("snapshot_date") or row.get("created_at") or "")[:10],
                    "overall_quality": row.get("overall_quality"),
                    "relationship_quality": row.get("relationship_quality"),
                    "ownership_quality": row.get("ownership_quality"),
                    "cost_quality": row.get("cost_quality"),
                    "freshness_quality": row.get("freshness_quality"),
                }
                for row in history[-30:]
            ]
        return [{"date": datetime.now(timezone.utc).date().isoformat(), **scores}]

    @staticmethod
    def _filter_cost_distribution(cost: dict[str, Any], key: str) -> dict[str, Any]:
        return {
            "application_spend": [
                row for row in cost.get("application_spend", []) if AIContextService._norm(row.get("name")) == key
            ],
            "monthly_cost": cost.get("monthly_cost", []),
        }

    @staticmethod
    def _first_value(rows: list[dict[str, Any]], field: str) -> Any:
        for row in rows:
            value = row.get(field)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _average(values: list[Any]) -> float:
        numeric = [float(value) for value in values if value not in (None, "")]
        if not numeric:
            return 0.0
        return round(sum(numeric) / len(numeric), 1)

    @staticmethod
    def _percent(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return round((float(numerator) / float(denominator)) * 100, 1)

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
        seen = set()
        output = []
        for row in rows:
            marker = tuple(row.get(field) for field in fields)
            if marker in seen:
                continue
            seen.add(marker)
            output.append(row)
        return output

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()
