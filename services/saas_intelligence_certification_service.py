from __future__ import annotations

from typing import Any

import streamlit as st

import pandas as pd

from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.enterprise_financial_model import EnterpriseFinancialModel
from services.saas_intelligence_service import SaaSIntelligenceService


def _safe_call(fn, fallback):
    try:
        return fn() or fallback
    except Exception:
        return fallback


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value if value is not None else fallback))
    except (TypeError, ValueError):
        return fallback


def _money(value: Any) -> str:
    amount = _safe_float(value)
    if abs(amount) >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M".replace(".0M", "M")
    if abs(amount) >= 1_000:
        value = amount / 1_000
        return f"${value:,.0f}K" if float(value).is_integer() else f"${value:,.1f}K"
    return f"${amount:,.0f}"


class SaaSIntelligenceCertificationService:
    """Certification service for the SaaS Intelligence page."""

    @staticmethod
    def format_money(value: Any) -> str:
        return _money(value)

    @staticmethod
    def escape_markdown_currency(text: str) -> str:
        return str(text or "").replace("$", r"\$")

    @staticmethod
    def format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        formatted = df.copy()
        for column in columns:
            if column in formatted.columns:
                formatted[column] = formatted[column].apply(_money)
        return formatted

    @staticmethod
    def format_percent_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        formatted = df.copy()
        for column in columns:
            if column in formatted.columns:
                formatted[column] = formatted[column].apply(lambda value: f"{_safe_float(value):.1f}%")
        return formatted

    @staticmethod
    def status_for_count(value: int) -> str:
        return "critical" if value else "healthy"

    @staticmethod
    def status_for_value(value: float) -> str:
        return "warning" if value else "healthy"

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_dashboard() -> dict[str, Any]:
        kpis = SaaSIntelligenceService.get_kpis()
        dataframes = {
            "vendor_spend": SaaSIntelligenceService.vendor_spend_dataframe(),
            "renewal_heatmap": SaaSIntelligenceService.renewal_heatmap_dataframe(),
            "renewal_risks": SaaSIntelligenceService.renewal_risks_dataframe(),
            "license_waste": SaaSIntelligenceService.license_waste_dataframe(),
            "ai_governance": SaaSIntelligenceService.ai_license_governance_dataframe(),
            "ai_risk": SaaSIntelligenceService.ai_risk_summary_dataframe(),
            "ai_recommendations": SaaSIntelligenceService.ai_optimization_recommendations_dataframe(),
            "inactive_users": SaaSIntelligenceService.inactive_users_dataframe(),
            "saas_portfolio": SaaSIntelligenceService.saas_portfolio_dataframe(),
        }
        metrics = SaaSIntelligenceCertificationService._metrics(kpis, dataframes)
        financial_model = EnterpriseFinancialModel.get_enterprise_summary()
        reconciliation = EnterpriseFinancialModel.get_reconciliation_status()
        business_context = SaaSIntelligenceCertificationService._business_context(metrics)

        return {
            "kpis": kpis,
            "metrics": metrics,
            "dataframes": dataframes,
            "financial_model": financial_model,
            "reconciliation": reconciliation,
            "reconciliation_cards": {
                "status": reconciliation.get("status") or "Unknown",
                "allocation_coverage": _safe_float(reconciliation.get("allocation_coverage")),
                "allocation_coverage_display": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                "variance": _safe_float(reconciliation.get("variance")),
                "variance_display": _money(reconciliation.get("variance")),
                "allocated_spend": _safe_float(financial_model.get("allocated_spend")),
                "allocated_spend_display": _money(financial_model.get("allocated_spend")),
                "unallocated_spend": _safe_float(financial_model.get("unallocated_spend")),
                "unallocated_spend_display": _money(financial_model.get("unallocated_spend")),
                "variance_status": reconciliation.get("status") or "Unknown",
            },
            "business_context": business_context,
            "executive_summary": SaaSIntelligenceCertificationService._executive_summary(
                metrics,
                financial_model,
                reconciliation,
                business_context,
            ),
            "evidence": SaaSIntelligenceCertificationService._evidence(
                metrics,
                financial_model,
                reconciliation,
                business_context,
                dataframes,
            ),
        }

    @staticmethod
    def _metrics(kpis: dict[str, Any], dataframes: dict[str, pd.DataFrame]) -> dict[str, Any]:
        license_waste_df = dataframes["license_waste"]
        ai_recommendations_df = dataframes["ai_recommendations"]
        vendor_spend_df = dataframes["vendor_spend"]

        total_saas_spend = _safe_float(kpis.get("total_saas_spend"))
        ai_spend = _safe_float(kpis.get("ai_spend"))
        total_subscription_spend = total_saas_spend + ai_spend
        ai_vendors = kpis.get("ai_vendors", [])
        ai_vendor_count = len(ai_vendors) if isinstance(ai_vendors, list) else _safe_int(ai_vendors)
        license_count = (
            _safe_int(license_waste_df["Purchased"].sum())
            if not license_waste_df.empty and "Purchased" in license_waste_df.columns
            else _safe_int(kpis.get("saas_platforms"))
        )
        inactive_users = _safe_int(kpis.get("inactive_users"))
        license_waste = (
            _safe_int(license_waste_df["Unused"].sum())
            if not license_waste_df.empty and "Unused" in license_waste_df.columns
            else inactive_users
        )
        duplicate_tools = len(ai_recommendations_df)
        vendor_count = _safe_int(kpis.get("vendor_count"))
        vendor_health = 100 if vendor_count and not vendor_spend_df.empty else 0
        if duplicate_tools or license_waste or inactive_users:
            vendor_health = max(vendor_health - min((duplicate_tools + license_waste + inactive_users) * 3, 35), 50)

        return {
            "total_saas_spend": total_saas_spend,
            "ai_spend": ai_spend,
            "total_license_spend": _safe_float(kpis.get("total_license_spend")),
            "total_subscription_spend": total_subscription_spend,
            "vendor_count": vendor_count,
            "largest_vendor": kpis.get("largest_vendor") or "Unknown",
            "ai_vendor_count": ai_vendor_count,
            "license_count": license_count,
            "inactive_users": inactive_users,
            "license_waste": license_waste,
            "renewals_due": _safe_int(kpis.get("renewal_risks")),
            "duplicate_tools": duplicate_tools,
            "potential_savings": _safe_float(kpis.get("optimization_potential")),
            "saas_platforms": _safe_int(kpis.get("saas_platforms")),
            "ai_tools": _safe_int(kpis.get("ai_tools")),
            "vendor_portfolio_health": round(vendor_health, 1),
            "vendor_rows": len(vendor_spend_df),
            "renewal_rows": len(dataframes["renewal_risks"]),
            "license_waste_rows": len(license_waste_df),
            "inactive_user_rows": len(dataframes["inactive_users"]),
            "ai_governance_rows": len(dataframes["ai_governance"]),
            "ai_recommendation_rows": len(ai_recommendations_df),
        }

    @staticmethod
    def _business_context(metrics: dict[str, Any]) -> dict[str, Any]:
        unit_summary = _safe_call(BusinessUnitService.get_summary, {})
        capability_summary = _safe_call(BusinessCapabilityService.get_capability_summary, {})
        service_summary = _safe_call(BusinessServiceService.get_service_summary, {})
        process_summary = _safe_call(BusinessProcessService.get_process_summary, {})

        return {
            "business_units": _safe_int(unit_summary.get("business_units") or unit_summary.get("total_business_units")),
            "capabilities": _safe_int(capability_summary.get("capabilities") or capability_summary.get("total_capabilities")),
            "business_services": _safe_int(service_summary.get("business_services") or service_summary.get("total_services")),
            "business_processes": _safe_int(process_summary.get("business_processes") or process_summary.get("total_processes")),
            "applications": _safe_int(service_summary.get("applications")),
            "saas_ai_platforms": _safe_int(metrics.get("saas_platforms")) + _safe_int(metrics.get("ai_tools")),
            "mapping_coverage": _safe_float(
                service_summary.get("mapping_coverage")
                or capability_summary.get("mapping_coverage")
                or unit_summary.get("mapping_coverage")
            ),
        }

    @staticmethod
    def executive_narrative(metrics: dict[str, Any]) -> str:
        sentences = [
            (
                "Enterprise technology subscriptions total approximately "
                f"{_money(metrics.get('total_subscription_spend'))} annually, including "
                f"{_money(metrics.get('total_saas_spend'))} in SaaS spend and {_money(metrics.get('ai_spend'))} in AI spend."
            ),
            f"{_safe_int(metrics.get('renewals_due'))} renewal events require immediate CIO review.",
            (
                f"AI tooling spans {_safe_int(metrics.get('ai_tools'))} platforms across {_safe_int(metrics.get('ai_vendor_count'))} vendors, "
                f"with {_money(metrics.get('potential_savings'))} in estimated annual optimization potential."
            ),
            (
                f"{_safe_int(metrics.get('inactive_users'))} inactive users and {_safe_int(metrics.get('license_waste'))} unused licenses should be reviewed "
                "for subscription cleanup."
            ),
            "Duplicate SaaS and AI capabilities remain the largest near-term consolidation opportunity.",
        ]
        return " ".join(sentences)

    @staticmethod
    def _executive_summary(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
    ) -> str:
        sentences = [
            SaaSIntelligenceCertificationService.executive_narrative(metrics),
            f"Vendor portfolio health is {_safe_float(metrics.get('vendor_portfolio_health')):.1f}% across {_safe_int(metrics.get('vendor_count'))} vendors.",
            f"Business architecture context includes {_safe_int(business_context.get('business_units'))} business units, {_safe_int(business_context.get('capabilities'))} capabilities, {_safe_int(business_context.get('business_services'))} services, and {_safe_int(business_context.get('applications'))} applications.",
            f"Data reconciliation status is {reconciliation.get('status') or 'Unknown'} with {_safe_float(reconciliation.get('allocation_coverage')):.1f}% allocation coverage and {_money(financial_model.get('unallocated_spend'))} unallocated spend.",
        ]
        return SaaSIntelligenceCertificationService.escape_markdown_currency(" ".join(sentences))

    @staticmethod
    def _evidence(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
        dataframes: dict[str, pd.DataFrame],
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {"Section": "SaaS Portfolio", "Source": "SaaSIntelligenceService / SaaSIntelligenceRepository", "Mode": "Service"},
                {"Section": "License Waste", "Source": "SaaSIntelligenceService.get_license_waste", "Mode": "Service"},
                {"Section": "Renewal Risk", "Source": "SaaSIntelligenceService.get_renewal_risk", "Mode": "Service"},
                {"Section": "AI Governance", "Source": "AIGovernanceService through SaaSIntelligenceService", "Mode": "Service"},
                {"Section": "Business Architecture", "Source": "BusinessUnit/Capability/Service/Process services", "Mode": "Service"},
                {"Section": "Financial Model", "Source": "EnterpriseFinancialModel", "Mode": "Canonical"},
            ],
            "data_coverage": [
                {"Coverage Area": "SaaS Platforms", "Value": f"{_safe_int(metrics.get('saas_platforms')):,}", "Status": "Tracked"},
                {"Coverage Area": "AI Tools", "Value": f"{_safe_int(metrics.get('ai_tools')):,}", "Status": "Tracked"},
                {"Coverage Area": "Vendor Rows", "Value": f"{_safe_int(metrics.get('vendor_rows')):,}", "Status": "Tracked"},
                {"Coverage Area": "Renewal Rows", "Value": f"{_safe_int(metrics.get('renewal_rows')):,}", "Status": "Tracked"},
                {"Coverage Area": "License Waste Rows", "Value": f"{_safe_int(metrics.get('license_waste_rows')):,}", "Status": "Tracked"},
                {"Coverage Area": "Financial Reconciliation", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%", "Status": reconciliation.get("status") or "Unknown"},
            ],
            "relationship_summary": [
                {"Layer": "Business Units", "Count": _safe_int(business_context.get("business_units"))},
                {"Layer": "Capabilities", "Count": _safe_int(business_context.get("capabilities"))},
                {"Layer": "Business Services", "Count": _safe_int(business_context.get("business_services"))},
                {"Layer": "Applications", "Count": _safe_int(business_context.get("applications"))},
                {"Layer": "SaaS Platforms", "Count": _safe_int(metrics.get("saas_platforms"))},
                {"Layer": "AI Platforms", "Count": _safe_int(metrics.get("ai_tools"))},
            ],
            "financial_reconciliation": [
                {"Metric": "Data Reconciliation Status", "Value": reconciliation.get("status") or "Unknown"},
                {"Metric": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%"},
                {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                {"Metric": "SaaS Spend", "Value": _money(metrics.get("total_saas_spend"))},
                {"Metric": "AI Spend", "Value": _money(metrics.get("ai_spend"))},
            ],
            "ai_interpretation": (
                "SaaS Intelligence is certification-ready because it exposes SaaS spend, AI spend, renewal risk, "
                "license waste, duplicate tooling, vendor concentration, and optimization recommendations. "
                "The next maturity step is explicit business capability and application ownership for every SaaS and AI platform."
            ),
            "raw_evidence": {
                "SaaS Portfolio": [
                    {"Metric": "Vendor Rows", "Value": len(dataframes.get("vendor_spend", pd.DataFrame()))},
                    {"Metric": "Renewal Risk Rows", "Value": len(dataframes.get("renewal_risks", pd.DataFrame()))},
                    {"Metric": "License Waste Rows", "Value": len(dataframes.get("license_waste", pd.DataFrame()))},
                    {"Metric": "Inactive User Rows", "Value": len(dataframes.get("inactive_users", pd.DataFrame()))},
                ],
                "SaaS Metrics": [
                    {"Metric": "Total SaaS Spend", "Value": _money(metrics.get("total_saas_spend"))},
                    {"Metric": "AI Spend", "Value": _money(metrics.get("ai_spend"))},
                    {"Metric": "License Spend", "Value": _money(metrics.get("total_license_spend"))},
                    {"Metric": "Optimization Potential", "Value": _money(metrics.get("potential_savings"))},
                    {"Metric": "Renewal Risks", "Value": _safe_int(metrics.get("renewals_due"))},
                ],
                "Financial Model": [
                    {"Metric": "Enterprise Total", "Value": _money(financial_model.get("enterprise_total"))},
                    {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                    {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                    {"Metric": "Generated At", "Value": str(financial_model.get("generated_at") or "Unknown")},
                ],
            },
        }

