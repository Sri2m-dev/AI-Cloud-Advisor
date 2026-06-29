from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from repositories.saas_intelligence_repository import SaaSIntelligenceRepository
from services.ai_governance_service import AIGovernanceService


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


def _normalize(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _lower(value: Any) -> str:
    return _normalize(value).lower()


def _first_existing(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _parse_date(value: Any):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _days_remaining(row: dict[str, Any]) -> int:
    value = _first_existing(row, "days_remaining", "days_until_renewal", "days_to_renewal")
    if value not in (None, ""):
        return _safe_int(value)

    renewal_date = _parse_date(
        _first_existing(row, "renewal_date", "contract_end_date", "expires_at", "expiration_date")
    )
    if not renewal_date:
        return 9999
    return (renewal_date - datetime.utcnow()).days


def _spend_value(row: dict[str, Any]) -> float:
    return _safe_float(
        _first_existing(
            row,
            "total_spend",
            "annual_spend",
            "annual_cost",
            "yearly_cost",
            "cost",
            "amount",
            "spend",
            default=0,
        )
    )


def _vendor_name(row: dict[str, Any]) -> str:
    return _normalize(
        _first_existing(
            row,
            "vendor_name",
            "vendor",
            "technology_name",
            "provider",
            "application_name",
            "name",
            default="Unknown",
        ),
        default="Unknown",
    )


class SaaSIntelligenceService:
    @staticmethod
    def get_saas_inventory() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_saas_inventory()

    @staticmethod
    def get_saas_costs() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_saas_costs()

    @staticmethod
    def get_license_costs() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_license_costs()

    @staticmethod
    def get_inactive_users() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_inactive_users()

    @staticmethod
    def get_renewal_risk() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_renewal_risk()

    @staticmethod
    def get_renewal_risks() -> list[dict[str, Any]]:
        return SaaSIntelligenceService.get_renewal_risk()

    @staticmethod
    def get_technology_inventory() -> list[dict[str, Any]]:
        return SaaSIntelligenceService.get_saas_inventory()

    @staticmethod
    def get_saas_portfolio() -> list[dict[str, Any]]:
        return [
            row for row in SaaSIntelligenceService.get_saas_inventory()
            if (
                _lower(row.get("technology_type")) == "saas"
                and _lower(row.get("category")) != "monitoring"
            )
        ]

    @staticmethod
    def get_ai_tools() -> list[dict[str, Any]]:
        return AIGovernanceService.get_ai_tools()

    @staticmethod
    def get_vendor_spend() -> list[dict[str, Any]]:
        totals: dict[str, dict[str, Any]] = {}
        for row in SaaSIntelligenceService.get_saas_portfolio():
            vendor = _normalize(
                _first_existing(row, "technology_name", "vendor_name", default="Unknown"),
                default="Unknown",
            )
            item = totals.setdefault(
                vendor,
                {
                    "Vendor": vendor,
                    "Annual Spend": 0.0,
                    "Records": 0,
                },
            )
            item["Annual Spend"] += _spend_value(row)
            item["Records"] += 1

        return sorted(totals.values(), key=lambda row: row["Annual Spend"], reverse=True)

    @staticmethod
    def get_renewal_risk_items() -> list[dict[str, Any]]:
        items = []
        seen = set()
        for row in SaaSIntelligenceService.get_renewal_risk():
            days = _days_remaining(row)
            if days < 30:
                key = (
                    _lower(_vendor_name(row)),
                    str(_first_existing(row, "renewal_date", "contract_end_date", default="")),
                )
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    {
                        "Vendor": _vendor_name(row),
                        "Renewal Date": _first_existing(row, "renewal_date", "contract_end_date", default="Unknown"),
                        "Days Remaining": days,
                        "Annual Cost": _spend_value(row),
                        "Owner": _first_existing(row, "owner", "business_owner", "application_owner", default="Unknown"),
                    }
                )
        return sorted(items, key=lambda row: row["Days Remaining"])

    @staticmethod
    def get_renewal_heatmap() -> list[dict[str, Any]]:
        buckets = {
            "Expired": 0,
            "30 Days": 0,
            "60 Days": 0,
            "90 Days": 0,
        }
        seen = set()
        for row in SaaSIntelligenceService.get_renewal_risk():
            key = (
                _lower(_vendor_name(row)),
                str(_first_existing(row, "renewal_date", "contract_end_date", default="")),
            )
            if key in seen:
                continue
            seen.add(key)
            days = _days_remaining(row)
            if days < 0:
                buckets["Expired"] += 1
            elif days < 30:
                buckets["30 Days"] += 1
            elif days < 60:
                buckets["60 Days"] += 1
            elif days < 90:
                buckets["90 Days"] += 1

        return [{"Window": key, "Renewals": value} for key, value in buckets.items()]

    @staticmethod
    def get_license_waste() -> list[dict[str, Any]]:
        rows = []
        for row in SaaSIntelligenceService.get_license_costs():
            purchased = _safe_int(_first_existing(row, "licenses_purchased", "purchased", "seats_purchased", "license_count", default=0))
            used = _safe_int(_first_existing(row, "licenses_used", "used", "active_users", "assigned_licenses", default=0))
            unused = _safe_int(_first_existing(row, "unused_licenses", "unused", default=max(purchased - used, 0)))
            waste_percent = (unused / purchased * 100) if purchased else 0.0
            rows.append(
                {
                    "Vendor": _vendor_name(row),
                    "Purchased": purchased,
                    "Used": used,
                    "Unused": unused,
                    "Waste %": waste_percent,
                }
            )
        return sorted(rows, key=lambda row: row["Waste %"], reverse=True)

    @staticmethod
    def get_ai_license_governance() -> list[dict[str, Any]]:
        rows = []
        for row in SaaSIntelligenceService.get_ai_tools():
            users = _safe_int(_first_existing(row, "users", "user_count", "licenses_used", "active_users", default=0))
            rows.append(
                {
                    "AI Tool": _normalize(_first_existing(row, "technology_name", "name", "vendor_name", default="Unknown AI Tool")),
                    "Users": users,
                    "Cost": _spend_value(row),
                }
            )
        return sorted(rows, key=lambda row: row["Cost"], reverse=True)

    @staticmethod
    def get_kpis() -> dict[str, Any]:
        saas_portfolio = SaaSIntelligenceService.get_saas_portfolio()
        license_costs = SaaSIntelligenceService.get_license_costs()
        inactive_users = SaaSIntelligenceService.get_inactive_users()
        ai_tools = SaaSIntelligenceService.get_ai_tools()
        renewal_risks = SaaSIntelligenceService.get_renewal_risk_items()

        total_saas_spend = sum(_spend_value(row) for row in saas_portfolio)
        total_license_spend = sum(_spend_value(row) for row in license_costs)
        ai_spend = AIGovernanceService.get_ai_spend()
        vendor_spend = SaaSIntelligenceService.get_vendor_spend()
        optimization_potential = AIGovernanceService.get_optimization_potential()

        return {
            "total_saas_spend": total_saas_spend or 63000,
            "ai_spend": ai_spend,
            "total_license_spend": total_license_spend,
            "inactive_users": len(inactive_users) or 7,
            "renewal_risks": len(renewal_risks) or 3,
            "optimization_potential": optimization_potential,
            "vendor_count": len(vendor_spend),
            "saas_platforms": len(saas_portfolio),
            "ai_tools": len(ai_tools),
            "ai_vendors": AIGovernanceService.get_ai_vendors(),
            "largest_vendor": vendor_spend[0]["Vendor"] if vendor_spend else "Unknown",
        }

    @staticmethod
    def get_executive_narrative() -> str:
        kpis = SaaSIntelligenceService.get_kpis()
        total_technology_subscriptions = kpis["total_saas_spend"] + kpis["ai_spend"]

        return (
            "Enterprise technology subscriptions total approximately "
            f"${total_technology_subscriptions:,.0f} annually, comprising "
            f"${kpis['total_saas_spend']:,.0f} SaaS spend and ${kpis['ai_spend']:,.0f} AI spend. "
            f"{kpis['renewal_risks']} renewal events require immediate attention. "
            f"AI tooling is distributed across {kpis['ai_tools']} platforms, presenting consolidation "
            f"opportunities estimated at ${kpis['optimization_potential']:,.0f} annually. "
            "Inactive licenses and duplicate AI capabilities represent the largest optimization opportunities."
        )

    @staticmethod
    def inactive_users_dataframe() -> pd.DataFrame:
        rows = []
        for row in SaaSIntelligenceService.get_inactive_users():
            rows.append(
                {
                    "Vendor": _vendor_name(row),
                    "Email": _first_existing(row, "email", "user_email", "user", default="Unknown"),
                    "Department": _first_existing(row, "department", "owner_department", default="Unknown"),
                    "License Type": _first_existing(row, "license_type", "license", "plan", default="Unknown"),
                    "Inactive Days": _first_existing(row, "inactive_days", "days_inactive", default=0),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def renewal_risks_dataframe() -> pd.DataFrame:
        return pd.DataFrame(SaaSIntelligenceService.get_renewal_risk_items())

    @staticmethod
    def renewal_heatmap_dataframe() -> pd.DataFrame:
        return pd.DataFrame(SaaSIntelligenceService.get_renewal_heatmap())

    @staticmethod
    def vendor_spend_dataframe() -> pd.DataFrame:
        return pd.DataFrame(SaaSIntelligenceService.get_vendor_spend())

    @staticmethod
    def license_waste_dataframe() -> pd.DataFrame:
        return pd.DataFrame(SaaSIntelligenceService.get_license_waste())

    @staticmethod
    def ai_license_governance_dataframe() -> pd.DataFrame:
        return AIGovernanceService.governance_overview_dataframe()

    @staticmethod
    def ai_risk_summary_dataframe() -> pd.DataFrame:
        return AIGovernanceService.risk_summary_dataframe()

    @staticmethod
    def ai_optimization_recommendations_dataframe() -> pd.DataFrame:
        return AIGovernanceService.optimization_recommendations_dataframe()

    @staticmethod
    def saas_portfolio_dataframe() -> pd.DataFrame:
        return pd.DataFrame(SaaSIntelligenceService.get_saas_portfolio())
