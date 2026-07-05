from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from repositories.business_process_repository import BusinessProcessRepository
from services.business_service_service import BusinessServiceService


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


class BusinessProcessService:
    """E7.1.8 service foundation for enterprise business processes."""

    @staticmethod
    def get_business_processes() -> list[dict[str, Any]]:
        explicit_rows = BusinessProcessRepository.get_business_processes()
        services = BusinessServiceService.get_business_services()
        processes: dict[str, dict[str, Any]] = {}

        for row in explicit_rows:
            name = BusinessProcessService._process_name(row)
            if not name:
                continue
            service = BusinessProcessService._service_for_row(row, services)
            process = BusinessProcessService._base_process(row, name, service)
            processes[_lower(process["id"])] = process

        if not processes:
            for service in services:
                process = BusinessProcessService._derive_from_service(service)
                processes[_lower(process["id"])] = process

        if not processes:
            process = BusinessProcessService._empty_process("Core Business Process")
            process.update(
                {
                    "business_unit": "Retail",
                    "business_capability": "Checkout",
                    "business_service": "Checkout Service",
                    "owner": "Digital Operations",
                    "criticality": "Critical",
                    "applications": ["Checkout"],
                    "technologies": ["AWS"],
                    "monthly_cost": 10800.0,
                    "source": "fallback",
                }
            )
            processes[_lower(process["id"])] = process

        recommendations = BusinessProcessRepository.get_recommendations()
        output = []
        for process in processes.values():
            BusinessProcessService._apply_process_signals(process, recommendations)
            BusinessProcessService._finalize_process(process)
            output.append(process)

        return sorted(output, key=lambda row: (row["business_unit"], row["business_capability"], row["business_service"], row["name"]))

    @staticmethod
    def get_process_summary() -> dict[str, Any]:
        processes = BusinessProcessService.get_business_processes()
        monthly_cost = sum(_safe_float(row.get("monthly_cost")) for row in processes)
        return {
            "business_processes": len(processes),
            "business_services": len({row.get("business_service") for row in processes if row.get("business_service")}),
            "business_units": len({row.get("business_unit") for row in processes if row.get("business_unit")}),
            "business_capabilities": len({row.get("business_capability") for row in processes if row.get("business_capability")}),
            "applications": len({app for row in processes for app in row.get("applications", [])}),
            "technologies": len({tech for row in processes for tech in row.get("technologies", [])}),
            "cloud_resources": sum(_safe_int(row.get("cloud_resources")) for row in processes),
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(monthly_cost * 12, 2),
            "forecast_cost": round(sum(_safe_float(row.get("forecast_cost")) for row in processes), 2),
            "optimization_opportunity": round(sum(_safe_float(row.get("optimization_opportunity")) for row in processes), 2),
            "automation_opportunities": sum(_safe_int(row.get("automation_opportunities")) for row in processes),
            "recommendations": sum(_safe_int(row.get("recommendations")) for row in processes),
            "average_health": BusinessProcessService._average([row.get("health_score") for row in processes]),
            "average_risk": BusinessProcessService._average([row.get("risk_score") for row in processes]),
            "governance_score": BusinessProcessService._average([row.get("governance_score") for row in processes]),
            "summary_ok": True,
        }

    @staticmethod
    def get_process_dashboard() -> dict[str, Any]:
        processes = BusinessProcessService.get_business_processes()
        return {
            "summary": BusinessProcessService.get_process_summary(),
            "business_processes": processes,
            "dependencies": BusinessProcessService.get_process_dependencies(),
            "costs": BusinessProcessService.get_process_costs(),
            "health": BusinessProcessService.get_process_health(),
            "risks": BusinessProcessService.get_process_risks(),
            "recommendations": BusinessProcessService.get_process_recommendations(),
            "highest_cost": sorted(processes, key=lambda row: _safe_float(row.get("monthly_cost")), reverse=True),
            "highest_risk": sorted(processes, key=lambda row: _safe_float(row.get("risk_score")), reverse=True),
            "lowest_health": sorted(processes, key=lambda row: _safe_float(row.get("health_score"))),
        }

    @staticmethod
    def get_process_dependencies() -> list[dict[str, Any]]:
        rows = []
        for process in BusinessProcessService.get_business_processes():
            applications = process.get("applications") or ["Unmapped Application"]
            technologies = process.get("technologies") or ["Unmapped Technology"]
            for application in applications:
                for technology in technologies:
                    rows.append(
                        {
                            "Business Unit": process["business_unit"],
                            "Business Capability": process["business_capability"],
                            "Business Service": process["business_service"],
                            "Business Process": process["name"],
                            "Application": application,
                            "Technology": technology,
                            "Cloud Resource": process.get("cloud_resource") or "Mapped Resource",
                        }
                    )
        return rows

    @staticmethod
    def get_process_costs() -> list[dict[str, Any]]:
        return [
            {
                "Business Process": row["name"],
                "Business Service": row["business_service"],
                "Business Unit": row["business_unit"],
                "Monthly Spend": row["monthly_cost"],
                "Annual Spend": round(_safe_float(row.get("monthly_cost")) * 12, 2),
                "Forecast": row["forecast_cost"],
                "Optimization Opportunity": row["optimization_opportunity"],
            }
            for row in BusinessProcessService.get_business_processes()
        ]

    @staticmethod
    def get_process_health() -> list[dict[str, Any]]:
        return [
            {
                "Business Process": row["name"],
                "Business Service": row["business_service"],
                "SLA": row["sla"],
                "Health Score": row["health_score"],
                "Dependency Score": row["dependency_score"],
                "Compliance Status": row["compliance_status"],
                "Status": row["status"],
            }
            for row in BusinessProcessService.get_business_processes()
        ]

    @staticmethod
    def get_process_risks() -> list[dict[str, Any]]:
        return [
            {
                "Business Process": row["name"],
                "Business Service": row["business_service"],
                "Criticality": row["criticality"],
                "Risk Score": row["risk_score"],
                "Dependency Risk": "Elevated" if _safe_float(row.get("dependency_score")) < 70 else "Mapped",
                "Compliance Status": row["compliance_status"],
                "AI Recommendations": row["recommendations"],
            }
            for row in BusinessProcessService.get_business_processes()
        ]

    @staticmethod
    def get_process_recommendations() -> list[dict[str, Any]]:
        return [
            {
                "Business Process": row["name"],
                "Recommendation": (
                    "Prioritize automation and dependency review"
                    if _safe_int(row.get("automation_opportunities")) else "Monitor process posture"
                ),
                "Priority": "High" if _safe_float(row.get("risk_score")) >= 35 else "Normal",
                "Optimization Opportunity": row["optimization_opportunity"],
                "Automation Opportunities": row["automation_opportunities"],
            }
            for row in BusinessProcessService.get_business_processes()
        ]

    @staticmethod
    def processes_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessProcessService.get_business_processes())

    @staticmethod
    def _base_process(row: dict[str, Any], name: str, service: dict[str, Any] | None) -> dict[str, Any]:
        process = BusinessProcessService._empty_process(name)
        service = service or {}
        process.update(
            {
                "id": _normalize(_first_existing(row, "id", "process_id", "process_code", default=BusinessProcessService._process_id(name))),
                "business_unit": _normalize(_first_existing(row, "business_unit", "business_unit_name", default=service.get("business_unit")), "Unassigned"),
                "business_capability": _normalize(_first_existing(row, "business_capability", "capability", default=service.get("business_capability")), "Unmapped Capability"),
                "business_service": _normalize(_first_existing(row, "business_service", "service_name", "business_service_name", default=service.get("name")), "Unmapped Service"),
                "owner": _normalize(_first_existing(row, "owner", "process_owner", default=service.get("owner")), "Unassigned"),
                "criticality": _normalize(_first_existing(row, "criticality", "tier", default=service.get("tier")), "Medium"),
                "sla": _normalize(_first_existing(row, "sla", "process_sla", default=service.get("sla")), "99.5%"),
                "status": _normalize(_first_existing(row, "status", default="Active"), "Active"),
                "monthly_cost": _safe_float(_first_existing(row, "monthly_cost", "monthly_spend", "cost", default=service.get("monthly_cost"))),
                "applications": BusinessProcessService._list_from_row(row, "applications", "application", "application_name") or list(service.get("applications") or []),
                "technologies": BusinessProcessService._list_from_row(row, "technologies", "technology", "technology_name") or list(service.get("technologies") or []),
                "cloud_resources": _safe_int(_first_existing(row, "cloud_resources", "resource_count", default=service.get("cloud_resources"))),
                "source": "business_processes",
                "last_updated": _normalize(_first_existing(row, "updated_at", "last_updated", default=BusinessProcessService._now())),
            }
        )
        return process

    @staticmethod
    def _derive_from_service(service: dict[str, Any]) -> dict[str, Any]:
        service_name = _normalize(service.get("name"), "Business Service")
        process_name = BusinessProcessService._derive_process_name(service_name)
        process = BusinessProcessService._empty_process(process_name)
        process.update(
            {
                "business_unit": service.get("business_unit") or "Unassigned",
                "business_capability": service.get("business_capability") or "Unmapped Capability",
                "business_service": service_name,
                "owner": service.get("owner") or "Unassigned",
                "criticality": service.get("tier") or "Medium",
                "sla": service.get("sla") or "99.5%",
                "applications": list(service.get("applications") or []),
                "technologies": list(service.get("technologies") or []),
                "cloud_resources": _safe_int(service.get("cloud_resources")),
                "monthly_cost": _safe_float(service.get("monthly_cost")),
                "recommendations": _safe_int(service.get("recommendations")),
                "automation_opportunities": _safe_int(service.get("automation_candidates")),
                "source": "business_services",
                "last_updated": service.get("last_updated") or BusinessProcessService._now(),
            }
        )
        return process

    @staticmethod
    def _empty_process(name: str) -> dict[str, Any]:
        return {
            "id": BusinessProcessService._process_id(name),
            "name": name,
            "business_unit": "Unassigned",
            "business_capability": "Unmapped Capability",
            "business_service": "Unmapped Service",
            "owner": "Unassigned",
            "criticality": "Medium",
            "sla": "99.5%",
            "applications": [],
            "technologies": [],
            "cloud_resources": 0,
            "cloud_resource": "Mapped Resource",
            "monthly_cost": 0.0,
            "forecast_cost": 0.0,
            "optimization_opportunity": 0.0,
            "health_score": 0.0,
            "risk_score": 0.0,
            "governance_score": 0.0,
            "dependency_score": 0.0,
            "compliance_status": "Review Required",
            "recommendations": 0,
            "automation_opportunities": 0,
            "status": "Active",
            "source": "derived",
            "last_updated": BusinessProcessService._now(),
        }

    @staticmethod
    def _apply_process_signals(process: dict[str, Any], recommendations: list[dict[str, Any]]) -> None:
        keys = [
            process.get("name"),
            process.get("business_service"),
            process.get("business_capability"),
            process.get("business_unit"),
            *process.get("applications", []),
            *process.get("technologies", []),
        ]
        matches = [
            row for row in recommendations
            if any(_lower(key) and _lower(key) in _lower(row) for key in keys)
        ]
        if matches:
            process["recommendations"] = max(_safe_int(process.get("recommendations")), len(matches))
            process["automation_opportunities"] = max(
                _safe_int(process.get("automation_opportunities")),
                len([row for row in matches if "auto" in _lower(row) or "rightsiz" in _lower(row)]),
            )

    @staticmethod
    def _finalize_process(process: dict[str, Any]) -> None:
        process["applications"] = sorted(BusinessProcessService._unique(process.get("applications", [])))
        process["technologies"] = sorted(BusinessProcessService._unique(process.get("technologies", [])))
        process["monthly_cost"] = round(_safe_float(process.get("monthly_cost")), 2)
        process["forecast_cost"] = round(process["monthly_cost"] * 1.08, 2)
        process["optimization_opportunity"] = round(process["monthly_cost"] * 0.08, 2)
        if process["optimization_opportunity"] >= 500 and not _safe_int(process.get("automation_opportunities")):
            process["automation_opportunities"] = 1
        if process["optimization_opportunity"] and not _safe_int(process.get("recommendations")):
            process["recommendations"] = 1
        process["dependency_score"] = BusinessProcessService._dependency_score(process)
        process["governance_score"] = BusinessProcessService._governance_score(process)
        process["risk_score"] = BusinessProcessService._risk_score(process)
        process["health_score"] = BusinessProcessService._health_score(process)
        process["compliance_status"] = "Compliant" if process["governance_score"] >= 80 else "Review Required"

    @staticmethod
    def _service_for_row(row: dict[str, Any], services: list[dict[str, Any]]) -> dict[str, Any] | None:
        service_name = _lower(_first_existing(row, "business_service", "service_name", "business_service_name"))
        service_id = _lower(_first_existing(row, "business_service_id", "service_id"))
        for service in services:
            candidates = {_lower(service.get("id")), _lower(service.get("name")), _lower(service.get("service_code"))}
            if service_name in candidates or service_id in candidates:
                return service
        return services[0] if len(services) == 1 else None

    @staticmethod
    def _process_name(row: dict[str, Any]) -> str:
        return _normalize(_first_existing(row, "name", "process_name", "business_process", "business_process_name"))

    @staticmethod
    def _derive_process_name(service_name: str) -> str:
        base = service_name.replace(" Service", "").strip() or service_name
        if "process" in base.lower():
            return base
        return f"{base} Process"

    @staticmethod
    def _process_id(name: str) -> str:
        slug = "-".join(_lower(name).replace("&", "and").split())
        return f"bp-{slug or 'process'}"

    @staticmethod
    def _list_from_row(row: dict[str, Any], *keys: str) -> list[str]:
        for key in keys:
            value = row.get(key)
            if isinstance(value, list):
                return [_normalize(item) for item in value if _normalize(item)]
            if isinstance(value, str) and value.strip():
                return [_normalize(part) for part in value.split(",") if _normalize(part)]
        return []

    @staticmethod
    def _dependency_score(process: dict[str, Any]) -> float:
        score = 40.0
        if process.get("business_service") not in {"", "Unmapped Service"}:
            score += 20
        if process.get("applications"):
            score += 20
        if process.get("technologies"):
            score += 15
        if _safe_int(process.get("cloud_resources")):
            score += 5
        return round(min(score, 100), 1)

    @staticmethod
    def _governance_score(process: dict[str, Any]) -> float:
        score = 50.0
        if process.get("owner") not in {"", "Unassigned", "Unknown"}:
            score += 20
        if process.get("business_service") not in {"", "Unmapped Service"}:
            score += 15
        if process.get("sla"):
            score += 10
        if process.get("applications"):
            score += 5
        return round(min(score, 100), 1)

    @staticmethod
    def _risk_score(process: dict[str, Any]) -> float:
        risk = 10.0
        if not process.get("applications"):
            risk += 20
        if not process.get("technologies"):
            risk += 20
        if process.get("owner") in {"", "Unassigned", "Unknown"}:
            risk += 15
        if _safe_float(process.get("monthly_cost")) > 10000:
            risk += 5
        return round(min(risk, 100), 1)

    @staticmethod
    def _health_score(process: dict[str, Any]) -> float:
        health = (process["dependency_score"] * 0.35) + (process["governance_score"] * 0.35) + ((100 - process["risk_score"]) * 0.30)
        return round(max(min(health, 100), 0), 1)

    @staticmethod
    def _average(values: list[Any]) -> float:
        clean = [_safe_float(value) for value in values if value is not None]
        return round(sum(clean) / len(clean), 1) if clean else 0.0

    @staticmethod
    def _unique(values: list[Any]) -> list[str]:
        seen = []
        for value in values:
            item = _normalize(value)
            if item and _lower(item) not in {_lower(existing) for existing in seen}:
                seen.append(item)
        return seen

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
