from __future__ import annotations

from typing import Any

import pandas as pd

from repositories.technology_graph_repository import TechnologyGraphRepository


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


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _normalize(value).lower()


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


class TechnologyGraphService:

    @staticmethod
    def get_inventory() -> list[dict[str, Any]]:
        return TechnologyGraphRepository.get_technology_inventory()

    @staticmethod
    def get_relationships() -> list[dict[str, Any]]:
        return TechnologyGraphRepository.get_technology_relationships()

    @staticmethod
    def get_vendor_spend() -> list[dict[str, Any]]:
        return TechnologyGraphRepository.get_vendor_spend()

    @staticmethod
    def get_renewal_risks() -> list[dict[str, Any]]:
        return TechnologyGraphRepository.get_renewal_risks()

    @staticmethod
    def get_inactive_users() -> list[dict[str, Any]]:
        return TechnologyGraphRepository.get_inactive_saas_users()

    @staticmethod
    def _technology_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "technology_name",
                "application",
                "app_name",
                "tool_name",
                "product",
                "software_name",
                "service",
                default="Unknown",
            )
        )

    @staticmethod
    def _vendor_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "vendor_name",
                "vendor",
                "provider",
                "supplier",
                default="Unknown",
            )
        )

    @staticmethod
    def _annual_cost(row: dict[str, Any]) -> float:
        return _safe_float(
            _first_existing(
                row,
                "annual_cost",
                "annual_spend",
                "total_spend",
                "cost",
                "amount",
                default=0,
            )
        )

    @staticmethod
    def _build_lookup_context() -> dict[str, Any]:
        inventory = TechnologyGraphService.get_inventory()
        relationships = TechnologyGraphService.get_relationships()
        renewals = TechnologyGraphService.get_renewal_risks()
        inactive_users = TechnologyGraphService.get_inactive_users()

        dependency_counts: dict[str, int] = {}
        departments_by_technology: dict[str, set[str]] = {}

        for row in relationships:
            source = _normalize(row.get("source_name"))
            target = _normalize(row.get("target_name"))
            target_type = _lower(row.get("target_type"))

            if source:
                dependency_counts[source] = dependency_counts.get(source, 0) + 1
            if target:
                dependency_counts[target] = dependency_counts.get(target, 0) + 1
            if source and target and target_type == "department":
                departments_by_technology.setdefault(source, set()).add(target)

        renewals_by_vendor: dict[str, list[dict[str, Any]]] = {}
        for row in renewals:
            vendor = TechnologyGraphService._vendor_name(row)
            renewals_by_vendor.setdefault(_lower(vendor), []).append(row)

        inactive_by_vendor: dict[str, int] = {}
        for row in inactive_users:
            vendor = TechnologyGraphService._vendor_name(row)
            inactive_by_vendor[_lower(vendor)] = inactive_by_vendor.get(_lower(vendor), 0) + 1

        total_cost = sum(TechnologyGraphService._annual_cost(row) for row in inventory)
        max_cost = max(
            [TechnologyGraphService._annual_cost(row) for row in inventory] or [0]
        )

        return {
            "inventory": inventory,
            "relationships": relationships,
            "dependency_counts": dependency_counts,
            "departments_by_technology": departments_by_technology,
            "renewals_by_vendor": renewals_by_vendor,
            "inactive_by_vendor": inactive_by_vendor,
            "total_cost": total_cost,
            "max_cost": max_cost,
        }

    @staticmethod
    def get_enriched_technologies() -> list[dict[str, Any]]:
        context = TechnologyGraphService._build_lookup_context()
        enriched = []

        for row in context["inventory"]:
            technology = TechnologyGraphService._technology_name(row)
            vendor = TechnologyGraphService._vendor_name(row)
            annual_cost = TechnologyGraphService._annual_cost(row)
            dependencies = context["dependency_counts"].get(technology, 0)
            renewals = len(context["renewals_by_vendor"].get(_lower(vendor), []))
            inactive_users = context["inactive_by_vendor"].get(_lower(vendor), 0)
            departments = sorted(context["departments_by_technology"].get(technology, set()))

            cost_ratio = annual_cost / context["max_cost"] if context["max_cost"] else 0
            cost_share = annual_cost / context["total_cost"] if context["total_cost"] else 0
            annual_cost_weight = min(cost_ratio * 80, 80)
            dependency_weight = min(dependencies * 7.5, 20)
            renewal_weight = min(renewals * 10, 20)
            inactive_license_weight = min(inactive_users * 2.5, 10)
            criticality = min(
                round(
                    annual_cost_weight
                    + dependency_weight
                    + renewal_weight
                    + inactive_license_weight,
                    1,
                ),
                100,
            )

            health_score = max(
                round(
                    100
                    - min(cost_share * 25, 18)
                    - min(dependencies * 4, 18)
                    - min(renewals * 5, 18)
                    - min(inactive_users * 2, 12),
                    1,
                ),
                0,
            )

            enriched.append(
                {
                    "Technology": technology,
                    "Vendor": vendor,
                    "Type": row.get("technology_type") or "Unknown",
                    "Annual Cost": annual_cost,
                    "Cost Share": cost_share,
                    "Dependencies": dependencies,
                    "Renewals": renewals,
                    "Inactive Users": inactive_users,
                    "License Waste": inactive_users * 1000,
                    "Department Exposure": len(departments),
                    "Departments": ", ".join(departments) if departments else "Unassigned",
                    "Health": health_score,
                    "Risk": _risk_from_score(health_score),
                    "Criticality": criticality,
                }
            )

        return sorted(enriched, key=lambda row: row["Criticality"], reverse=True)

    @staticmethod
    def get_criticality_ranking() -> list[dict[str, Any]]:
        return [
            {
                "Technology": row["Technology"],
                "Criticality": row["Criticality"],
                "Annual Cost": row["Annual Cost"],
                "Dependencies": row["Dependencies"],
                "Renewals": row["Renewals"],
                "Inactive Users": row["Inactive Users"],
                "Risk": row["Risk"],
            }
            for row in TechnologyGraphService.get_enriched_technologies()
        ]

    @staticmethod
    def get_department_impact() -> list[dict[str, Any]]:
        enriched_by_technology = {
            row["Technology"]: row
            for row in TechnologyGraphService.get_enriched_technologies()
        }
        relationships = TechnologyGraphService.get_relationships()
        department_rows = []

        for row in relationships:
            if _lower(row.get("target_type")) != "department":
                continue

            technology = _normalize(row.get("source_name"))
            department = _normalize(row.get("target_name")) or "Unknown"
            tech = enriched_by_technology.get(technology)
            if not tech:
                continue

            department_rows.append(
                {
                    "Department": department,
                    "Technology": technology,
                    "Annual Cost": tech["Annual Cost"],
                    "Health": tech["Health"],
                    "Risk": tech["Risk"],
                    "Criticality": tech["Criticality"],
                }
            )

        if not department_rows:
            return []

        df = pd.DataFrame(department_rows).drop_duplicates(
            subset=["Department", "Technology"]
        )
        summary = (
            df.groupby("Department", as_index=False)
            .agg(
                Technologies=("Technology", "nunique"),
                Annual_Cost=("Annual Cost", "sum"),
                Average_Health=("Health", "mean"),
                Max_Criticality=("Criticality", "max"),
            )
            .rename(
                columns={
                    "Annual_Cost": "Annual Cost",
                    "Average_Health": "Average Health",
                    "Max_Criticality": "Department Risk Score",
                }
            )
            .sort_values("Department Risk Score", ascending=False)
        )
        summary["Average Health"] = summary["Average Health"].round(1)
        summary["Department Risk Score"] = summary["Department Risk Score"].round(1)
        return summary.to_dict("records")

    @staticmethod
    def get_vendor_concentration() -> list[dict[str, Any]]:
        enriched = TechnologyGraphService.get_enriched_technologies()
        if not enriched:
            return []

        df = pd.DataFrame(enriched)
        total_spend = df["Annual Cost"].sum()
        if not total_spend:
            return []

        summary = (
            df.groupby("Vendor", as_index=False)
            .agg(
                Technologies=("Technology", "nunique"),
                Total_Spend=("Annual Cost", "sum"),
                Max_Criticality=("Criticality", "max"),
            )
            .rename(
                columns={
                    "Total_Spend": "Total Spend",
                    "Max_Criticality": "Max Criticality",
                }
            )
            .sort_values("Total Spend", ascending=False)
        )
        summary["Spend Share"] = (summary["Total Spend"] / total_spend * 100).round(1)
        summary["Concentration Risk"] = summary["Spend Share"].apply(
            lambda share: "High" if share >= 35 else "Medium" if share >= 20 else "Low"
        )
        return summary.to_dict("records")

    @staticmethod
    def get_health_heatmap() -> list[dict[str, Any]]:
        return [
            {
                "Technology": row["Technology"],
                "Cost": row["Annual Cost"],
                "Risk": row["Risk"],
                "Dependencies": row["Dependencies"],
                "Renewals": row["Renewals"],
                "Waste": row["License Waste"],
                "Health": row["Health"],
            }
            for row in TechnologyGraphService.get_enriched_technologies()
        ]

    @staticmethod
    def get_kpis() -> dict[str, Any]:
        enriched = TechnologyGraphService.get_enriched_technologies()
        vendor_concentration = TechnologyGraphService.get_vendor_concentration()
        total_spend = sum(row["Annual Cost"] for row in enriched)
        total_waste = len(TechnologyGraphService.get_inactive_users()) * 1000
        medium_or_higher = len(
            [
                row for row in enriched
                if row["Risk"] in {"Critical", "High", "Medium"}
            ]
        )
        top_spend_technology = max(
            enriched,
            key=lambda row: row["Annual Cost"],
        ) if enriched else None

        return {
            "technologies": len(enriched),
            "relationships": len(TechnologyGraphService.get_relationships()),
            "total_spend": total_spend,
            "total_waste": total_waste,
            "medium_or_higher": medium_or_higher,
            "top_vendor_share": vendor_concentration[0]["Spend Share"] if vendor_concentration else 0,
            "top_technology": top_spend_technology["Technology"] if top_spend_technology else "Unknown",
            "top_technology_share": round(top_spend_technology["Cost Share"] * 100, 1) if top_spend_technology else 0,
        }

    @staticmethod
    def get_executive_narrative() -> str:
        enriched = TechnologyGraphService.get_enriched_technologies()
        concentration = TechnologyGraphService.get_vendor_concentration()
        kpis = TechnologyGraphService.get_kpis()

        if not enriched:
            return "No technology graph intelligence is currently available."

        top_technology = max(
            enriched,
            key=lambda row: row["Annual Cost"],
        )
        top_vendor = concentration[0] if concentration else None
        top_two_share = (
            sum(row["Spend Share"] for row in concentration[:2])
            if concentration
            else 0
        )

        vendor_sentence = (
            f"{top_vendor['Vendor']} technologies account for {top_vendor['Spend Share']:.0f}% of total technology expenditure, "
            f"creating {top_vendor['Concentration Risk'].lower()} vendor concentration risk."
            if top_vendor
            else "Vendor concentration risk is not available yet."
        )

        return (
            f"{top_technology['Technology']} represents {top_technology['Cost Share'] * 100:.0f}% of enterprise technology spend "
            f"and remains the most business-critical platform. "
            f"{vendor_sentence} "
            f"{kpis['medium_or_higher']} technologies are classified as medium risk or higher due to renewal exposure, "
            f"license waste, spend concentration, or dependency concentration. "
            f"License optimization opportunities of approximately ${kpis['total_waste']:,.0f} annually remain available across inactive SaaS subscriptions. "
            f"The top two vendors represent {top_two_share:.0f}% of tracked technology spend."
        )

    @staticmethod
    def enriched_technologies_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyGraphService.get_enriched_technologies())

    @staticmethod
    def criticality_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyGraphService.get_criticality_ranking())

    @staticmethod
    def department_impact_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyGraphService.get_department_impact())

    @staticmethod
    def vendor_concentration_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyGraphService.get_vendor_concentration())

    @staticmethod
    def health_heatmap_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyGraphService.get_health_heatmap())
