from __future__ import annotations

from typing import Any

import pandas as pd

from repositories.technology_health_repository import TechnologyHealthRepository


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


class TechnologyHealthService:

    @staticmethod
    def get_inventory() -> list[dict[str, Any]]:
        return TechnologyHealthRepository.get_technology_inventory()

    @staticmethod
    def get_relationships() -> list[dict[str, Any]]:
        return TechnologyHealthRepository.get_technology_relationships()

    @staticmethod
    def get_vendor_spend() -> list[dict[str, Any]]:
        return TechnologyHealthRepository.get_vendor_spend()

    @staticmethod
    def get_renewal_risks() -> list[dict[str, Any]]:
        return TechnologyHealthRepository.get_renewal_risks()

    @staticmethod
    def get_inactive_users() -> list[dict[str, Any]]:
        return TechnologyHealthRepository.get_inactive_saas_users()

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
    def _renewal_days(row: dict[str, Any]) -> int:
        return _safe_int(
            _first_existing(
                row,
                "days_remaining",
                "days_until_renewal",
                "days_to_renewal",
                default=99999,
            )
        )

    @staticmethod
    def _renewal_cost(row: dict[str, Any]) -> float:
        return _safe_float(
            _first_existing(
                row,
                "annual_cost",
                "annual_spend",
                "contract_value",
                "yearly_cost",
                default=0,
            )
        )

    @staticmethod
    def get_health_matrix() -> list[dict[str, Any]]:
        inventory = TechnologyHealthService.get_inventory()
        relationships = TechnologyHealthService.get_relationships()
        renewals = TechnologyHealthService.get_renewal_risks()
        inactive_users = TechnologyHealthService.get_inactive_users()

        relationship_counts: dict[str, int] = {}
        for row in relationships:
            source = _normalize(row.get("source_name"))
            target = _normalize(row.get("target_name"))
            if source:
                relationship_counts[source] = relationship_counts.get(source, 0) + 1
            if target:
                relationship_counts[target] = relationship_counts.get(target, 0) + 1

        renewal_by_vendor: dict[str, list[dict[str, Any]]] = {}
        for row in renewals:
            vendor = TechnologyHealthService._vendor_name(row)
            renewal_by_vendor.setdefault(_lower(vendor), []).append(row)

        inactive_by_vendor: dict[str, int] = {}
        for row in inactive_users:
            vendor = TechnologyHealthService._vendor_name(row)
            inactive_by_vendor[_lower(vendor)] = inactive_by_vendor.get(_lower(vendor), 0) + 1

        matrix = []
        for row in inventory:
            technology_name = TechnologyHealthService._technology_name(row)
            vendor_name = TechnologyHealthService._vendor_name(row)
            annual_cost = _safe_float(row.get("annual_cost"))
            dependency_count = relationship_counts.get(technology_name, 0)
            vendor_renewals = renewal_by_vendor.get(_lower(vendor_name), [])
            renewal_count = len(vendor_renewals)
            inactive_count = inactive_by_vendor.get(_lower(vendor_name), 0)

            score = 100
            if annual_cost >= 50000:
                score -= 15
            elif annual_cost >= 10000:
                score -= 8
            if dependency_count >= 4:
                score -= 12
            elif dependency_count >= 2:
                score -= 6
            if renewal_count:
                score -= min(renewal_count * 8, 24)
            if inactive_count:
                score -= min(inactive_count * 2, 20)

            score = max(score, 0)
            if score >= 90:
                risk_bucket = "Healthy"
            elif score >= 80:
                risk_bucket = "Low"
            elif score >= 70:
                risk_bucket = "Medium"
            elif score >= 60:
                risk_bucket = "High"
            else:
                risk_bucket = "Critical"

            matrix.append(
                {
                    "Technology": technology_name,
                    "Type": row.get("technology_type") or "Unknown",
                    "Vendor": vendor_name,
                    "Department": row.get("owner_department") or row.get("business_owner") or "Unknown",
                    "Annual Cost": annual_cost,
                    "Dependencies": dependency_count,
                    "Renewal Risks": renewal_count,
                    "Inactive Users": inactive_count,
                    "Health Score": score,
                    "Risk": risk_bucket,
                    "Status": row.get("status") or "Unknown",
                }
            )

        return sorted(matrix, key=lambda item: item["Health Score"])

    @staticmethod
    def get_risk_distribution() -> list[dict[str, Any]]:
        matrix = TechnologyHealthService.get_health_matrix()
        counts: dict[str, int] = {}
        for row in matrix:
            risk = row["Risk"]
            counts[risk] = counts.get(risk, 0) + 1

        order = ["Critical", "High", "Medium", "Low", "Healthy"]
        return [
            {
                "risk": risk,
                "count": counts.get(risk, 0),
            }
            for risk in order
            if counts.get(risk, 0)
        ]

    @staticmethod
    def get_renewal_exposure() -> list[dict[str, Any]]:
        rows = []
        for row in TechnologyHealthService.get_renewal_risks():
            rows.append(
                {
                    "Vendor": TechnologyHealthService._vendor_name(row),
                    "Technology": TechnologyHealthService._technology_name(row),
                    "Renewal Date": _first_existing(row, "renewal_date", "contract_end_date", default="Unknown"),
                    "Days Remaining": TechnologyHealthService._renewal_days(row),
                    "Annual Cost": TechnologyHealthService._renewal_cost(row),
                    "Owner": _first_existing(row, "owner", "business_owner", "application_owner", default="Unknown"),
                }
            )

        return sorted(rows, key=lambda item: item["Days Remaining"])

    @staticmethod
    def get_license_waste_exposure() -> list[dict[str, Any]]:
        rows = []
        for row in TechnologyHealthService.get_inactive_users():
            rows.append(
                {
                    "Vendor": TechnologyHealthService._vendor_name(row),
                    "Email": _first_existing(row, "email", "user_email", "user", default="Unknown"),
                    "Department": _first_existing(row, "department", "owner_department", default="Unknown"),
                    "License Type": _first_existing(row, "license_type", "license", "plan", default="Unknown"),
                    "Inactive Days": _first_existing(row, "inactive_days", "days_inactive", default=0),
                    "Estimated Waste": 1000,
                }
            )

        return rows

    @staticmethod
    def get_dependency_edges() -> list[dict[str, Any]]:
        rows = []
        for row in TechnologyHealthService.get_relationships():
            rows.append(
                {
                    "Source": row.get("source_name") or "Unknown",
                    "Source Type": row.get("source_type") or "Unknown",
                    "Relationship": row.get("relationship_type") or "Unknown",
                    "Target": row.get("target_name") or "Unknown",
                    "Target Type": row.get("target_type") or "Unknown",
                }
            )
        return rows

    @staticmethod
    def get_kpis() -> dict[str, Any]:
        matrix = TechnologyHealthService.get_health_matrix()
        renewal_exposure = TechnologyHealthService.get_renewal_exposure()
        license_waste = TechnologyHealthService.get_license_waste_exposure()
        vendor_spend = TechnologyHealthService.get_vendor_spend()

        total_technologies = len(matrix)
        average_health = (
            round(sum(row["Health Score"] for row in matrix) / total_technologies, 1)
            if total_technologies
            else 0
        )
        critical_technologies = len([row for row in matrix if row["Risk"] == "Critical"])
        high_risk_technologies = len([row for row in matrix if row["Risk"] == "High"])
        medium_risk_technologies = len([row for row in matrix if row["Risk"] == "Medium"])
        renewal_cost = sum(_safe_float(row.get("Annual Cost")) for row in renewal_exposure)
        license_waste_value = sum(_safe_float(row.get("Estimated Waste")) for row in license_waste)
        vendor_count = len(
            {
                TechnologyHealthService._vendor_name(row)
                for row in TechnologyHealthService.get_inventory()
                if TechnologyHealthService._vendor_name(row) != "Unknown"
            }
        )

        if vendor_spend:
            vendor_count = max(
                vendor_count,
                len(
                    {
                        TechnologyHealthService._vendor_name(row)
                        for row in vendor_spend
                        if TechnologyHealthService._vendor_name(row) != "Unknown"
                    }
                ),
            )

        return {
            "total_technologies": total_technologies,
            "average_health": average_health,
            "critical_technologies": critical_technologies,
            "high_risk_technologies": high_risk_technologies,
            "medium_risk_technologies": medium_risk_technologies,
            "renewal_exposure": renewal_cost,
            "license_waste_exposure": license_waste_value,
            "vendor_count": vendor_count,
            "dependency_edges": len(TechnologyHealthService.get_dependency_edges()),
        }

    @staticmethod
    def health_matrix_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyHealthService.get_health_matrix())

    @staticmethod
    def risk_distribution_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyHealthService.get_risk_distribution())

    @staticmethod
    def renewal_exposure_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyHealthService.get_renewal_exposure())

    @staticmethod
    def license_waste_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyHealthService.get_license_waste_exposure())

    @staticmethod
    def dependency_edges_dataframe() -> pd.DataFrame:
        return pd.DataFrame(TechnologyHealthService.get_dependency_edges())
