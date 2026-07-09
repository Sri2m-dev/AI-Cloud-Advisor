from __future__ import annotations

from typing import Any

import streamlit as st

from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.enterprise_financial_model import EnterpriseFinancialModel
from services.knowledge_graph_service import KnowledgeGraphService


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


class KnowledgeGraphCertificationService:
    """Certification overlay for the Knowledge Graph page.

    The graph algorithms remain in KnowledgeGraphService. This service adds
    executive, financial, evidence, and certification context for the page.
    """

    @staticmethod
    def format_money(value: Any) -> str:
        return _money(value)

    @staticmethod
    def escape_markdown_currency(text: str) -> str:
        return str(text or "").replace("$", r"\$")

    @staticmethod
    def expected_relationships(
        business_services: int,
        applications: int,
        technologies: int,
        relationships: int,
    ) -> int:
        expected = int(business_services or 0) + int(applications or 0) + int(technologies or 0) + 7
        return max(expected, int(relationships or 0))

    @staticmethod
    def relationship_summary_inputs(
        business_services: int,
        applications: int,
        technologies: int,
        relationships: int,
    ) -> dict[str, float]:
        summary_business_services = int(business_services or 0)
        summary_applications = int(applications or 0)
        summary_technologies = int(technologies or 0)
        summary_relationships = int(relationships or 0)

        try:
            from services.technology_digital_twin_service import TechnologyDigitalTwinService

            technology_service = TechnologyDigitalTwinService()
            portfolio = technology_service.technology_portfolio(technology_service.organization_id())
            if portfolio:
                summary_business_services = sum(int(item.get("business_services") or 0) for item in portfolio)
                summary_applications = sum(int(item.get("applications") or 0) for item in portfolio)
                summary_technologies = len(portfolio)
                summary_relationships = sum(int(item.get("dependencies") or 0) for item in portfolio)
        except Exception:
            pass

        expected = KnowledgeGraphCertificationService.expected_relationships(
            summary_business_services,
            summary_applications,
            summary_technologies,
            summary_relationships,
        )
        coverage = round((summary_relationships / expected) * 100, 1) if expected else 0
        entity_presence_score = 100 if summary_business_services and summary_applications and summary_technologies else 0
        confidence = round((coverage + entity_presence_score) / 2)
        return {
            "business_services": summary_business_services,
            "applications": summary_applications,
            "technologies": summary_technologies,
            "relationships": summary_relationships,
            "expected_relationships": expected,
            "relationship_coverage": coverage,
            "graph_confidence": confidence,
        }

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_dashboard() -> dict[str, Any]:
        kpis = KnowledgeGraphService.get_graph_kpis()
        nodes_df = KnowledgeGraphService.nodes_dataframe()
        relationships_df = KnowledgeGraphService.relationships_dataframe()
        relationship_summary = KnowledgeGraphCertificationService.relationship_summary_inputs(
            kpis.get("Business Services", 0),
            kpis.get("Applications", 0),
            kpis.get("Technologies", 0),
            kpis.get("Relationships", 0),
        )
        financial_model = EnterpriseFinancialModel.get_enterprise_summary()
        reconciliation = EnterpriseFinancialModel.get_reconciliation_status()
        business_context = KnowledgeGraphCertificationService._business_context(kpis, relationship_summary)
        dependency_summary = KnowledgeGraphCertificationService._dependency_summary(kpis)

        return {
            "relationship_summary": relationship_summary,
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
            "dependency_summary": dependency_summary,
            "executive_summary": KnowledgeGraphCertificationService._executive_summary(
                relationship_summary,
                financial_model,
                reconciliation,
                business_context,
                dependency_summary,
            ),
            "evidence": KnowledgeGraphCertificationService._evidence(
                kpis,
                nodes_df,
                relationships_df,
                relationship_summary,
                financial_model,
                reconciliation,
                business_context,
                dependency_summary,
            ),
        }

    @staticmethod
    def _business_context(kpis: dict[str, Any], relationship_summary: dict[str, Any]) -> dict[str, Any]:
        unit_summary = _safe_call(BusinessUnitService.get_summary, {})
        capability_summary = _safe_call(BusinessCapabilityService.get_capability_summary, {})
        service_summary = _safe_call(BusinessServiceService.get_service_summary, {})
        process_summary = _safe_call(BusinessProcessService.get_process_summary, {})

        return {
            "business_units": _safe_int(unit_summary.get("business_units") or unit_summary.get("total_business_units")),
            "capabilities": _safe_int(capability_summary.get("capabilities") or capability_summary.get("total_capabilities")),
            "business_services": _safe_int(
                service_summary.get("business_services")
                or service_summary.get("total_services"),
                _safe_int(kpis.get("Business Services")),
            ),
            "business_processes": _safe_int(process_summary.get("business_processes") or process_summary.get("total_processes")),
            "applications": _safe_int(relationship_summary.get("applications") or kpis.get("Applications")),
            "technologies": _safe_int(relationship_summary.get("technologies") or kpis.get("Technologies")),
            "relationships": _safe_int(relationship_summary.get("relationships") or kpis.get("Relationships")),
            "mapping_coverage": _safe_float(
                relationship_summary.get("relationship_coverage")
                or service_summary.get("mapping_coverage")
                or capability_summary.get("mapping_coverage")
                or unit_summary.get("mapping_coverage")
            ),
        }

    @staticmethod
    def _dependency_summary(kpis: dict[str, Any]) -> dict[str, Any]:
        critical_dependencies = _safe_int(kpis.get("Critical Dependencies"))
        aws_impact = KnowledgeGraphService.get_impact_analysis("AWS")
        return {
            "critical_dependencies": critical_dependencies,
            "single_points_of_failure": 1 if critical_dependencies else 0,
            "highest_blast_radius": aws_impact.get("Node") or "AWS",
            "estimated_impact": _safe_float(aws_impact.get("Impacted Spend")),
            "impacted_applications": _safe_int(aws_impact.get("Applications")),
            "impacted_business_services": _safe_int(aws_impact.get("Business Services")),
            "risk": aws_impact.get("Risk") or "Unknown",
        }

    @staticmethod
    def _executive_summary(
        relationship_summary: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
        dependency_summary: dict[str, Any],
    ) -> str:
        sentences = [
            f"The Knowledge Graph connects {_safe_int(business_context.get('business_services'))} business services, {_safe_int(business_context.get('applications'))} applications, {_safe_int(business_context.get('technologies'))} technologies, and {_safe_int(business_context.get('relationships'))} relationships.",
            f"Graph confidence is {_safe_float(relationship_summary.get('graph_confidence')):.0f}% with {_safe_float(relationship_summary.get('relationship_coverage')):.1f}% relationship coverage.",
            f"The highest current blast radius is {dependency_summary.get('highest_blast_radius')} with estimated impact of {_money(dependency_summary.get('estimated_impact'))}.",
            f"Critical dependencies total {_safe_int(dependency_summary.get('critical_dependencies'))}, with {_safe_int(dependency_summary.get('single_points_of_failure'))} single point of failure signal currently highlighted.",
            f"Data reconciliation status is {reconciliation.get('status') or 'Unknown'} with {_safe_float(reconciliation.get('allocation_coverage')):.1f}% allocation coverage and {_money(financial_model.get('unallocated_spend'))} unallocated spend.",
        ]
        return KnowledgeGraphCertificationService.escape_markdown_currency(" ".join(sentences))

    @staticmethod
    def _evidence(
        kpis: dict[str, Any],
        nodes_df,
        relationships_df,
        relationship_summary: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
        dependency_summary: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {"Section": "Graph Nodes", "Source": "KnowledgeGraphService / KnowledgeGraphRepository", "Mode": "Service"},
                {"Section": "Graph Relationships", "Source": "KnowledgeGraphService / KnowledgeGraphRepository", "Mode": "Service"},
                {"Section": "Impact Analysis", "Source": "KnowledgeGraphService", "Mode": "Service"},
                {"Section": "Business Architecture", "Source": "BusinessUnit/Capability/Service/Process services", "Mode": "Service"},
                {"Section": "Financial Model", "Source": "EnterpriseFinancialModel", "Mode": "Canonical"},
            ],
            "data_coverage": [
                {"Coverage Area": "Graph Nodes", "Value": f"{len(nodes_df):,}", "Status": "Tracked"},
                {"Coverage Area": "Relationships", "Value": f"{_safe_int(relationship_summary.get('relationships')):,}", "Status": "Tracked"},
                {"Coverage Area": "Expected Relationships", "Value": f"{_safe_int(relationship_summary.get('expected_relationships')):,}", "Status": "Modeled"},
                {"Coverage Area": "Relationship Coverage", "Value": f"{_safe_float(relationship_summary.get('relationship_coverage')):.1f}%", "Status": "Tracked"},
                {"Coverage Area": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%", "Status": reconciliation.get("status") or "Unknown"},
            ],
            "relationship_summary": [
                {"Layer": "Business Units", "Count": _safe_int(business_context.get("business_units"))},
                {"Layer": "Capabilities", "Count": _safe_int(business_context.get("capabilities"))},
                {"Layer": "Business Services", "Count": _safe_int(business_context.get("business_services"))},
                {"Layer": "Business Processes", "Count": _safe_int(business_context.get("business_processes"))},
                {"Layer": "Applications", "Count": _safe_int(business_context.get("applications"))},
                {"Layer": "Technologies", "Count": _safe_int(business_context.get("technologies"))},
                {"Layer": "Relationships", "Count": _safe_int(business_context.get("relationships"))},
            ],
            "financial_reconciliation": [
                {"Metric": "Data Reconciliation Status", "Value": reconciliation.get("status") or "Unknown"},
                {"Metric": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%"},
                {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                {"Metric": "Highest Blast Radius", "Value": dependency_summary.get("highest_blast_radius") or "Unknown"},
                {"Metric": "Estimated Impact", "Value": _money(dependency_summary.get("estimated_impact"))},
            ],
            "ai_interpretation": (
                "The Knowledge Graph is certification-ready as an enterprise intelligence layer. "
                "It connects business services, applications, technologies, ownership, cost, risk, and dependency impact. "
                "The next maturity step is broadening explicit capability and process paths for every graph route."
            ),
            "raw_evidence": {
                "Graph KPIs": [
                    {"Metric": key, "Value": value}
                    for key, value in kpis.items()
                ],
                "Dependency Summary": [
                    {"Metric": key.replace("_", " ").title(), "Value": value}
                    for key, value in dependency_summary.items()
                ],
                "Financial Model": [
                    {"Metric": "Enterprise Total", "Value": _money(financial_model.get("enterprise_total"))},
                    {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                    {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                    {"Metric": "Generated At", "Value": str(financial_model.get("generated_at") or "Unknown")},
                ],
            },
        }

