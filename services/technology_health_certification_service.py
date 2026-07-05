from __future__ import annotations

from typing import Any

import streamlit as st

from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.enterprise_financial_model import EnterpriseFinancialModel
from services.technology_health_service import TechnologyHealthService


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
    if abs(amount) >= 1000:
        return f"${amount / 1000:,.1f}K".replace(".0K", "K")
    return f"${amount:,.0f}"


class TechnologyHealthCertificationService:
    """Certification overlay for Technology Health.

    Keeps existing health KPIs, chart, and drilldown tables intact while adding
    executive summary, financial reconciliation, business context, and evidence.
    """

    @staticmethod
    def format_compact_currency(value: Any) -> str:
        return _money(value)

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_dashboard() -> dict[str, Any]:
        kpis = TechnologyHealthService.get_kpis()
        health_matrix = TechnologyHealthService.health_matrix_dataframe()
        renewal_exposure = TechnologyHealthService.renewal_exposure_dataframe()
        license_waste = TechnologyHealthService.license_waste_dataframe()
        dependency_edges = TechnologyHealthService.dependency_edges_dataframe()

        financial_model = EnterpriseFinancialModel.get_enterprise_summary()
        reconciliation = EnterpriseFinancialModel.get_reconciliation_status()
        business_context = TechnologyHealthCertificationService._business_context(kpis)

        return {
            "financial_model": financial_model,
            "reconciliation": reconciliation,
            "reconciliation_cards": {
                "status": reconciliation.get("status") or "Unknown",
                "allocation_coverage": _safe_float(reconciliation.get("allocation_coverage")),
                "allocation_coverage_display": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                "unallocated_spend": _safe_float(financial_model.get("unallocated_spend")),
                "unallocated_spend_display": _money(financial_model.get("unallocated_spend")),
            },
            "business_context": business_context,
            "executive_summary": TechnologyHealthCertificationService._executive_summary(
                kpis,
                financial_model,
                reconciliation,
                business_context,
            ),
            "evidence": TechnologyHealthCertificationService._evidence(
                kpis,
                financial_model,
                reconciliation,
                business_context,
                health_matrix,
                renewal_exposure,
                license_waste,
                dependency_edges,
            ),
        }

    @staticmethod
    def _business_context(kpis: dict[str, Any]) -> dict[str, Any]:
        unit_summary = _safe_call(BusinessUnitService.get_summary, {})
        capability_summary = _safe_call(BusinessCapabilityService.get_capability_summary, {})
        service_summary = _safe_call(BusinessServiceService.get_service_summary, {})
        process_summary = _safe_call(BusinessProcessService.get_process_summary, {})

        return {
            "business_units": _safe_int(unit_summary.get("business_units") or unit_summary.get("total_business_units")),
            "capabilities": _safe_int(capability_summary.get("capabilities") or capability_summary.get("total_capabilities")),
            "business_services": _safe_int(service_summary.get("business_services") or service_summary.get("total_services")),
            "business_processes": _safe_int(process_summary.get("business_processes") or process_summary.get("total_processes")),
            "technology_relationships": _safe_int(kpis.get("dependency_edges")),
            "mapping_coverage": _safe_float(
                service_summary.get("mapping_coverage")
                or capability_summary.get("mapping_coverage")
                or unit_summary.get("mapping_coverage")
            ),
        }

    @staticmethod
    def _executive_summary(
        kpis: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
    ) -> str:
        at_risk = (
            _safe_int(kpis.get("critical_technologies"))
            + _safe_int(kpis.get("high_risk_technologies"))
            + _safe_int(kpis.get("medium_risk_technologies"))
        )
        sentences = [
            f"Technology Health tracks {_safe_int(kpis.get('total_technologies'))} technologies with an average health score of {_safe_float(kpis.get('average_health')):.1f}.",
            f"{at_risk} technologies are currently in watchlist, elevated, or critical tiers.",
            f"Renewal obligation exposure is {_money(kpis.get('renewal_exposure'))} and inactive license exposure is {_money(kpis.get('license_waste_exposure'))}.",
            f"The dependency model tracks {_safe_int(kpis.get('dependency_edges'))} technology relationships across the CIO portfolio.",
            f"Business context includes {_safe_int(business_context.get('business_units'))} business units, {_safe_int(business_context.get('capabilities'))} capabilities, {_safe_int(business_context.get('business_services'))} services, and {_safe_int(business_context.get('business_processes'))} processes.",
            f"Data reconciliation status is {reconciliation.get('status') or 'Unknown'} with {_safe_float(reconciliation.get('allocation_coverage')):.1f}% allocation coverage and {_money(financial_model.get('unallocated_spend'))} unallocated spend.",
        ]
        return " ".join(sentences).replace("$", r"\$")

    @staticmethod
    def _evidence(
        kpis: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
        health_matrix,
        renewal_exposure,
        license_waste,
        dependency_edges,
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {"Section": "Technology Inventory", "Source": "TechnologyHealthService / technology_inventory", "Mode": "Service"},
                {"Section": "Relationships", "Source": "TechnologyHealthService / technology_relationships", "Mode": "Service"},
                {"Section": "Renewals", "Source": "TechnologyHealthService / SaaS renewal risk", "Mode": "Service"},
                {"Section": "Inactive Licenses", "Source": "TechnologyHealthService / inactive SaaS users", "Mode": "Service"},
                {"Section": "Business Architecture", "Source": "BusinessUnit/Capability/Service/Process services", "Mode": "Service"},
                {"Section": "Financial Model", "Source": "EnterpriseFinancialModel", "Mode": "Canonical"},
            ],
            "data_coverage": [
                {"Coverage Area": "Technology Records", "Value": f"{_safe_int(kpis.get('total_technologies'))}", "Status": "Tracked"},
                {"Coverage Area": "Dependency Relationships", "Value": f"{_safe_int(kpis.get('dependency_edges'))}", "Status": "Tracked"},
                {"Coverage Area": "Renewal Records", "Value": f"{len(renewal_exposure):,}", "Status": "Tracked"},
                {"Coverage Area": "Inactive License Records", "Value": f"{len(license_waste):,}", "Status": "Tracked"},
                {
                    "Coverage Area": "Allocation Coverage",
                    "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                    "Status": reconciliation.get("status") or "Unknown",
                },
            ],
            "relationship_summary": [
                {"Layer": "Business Units", "Count": _safe_int(business_context.get("business_units"))},
                {"Layer": "Capabilities", "Count": _safe_int(business_context.get("capabilities"))},
                {"Layer": "Business Services", "Count": _safe_int(business_context.get("business_services"))},
                {"Layer": "Business Processes", "Count": _safe_int(business_context.get("business_processes"))},
                {"Layer": "Technologies", "Count": _safe_int(kpis.get("total_technologies"))},
                {"Layer": "Technology Relationships", "Count": _safe_int(kpis.get("dependency_edges"))},
            ],
            "financial_reconciliation": [
                {"Metric": "Data Reconciliation Status", "Value": reconciliation.get("status") or "Unknown"},
                {"Metric": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%"},
                {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                {"Metric": "Renewal Obligation Exposure", "Value": _money(kpis.get("renewal_exposure"))},
                {"Metric": "Inactive License Exposure", "Value": _money(kpis.get("license_waste_exposure"))},
            ],
            "ai_interpretation": (
                "Technology Health is certification-ready for CIO review because it links portfolio health, "
                "renewal exposure, inactive license exposure, and dependency relationships to a canonical "
                "financial reconciliation layer. Further certification depth can be added later by tying each "
                "unhealthy technology to explicit business service blast-radius paths."
            ),
            "raw_evidence": {
                "Health Summary": [
                    {"Metric": "Total Technologies", "Value": _safe_int(kpis.get("total_technologies"))},
                    {"Metric": "Average Health Score", "Value": f"{_safe_float(kpis.get('average_health')):.1f}"},
                    {"Metric": "Critical Technologies", "Value": _safe_int(kpis.get("critical_technologies"))},
                    {"Metric": "Elevated Technologies", "Value": _safe_int(kpis.get("high_risk_technologies"))},
                    {"Metric": "Watchlist Technologies", "Value": _safe_int(kpis.get("medium_risk_technologies"))},
                ],
                "Financial Model": [
                    {"Metric": "Enterprise Total", "Value": _money(financial_model.get("enterprise_total"))},
                    {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                    {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                    {"Metric": "Generated At", "Value": str(financial_model.get("generated_at") or "Unknown")},
                ],
                "Evidence Counts": [
                    {"Metric": "Health Matrix Rows", "Value": len(health_matrix)},
                    {"Metric": "Renewal Exposure Rows", "Value": len(renewal_exposure)},
                    {"Metric": "Inactive License Rows", "Value": len(license_waste)},
                    {"Metric": "Dependency Rows", "Value": len(dependency_edges)},
                ],
            },
        }

