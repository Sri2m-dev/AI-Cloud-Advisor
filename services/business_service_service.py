from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from repositories.business_service_repository import BusinessServiceRepository
from services.business_capability_service import BusinessCapabilityService
from services.business_unit_service import BusinessUnitService
from services.knowledge_graph_service import KnowledgeGraphService


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


class BusinessServiceService:
    """E7.1.3 service foundation for enterprise business services."""

    @staticmethod
    def get_business_services() -> list[dict[str, Any]]:
        service_rows = BusinessServiceRepository.get_business_services()
        app_rows = BusinessServiceRepository.get_application_registry()
        service_app_pairs = BusinessServiceService._service_application_pairs(service_rows, app_rows)
        app_tech_pairs = BusinessServiceService._application_technology_pairs()
        app_spend = BusinessServiceService._application_spend_lookup()
        tech_lookup = BusinessServiceService._technology_lookup()
        recommendations = BusinessServiceRepository.get_recommendations()
        approvals = BusinessServiceRepository.get_approval_queue()
        savings = BusinessServiceRepository.get_savings()
        incidents = BusinessServiceRepository.get_operations_events()

        services: dict[str, dict[str, Any]] = {}

        for row in service_rows:
            name = BusinessServiceService._service_name(row)
            if not name:
                continue
            services[_lower(name)] = BusinessServiceService._base_service(row, name)

        if not services:
            for app in app_rows:
                service_name = BusinessServiceService._service_name(app) or f"{BusinessServiceService._application_name(app)} Service"
                if service_name:
                    services[_lower(service_name)] = BusinessServiceService._base_service(app, service_name)

        if not services:
            unit = next(iter(BusinessUnitService.get_business_units()), {})
            name = "Checkout Service"
            services[_lower(name)] = {
                **BusinessServiceService._empty_service(name),
                "business_unit": unit.get("Business Unit") or "Retail",
                "business_capability": "Checkout",
                "owner": unit.get("Owner") or "Digital Commerce",
                "tier": "Tier 1",
                "sla": "99.9%",
                "applications": ["Checkout"],
                "status": "Active",
                "source": "fallback",
            }

        BusinessServiceService._apply_service_applications(services, service_app_pairs)
        BusinessServiceService._apply_application_technology(services, app_tech_pairs)
        BusinessServiceService._apply_costs(services, app_spend)
        BusinessServiceService._apply_signals(services, recommendations, approvals, savings, incidents)

        output = []
        for service in services.values():
            BusinessServiceService._apply_knowledge_graph_fallback(service)
            BusinessServiceService._finalize_service(service, tech_lookup)
            output.append(service)

        return sorted(output, key=lambda item: (item["business_unit"], item["business_capability"], item["name"]))

    @staticmethod
    def get_business_service(service_id: str) -> dict[str, Any] | None:
        service_key = _lower(service_id)
        if not service_key:
            return None
        for row in BusinessServiceService.get_business_services():
            candidates = [
                row.get("id"),
                row.get("name"),
                row.get("service_code"),
            ]
            if service_key in {_lower(value) for value in candidates}:
                return row
        raw = BusinessServiceRepository.get_business_service(service_id)
        if raw:
            name = BusinessServiceService._service_name(raw)
            return BusinessServiceService._base_service(raw, name)
        return None

    @staticmethod
    def get_services_by_capability() -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in BusinessServiceService.get_business_services():
            grouped.setdefault(row["business_capability"], []).append(row)
        return grouped

    @staticmethod
    def get_services_by_business_unit() -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in BusinessServiceService.get_business_services():
            grouped.setdefault(row["business_unit"], []).append(row)
        return grouped

    @staticmethod
    def get_service_summary() -> dict[str, Any]:
        services = BusinessServiceService.get_business_services()
        total_cost = sum(_safe_float(row.get("monthly_cost")) for row in services)
        total_savings = sum(_safe_float(row.get("potential_savings")) for row in services)
        avg_health = BusinessServiceService._average([row["health_score"] for row in services])
        avg_risk = BusinessServiceService._average([row["risk_score"] for row in services])
        return {
            "business_services": len(services),
            "business_units": len(BusinessServiceService.get_services_by_business_unit()),
            "business_capabilities": len(BusinessServiceService.get_services_by_capability()),
            "applications": len({app for row in services for app in row.get("applications", [])}),
            "technologies": len({tech for row in services for tech in row.get("technologies", [])}),
            "cloud_resources": sum(_safe_int(row.get("cloud_resources")) for row in services),
            "monthly_cost": round(total_cost, 2),
            "forecast_cost": round(sum(_safe_float(row.get("forecast_cost")) for row in services), 2),
            "potential_savings": round(total_savings, 2),
            "active_incidents": sum(_safe_int(row.get("active_incidents")) for row in services),
            "recommendations": sum(_safe_int(row.get("recommendations")) for row in services),
            "automation_candidates": sum(_safe_int(row.get("automation_candidates")) for row in services),
            "average_health": avg_health,
            "average_risk": avg_risk,
            "summary_ok": True,
        }

    @staticmethod
    def get_service_dashboard() -> dict[str, Any]:
        services = BusinessServiceService.get_business_services()
        return {
            "summary": BusinessServiceService.get_service_summary(),
            "business_services": services,
            "services_by_business_unit": BusinessServiceService.get_services_by_business_unit(),
            "services_by_capability": BusinessServiceService.get_services_by_capability(),
            "highest_cost": sorted(services, key=lambda row: _safe_float(row.get("monthly_cost")), reverse=True),
            "highest_risk": sorted(services, key=lambda row: _safe_float(row.get("risk_score")), reverse=True),
            "lowest_health": sorted(services, key=lambda row: _safe_float(row.get("health_score"))),
            "optimization_candidates": [
                row for row in services
                if _safe_float(row.get("potential_savings")) > 0 or _safe_int(row.get("recommendations")) > 0
            ],
            "relationship_paths": BusinessServiceService._relationship_paths(services),
        }

    @staticmethod
    def services_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessServiceService.get_business_services())

    @staticmethod
    def summary_dataframe() -> pd.DataFrame:
        summary = BusinessServiceService.get_service_summary()
        return pd.DataFrame(
            [
                {"Metric": "Business Services", "Value": summary["business_services"]},
                {"Metric": "Business Units", "Value": summary["business_units"]},
                {"Metric": "Business Capabilities", "Value": summary["business_capabilities"]},
                {"Metric": "Applications", "Value": summary["applications"]},
                {"Metric": "Technologies", "Value": summary["technologies"]},
                {"Metric": "Monthly Cost", "Value": summary["monthly_cost"]},
                {"Metric": "Potential Savings", "Value": summary["potential_savings"]},
                {"Metric": "Average Health", "Value": summary["average_health"]},
            ]
        )

    @staticmethod
    def _base_service(row: dict[str, Any], name: str) -> dict[str, Any]:
        capability = BusinessServiceService._capability_name(row) or BusinessServiceService._derive_capability(name)
        unit = BusinessServiceService._business_unit_name(row) or BusinessServiceService._business_unit_for_capability(capability)
        return {
            **BusinessServiceService._empty_service(name),
            "id": _normalize(_first_existing(row, "id", "service_id", "service_code", default=BusinessServiceService._service_id(name))),
            "service_code": _normalize(_first_existing(row, "service_code", "code", default="")),
            "business_unit": unit,
            "business_capability": capability,
            "owner": _normalize(_first_existing(row, "owner", "service_owner", "business_owner", default="Unassigned"), "Unassigned"),
            "tier": _normalize(_first_existing(row, "tier", "criticality", default=BusinessServiceService._tier_from_criticality(row)), "Tier 2"),
            "sla": _normalize(_first_existing(row, "sla", "service_sla", default="99.5%"), "99.5%"),
            "monthly_cost": BusinessServiceService._monthly_value(row),
            "status": BusinessServiceService._status(row),
            "last_updated": _normalize(_first_existing(row, "updated_at", "last_updated", default=BusinessServiceService._now())),
            "source": "business_services",
        }

    @staticmethod
    def _empty_service(name: str) -> dict[str, Any]:
        return {
            "id": BusinessServiceService._service_id(name),
            "service_code": "",
            "name": name,
            "business_unit": "Unassigned",
            "business_capability": "Unmapped Capability",
            "owner": "Unassigned",
            "tier": "Tier 2",
            "sla": "99.5%",
            "applications": [],
            "technologies": [],
            "cloud_resources": 0,
            "vendors": [],
            "monthly_cost": 0.0,
            "forecast_cost": 0.0,
            "health_score": 0.0,
            "risk_score": 0.0,
            "governance_score": 0.0,
            "optimization": 0.0,
            "potential_savings": 0.0,
            "active_incidents": 0,
            "recommendations": 0,
            "automation_candidates": 0,
            "status": "Active",
            "last_updated": BusinessServiceService._now(),
            "source": "derived",
        }

    @staticmethod
    def _service_application_pairs(
        service_rows: list[dict[str, Any]],
        app_rows: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        service_names = [BusinessServiceService._service_name(row) for row in service_rows]
        service_names = [name for name in service_names if name]

        for row in BusinessServiceRepository.get_business_service_relationships():
            source = _normalize(_first_existing(row, "source_name", "source", "from_name", "business_service_name", "service_name"))
            target = _normalize(_first_existing(row, "target_name", "target", "to_name", "application_name", "dependent_name"))
            source_type = _lower(_first_existing(row, "source_type", "from_type", default=""))
            target_type = _lower(_first_existing(row, "target_type", "to_type", default=""))
            if source and target and ("business service" in source_type or "application" in target_type or _lower(source) in {_lower(item) for item in service_names}):
                pairs.append((source, target))

        for row in app_rows:
            app = BusinessServiceService._application_name(row)
            service = BusinessServiceService._service_name(row)
            if not service and len(service_names) == 1:
                service = service_names[0]
            if service and app:
                pairs.append((service, app))

        return BusinessServiceService._dedupe_pairs(pairs)

    @staticmethod
    def _application_technology_pairs() -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []

        for row in BusinessServiceRepository.get_application_spend_mapping():
            app = BusinessServiceService._application_name(row)
            tech = BusinessServiceService._technology_name(row)
            if app and tech:
                pairs.append((app, tech))

        for row in BusinessServiceRepository.get_technology_relationships():
            source = _normalize(_first_existing(row, "source_name", "source", "from_name"))
            target = _normalize(_first_existing(row, "target_name", "target", "to_name"))
            source_type = _lower(_first_existing(row, "source_type", "from_type", default=""))
            target_type = _lower(_first_existing(row, "target_type", "to_type", default=""))
            if source and target and ("application" in source_type or "technology" in target_type or "vendor" in target_type):
                pairs.append((source, target))

        for row in BusinessServiceRepository.get_application_registry():
            app = BusinessServiceService._application_name(row)
            provider = _normalize(_first_existing(row, "cloud_provider", "technology_name", "platform", default=""))
            if app and provider:
                pairs.append((app, provider))

        return BusinessServiceService._dedupe_pairs(pairs)

    @staticmethod
    def _apply_service_applications(services: dict[str, dict[str, Any]], pairs: list[tuple[str, str]]) -> None:
        if not pairs and len(services) == 1:
            service = next(iter(services.values()))
            for app in BusinessServiceRepository.get_application_registry():
                app_name = BusinessServiceService._application_name(app)
                if app_name:
                    service["applications"].append(app_name)
            return

        for service_name, application in pairs:
            service = services.get(_lower(service_name))
            if not service and len(services) == 1:
                service = next(iter(services.values()))
            if service and application:
                service["applications"].append(application)

    @staticmethod
    def _apply_application_technology(services: dict[str, dict[str, Any]], pairs: list[tuple[str, str]]) -> None:
        tech_by_app: dict[str, set[str]] = {}
        for app, tech in pairs:
            tech_by_app.setdefault(_lower(app), set()).add(tech)

        for service in services.values():
            for app in service["applications"]:
                service["technologies"].extend(sorted(tech_by_app.get(_lower(app), set())))

    @staticmethod
    def _apply_costs(services: dict[str, dict[str, Any]], app_spend: dict[str, float]) -> None:
        for service in services.values():
            app_cost = sum(app_spend.get(_lower(app), 0.0) for app in service["applications"])
            direct_service_cost = app_spend.get(_lower(service["name"]), 0.0)
            service["monthly_cost"] += app_cost + direct_service_cost

    @staticmethod
    def _apply_signals(
        services: dict[str, dict[str, Any]],
        recommendations: list[dict[str, Any]],
        approvals: list[dict[str, Any]],
        savings: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
    ) -> None:
        for service in services.values():
            text_keys = [service["name"], service["business_capability"], service["business_unit"], *service["applications"], *service["technologies"]]
            matched_recommendations = BusinessServiceService._matching_rows(recommendations, text_keys)
            matched_approvals = BusinessServiceService._matching_rows(approvals, text_keys)
            matched_savings = BusinessServiceService._matching_rows(savings, text_keys)
            matched_incidents = BusinessServiceService._matching_rows(incidents, text_keys)

            service["recommendations"] = len(matched_recommendations)
            service["automation_candidates"] = len([
                row for row in matched_recommendations
                if BusinessServiceService._is_automation_candidate(row)
            ])
            service["active_incidents"] = len(matched_incidents)
            service["potential_savings"] += sum(BusinessServiceService._savings_value(row) for row in matched_recommendations + matched_savings)
            service["optimization"] += service["potential_savings"]
            if matched_approvals:
                service["governance_score"] = max(_safe_float(service.get("governance_score")) - min(len(matched_approvals) * 8, 24), 0)

    @staticmethod
    def _apply_knowledge_graph_fallback(service: dict[str, Any]) -> None:
        try:
            levels = KnowledgeGraphService.get_explorer_levels(service["name"])
        except Exception:
            levels = {}

        if not service["applications"]:
            service["applications"].extend(levels.get("applications") or [])
        if not service["technologies"]:
            service["technologies"].extend(levels.get("technologies") or [])

        if not service["applications"]:
            selected = levels.get("selected_application")
            if selected:
                service["applications"].append(selected)

    @staticmethod
    def _finalize_service(service: dict[str, Any], tech_lookup: dict[str, dict[str, Any]]) -> None:
        service["applications"] = sorted(BusinessServiceService._unique(service["applications"]))
        service["technologies"] = sorted(BusinessServiceService._unique(service["technologies"]))
        vendors = []
        cloud_resources = 0
        for tech in service["technologies"]:
            row = tech_lookup.get(_lower(tech), {})
            vendor = _normalize(_first_existing(row, "vendor_name", "vendor", "provider", default=tech))
            if vendor:
                vendors.append(vendor)
            if BusinessServiceService._is_cloud_resource(row, tech):
                cloud_resources += 1

        service["vendors"] = sorted(BusinessServiceService._unique(vendors))
        service["cloud_resources"] = cloud_resources
        service["monthly_cost"] = round(_safe_float(service["monthly_cost"]), 2)
        service["forecast_cost"] = round(service["monthly_cost"] * 1.08, 2)
        if not service["potential_savings"] and service["monthly_cost"]:
            service["potential_savings"] = round(service["monthly_cost"] * 0.08, 2)
            service["optimization"] = service["potential_savings"]
        service["governance_score"] = BusinessServiceService._governance_score(service)
        service["risk_score"] = BusinessServiceService._risk_score(service)
        service["health_score"] = BusinessServiceService._health_score(service)
        if service["potential_savings"] and not service["recommendations"]:
            service["recommendations"] = 1
        if service["potential_savings"] >= 500 and not service["automation_candidates"]:
            service["automation_candidates"] = 1

    @staticmethod
    def _relationship_paths(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for service in services:
            for app in service.get("applications", []):
                for tech in service.get("technologies", []) or ["Unmapped Technology"]:
                    rows.append(
                        {
                            "Business Unit": service["business_unit"],
                            "Business Capability": service["business_capability"],
                            "Business Service": service["name"],
                            "Application": app,
                            "Technology": tech,
                        }
                    )
        return rows

    @staticmethod
    def _service_name(row: dict[str, Any]) -> str:
        return _normalize(_first_existing(row, "service_name", "business_service_name", "service", "name", default=""))

    @staticmethod
    def _application_name(row: dict[str, Any]) -> str:
        return _normalize(_first_existing(row, "application_name", "app_name", "application", "registry_application", "name", default=""))

    @staticmethod
    def _technology_name(row: dict[str, Any]) -> str:
        return _normalize(_first_existing(row, "technology_name", "technology", "tool_name", "product", "vendor_name", "provider", "cloud", default=""))

    @staticmethod
    def _business_unit_name(row: dict[str, Any]) -> str:
        return _normalize(_first_existing(row, "business_unit", "business_unit_name", "Business Unit", "department", default=""))

    @staticmethod
    def _capability_name(row: dict[str, Any]) -> str:
        return _normalize(_first_existing(row, "business_capability", "capability_name", "capability", "Business Capability", default=""))

    @staticmethod
    def _derive_capability(name: str) -> str:
        candidate = _normalize(name, "Unmapped Capability")
        for suffix in (" Service", " Application", " API", " Portal"):
            if candidate.endswith(suffix):
                candidate = candidate[: -len(suffix)]
        return _normalize(candidate, "Unmapped Capability")

    @staticmethod
    def _business_unit_for_capability(capability: str) -> str:
        for row in BusinessCapabilityService.get_capabilities():
            if _lower(row.get("name")) == _lower(capability):
                return row.get("business_unit") or "Unassigned"
        units = BusinessUnitService.get_business_units()
        return units[0].get("Business Unit") if units else "Retail"

    @staticmethod
    def _service_id(name: str) -> str:
        return f"svc-{_lower(name).replace(' ', '-') or 'unmapped'}"

    @staticmethod
    def _tier_from_criticality(row: dict[str, Any]) -> str:
        criticality = _lower(_first_existing(row, "criticality", "service_criticality", default=""))
        if criticality in {"critical", "tier 1", "tier1", "high"}:
            return "Tier 1"
        if criticality == "medium":
            return "Tier 2"
        return "Tier 3"

    @staticmethod
    def _status(row: dict[str, Any]) -> str:
        value = _normalize(_first_existing(row, "status", "active", default="Active"))
        if value.lower() == "true":
            return "Active"
        if value.lower() == "false":
            return "Inactive"
        return value.title() if value.isupper() else value

    @staticmethod
    def _monthly_value(row: dict[str, Any]) -> float:
        monthly = _safe_float(_first_existing(row, "monthly_cost", "monthly_spend", "total_spend", "total_cost", "cost", default=0))
        if monthly:
            return monthly
        return _safe_float(_first_existing(row, "annual_cost", "annual_spend", "annual_service_cost", default=0)) / 12

    @staticmethod
    def _application_spend_lookup() -> dict[str, float]:
        spend: dict[str, float] = {}
        for row in BusinessServiceRepository.get_application_spend():
            application = BusinessServiceService._application_name(row)
            if application:
                spend[_lower(application)] = spend.get(_lower(application), 0.0) + BusinessServiceService._monthly_value(row)
        return spend

    @staticmethod
    def _technology_lookup() -> dict[str, dict[str, Any]]:
        return {
            _lower(BusinessServiceService._technology_name(row)): row
            for row in BusinessServiceRepository.get_technology_inventory()
            if BusinessServiceService._technology_name(row)
        }

    @staticmethod
    def _matching_rows(rows: list[dict[str, Any]], keys: list[Any]) -> list[dict[str, Any]]:
        terms = {_lower(key) for key in keys if _normalize(key)}
        matches = []
        for row in rows:
            text = _lower(" ".join(str(value or "") for value in row.values()))
            if any(term and term in text for term in terms):
                matches.append(row)
        return matches

    @staticmethod
    def _savings_value(row: dict[str, Any]) -> float:
        return _safe_float(
            _first_existing(
                row,
                "estimated_savings",
                "savings",
                "savings_monthly",
                "potential_savings",
                "optimization_potential",
                default=0,
            )
        )

    @staticmethod
    def _is_automation_candidate(row: dict[str, Any]) -> bool:
        if row.get("automation_eligible") is True:
            return True
        text = _lower(" ".join(str(value or "") for value in row.values()))
        return any(token in text for token in ("rightsize", "cleanup", "automate", "autoscaling", "optimiz"))

    @staticmethod
    def _is_cloud_resource(row: dict[str, Any], technology: str) -> bool:
        text = _lower(" ".join(str(value or "") for value in row.values()) + " " + technology)
        return any(token in text for token in ("aws", "azure", "gcp", "cloud", "ec2", "s3", "rds", "lambda"))

    @staticmethod
    def _governance_score(service: dict[str, Any]) -> float:
        dimensions = [
            bool(service.get("business_unit")),
            bool(service.get("business_capability")),
            bool(service.get("applications")),
            bool(service.get("technologies")),
            service.get("owner") not in {"", "Unassigned", "Unknown"},
            _safe_float(service.get("monthly_cost")) > 0,
        ]
        base = sum(1 for item in dimensions if item) / len(dimensions) * 100
        return round(max(base - _safe_int(service.get("active_incidents")) * 5, 0), 1)

    @staticmethod
    def _risk_score(service: dict[str, Any]) -> float:
        risk = 100 - _safe_float(service.get("governance_score"))
        if _safe_int(service.get("active_incidents")):
            risk += min(_safe_int(service.get("active_incidents")) * 12, 36)
        if _lower(service.get("tier")) in {"tier 1", "critical"}:
            risk += 5
        if _safe_float(service.get("monthly_cost")) >= 10000:
            risk += 5
        return round(min(max(risk, 0), 100), 1)

    @staticmethod
    def _health_score(service: dict[str, Any]) -> float:
        governance = _safe_float(service.get("governance_score"))
        risk = _safe_float(service.get("risk_score"))
        return round(max(min((governance * 0.7) + ((100 - risk) * 0.3), 100), 0), 1)

    @staticmethod
    def _average(values: list[float]) -> float:
        clean = [_safe_float(value) for value in values]
        return round(sum(clean) / len(clean), 1) if clean else 0.0

    @staticmethod
    def _unique(values: list[Any]) -> list[str]:
        seen = set()
        output = []
        for value in values:
            text = _normalize(value)
            key = _lower(text)
            if not text or key in seen:
                continue
            seen.add(key)
            output.append(text)
        return output

    @staticmethod
    def _dedupe_pairs(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
        seen = set()
        output = []
        for left, right in rows:
            key = (_lower(left), _lower(right))
            if not left or not right or key in seen:
                continue
            seen.add(key)
            output.append((left, right))
        return output

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
