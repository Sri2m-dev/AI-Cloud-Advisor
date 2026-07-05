from __future__ import annotations

from typing import Any

import streamlit as st

from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.enterprise_financial_model import EnterpriseFinancialModel
from services.technology_digital_twin_service import TechnologyDigitalTwinService


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


class TechnologyDigitalTwinCertificationService:
    """Certification overlay for the Technology Digital Twin page.

    The twin composition and graph logic remain in TechnologyDigitalTwinService.
    This service adds executive, financial, business architecture, and evidence
    metadata needed for certification.
    """

    @staticmethod
    def format_money(value: Any) -> str:
        return _money(value)

    @staticmethod
    def escape_markdown_currency(text: str) -> str:
        return str(text or "").replace("$", r"\$")

    @staticmethod
    def strongest_mapped_index(portfolio: list[dict[str, Any]]) -> int:
        if not portfolio:
            return 0

        def score(item: dict[str, Any]) -> tuple[float, float, float, float, float]:
            name_bonus = 1000 if str(item.get("name") or "").strip().upper() == "AWS" else 0
            relationships = _safe_float(item.get("dependencies"))
            applications = _safe_float(item.get("applications"))
            services = _safe_float(item.get("business_services"))
            cost = _safe_float(item.get("monthly_cost"))
            health = _safe_float(item.get("health"))
            return (
                name_bonus + relationships * 20 + applications * 15 + services * 15,
                cost,
                health,
                applications,
                relationships,
            )

        best = max(range(len(portfolio)), key=lambda index: score(portfolio[index]))
        return int(best)

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_dashboard(
        _service: TechnologyDigitalTwinService | None = None,
        organization_id: str | None = None,
        portfolio: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        service = _service or TechnologyDigitalTwinService()
        organization_id = organization_id or service.organization_id()
        portfolio = portfolio if portfolio is not None else service.technology_portfolio(organization_id)

        metrics = TechnologyDigitalTwinCertificationService._metrics(service, organization_id, portfolio)
        financial_model = EnterpriseFinancialModel.get_enterprise_summary()
        reconciliation = EnterpriseFinancialModel.get_reconciliation_status()
        business_context = TechnologyDigitalTwinCertificationService._business_context(metrics)

        return {
            "metrics": metrics,
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
            "executive_summary": TechnologyDigitalTwinCertificationService._executive_summary(
                metrics,
                financial_model,
                reconciliation,
                business_context,
            ),
            "evidence": TechnologyDigitalTwinCertificationService._evidence(
                metrics,
                financial_model,
                reconciliation,
                business_context,
            ),
        }

    @staticmethod
    def _metrics(
        service: TechnologyDigitalTwinService,
        organization_id: str,
        portfolio: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total_twins = len(portfolio)
        healthy_twins = sum(1 for item in portfolio if _safe_float(item.get("health")) >= 85)
        degraded_twins = sum(1 for item in portfolio if _safe_float(item.get("health")) < 70)
        monthly_cost = sum(_safe_float(item.get("monthly_cost")) for item in portfolio)
        application_mappings = sum(_safe_int(item.get("applications")) for item in portfolio)
        service_mappings = sum(_safe_int(item.get("business_services")) for item in portfolio)
        relationship_count = sum(_safe_int(item.get("dependencies")) for item in portfolio)
        mapped_twins = sum(
            1
            for item in portfolio
            if _safe_int(item.get("applications")) or _safe_int(item.get("business_services")) or _safe_int(item.get("dependencies"))
        )
        twin_coverage = round((mapped_twins / total_twins) * 100, 1) if total_twins else 0
        average_health = (
            round(sum(_safe_float(item.get("health")) for item in portfolio) / total_twins, 1)
            if total_twins
            else 0
        )
        average_risk = (
            round(sum(_safe_float(item.get("risk")) for item in portfolio) / total_twins, 1)
            if total_twins
            else 0
        )
        critical_risks = service.get_critical_risks(organization_id) if portfolio else []
        active_incidents = service.get_active_incidents(organization_id) if portfolio else []
        recommendations = service.get_recommendations(organization_id) if portfolio else []
        automation_candidates = service.get_automation_candidates(organization_id) if portfolio else []
        graph = service.graph(organization_id)

        return {
            "total_twins": total_twins,
            "healthy_twins": healthy_twins,
            "degraded_twins": degraded_twins,
            "monthly_cost": monthly_cost,
            "annual_cost": monthly_cost * 12,
            "application_mappings": application_mappings,
            "service_mappings": service_mappings,
            "relationship_count": relationship_count,
            "mapped_twins": mapped_twins,
            "twin_coverage": twin_coverage,
            "average_health": average_health,
            "average_risk": average_risk,
            "critical_risks": len(critical_risks),
            "active_incidents": len(active_incidents),
            "recommendations": len(recommendations),
            "automation_candidates": len(automation_candidates),
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
            "infrastructure_nodes": len(graph.get("infrastructure_nodes", [])),
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
            "business_services": _safe_int(
                service_summary.get("business_services") or service_summary.get("total_services"),
                _safe_int(metrics.get("service_mappings")),
            ),
            "business_processes": _safe_int(process_summary.get("business_processes") or process_summary.get("total_processes")),
            "applications": _safe_int(metrics.get("application_mappings")),
            "technologies": _safe_int(metrics.get("total_twins")),
            "technology_relationships": _safe_int(metrics.get("relationship_count")),
            "mapping_coverage": _safe_float(
                service_summary.get("mapping_coverage")
                or capability_summary.get("mapping_coverage")
                or unit_summary.get("mapping_coverage")
                or metrics.get("twin_coverage")
            ),
        }

    @staticmethod
    def _executive_summary(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
    ) -> str:
        sentences = [
            f"The Technology Digital Twin estate contains {_safe_int(metrics.get('total_twins'))} canonical technology twins with {_safe_float(metrics.get('twin_coverage')):.1f}% mapping coverage.",
            f"Average technology health is {_safe_float(metrics.get('average_health')):.1f}% with {_safe_int(metrics.get('critical_risks'))} critical risk signals and {_safe_int(metrics.get('active_incidents'))} active operational incidents.",
            f"Mapped monthly technology spend is {_money(metrics.get('monthly_cost'))}, with {_safe_int(metrics.get('recommendations'))} AI recommendations and {_safe_int(metrics.get('automation_candidates'))} automation candidates.",
            f"Business architecture context includes {_safe_int(business_context.get('business_units'))} business units, {_safe_int(business_context.get('capabilities'))} capabilities, {_safe_int(business_context.get('business_services'))} services, and {_safe_int(business_context.get('business_processes'))} processes.",
            f"Data reconciliation status is {reconciliation.get('status') or 'Unknown'} with {_safe_float(reconciliation.get('allocation_coverage')):.1f}% allocation coverage and {_money(financial_model.get('unallocated_spend'))} unallocated spend.",
        ]
        return TechnologyDigitalTwinCertificationService.escape_markdown_currency(" ".join(sentences))

    @staticmethod
    def _evidence(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {"Section": "Technology Twins", "Source": "TechnologyDigitalTwinService", "Mode": "Service"},
                {"Section": "Technology Graph", "Source": "TechnologyDigitalTwinService.graph", "Mode": "Service"},
                {"Section": "Business Architecture", "Source": "BusinessUnit/Capability/Service/Process services", "Mode": "Service"},
                {"Section": "Financial Model", "Source": "EnterpriseFinancialModel", "Mode": "Canonical"},
                {"Section": "AI / Automation", "Source": "TechnologyDigitalTwinService recommendations", "Mode": "Service"},
            ],
            "data_coverage": [
                {"Coverage Area": "Technology Twins", "Value": f"{_safe_int(metrics.get('total_twins')):,}", "Status": "Tracked"},
                {"Coverage Area": "Mapped Twins", "Value": f"{_safe_int(metrics.get('mapped_twins')):,}", "Status": "Tracked"},
                {"Coverage Area": "Twin Mapping Coverage", "Value": f"{_safe_float(metrics.get('twin_coverage')):.1f}%", "Status": "Tracked"},
                {"Coverage Area": "Graph Edges", "Value": f"{_safe_int(metrics.get('graph_edges')):,}", "Status": "Tracked"},
                {"Coverage Area": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%", "Status": reconciliation.get("status") or "Unknown"},
            ],
            "relationship_summary": [
                {"Layer": "Business Units", "Count": _safe_int(business_context.get("business_units"))},
                {"Layer": "Capabilities", "Count": _safe_int(business_context.get("capabilities"))},
                {"Layer": "Business Services", "Count": _safe_int(business_context.get("business_services"))},
                {"Layer": "Business Processes", "Count": _safe_int(business_context.get("business_processes"))},
                {"Layer": "Applications", "Count": _safe_int(business_context.get("applications"))},
                {"Layer": "Technology Twins", "Count": _safe_int(metrics.get("total_twins"))},
                {"Layer": "Technology Relationships", "Count": _safe_int(metrics.get("relationship_count"))},
            ],
            "financial_reconciliation": [
                {"Metric": "Data Reconciliation Status", "Value": reconciliation.get("status") or "Unknown"},
                {"Metric": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%"},
                {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                {"Metric": "Mapped Technology Monthly Spend", "Value": _money(metrics.get("monthly_cost"))},
            ],
            "ai_interpretation": (
                "The Technology Digital Twin is certification-ready as a CIO intelligence workspace. "
                "It connects portfolio health, cost, risk, operations, infrastructure, AI recommendations, "
                "dependency context, and technical evidence. Remaining maturity comes from expanding explicit "
                "business-service and application mappings for every technology node."
            ),
            "raw_evidence": {
                "Twin Portfolio": [
                    {"Metric": "Technology Twins", "Value": _safe_int(metrics.get("total_twins"))},
                    {"Metric": "Healthy Twins", "Value": _safe_int(metrics.get("healthy_twins"))},
                    {"Metric": "Degraded Twins", "Value": _safe_int(metrics.get("degraded_twins"))},
                    {"Metric": "Application Mappings", "Value": _safe_int(metrics.get("application_mappings"))},
                    {"Metric": "Business Service Mappings", "Value": _safe_int(metrics.get("service_mappings"))},
                    {"Metric": "Relationship Count", "Value": _safe_int(metrics.get("relationship_count"))},
                ],
                "Operational Intelligence": [
                    {"Metric": "Critical Risks", "Value": _safe_int(metrics.get("critical_risks"))},
                    {"Metric": "Active Incidents", "Value": _safe_int(metrics.get("active_incidents"))},
                    {"Metric": "AI Recommendations", "Value": _safe_int(metrics.get("recommendations"))},
                    {"Metric": "Automation Candidates", "Value": _safe_int(metrics.get("automation_candidates"))},
                ],
                "Financial Model": [
                    {"Metric": "Enterprise Total", "Value": _money(financial_model.get("enterprise_total"))},
                    {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                    {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                    {"Metric": "Generated At", "Value": str(financial_model.get("generated_at") or "Unknown")},
                ],
            },
        }

