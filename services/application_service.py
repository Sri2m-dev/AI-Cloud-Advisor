from __future__ import annotations

from typing import Any

import pandas as pd

from repositories.application_repository import ApplicationRepository


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


def _text(value: Any, fallback: str = "Unknown") -> str:
    value = str(value or "").strip()
    return value if value else fallback


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _criticality_risk(value: Any) -> int:
    level = _lower(value)
    if level in {"critical", "tier 0", "tier 1", "high"}:
        return 18
    if level in {"medium", "tier 2"}:
        return 10
    if level in {"low", "tier 3"}:
        return 4
    return 6


def _health_risk(score: float) -> str:
    if score >= 90:
        return "Healthy"
    if score >= 80:
        return "Low"
    if score >= 70:
        return "Medium"
    if score >= 60:
        return "High"
    return "Critical"


class ApplicationService:

    @staticmethod
    def get_registry() -> list[dict[str, Any]]:
        return ApplicationRepository.get_application_registry()

    @staticmethod
    def get_spend_mapping() -> list[dict[str, Any]]:
        return ApplicationRepository.get_application_spend_mapping()

    @staticmethod
    def get_application_spend() -> list[dict[str, Any]]:
        return ApplicationRepository.get_application_spend()

    @staticmethod
    def get_application_master() -> list[dict[str, Any]]:
        return ApplicationRepository.get_application_master()

    @staticmethod
    def _spend_application(row: dict[str, Any]) -> str:
        return _text(row.get("spend_application") or row.get("application_name"))

    @staticmethod
    def _registry_app_label(row: dict[str, Any]) -> str:
        return _text(row.get("registry_app") or row.get("app_name"))

    @staticmethod
    def _business_unit(row: dict[str, Any]) -> str:
        return _text(row.get("business_unit"))

    @staticmethod
    def _department(row: dict[str, Any]) -> str:
        return _text(row.get("department"))

    @staticmethod
    def _team(row: dict[str, Any]) -> str:
        return _text(row.get("team_name"))

    @staticmethod
    def _owner(row: dict[str, Any]) -> str:
        return _text(row.get("owner_name"), fallback="Unassigned")

    @staticmethod
    def _criticality(row: dict[str, Any]) -> str:
        return _text(row.get("criticality"), fallback="Medium")

    @staticmethod
    def _cloud(row: dict[str, Any]) -> str:
        return _text(row.get("cloud_provider"))

    @staticmethod
    def _cost_center(row: dict[str, Any]) -> str:
        return _text(row.get("cost_center"))

    @staticmethod
    def _spend_value(row: dict[str, Any]) -> float:
        return _safe_float(
            _first_existing(
                row,
                "application_spend",
                "annual_spend",
                "total_spend",
                "spend",
                "allocated_cost",
                "allocated_spend",
                "cost",
                "amount",
                "monthly_cost",
                default=0,
            )
        )

    @staticmethod
    def _spend_type(row: dict[str, Any]) -> str:
        return _text(_first_existing(row, "spend_type", "cost_type", "category", "source_type", default="Unclassified"))

    @staticmethod
    def _spend_by_application() -> dict[str, float]:
        spend_rows = ApplicationService._enriched_spend_rows()
        mapping_rows = ApplicationService.get_spend_mapping()
        totals: dict[str, float] = {}

        for row in spend_rows or mapping_rows:
            application = ApplicationService._spend_application(row)
            totals[application] = totals.get(application, 0.0) + ApplicationService._spend_value(row)

        return totals

    @staticmethod
    def _master_lookup() -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for row in ApplicationService.get_application_master():
            normalized_key = _lower(row.get("spend_application"))
            if normalized_key:
                lookup[normalized_key] = row
        return lookup

    @staticmethod
    def _enriched_spend_rows() -> list[dict[str, Any]]:
        spend_rows = ApplicationService.get_application_spend()
        master_lookup = ApplicationService._master_lookup()
        enriched_rows = []

        for spend_row in spend_rows:
            application = ApplicationService._spend_application(spend_row)
            master = master_lookup.get(_lower(application), {})
            merged = {**spend_row, **master}
            merged["spend_application"] = application
            enriched_rows.append(merged)

        if enriched_rows:
            return enriched_rows

        return ApplicationService.get_application_master()

    @staticmethod
    def get_portfolio() -> list[dict[str, Any]]:
        rows = ApplicationService._enriched_spend_rows()
        spend_by_app = ApplicationService._spend_by_application()
        max_spend = max(spend_by_app.values() or [0])
        total_spend = sum(spend_by_app.values())
        grouped: dict[str, dict[str, Any]] = {}

        for row in rows:
            application = ApplicationService._spend_application(row)
            grouped.setdefault(
                application,
                {
                    "row": row,
                    "spend": 0.0,
                },
            )
            grouped[application]["spend"] += ApplicationService._spend_value(row)

        portfolio = []
        for application, grouped_row in grouped.items():
            row = grouped_row["row"]
            spend = spend_by_app.get(application, grouped_row["spend"])
            cost_risk = min((spend / max_spend) * 22, 22) if max_spend else 0
            concentration_risk = min((spend / total_spend) * 18, 18) if total_spend else 0
            criticality_risk = _criticality_risk(ApplicationService._criticality(row))
            health = max(round(100 - cost_risk - concentration_risk - criticality_risk, 1), 0)

            portfolio.append(
                {
                    "Application": application,
                    "Registry Application": ApplicationService._registry_app_label(row),
                    "Business Unit": ApplicationService._business_unit(row),
                    "Department": ApplicationService._department(row),
                    "Team": ApplicationService._team(row),
                    "Owner": ApplicationService._owner(row),
                    "Criticality": ApplicationService._criticality(row),
                    "Cloud": ApplicationService._cloud(row),
                    "Cost Center": ApplicationService._cost_center(row),
                    "Application Spend": spend,
                    "Health": health,
                    "Risk": _health_risk(health),
                }
            )

        return sorted(portfolio, key=lambda item: item["Application Spend"], reverse=True)

    @staticmethod
    def get_critical_applications() -> list[dict[str, Any]]:
        portfolio = ApplicationService.get_portfolio()
        if not portfolio:
            return []

        df = pd.DataFrame(portfolio)
        critical_df = df[
            df["Criticality"].astype(str).str.lower().isin(
                {"critical", "tier 0", "tier 1", "high"}
            )
        ].copy()

        if critical_df.empty:
            return []

        summary = (
            critical_df.groupby(["Registry Application", "Criticality"], as_index=False)
            .agg(
                Applications=("Application", "nunique"),
                Spend=("Application Spend", "sum"),
                Owner=("Owner", "first"),
                Business_Unit=("Business Unit", "first"),
                Department=("Department", "first"),
            )
            .rename(
                columns={
                    "Registry Application": "Application",
                    "Business_Unit": "Business Unit",
                }
            )
            .sort_values("Spend", ascending=False)
        )
        return summary.to_dict("records")

    @staticmethod
    def get_application_cost_breakdown() -> list[dict[str, Any]]:
        rows = ApplicationService._enriched_spend_rows()
        if not rows:
            rows = ApplicationService.get_spend_mapping()

        data = []
        for row in rows:
            data.append(
                {
                    "Application": ApplicationService._spend_application(row),
                    "Spend Type": ApplicationService._spend_type(row),
                    "Business Unit": ApplicationService._business_unit(row),
                    "Cost": ApplicationService._spend_value(row),
                    "Cloud": ApplicationService._cloud(row),
                    "Cost Center": ApplicationService._cost_center(row),
                }
            )
        return data

    @staticmethod
    def get_kpis() -> dict[str, Any]:
        portfolio = ApplicationService.get_portfolio()
        total_spend = sum(row["Application Spend"] for row in portfolio)
        owners = {
            row["Owner"]
            for row in portfolio
            if row["Owner"] not in {"Unknown", "Unassigned"}
        }

        return {
            "applications": len(portfolio),
            "critical_applications": len(ApplicationService.get_critical_applications()),
            "application_spend": total_spend,
            "business_units": len({row["Business Unit"] for row in portfolio if row["Business Unit"] != "Unknown"}),
            "departments": len({row["Department"] for row in portfolio if row["Department"] != "Unknown"}),
            "owners": len(owners),
            "owner_gaps": len([row for row in portfolio if row["Owner"] in {"Unknown", "Unassigned"}]),
        }

    @staticmethod
    def get_business_service_matrix() -> list[dict[str, Any]]:
        portfolio = ApplicationService.get_portfolio()
        rows = []
        for item in portfolio:
            for service_type, service_name in [
                ("Business Unit", item["Business Unit"]),
                ("Department", item["Department"]),
                ("Team", item["Team"]),
            ]:
                if service_name == "Unknown":
                    continue
                rows.append(
                    {
                        "Service Type": service_type,
                        "Service": service_name,
                        "Application": item["Application"],
                        "Owner": item["Owner"],
                        "Criticality": item["Criticality"],
                        "Cost": item["Application Spend"],
                        "Health": item["Health"],
                        "Risk": item["Risk"],
                    }
                )
        return rows

    @staticmethod
    def get_service_cost_view() -> list[dict[str, Any]]:
        matrix = ApplicationService.get_business_service_matrix()
        if not matrix:
            return []

        df = pd.DataFrame(matrix).drop_duplicates(
            subset=["Service Type", "Service", "Application"]
        )
        summary = (
            df.groupby(["Service Type", "Service"], as_index=False)
            .agg(
                Applications=("Application", "nunique"),
                Total_Spend=("Cost", "sum"),
                Average_Health=("Health", "mean"),
            )
            .rename(
                columns={
                    "Total_Spend": "Total Spend",
                    "Average_Health": "Average Health",
                }
            )
            .sort_values("Total Spend", ascending=False)
        )
        summary["Average Health"] = summary["Average Health"].round(1)
        return summary.to_dict("records")

    @staticmethod
    def get_owner_accountability() -> list[dict[str, Any]]:
        portfolio = ApplicationService.get_portfolio()
        if not portfolio:
            return []

        df = pd.DataFrame(portfolio)
        summary = (
            df.groupby("Owner", as_index=False)
            .agg(
                Apps=("Application", "nunique"),
                Spend=("Application Spend", "sum"),
            )
            .sort_values("Spend", ascending=False)
        )
        return summary.to_dict("records")

    @staticmethod
    def get_cost_center_view() -> list[dict[str, Any]]:
        portfolio = ApplicationService.get_portfolio()
        if not portfolio:
            return []

        df = pd.DataFrame(portfolio)
        summary = (
            df.groupby("Cost Center", as_index=False)
            .agg(
                Applications=("Application", "nunique"),
                Spend=("Application Spend", "sum"),
            )
            .sort_values("Spend", ascending=False)
        )
        return summary.to_dict("records")

    @staticmethod
    def get_service_risk_view() -> list[dict[str, Any]]:
        matrix = ApplicationService.get_business_service_matrix()
        if not matrix:
            return []

        df = pd.DataFrame(matrix).drop_duplicates(
            subset=["Service Type", "Service", "Application"]
        )
        df["Is Critical"] = df["Criticality"].astype(str).str.lower().isin(
            {"critical", "tier 0", "tier 1", "high"}
        )
        spend_threshold = df["Cost"].quantile(0.75) if not df.empty else 0
        df["Is High Spend"] = df["Cost"] >= spend_threshold
        df["Owner Gap"] = df["Owner"].isin(["Unknown", "Unassigned"])

        summary = (
            df.groupby(["Service Type", "Service"], as_index=False)
            .agg(
                Critical_Applications=("Is Critical", "sum"),
                High_Spend_Apps=("Is High Spend", "sum"),
                Owner_Gaps=("Owner Gap", "sum"),
            )
            .rename(
                columns={
                    "Critical_Applications": "Critical Applications",
                    "High_Spend_Apps": "High Spend Apps",
                    "Owner_Gaps": "Owner Gaps",
                }
            )
            .sort_values(["Critical Applications", "High Spend Apps", "Owner Gaps"], ascending=False)
        )
        return summary.to_dict("records")

    @staticmethod
    def portfolio_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationService.get_portfolio())

    @staticmethod
    def cost_breakdown_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationService.get_application_cost_breakdown())

    @staticmethod
    def critical_applications_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationService.get_critical_applications())

    @staticmethod
    def business_service_matrix_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationService.get_business_service_matrix())

    @staticmethod
    def service_cost_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationService.get_service_cost_view())

    @staticmethod
    def service_risk_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationService.get_service_risk_view())

    @staticmethod
    def owner_accountability_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationService.get_owner_accountability())

    @staticmethod
    def cost_center_dataframe() -> pd.DataFrame:
        return pd.DataFrame(ApplicationService.get_cost_center_view())
