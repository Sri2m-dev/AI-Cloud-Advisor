from __future__ import annotations

from typing import Any

import pandas as pd

from repositories.application_portfolio_repository import ApplicationPortfolioRepository


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


class ApplicationPortfolioService:
    @staticmethod
    def get_applications() -> list[dict[str, Any]]:
        return ApplicationPortfolioRepository.get_applications()

    @staticmethod
    def _is_active(row: dict[str, Any]) -> bool:
        value = row.get("active", True)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "active")

    @staticmethod
    def _active_applications() -> list[dict[str, Any]]:
        applications = ApplicationPortfolioService.get_applications()
        return [
            row for row in applications
            if ApplicationPortfolioService._is_active(row)
        ]

    @staticmethod
    def get_application_spend() -> list[dict[str, Any]]:
        return ApplicationPortfolioRepository.get_application_spend()

    @staticmethod
    def get_application_dependencies() -> list[dict[str, Any]]:
        return ApplicationPortfolioRepository.get_application_dependencies()

    @staticmethod
    def get_application_risks() -> list[dict[str, Any]]:
        return ApplicationPortfolioRepository.get_application_risks()

    @staticmethod
    def get_unallocated_spend() -> list[dict[str, Any]]:
        return ApplicationPortfolioRepository.get_unallocated_spend()

    @staticmethod
    def get_application_spend_mapping() -> list[dict[str, Any]]:
        return ApplicationPortfolioRepository.get_application_spend_mapping()

    @staticmethod
    def _app_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "app_name",
                "application_name",
                "application",
                "registry_app_name",
                "registry_app",
                "name",
                default="Unknown Application",
            )
        )

    @staticmethod
    def _spend_app_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "spend_application_name",
                "spend_application",
                "application_name",
                "application",
                "app_name",
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
                "name",
                default="Unknown Technology",
            )
        )

    @staticmethod
    def _spend_value(row: dict[str, Any]) -> float:
        return _safe_float(
            _first_existing(
                row,
                "total_spend",
                "annual_spend",
                "annual_cost",
                "cost",
                "amount",
                "spend",
                default=0,
            )
        )

    @staticmethod
    def _spend_type(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "spend_type",
                "cost_type",
                "category",
                "source_type",
                default="Unclassified",
            ),
            default="Unclassified",
        )

    @staticmethod
    def _dependency_type(name: str, row: dict[str, Any] | None = None) -> str:
        row = row or {}
        explicit = _normalize(
            _first_existing(
                row,
                "technology_type",
                "target_type",
                "relationship_type",
                "category",
                default="",
            )
        )
        if explicit and explicit.lower() not in {"depends_on", "uses", "supports"}:
            return explicit

        name_l = _lower(name)
        if name_l in {"aws", "azure", "gcp"}:
            return "Cloud"
        if "datadog" in name_l:
            return "Monitoring"
        if "managed" in name_l or "msp" in name_l:
            return "MSP"
        return "SaaS"

    @staticmethod
    def _application_lookup() -> dict[str, dict[str, Any]]:
        return {
            _lower(ApplicationPortfolioService._app_name(row)): row
            for row in ApplicationPortfolioService._active_applications()
        }

    @staticmethod
    def _spend_mapping() -> dict[str, str]:
        mapping: dict[str, str] = {}
        application_lookup = ApplicationPortfolioService._application_lookup()

        for row in ApplicationPortfolioService.get_application_spend_mapping():
            spend_app = _normalize(
                _first_existing(
                    row,
                    "spend_application_name",
                    "spend_application",
                    "source_name",
                    "application_name",
                    "application",
                )
            )
            registry_app = _normalize(
                _first_existing(
                    row,
                    "registry_app_name",
                    "registry_application",
                    "target_name",
                    "app_name",
                    "application",
                )
            )
            if not registry_app and len(application_lookup) == 1:
                registry_app = ApplicationPortfolioService._app_name(next(iter(application_lookup.values())))
            if spend_app and registry_app:
                mapping[_lower(spend_app)] = registry_app

        for row in ApplicationPortfolioService._active_applications():
            app_name = ApplicationPortfolioService._app_name(row)
            mapping.setdefault(_lower(app_name), app_name)

        return mapping

    @staticmethod
    def _spend_by_registered_application() -> dict[str, dict[str, float]]:
        mapping = ApplicationPortfolioService._spend_mapping()
        totals: dict[str, dict[str, float]] = {}

        for row in ApplicationPortfolioService.get_application_spend():
            spend_app = ApplicationPortfolioService._spend_app_name(row)
            registry_app = mapping.get(_lower(spend_app))
            if not registry_app:
                continue

            spend_type = ApplicationPortfolioService._spend_type(row)
            totals.setdefault(registry_app, {})
            totals[registry_app][spend_type] = totals[registry_app].get(spend_type, 0.0) + ApplicationPortfolioService._spend_value(row)

        return totals

    @staticmethod
    def _technology_cost_lookup() -> dict[str, float]:
        costs: dict[str, float] = {}
        for row in ApplicationPortfolioService.get_unallocated_spend():
            technology = ApplicationPortfolioService._technology_name(row)
            costs[_lower(technology)] = costs.get(_lower(technology), 0.0) + ApplicationPortfolioService._spend_value(row)
        return costs

    @staticmethod
    def _technology_display_lookup() -> dict[str, str]:
        return {
            _lower(ApplicationPortfolioService._technology_name(row)): ApplicationPortfolioService._technology_name(row)
            for row in ApplicationPortfolioService.get_unallocated_spend()
        }

    @staticmethod
    def get_application_summary() -> dict[str, Any]:
        applications = ApplicationPortfolioService.get_applications()
        active_apps = [
            row for row in applications
            if ApplicationPortfolioService._is_active(row)
        ]
        allocation = ApplicationPortfolioService.get_application_cost_allocation()
        dependencies = ApplicationPortfolioService.get_dependency_graph()
        unallocated = ApplicationPortfolioService.get_unallocated_spend_analysis()

        critical_count = len(
            [
                row for row in active_apps
                if _lower(row.get("criticality")) in {"critical", "tier 1", "tier1", "high"}
            ]
        )
        allocated_spend = sum(row["Total"] for row in allocation)
        unallocated_spend = sum(row["Amount"] for row in unallocated)

        return {
            "applications": len(active_apps),
            "critical_applications": critical_count,
            "allocated_spend": allocated_spend,
            "unallocated_spend": unallocated_spend,
            "technology_dependencies": len(
                {
                    row["Target"]
                    for row in dependencies
                    if row["Target Type"] == "Technology"
                }
            ),
        }

    @staticmethod
    def get_application_cost_allocation() -> list[dict[str, Any]]:
        spend_by_app = ApplicationPortfolioService._spend_by_registered_application()
        spend_types = {
            "Cloud": ("cloud",),
            "SaaS": ("saas", "software", "subscription"),
            "MSP": ("msp", "managed"),
            "License": ("license", "licence"),
        }

        rows: list[dict[str, Any]] = []
        for app in ApplicationPortfolioService._active_applications():
            app_name = ApplicationPortfolioService._app_name(app)
            spend = spend_by_app.get(app_name, {})
            row = {"App": app_name, "Cloud": 0.0, "SaaS": 0.0, "MSP": 0.0, "License": 0.0}

            for spend_type, amount in spend.items():
                lowered = _lower(spend_type)
                matched = False
                for column, aliases in spend_types.items():
                    if any(alias in lowered for alias in aliases):
                        row[column] += amount
                        matched = True
                        break
                if not matched:
                    row["License"] += amount

            row["Total"] = row["Cloud"] + row["SaaS"] + row["MSP"] + row["License"]
            rows.append(row)

        return sorted(rows, key=lambda row: row["Total"], reverse=True)

    @staticmethod
    def get_dependency_graph() -> list[dict[str, Any]]:
        app_lookup = ApplicationPortfolioService._application_lookup()
        technology_rows = {
            _lower(ApplicationPortfolioService._technology_name(row)): row
            for row in ApplicationPortfolioService.get_unallocated_spend()
        }
        edges: list[dict[str, Any]] = []

        for row in ApplicationPortfolioService.get_application_dependencies():
            source = _normalize(_first_existing(row, "source_name", "source", "from_name", "application_name", "application"))
            target = _normalize(_first_existing(row, "target_name", "target", "to_name", "technology_name", "dependent_name"))
            if not source or not target:
                continue

            source_type = "Application" if _lower(source) in app_lookup else _normalize(_first_existing(row, "source_type", "from_type", default="Business Service"))
            target_type = "Technology" if _lower(target) in technology_rows else _normalize(_first_existing(row, "target_type", "to_type", default="Technology"))

            if source_type == "Business Service" and target_type == "Application":
                continue

            edges.append(
                {
                    "Source": source,
                    "Source Type": source_type,
                    "Target": target,
                    "Target Type": target_type,
                    "Dependency Type": ApplicationPortfolioService._dependency_type(target, technology_rows.get(_lower(target))),
                }
            )

        return _dedupe(edges, ("Source", "Target", "Dependency Type"))

    @staticmethod
    def get_risk_summary() -> list[dict[str, Any]]:
        summary = ApplicationPortfolioService.get_application_summary()
        risks = []

        if summary["critical_applications"] == 1:
            risks.append({"Risk": "Single critical application", "Impact": "High"})
        elif summary["critical_applications"] > 1:
            risks.append({"Risk": "Multiple critical applications", "Impact": "High"})

        cloud_unallocated = any(
            _lower(row["Technology"]) in {"aws", "azure", "gcp"} and row["Amount"] > 0
            for row in ApplicationPortfolioService.get_unallocated_spend_analysis()
        )
        if cloud_unallocated:
            risks.append({"Risk": "Cloud spend not allocated", "Impact": "High"})

        if summary["technology_dependencies"] >= 3:
            risks.append({"Risk": "Dependency concentration", "Impact": "Medium"})

        return risks

    @staticmethod
    def get_unallocated_spend_analysis() -> list[dict[str, Any]]:
        dependencies = {
            _lower(row["Target"])
            for row in ApplicationPortfolioService.get_dependency_graph()
            if row["Target Type"] == "Technology"
        }
        costs = ApplicationPortfolioService._technology_cost_lookup()
        display = ApplicationPortfolioService._technology_display_lookup()

        rows = []
        for key, amount in costs.items():
            if key in dependencies and key not in {"aws", "azure", "gcp"}:
                continue
            rows.append(
                {
                    "Spend Source": display.get(key, key.title()),
                    "Technology": display.get(key, key.title()),
                    "Amount": amount,
                    "Status": "Unallocated",
                    "Reason": "No application mapping",
                }
            )
        return sorted(rows, key=lambda row: row["Amount"], reverse=True)

    @staticmethod
    def get_dependency_summary() -> list[dict[str, Any]]:
        dependencies = ApplicationPortfolioService.get_dependency_graph()
        summary = []
        seen = set()
        for row in dependencies:
            if row["Target Type"] != "Technology":
                continue
            key = _lower(row["Target"])
            if key in seen:
                continue
            seen.add(key)
            summary.append(
                {
                    "Dependency": row["Target"],
                    "Type": row["Dependency Type"],
                }
            )
        return summary

    @staticmethod
    def get_executive_narrative() -> str:
        applications = ApplicationPortfolioService._active_applications()
        summary = ApplicationPortfolioService.get_application_summary()
        dependencies = ApplicationPortfolioService.get_dependency_summary()
        allocated = summary["allocated_spend"]
        unallocated = summary["unallocated_spend"]
        coverage = allocated / (allocated + unallocated) * 100 if allocated + unallocated else 0

        if not applications:
            return "No registered applications are currently available for portfolio intelligence."

        top_app = ApplicationPortfolioService._app_name(applications[0])
        dependency_names = [row["Dependency"] for row in dependencies]
        dependency_text = ", ".join(dependency_names[:-1])
        if len(dependency_names) > 1:
            dependency_text = f"{dependency_text} and {dependency_names[-1]}" if dependency_text else dependency_names[-1]
        elif dependency_names:
            dependency_text = dependency_names[0]
        else:
            dependency_text = "no mapped technology dependencies"

        return (
            f"{top_app} is currently the only registered business application and represents 100% of the application portfolio. "
            f"The application depends on {dependency_text}. "
            f"Approximately ${allocated:,.0f} of spend is allocated while ${unallocated:,.0f} remains unmapped, "
            f"indicating a chargeback and governance opportunity. Allocation coverage is estimated at {coverage:.1f}%."
        )

    @staticmethod
    def application_portfolio_dataframe() -> pd.DataFrame:
        rows = []
        for row in ApplicationPortfolioService._active_applications():
            rows.append(
                {
                    "Application": ApplicationPortfolioService._app_name(row),
                    "Owner": _normalize(_first_existing(row, "owner_name", "owner", "application_owner", default="Unassigned")),
                    "Criticality": _normalize(_first_existing(row, "criticality", default="Standard")),
                    "Business Unit": _normalize(_first_existing(row, "business_unit", default="Unassigned")),
                    "Cost Center": _normalize(_first_existing(row, "cost_center", default="Unassigned")),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def cost_allocation_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationPortfolioService.get_application_cost_allocation())

    @staticmethod
    def dependency_graph_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationPortfolioService.get_dependency_graph())

    @staticmethod
    def dependency_summary_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationPortfolioService.get_dependency_summary())

    @staticmethod
    def risk_summary_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationPortfolioService.get_risk_summary())

    @staticmethod
    def unallocated_spend_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationPortfolioService.get_unallocated_spend_analysis())
