from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.enterprise_ownership_service import EnterpriseOwnershipService
from services.supabase_client import supabase


class BusinessCapabilityService:
    TABLE_NAME = "business_capability_registry"

    @staticmethod
    def sync_business_capabilities(organization_id: str | None = None) -> dict[str, Any]:
        context = BusinessCapabilityService._load_context(organization_id)
        capability_rows = BusinessCapabilityService._build_capability_rows(context)
        BusinessCapabilityService._persist_capabilities(capability_rows)
        health_rows = BusinessCapabilityService._build_health_rows(capability_rows, context)
        return {
            "status": "SUCCESS",
            "organization_id": context["organization_id"],
            "total_capabilities": len(capability_rows),
            "capabilities_synced": len(capability_rows),
            "critical_capabilities": len([row for row in capability_rows if BusinessCapabilityService._is_critical(row)]),
            "average_health": BusinessCapabilityService._average([row["Health Score"] for row in health_rows]),
            "capabilities": capability_rows,
            "health": health_rows,
        }

    @staticmethod
    def get_capability_summary(organization_id: str | None = None) -> dict[str, Any]:
        sync = BusinessCapabilityService.sync_business_capabilities(organization_id)
        health = sync["health"]
        spend = BusinessCapabilityService.get_capability_spend(sync["organization_id"])
        total_spend = sum(float(row.get("Monthly Spend") or 0) for row in spend)
        optimization = sum(float(row.get("Optimization Opportunity") or 0) for row in health)
        return {
            **sync,
            "total_capability_spend": round(total_spend, 2),
            "optimization_opportunity": round(optimization, 2),
            "governance_score": BusinessCapabilityService._average([row["Governance Score"] for row in health]),
        }

    @staticmethod
    def get_capability_health(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = BusinessCapabilityService._load_context(organization_id)
        capabilities = BusinessCapabilityService._build_capability_rows(context)
        return BusinessCapabilityService._build_health_rows(capabilities, context)

    @staticmethod
    def get_capability_spend(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = BusinessCapabilityService._load_context(organization_id)
        capabilities = BusinessCapabilityService._build_capability_rows(context)
        health = BusinessCapabilityService._build_health_rows(capabilities, context)
        return [
            {
                "Business Capability": row["Business Capability"],
                "Monthly Spend": row["Monthly Spend"],
                "Optimization Opportunity": row["Optimization Opportunity"],
            }
            for row in health
        ]

    @staticmethod
    def get_capability_assets(organization_id: str | None = None) -> list[dict[str, Any]]:
        rows = BusinessCapabilityService._load_context(organization_id)["ownership"]
        return [
            {
                "Business Capability": row.get("business_capability") or "Unmapped",
                "Enterprise Asset ID": row.get("enterprise_asset_id"),
                "Application": row.get("application"),
                "Business Service": row.get("business_service"),
                "Owner": row.get("technical_owner") or row.get("business_owner") or row.get("executive_owner"),
                "Criticality": row.get("criticality"),
            }
            for row in rows
        ]

    @staticmethod
    def get_capability_applications(organization_id: str | None = None) -> list[dict[str, Any]]:
        rows = BusinessCapabilityService._load_context(organization_id)["ownership"]
        grouped: dict[str, set[str]] = {}
        for row in rows:
            capability = row.get("business_capability") or "Unmapped"
            application = row.get("application")
            if application:
                grouped.setdefault(capability, set()).add(application)
        return [
            {
                "Business Capability": capability,
                "Applications": len(applications),
                "Application List": ", ".join(sorted(applications)),
            }
            for capability, applications in sorted(grouped.items())
        ]

    @staticmethod
    def get_capability_risk(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "Business Capability": row["Business Capability"],
                "Risk": row["Risk"],
                "Health Score": row["Health Score"],
                "Criticality": row["Criticality"],
                "Missing Executive Owner": row["Missing Executive Owner"],
                "Ownership Completeness": row["Ownership Completeness"],
            }
            for row in BusinessCapabilityService.get_capability_health(organization_id)
        ]

    @staticmethod
    def get_capability_dependencies(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = BusinessCapabilityService._load_context(organization_id)
        dependencies = []
        for row in context["relationships"]:
            source = row.get("source_name") or row.get("source")
            target = row.get("target_name") or row.get("target")
            relationship = row.get("relationship_type") or row.get("relationship")
            if source and target:
                dependencies.append(
                    {
                        "Source": source,
                        "Relationship": relationship,
                        "Target": target,
                    }
                )
        for row in context["ownership"]:
            dependencies.append(
                {
                    "Source": row.get("business_capability") or "Unmapped",
                    "Relationship": "OWNS_SERVICE",
                    "Target": row.get("business_service") or "Unmapped",
                }
            )
            dependencies.append(
                {
                    "Source": row.get("business_service") or "Unmapped",
                    "Relationship": "SUPPORTS_APPLICATION",
                    "Target": row.get("application") or "Unmapped",
                }
            )
        return BusinessCapabilityService._dedupe(dependencies, ("Source", "Relationship", "Target"))

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        summary = BusinessCapabilityService.get_capability_summary(organization_id)
        health = summary["health"]
        spend = BusinessCapabilityService.get_capability_spend(summary["organization_id"])
        assets = BusinessCapabilityService.get_capability_assets(summary["organization_id"])
        applications = BusinessCapabilityService.get_capability_applications(summary["organization_id"])
        return {
            "summary": summary,
            "health": health,
            "spend": spend,
            "assets": assets,
            "applications": applications,
            "health_matrix": health,
            "spend_by_capability": spend,
            "assets_by_capability": BusinessCapabilityService._distribution(
                assets,
                "Business Capability",
                "Business Capability",
            ),
            "applications_by_capability": applications,
            "risk_heatmap": BusinessCapabilityService.get_capability_risk(summary["organization_id"]),
            "dependency_graph": BusinessCapabilityService.get_capability_dependencies(summary["organization_id"]),
            "critical_capabilities": [row for row in health if row["Criticality"] in {"Critical", "High"}],
            "lowest_health": sorted(health, key=lambda row: row["Health Score"])[:10],
            "highest_spend": sorted(health, key=lambda row: row["Monthly Spend"], reverse=True)[:10],
            "missing_executive_owner": [row for row in health if row["Missing Executive Owner"]],
            "improvement_recommendations": BusinessCapabilityService._recommendations(health),
        }

    @staticmethod
    def _load_context(organization_id: str | None = None) -> dict[str, Any]:
        ownership_summary = EnterpriseOwnershipService.sync_asset_ownership(organization_id)
        org_id = ownership_summary["organization_id"]
        return {
            "organization_id": org_id,
            "ownership": ownership_summary.get("ownership", []),
            "registry": BusinessCapabilityService._load_registry(org_id),
            "applications": BusinessCapabilityService._fetch_rows("application_registry"),
            "business_services": BusinessCapabilityService._fetch_rows("business_services"),
            "relationships": BusinessCapabilityService._fetch_org_rows("relationship_graph", org_id)
            + BusinessCapabilityService._fetch_rows("business_service_relationships"),
            "costs": BusinessCapabilityService._fetch_rows("unified_cloud_costs"),
            "recommendations": BusinessCapabilityService._fetch_org_rows("recommendations", org_id),
        }

    @staticmethod
    def _build_capability_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
        by_name: dict[str, dict[str, Any]] = {}
        registry_by_name = {
            BusinessCapabilityService._norm(row.get("capability_name")): row
            for row in context["registry"]
            if row.get("capability_name")
        }
        now = datetime.now(timezone.utc).isoformat()

        for ownership in context["ownership"]:
            capability_name = ownership.get("business_capability") or "Unmapped Capability"
            key = BusinessCapabilityService._norm(capability_name)
            registry = registry_by_name.get(key, {})
            row = by_name.setdefault(
                key,
                {
                    "organization_id": context["organization_id"],
                    "capability_code": registry.get("capability_code") or BusinessCapabilityService._capability_code(len(by_name) + 1),
                    "capability_name": capability_name,
                    "capability_description": registry.get("capability_description") or f"{capability_name} business capability",
                    "business_domain": registry.get("business_domain") or ownership.get("department") or "Digital Commerce",
                    "business_unit": registry.get("business_unit") or BusinessCapabilityService._business_unit(ownership, context),
                    "executive_owner": registry.get("executive_owner") or ownership.get("executive_owner"),
                    "department": registry.get("department") or ownership.get("department"),
                    "criticality": registry.get("criticality") or ownership.get("criticality") or "Medium",
                    "maturity": int(registry.get("maturity") or 3),
                    "status": registry.get("status") or "Active",
                    "created_at": registry.get("created_at") or now,
                    "updated_at": now,
                },
            )
            row["executive_owner"] = row.get("executive_owner") or ownership.get("executive_owner")
            row["department"] = row.get("department") or ownership.get("department")
            row["criticality"] = BusinessCapabilityService._max_criticality(
                row.get("criticality"),
                ownership.get("criticality"),
            )

        return sorted(by_name.values(), key=lambda row: row["capability_name"])

    @staticmethod
    def _build_health_rows(capabilities: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        ownership = context["ownership"]
        costs = context["costs"]
        recommendations = context["recommendations"]
        for capability in capabilities:
            name = capability["capability_name"]
            cap_assets = [
                row for row in ownership if BusinessCapabilityService._norm(row.get("business_capability")) == BusinessCapabilityService._norm(name)
            ]
            applications = {row.get("application") for row in cap_assets if row.get("application")}
            cloud_services = BusinessCapabilityService._cloud_services(cap_assets, costs)
            saas_dependencies = BusinessCapabilityService._saas_dependencies(name, applications, context["relationships"])
            monthly_spend = BusinessCapabilityService._monthly_spend(cap_assets, costs)
            optimization = BusinessCapabilityService._optimization_opportunity(name, applications, recommendations, monthly_spend)
            ownership_completeness = BusinessCapabilityService._average(
                [float(row.get("ownership_score") or 0) for row in cap_assets]
            )
            governance_score = round((ownership_completeness * 0.7) + (BusinessCapabilityService._maturity_score(capability) * 0.3), 1)
            cost_trend = "Stable"
            risk = BusinessCapabilityService._risk(capability, governance_score, monthly_spend, optimization)
            health = BusinessCapabilityService._health_score(governance_score, monthly_spend, optimization, capability)
            rows.append(
                {
                    "Business Capability": name,
                    "Health Score": health,
                    "Asset Count": len(cap_assets),
                    "Application Count": len(applications),
                    "Cloud Services Used": len(cloud_services),
                    "SaaS Dependencies": len(saas_dependencies),
                    "Active Incidents": 0,
                    "Governance Score": governance_score,
                    "Ownership Completeness": ownership_completeness,
                    "Cost Trend": cost_trend,
                    "Optimization Opportunity": round(optimization, 2),
                    "Monthly Spend": round(monthly_spend, 2),
                    "Risk": risk,
                    "Owner": capability.get("executive_owner") or "Unassigned",
                    "Criticality": capability.get("criticality") or "Medium",
                    "Business Unit": capability.get("business_unit") or "Unassigned",
                    "Department": capability.get("department") or "Unassigned",
                    "Missing Executive Owner": not bool(capability.get("executive_owner")),
                }
            )
        return rows

    @staticmethod
    def _persist_capabilities(rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            supabase.table(BusinessCapabilityService.TABLE_NAME).upsert(
                rows,
                on_conflict="organization_id,capability_name",
            ).execute()
        except Exception as exc:
            print("BUSINESS CAPABILITY REGISTRY UPSERT FAILED:", exc)

    @staticmethod
    def _load_registry(organization_id: str) -> list[dict[str, Any]]:
        try:
            return (
                supabase.table(BusinessCapabilityService.TABLE_NAME)
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
                .data
                or []
            )
        except Exception as exc:
            print("BUSINESS CAPABILITY REGISTRY LOAD FAILED:", exc)
            return []

    @staticmethod
    def _fetch_org_rows(table_name: str, organization_id: str) -> list[dict[str, Any]]:
        try:
            rows = (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
                .data
                or []
            )
            if rows:
                return rows
            return (
                supabase.table(table_name)
                .select("*")
                .is_("organization_id", "null")
                .execute()
                .data
                or []
            )
        except Exception:
            return []

    @staticmethod
    def _fetch_rows(table_name: str) -> list[dict[str, Any]]:
        try:
            return supabase.table(table_name).select("*").execute().data or []
        except Exception:
            return []

    @staticmethod
    def _business_unit(ownership: dict[str, Any], context: dict[str, Any]) -> str | None:
        app = BusinessCapabilityService._norm(ownership.get("application"))
        for row in context["applications"]:
            if BusinessCapabilityService._norm(row.get("app_name")) == app:
                return row.get("business_unit")
        return None

    @staticmethod
    def _cloud_services(assets: list[dict[str, Any]], costs: list[dict[str, Any]]) -> set[str]:
        services = set()
        asset_apps = {BusinessCapabilityService._norm(row.get("application")) for row in assets if row.get("application")}
        for row in costs:
            if BusinessCapabilityService._norm(row.get("application")) in asset_apps:
                services.add(str(row.get("service_name") or "Unknown"))
        if not services:
            services = {str(row.get("business_service") or row.get("application") or "Unknown") for row in assets}
        return {service for service in services if service and service != "Unknown"}

    @staticmethod
    def _saas_dependencies(capability: str, applications: set[str], relationships: list[dict[str, Any]]) -> set[str]:
        deps = set()
        app_keys = {BusinessCapabilityService._norm(app) for app in applications}
        cap_key = BusinessCapabilityService._norm(capability)
        for row in relationships:
            source = BusinessCapabilityService._norm(row.get("source_name") or row.get("source"))
            target_type = BusinessCapabilityService._norm(row.get("target_type"))
            target = str(row.get("target_name") or row.get("target") or "").strip()
            if source in app_keys | {cap_key} and ("saas" in target_type or "ai" in target_type):
                deps.add(target)
        return deps

    @staticmethod
    def _monthly_spend(assets: list[dict[str, Any]], costs: list[dict[str, Any]]) -> float:
        apps = {BusinessCapabilityService._norm(row.get("application")) for row in assets if row.get("application")}
        providers = {BusinessCapabilityService._norm(row.get("vendor")) for row in assets if row.get("vendor")}
        total = 0.0
        for row in costs:
            app_match = BusinessCapabilityService._norm(row.get("application")) in apps
            provider_match = BusinessCapabilityService._norm(row.get("cloud")) in providers
            if app_match or provider_match:
                total += BusinessCapabilityService._float(row.get("cost"))
        return total

    @staticmethod
    def _optimization_opportunity(
        capability: str,
        applications: set[str],
        recommendations: list[dict[str, Any]],
        monthly_spend: float,
    ) -> float:
        app_keys = {BusinessCapabilityService._norm(app) for app in applications}
        total = 0.0
        for row in recommendations:
            text = BusinessCapabilityService._norm(" ".join(str(value or "") for value in row.values()))
            if BusinessCapabilityService._norm(capability) in text or any(app in text for app in app_keys):
                total += BusinessCapabilityService._float(row.get("estimated_savings"))
        return total if total else round(monthly_spend * 0.05, 2)

    @staticmethod
    def _health_score(governance_score: float, spend: float, optimization: float, capability: dict[str, Any]) -> float:
        maturity_score = BusinessCapabilityService._maturity_score(capability)
        optimization_penalty = min((optimization / spend) * 20, 20) if spend else 0
        criticality_penalty = 4 if BusinessCapabilityService._is_critical(capability) else 0
        return round(max((governance_score * 0.55) + (maturity_score * 0.35) + 10 - optimization_penalty - criticality_penalty, 0), 1)

    @staticmethod
    def _risk(capability: dict[str, Any], governance_score: float, spend: float, optimization: float) -> str:
        if governance_score < 70 or (spend and optimization / spend > 0.2):
            return "High"
        if BusinessCapabilityService._is_critical(capability) and governance_score < 85:
            return "Medium"
        return "Low"

    @staticmethod
    def _maturity_score(capability: dict[str, Any]) -> float:
        return min(max(BusinessCapabilityService._float(capability.get("maturity")) * 20, 0), 100)

    @staticmethod
    def _recommendations(health_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recommendations = []
        for row in health_rows:
            if row["Missing Executive Owner"]:
                recommendations.append({"Business Capability": row["Business Capability"], "Recommendation": "Assign executive owner"})
            if row["Ownership Completeness"] < 100:
                recommendations.append({"Business Capability": row["Business Capability"], "Recommendation": "Complete ownership metadata"})
            if row["Optimization Opportunity"] > 0:
                recommendations.append({"Business Capability": row["Business Capability"], "Recommendation": "Review optimization opportunities"})
            if row["Health Score"] < 80:
                recommendations.append({"Business Capability": row["Business Capability"], "Recommendation": "Prioritize capability health review"})
        return recommendations

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], field: str, label: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get(field) or "Unmapped"
            counts[str(value)] = counts.get(str(value), 0) + 1
        return [{label: key, "Count": value} for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)]

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
        seen = set()
        output = []
        for row in rows:
            key = tuple(row.get(item) for item in keys)
            if key in seen:
                continue
            seen.add(key)
            output.append(row)
        return output

    @staticmethod
    def _max_criticality(left: Any, right: Any) -> str:
        order = {"critical": 4, "high": 3, "medium": 2, "standard": 1, "low": 1}
        left_text = str(left or "Medium")
        right_text = str(right or "")
        return right_text if order.get(BusinessCapabilityService._norm(right_text), 0) > order.get(BusinessCapabilityService._norm(left_text), 0) else left_text

    @staticmethod
    def _is_critical(row: dict[str, Any]) -> bool:
        return BusinessCapabilityService._norm(row.get("criticality")) in {"critical", "high", "tier 1", "tier1"}

    @staticmethod
    def _capability_code(sequence: int) -> str:
        return f"BC-{sequence:03d}"

    @staticmethod
    def _average(values: list[float]) -> float:
        return round(sum(values) / len(values), 1) if values else 0.0

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()
