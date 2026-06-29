from __future__ import annotations

from typing import Any

import pandas as pd

from repositories.business_service_graph_repository import BusinessServiceGraphRepository
from services.ai_governance_service import AIGovernanceService


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


def _first_existing(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


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


def _graph_ai_tool_name(row: dict[str, Any]) -> str:
    name = _normalize(
        _first_existing(
            row,
            "technology_name",
            "tool",
            "application_name",
            "name",
            default="Unknown AI Tool",
        )
    )
    if name.lower() in {"copilot", "microsoft copilot", "copilot enterprise"}:
        return "GitHub Copilot"
    return name


def _risk_from_score(score: float) -> str:
    if score >= 90:
        return "Healthy"
    if score >= 80:
        return "Low"
    if score >= 70:
        return "Medium"
    if score >= 60:
        return "High"
    return "Critical"


class BusinessServiceGraphService:
    @staticmethod
    def get_business_services() -> list[dict[str, Any]]:
        return BusinessServiceGraphRepository.get_business_services()

    @staticmethod
    def get_business_service_relationships() -> list[dict[str, Any]]:
        return BusinessServiceGraphRepository.get_business_service_relationships()

    @staticmethod
    def get_application_registry() -> list[dict[str, Any]]:
        return BusinessServiceGraphRepository.get_application_registry()

    @staticmethod
    def get_application_spend_mapping() -> list[dict[str, Any]]:
        return BusinessServiceGraphRepository.get_application_spend_mapping()

    @staticmethod
    def get_technology_inventory() -> list[dict[str, Any]]:
        return BusinessServiceGraphRepository.get_technology_inventory()

    @staticmethod
    def get_technology_relationships() -> list[dict[str, Any]]:
        return BusinessServiceGraphRepository.get_technology_relationships()

    @staticmethod
    def get_application_spend() -> list[dict[str, Any]]:
        return BusinessServiceGraphRepository.get_application_spend()

    @staticmethod
    def _service_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "service_name",
                "business_service_name",
                "name",
                "service",
                default="Unknown Service",
            )
        )

    @staticmethod
    def _application_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "application_name",
                "application",
                "app_name",
                "name",
                "registry_application",
                default="Unknown Application",
            )
        )

    @staticmethod
    def _technology_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "technology_name",
                "technology",
                "tool_name",
                "product",
                "vendor_name",
                "provider",
                "service_name",
                default="Unknown Technology",
            )
        )

    @staticmethod
    def _owner(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "service_owner",
                "application_owner",
                "owner",
                "business_owner",
                "technology_owner",
                default="Unassigned",
            )
        )

    @staticmethod
    def _annual_cost(row: dict[str, Any]) -> float:
        annual_cost = _safe_float(
            _first_existing(
                row,
                "annual_cost",
                "annual_spend",
                "annual_service_cost",
                "total_spend",
                "total_cost",
                "cost",
                "amount",
                default=0,
            )
        )
        if annual_cost:
            return annual_cost
        return _safe_float(_first_existing(row, "monthly_cost", "monthly_spend", default=0)) * 12

    @staticmethod
    def _service_lookup() -> dict[str, dict[str, Any]]:
        return {
            _lower(BusinessServiceGraphService._service_name(row)): row
            for row in BusinessServiceGraphService.get_business_services()
        }

    @staticmethod
    def _application_spend_lookup() -> dict[str, float]:
        spend: dict[str, float] = {}
        for row in BusinessServiceGraphService.get_application_spend():
            application = BusinessServiceGraphService._application_name(row)
            spend[_lower(application)] = spend.get(_lower(application), 0.0) + BusinessServiceGraphService._annual_cost(row)
        return spend

    @staticmethod
    def _technology_lookup() -> dict[str, dict[str, Any]]:
        return {
            _lower(BusinessServiceGraphService._technology_name(row)): row
            for row in BusinessServiceGraphService.get_technology_inventory()
        }

    @staticmethod
    def _primary_application_name(edges: list[dict[str, Any]]) -> str:
        application_names = [
            edge["target_name"]
            for edge in edges
            if _lower(edge.get("target_type")) == "application"
        ]
        if application_names:
            for application in application_names:
                if _lower(application) == "checkout":
                    return application
            return application_names[0]

        for row in BusinessServiceGraphService.get_application_registry():
            application = BusinessServiceGraphService._application_name(row)
            if application:
                return application

        return "Checkout"

    @staticmethod
    def _ai_graph_tools() -> list[str]:
        preferred_tools = {"chatgpt enterprise", "github copilot", "copilot", "copilot enterprise"}
        tools = [
            _graph_ai_tool_name(row)
            for row in AIGovernanceService.get_ai_tools()
            if _lower(_graph_ai_tool_name(row)) in preferred_tools
        ]
        if not tools:
            tools = ["ChatGPT Enterprise", "GitHub Copilot"]
        return sorted(set(tools), key=lambda item: ("copilot" in item.lower(), item))

    @staticmethod
    def get_graph_edges() -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []

        for row in BusinessServiceGraphService.get_business_service_relationships():
            source_name = _normalize(
                _first_existing(
                    row,
                    "source_name",
                    "source",
                    "parent_name",
                    "from_name",
                    "business_service_name",
                    "service_name",
                )
            )
            target_name = _normalize(
                _first_existing(
                    row,
                    "target_name",
                    "target",
                    "child_name",
                    "to_name",
                    "application_name",
                    "technology_name",
                    "dependent_name",
                )
            )
            if not source_name or not target_name:
                continue

            edges.append(
                {
                    "source_type": _normalize(_first_existing(row, "source_type", "from_type", default="Business Service")),
                    "source_name": source_name,
                    "relationship_type": _normalize(_first_existing(row, "relationship_type", "relationship", "type", default="depends_on")),
                    "target_type": _normalize(_first_existing(row, "target_type", "to_type", default="Application")),
                    "target_name": target_name,
                }
            )

        service_lookup = BusinessServiceGraphService._service_lookup()
        application_rows = BusinessServiceGraphService.get_application_registry()

        for row in application_rows:
            application = BusinessServiceGraphService._application_name(row)
            service = _normalize(
                _first_existing(
                    row,
                    "business_service_name",
                    "service_name",
                    "service",
                    default="",
                )
            )
            if not service and len(service_lookup) == 1:
                service = BusinessServiceGraphService._service_name(next(iter(service_lookup.values())))
            if service and application:
                edges.append(
                    {
                        "source_type": "Business Service",
                        "source_name": service,
                        "relationship_type": "supports",
                        "target_type": "Application",
                        "target_name": application,
                    }
                )

            technology = _normalize(_first_existing(row, "technology_name", "technology", "cloud", "platform", default=""))
            if application and technology:
                edges.append(
                    {
                        "source_type": "Application",
                        "source_name": application,
                        "relationship_type": "runs_on",
                        "target_type": "Technology",
                        "target_name": technology,
                    }
                )

        for row in BusinessServiceGraphService.get_application_spend_mapping():
            application = BusinessServiceGraphService._application_name(row)
            technology = BusinessServiceGraphService._technology_name(row)
            if application and technology:
                edges.append(
                    {
                        "source_type": "Application",
                        "source_name": application,
                        "relationship_type": _normalize(_first_existing(row, "relationship_type", "relationship", default="uses")),
                        "target_type": "Technology",
                        "target_name": technology,
                    }
                )

        for row in BusinessServiceGraphService.get_technology_relationships():
            source_type = _normalize(_first_existing(row, "source_type", default="Technology"))
            target_type = _normalize(_first_existing(row, "target_type", default="Technology"))
            source_name = _normalize(_first_existing(row, "source_name", "source", "from_name"))
            target_name = _normalize(_first_existing(row, "target_name", "target", "to_name"))
            if source_name and target_name:
                edges.append(
                    {
                        "source_type": source_type,
                        "source_name": source_name,
                        "relationship_type": _normalize(_first_existing(row, "relationship_type", "relationship", default="depends_on")),
                        "target_type": target_type,
                        "target_name": target_name,
                    }
                )

        application = BusinessServiceGraphService._primary_application_name(edges)
        for tool in BusinessServiceGraphService._ai_graph_tools():
            edges.append(
                {
                    "source_type": "Application",
                    "source_name": application,
                    "relationship_type": "uses_ai",
                    "target_type": "Technology",
                    "target_name": tool,
                }
            )

        return _dedupe(edges, ("source_type", "source_name", "relationship_type", "target_type", "target_name"))

    @staticmethod
    def get_application_technology_mapping() -> list[dict[str, Any]]:
        edges = BusinessServiceGraphService.get_graph_edges()
        service_by_application: dict[str, set[str]] = {}
        technologies_by_application: dict[str, set[str]] = {}

        for edge in edges:
            if _lower(edge.get("source_type")) == "business service" and _lower(edge.get("target_type")) == "application":
                service_by_application.setdefault(_lower(edge["target_name"]), set()).add(edge["source_name"])
            if _lower(edge.get("source_type")) == "application" and _lower(edge.get("target_type")) == "technology":
                technologies_by_application.setdefault(_lower(edge["source_name"]), set()).add(edge["target_name"])

        app_spend = BusinessServiceGraphService._application_spend_lookup()
        service_lookup = BusinessServiceGraphService._service_lookup()
        technology_lookup = BusinessServiceGraphService._technology_lookup()

        mappings: list[dict[str, Any]] = []
        for app_key, technologies in technologies_by_application.items():
            services = service_by_application.get(app_key) or {"Unmapped Service"}
            for service in sorted(services):
                service_row = service_lookup.get(_lower(service), {})
                for technology in sorted(technologies):
                    tech_row = technology_lookup.get(_lower(technology), {})
                    health_score = _safe_float(_first_existing(tech_row, "health_score", "health", default=85))
                    mappings.append(
                        {
                            "Business Service": service,
                            "Application": app_key.title(),
                            "Technology": technology,
                            "Annual Spend": app_spend.get(app_key, BusinessServiceGraphService._annual_cost(tech_row)),
                            "Owner": BusinessServiceGraphService._owner(service_row) if service_row else BusinessServiceGraphService._owner(tech_row),
                            "Risk": _normalize(_first_existing(tech_row, "risk", "risk_status", default=_risk_from_score(health_score))),
                        }
                    )

        return mappings

    @staticmethod
    def get_technology_risk_impact() -> list[dict[str, Any]]:
        mappings = BusinessServiceGraphService.get_application_technology_mapping()
        if not mappings:
            return []

        df = pd.DataFrame(mappings)
        summary = (
            df.groupby("Technology", as_index=False)
            .agg(
                Business_Services=("Business Service", "nunique"),
                Applications=("Application", "nunique"),
                Annual_Spend=("Annual Spend", "sum"),
                Owner=("Owner", "first"),
                Risk=("Risk", "first"),
            )
            .rename(
                columns={
                    "Business_Services": "Business Services",
                    "Annual_Spend": "Annual Spend",
                }
            )
        )
        summary["Impact"] = summary.apply(
            lambda row: (
                "High"
                if row["Business Services"] >= 2 or str(row["Risk"]) in {"Critical", "High"}
                else "Medium"
                if row["Applications"] >= 2 or row["Annual Spend"] >= 10000
                else "Low"
            ),
            axis=1,
        )
        return summary.sort_values(["Impact", "Annual Spend"], ascending=[True, False]).to_dict("records")

    @staticmethod
    def get_kpis() -> dict[str, Any]:
        services = BusinessServiceGraphService.get_business_services()
        edges = BusinessServiceGraphService.get_graph_edges()
        mappings = BusinessServiceGraphService.get_application_technology_mapping()
        impact = BusinessServiceGraphService.get_technology_risk_impact()

        service_count = len(services)
        application_count = len({row["Application"] for row in mappings})
        technology_count = len({row["Technology"] for row in mappings})
        total_spend = sum(row["Annual Spend"] for row in mappings)
        high_impact = len([row for row in impact if row["Impact"] == "High"])

        if not total_spend:
            total_spend = sum(BusinessServiceGraphService._annual_cost(row) for row in services)

        return {
            "business_services": service_count,
            "applications": application_count,
            "technologies": technology_count,
            "relationships": len(edges),
            "annual_spend": total_spend,
            "high_impact_technologies": high_impact,
        }

    @staticmethod
    def get_executive_narrative() -> str:
        kpis = BusinessServiceGraphService.get_kpis()
        impact = BusinessServiceGraphService.get_technology_risk_impact()
        mappings = BusinessServiceGraphService.get_application_technology_mapping()

        if not mappings:
            return "Business service graph intelligence is ready, but application-to-technology mappings are not available yet."

        top_technology = max(impact, key=lambda row: row["Annual Spend"]) if impact else None
        top_sentence = (
            f"{top_technology['Technology']} has the highest mapped business impact across "
            f"{top_technology['Applications']} application(s) and {top_technology['Business Services']} business service(s)."
            if top_technology
            else "No dominant technology dependency is currently identified."
        )

        return (
            f"The enterprise graph currently connects {kpis['business_services']} business service(s), "
            f"{kpis['applications']} application(s), and {kpis['technologies']} technology platform(s) through "
            f"{kpis['relationships']} relationship(s). {top_sentence} "
            f"Tracked annual service and application spend is approximately ${kpis['annual_spend']:,.0f}. "
            f"{kpis['high_impact_technologies']} technology platform(s) currently carry high business-service impact."
        )

    @staticmethod
    def graph_edges_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessServiceGraphService.get_graph_edges())

    @staticmethod
    def application_technology_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessServiceGraphService.get_application_technology_mapping())

    @staticmethod
    def technology_risk_impact_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessServiceGraphService.get_technology_risk_impact())
