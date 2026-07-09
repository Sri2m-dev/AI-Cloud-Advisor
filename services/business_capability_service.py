from __future__ import annotations

from typing import Any

import pandas as pd

from repositories.business_capability_repository import BusinessCapabilityRepository
from services.business_unit_service import BusinessUnitService


def _normalize(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _lower(value: Any) -> str:
    return _normalize(value).lower()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _first_existing(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


class BusinessCapabilityService:
    """E7.1.2 service for the enterprise business capability foundation."""

    @staticmethod
    def get_capabilities() -> list[dict[str, Any]]:
        explicit = BusinessCapabilityRepository.get_business_capabilities()
        services = BusinessCapabilityRepository.get_business_services()
        applications = BusinessCapabilityRepository.get_application_registry()
        spend = BusinessCapabilityRepository.get_application_spend()

        capabilities: dict[str, dict[str, Any]] = {}

        for row in explicit:
            capability = BusinessCapabilityService._capability_name(row)
            if not capability:
                continue
            item = BusinessCapabilityService._ensure_capability(
                capabilities,
                capability,
                BusinessCapabilityService._business_unit_name(row),
                source="business_capabilities",
            )
            item["id"] = _first_existing(row, "id", "capability_id", default=item["id"])
            item["business_unit_id"] = _first_existing(row, "business_unit_id", default=item["business_unit_id"])
            item["owner"] = _normalize(_first_existing(row, "owner", "capability_owner", default=item["owner"]), item["owner"])
            item["criticality"] = BusinessCapabilityService._max_criticality(
                item["criticality"],
                _first_existing(row, "criticality", "tier"),
            )
            item["status"] = _normalize(_first_existing(row, "status", default=item["status"]), item["status"])

        for row in services:
            capability = BusinessCapabilityService._capability_name(row) or BusinessCapabilityService._derive_capability(row)
            unit = BusinessCapabilityService._business_unit_name(row)
            item = BusinessCapabilityService._ensure_capability(capabilities, capability, unit, source="business_services")
            item["business_services"] += 1
            item["owner"] = BusinessCapabilityService._prefer_assigned(
                item["owner"],
                _first_existing(row, "owner", "service_owner", "business_owner"),
            )
            item["criticality"] = BusinessCapabilityService._max_criticality(
                item["criticality"],
                _first_existing(row, "criticality", "service_criticality"),
            )
            item["monthly_cost"] += BusinessCapabilityService._monthly_value(row)

        for row in applications:
            capability = BusinessCapabilityService._capability_name(row) or BusinessCapabilityService._derive_capability(row)
            unit = BusinessCapabilityService._business_unit_name(row)
            item = BusinessCapabilityService._ensure_capability(capabilities, capability, unit, source="application_registry")
            item["applications"] += 1
            item["owner"] = BusinessCapabilityService._prefer_assigned(
                item["owner"],
                _first_existing(row, "owner", "owner_name", "application_owner", "business_owner"),
            )
            item["criticality"] = BusinessCapabilityService._max_criticality(
                item["criticality"],
                _first_existing(row, "criticality", "application_criticality"),
            )

        BusinessCapabilityService._apply_spend(capabilities, spend)

        if not capabilities:
            retail_unit = next(iter(BusinessUnitService.get_business_units()), {})
            item = BusinessCapabilityService._ensure_capability(
                capabilities,
                "Checkout",
                retail_unit.get("Business Unit") or "Retail",
                source="fallback",
            )
            item["owner"] = retail_unit.get("Owner") or "Digital Commerce"
            item["criticality"] = "Critical"
            item["applications"] = 1
            item["business_services"] = 1
            item["monthly_cost"] = 10800.0

        output = []
        for item in capabilities.values():
            item["monthly_cost"] = round(_safe_float(item["monthly_cost"]), 2)
            item["mapping_coverage"] = BusinessCapabilityService._mapping_coverage(item)
            item["risk_score"] = BusinessCapabilityService._risk_score(item)
            item["health_score"] = BusinessCapabilityService._health_score(item)
            output.append(item)

        return sorted(output, key=lambda row: (row["business_unit"], row["name"]))

    @staticmethod
    def get_capabilities_by_business_unit() -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in BusinessCapabilityService.get_capabilities():
            grouped.setdefault(row["business_unit"], []).append(row)
        return grouped

    @staticmethod
    def get_capability_summary(organization_id: str | None = None) -> dict[str, Any]:
        capabilities = BusinessCapabilityService.get_capabilities()
        critical = [row for row in capabilities if row["criticality"] in {"Critical", "High"}]
        total_spend = sum(_safe_float(row["monthly_cost"]) for row in capabilities)
        avg_health = BusinessCapabilityService._average([row["health_score"] for row in capabilities])
        avg_coverage = BusinessCapabilityService._average([row["mapping_coverage"] for row in capabilities])
        governance_score = round((avg_health * 0.6) + (avg_coverage * 0.4), 1)

        return {
            "status": "SUCCESS",
            "organization_id": organization_id,
            "capabilities": capabilities,
            "health": BusinessCapabilityService.get_capability_health(organization_id),
            "total_capabilities": len(capabilities),
            "capabilities_synced": len(capabilities),
            "critical_capabilities": len(critical),
            "average_health": avg_health,
            "mapping_coverage": avg_coverage,
            "total_capability_spend": round(total_spend, 2),
            "optimization_opportunity": round(total_spend * 0.08, 2),
            "governance_score": governance_score,
            "business_units": len(BusinessCapabilityService.get_capabilities_by_business_unit()),
            "applications": sum(_safe_int(row["applications"]) for row in capabilities),
            "business_services": sum(_safe_int(row["business_services"]) for row in capabilities),
        }

    @staticmethod
    def get_capability_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        capabilities = BusinessCapabilityService.get_capabilities()
        summary = BusinessCapabilityService.get_capability_summary(organization_id)
        health = BusinessCapabilityService.get_capability_health(organization_id)
        spend = BusinessCapabilityService.get_capability_spend(organization_id)
        applications = BusinessCapabilityService.get_capability_applications(organization_id)
        assets = BusinessCapabilityService.get_capability_assets(organization_id)
        risk = BusinessCapabilityService.get_capability_risk(organization_id)
        dependencies = BusinessCapabilityService.get_capability_dependencies(organization_id)

        return {
            "summary": summary,
            "capabilities": capabilities,
            "health": health,
            "spend": spend,
            "assets": assets,
            "applications": applications,
            "health_matrix": health,
            "spend_by_capability": spend,
            "assets_by_capability": BusinessCapabilityService._distribution(assets, "Business Capability"),
            "applications_by_capability": applications,
            "risk_heatmap": risk,
            "dependency_graph": dependencies,
            "critical_capabilities": [row for row in health if row["Criticality"] in {"Critical", "High"}],
            "lowest_health": sorted(health, key=lambda row: row["Health Score"])[:10],
            "highest_spend": sorted(health, key=lambda row: row["Monthly Spend"], reverse=True)[:10],
            "missing_executive_owner": [row for row in health if row["Owner"] in {"Unassigned", "Unknown", ""}],
            "improvement_recommendations": BusinessCapabilityService._recommendations(health),
            "capabilities_by_business_unit": BusinessCapabilityService.get_capabilities_by_business_unit(),
        }

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        return BusinessCapabilityService.get_capability_dashboard(organization_id)

    @staticmethod
    def sync_business_capabilities(organization_id: str | None = None) -> dict[str, Any]:
        return BusinessCapabilityService.get_capability_summary(organization_id)

    @staticmethod
    def get_capability_health(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "Business Capability": row["name"],
                "Business Unit": row["business_unit"],
                "Health Score": row["health_score"],
                "Risk Score": row["risk_score"],
                "Risk": BusinessCapabilityService._risk_label(row["risk_score"]),
                "Application Count": row["applications"],
                "Asset Count": row["applications"] + row["business_services"],
                "Business Services": row["business_services"],
                "Monthly Spend": row["monthly_cost"],
                "Optimization Opportunity": round(row["monthly_cost"] * 0.08, 2),
                "Governance Score": row["mapping_coverage"],
                "Ownership Completeness": 0 if row["owner"] in {"Unassigned", "Unknown", ""} else 100,
                "Cost Trend": "Stable",
                "Owner": row["owner"],
                "Criticality": row["criticality"],
                "Department": row["business_unit"],
                "Missing Executive Owner": row["owner"] in {"Unassigned", "Unknown", ""},
            }
            for row in BusinessCapabilityService.get_capabilities()
        ]

    @staticmethod
    def get_capability_spend(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "Business Capability": row["name"],
                "Business Unit": row["business_unit"],
                "Monthly Spend": row["monthly_cost"],
                "Optimization Opportunity": round(row["monthly_cost"] * 0.08, 2),
            }
            for row in BusinessCapabilityService.get_capabilities()
        ]

    @staticmethod
    def get_capability_assets(organization_id: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for row in BusinessCapabilityService.get_capabilities():
            rows.append(
                {
                    "Business Capability": row["name"],
                    "Business Unit": row["business_unit"],
                    "Enterprise Asset ID": row["id"],
                    "Application": row["applications"],
                    "Business Service": row["business_services"],
                    "Owner": row["owner"],
                    "Criticality": row["criticality"],
                }
            )
        return rows

    @staticmethod
    def get_capability_applications(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "Business Capability": row["name"],
                "Business Unit": row["business_unit"],
                "Applications": row["applications"],
                "Application List": f"{row['applications']} mapped application(s)",
            }
            for row in BusinessCapabilityService.get_capabilities()
        ]

    @staticmethod
    def get_capability_risk(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "Business Capability": row["name"],
                "Business Unit": row["business_unit"],
                "Risk": BusinessCapabilityService._risk_label(row["risk_score"]),
                "Risk Score": row["risk_score"],
                "Health Score": row["health_score"],
                "Criticality": row["criticality"],
                "Mapping Coverage": row["mapping_coverage"],
                "Missing Executive Owner": row["owner"] in {"Unassigned", "Unknown", ""},
            }
            for row in BusinessCapabilityService.get_capabilities()
        ]

    @staticmethod
    def get_capability_dependencies(organization_id: str | None = None) -> list[dict[str, Any]]:
        dependencies = []
        for row in BusinessCapabilityRepository.get_business_service_relationships():
            source = _first_existing(row, "source_name", "source")
            target = _first_existing(row, "target_name", "target")
            if source and target:
                dependencies.append(
                    {
                        "Source": source,
                        "Relationship": _first_existing(row, "relationship_type", "relationship", default="RELATES_TO"),
                        "Target": target,
                    }
                )

        for row in BusinessCapabilityService.get_capabilities():
            dependencies.append(
                {
                    "Source": row["business_unit"],
                    "Relationship": "OWNS_CAPABILITY",
                    "Target": row["name"],
                }
            )
        return BusinessCapabilityService._dedupe(dependencies, ("Source", "Relationship", "Target"))

    @staticmethod
    def capabilities_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessCapabilityService.get_capabilities())

    @staticmethod
    def summary_dataframe() -> pd.DataFrame:
        summary = BusinessCapabilityService.get_capability_summary()
        return pd.DataFrame(
            [
                {"Metric": "Capabilities", "Value": summary["total_capabilities"]},
                {"Metric": "Business Units", "Value": summary["business_units"]},
                {"Metric": "Applications", "Value": summary["applications"]},
                {"Metric": "Business Services", "Value": summary["business_services"]},
                {"Metric": "Monthly Cost", "Value": summary["total_capability_spend"]},
                {"Metric": "Average Health", "Value": summary["average_health"]},
                {"Metric": "Mapping Coverage", "Value": summary["mapping_coverage"]},
            ]
        )

    @staticmethod
    def _ensure_capability(
        capabilities: dict[str, dict[str, Any]],
        name: str,
        business_unit: str,
        *,
        source: str,
    ) -> dict[str, Any]:
        capability = _normalize(name, "Unmapped Capability")
        unit = _normalize(business_unit, BusinessCapabilityService._default_business_unit())
        key = f"{_lower(unit)}::{_lower(capability)}"
        if key not in capabilities:
            capabilities[key] = {
                "id": BusinessCapabilityService._capability_id(unit, capability),
                "business_unit_id": BusinessCapabilityService._business_unit_id(unit),
                "business_unit": unit,
                "name": capability,
                "owner": "Unassigned",
                "criticality": "Medium",
                "applications": 0,
                "business_services": 0,
                "monthly_cost": 0.0,
                "health_score": 0.0,
                "risk_score": 0.0,
                "mapping_coverage": 0.0,
                "status": "Active",
                "source": source,
            }
        elif capabilities[key].get("source") == "fallback":
            capabilities[key]["source"] = source
        return capabilities[key]

    @staticmethod
    def _capability_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "capability_name",
                "business_capability",
                "Business Capability",
                "capability",
                default="",
            )
        )

    @staticmethod
    def _derive_capability(row: dict[str, Any]) -> str:
        service = _normalize(_first_existing(row, "service_name", "business_service_name", "service", default=""))
        app = _normalize(_first_existing(row, "app_name", "application_name", "application", "name", default=""))
        candidate = service or app or "Unmapped Capability"
        for suffix in (" Service", " Application", " API", " Portal"):
            if candidate.endswith(suffix):
                candidate = candidate[: -len(suffix)]
        return _normalize(candidate, "Unmapped Capability")

    @staticmethod
    def _business_unit_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "business_unit",
                "business_unit_name",
                "Business Unit",
                "department",
                default="",
            )
        )

    @staticmethod
    def _default_business_unit() -> str:
        units = BusinessUnitService.get_business_units()
        return _normalize(units[0].get("Business Unit") if units else "", "Retail")

    @staticmethod
    def _business_unit_id(unit: str) -> str:
        return f"bu-{_lower(unit).replace(' ', '-') or 'unmapped'}"

    @staticmethod
    def _capability_id(unit: str, capability: str) -> str:
        return f"cap-{_lower(unit).replace(' ', '-')}-{_lower(capability).replace(' ', '-')}"

    @staticmethod
    def _monthly_value(row: dict[str, Any]) -> float:
        monthly = _safe_float(_first_existing(row, "monthly_cost", "monthly_spend", "total_spend", "total_cost", "cost", default=0))
        if monthly:
            return monthly
        return _safe_float(_first_existing(row, "annual_cost", "annual_spend", default=0)) / 12

    @staticmethod
    def _apply_spend(capabilities: dict[str, dict[str, Any]], spend_rows: list[dict[str, Any]]) -> None:
        if not spend_rows:
            return

        app_index = BusinessCapabilityService._application_capability_index()
        service_index = BusinessCapabilityService._service_capability_index()
        for row in spend_rows:
            capability = BusinessCapabilityService._capability_name(row)
            unit = BusinessCapabilityService._business_unit_name(row)
            application = _normalize(_first_existing(row, "application_name", "app_name", "application", "name", default=""))
            if not capability:
                indexed = app_index.get(_lower(application)) or service_index.get(_lower(application))
                if indexed:
                    unit, capability = indexed
            if not capability:
                continue
            item = BusinessCapabilityService._ensure_capability(capabilities, capability, unit, source="mart_application_spend")
            item["monthly_cost"] += BusinessCapabilityService._monthly_value(row)

    @staticmethod
    def _application_capability_index() -> dict[str, tuple[str, str]]:
        index = {}
        for row in BusinessCapabilityRepository.get_application_registry():
            app = _normalize(_first_existing(row, "app_name", "application_name", "application", "name", default=""))
            capability = BusinessCapabilityService._capability_name(row) or BusinessCapabilityService._derive_capability(row)
            unit = BusinessCapabilityService._business_unit_name(row)
            if app:
                index[_lower(app)] = (unit, capability)
        return index

    @staticmethod
    def _service_capability_index() -> dict[str, tuple[str, str]]:
        index = {}
        for row in BusinessCapabilityRepository.get_business_services():
            service = _normalize(_first_existing(row, "service_name", "business_service_name", "service", "name", default=""))
            capability = BusinessCapabilityService._capability_name(row) or BusinessCapabilityService._derive_capability(row)
            unit = BusinessCapabilityService._business_unit_name(row)
            if service:
                index[_lower(service)] = (unit, capability)
        return index

    @staticmethod
    def _mapping_coverage(row: dict[str, Any]) -> float:
        dimensions = [
            bool(row.get("business_unit")),
            bool(row.get("applications")),
            bool(row.get("business_services")),
            _safe_float(row.get("monthly_cost")) > 0,
            row.get("owner") not in {"", "Unassigned", "Unknown"},
        ]
        return round(sum(1 for item in dimensions if item) / len(dimensions) * 100, 1)

    @staticmethod
    def _risk_score(row: dict[str, Any]) -> float:
        score = 100 - _safe_float(row.get("mapping_coverage"))
        if row.get("criticality") in {"Critical", "High"}:
            score += 10
        if _safe_float(row.get("monthly_cost")) >= 10000:
            score += 5
        return round(min(max(score, 0), 100), 1)

    @staticmethod
    def _health_score(row: dict[str, Any]) -> float:
        coverage = _safe_float(row.get("mapping_coverage"))
        risk = _safe_float(row.get("risk_score"))
        return round(max(min((coverage * 0.75) + ((100 - risk) * 0.25), 100), 0), 1)

    @staticmethod
    def _risk_label(score: float) -> str:
        if score >= 70:
            return "High"
        if score >= 35:
            return "Medium"
        return "Low"

    @staticmethod
    def _max_criticality(left: Any, right: Any) -> str:
        order = {"low": 1, "standard": 1, "medium": 2, "high": 3, "critical": 4, "tier 1": 4, "tier1": 4}
        left_text = _normalize(left, "Medium")
        right_text = _normalize(right, "")
        if not right_text:
            return left_text
        return right_text if order.get(_lower(right_text), 0) > order.get(_lower(left_text), 0) else left_text

    @staticmethod
    def _prefer_assigned(current: Any, candidate: Any) -> str:
        current_text = _normalize(current, "Unassigned")
        candidate_text = _normalize(candidate)
        if _lower(current_text) in {"", "unassigned", "unknown"} and candidate_text:
            return candidate_text
        return current_text

    @staticmethod
    def _average(values: list[float]) -> float:
        clean = [_safe_float(value) for value in values]
        return round(sum(clean) / len(clean), 1) if clean else 0.0

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in rows:
            value = _normalize(row.get(key), "Unassigned")
            counts[value] = counts.get(value, 0) + 1
        return [{key: key_value, "Count": count} for key_value, count in sorted(counts.items())]

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
        seen = set()
        deduped = []
        for row in rows:
            key = tuple(_lower(row.get(item)) for item in keys)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    @staticmethod
    def _recommendations(health_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recommendations = []
        for row in health_rows:
            if row["Governance Score"] < 80:
                recommendations.append(
                    {
                        "Business Capability": row["Business Capability"],
                        "Recommendation": "Improve service, application, cost, and ownership mappings.",
                    }
                )
            if row["Missing Executive Owner"]:
                recommendations.append(
                    {
                        "Business Capability": row["Business Capability"],
                        "Recommendation": "Assign an accountable business or executive owner.",
                    }
                )
        return recommendations
