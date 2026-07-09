from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.guards import require_login
from auth.role_constants import normalize_role
from components.cards import (
    render_insight_card,
    render_kpi_card,
    render_metric_card,
    render_risk_card,
)
from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.shared import (
    render_ai_narrative,
    render_business_context,
    render_evidence_panel,
    render_executive_summary,
    render_reconciliation_panel,
)
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.knowledge_graph_certification_service import KnowledgeGraphCertificationService
from services.knowledge_graph_service import KnowledgeGraphService
from shared.streamlit_compat import dataframe


st.set_page_config(page_title="Technology Knowledge Graph", layout="wide")


def _money(value: Any) -> str:
    return KnowledgeGraphCertificationService.format_money(value)


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    dataframe(df, hide_index=True)


def _format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    formatted = df.copy()
    for column in columns:
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(_money)
    return formatted


def _tree_text(tree: dict[str, Any]) -> str:
    lines = [str(tree["node"])]
    if tree["upstream"]:
        lines.append("  Upstream")
        for row in tree["upstream"]:
            lines.append(f"    -> {row['Node']} ({row['Relationship']})")
    if tree["downstream"]:
        lines.append("  Downstream")
        for row in tree["downstream"]:
            lines.append(f"    <- {row['Node']} ({row['Relationship']})")
    return "\n".join(lines)


def _graph_health_status(score: float) -> str:
    if score >= 90:
        return "healthy"
    if score >= 75:
        return "warning"
    return "critical"


def _selected_technology_detail(detail_df: pd.DataFrame, technology: str) -> dict[str, Any]:
    if detail_df.empty or "Technology" not in detail_df.columns:
        return {}

    matches = detail_df[
        detail_df["Technology"].astype(str).str.lower().eq(str(technology).lower())
    ]
    if matches.empty:
        return {}
    return matches.iloc[0].to_dict()


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_enterprise_sidebar(
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
        active_page=PAGE_PATHS["Technology Knowledge Graph"],
    )

    kpis = KnowledgeGraphService.get_graph_kpis()
    nodes_df = KnowledgeGraphService.nodes_dataframe()
    rel_df = KnowledgeGraphService.relationships_dataframe()
    total_entities = len(nodes_df)
    business_services = kpis.get("Business Services", 0)
    applications = kpis.get("Applications", 0)
    technologies = kpis.get("Technologies", 0)
    relationships = kpis.get("Relationships", 0)
    critical_dependencies = kpis.get("Critical Dependencies", 0)
    certification = KnowledgeGraphCertificationService.get_dashboard()
    relationship_summary = certification["relationship_summary"]
    reconciliation_cards = certification["reconciliation_cards"]
    business_context = certification["business_context"]
    dependency_summary = certification["dependency_summary"]
    financial_model = certification.get("financial_model") or {}
    evidence = certification["evidence"]
    summary_relationships = int(relationship_summary["relationships"])
    expected_relationships = int(relationship_summary["expected_relationships"])
    relationship_coverage = relationship_summary["relationship_coverage"]

    connected_nodes: set[str] = set()
    if not rel_df.empty:
        for column in ("source_name", "target_name"):
            if column in rel_df.columns:
                connected_nodes.update(rel_df[column].dropna().astype(str).str.lower().tolist())
    unmapped_nodes = 0
    if not nodes_df.empty and "Node" in nodes_df.columns:
        unmapped_nodes = len(
            [
                node
                for node in nodes_df["Node"].dropna().astype(str).tolist()
                if node.lower() not in connected_nodes
            ]
        )

    graph_health_score = round(
        ((total_entities - unmapped_nodes) / total_entities) * 100,
        1,
    ) if total_entities else 0
    graph_confidence = int(relationship_summary["graph_confidence"])

    def render_certification_summary() -> None:
        render_executive_summary(
            {
                "title": "Executive Summary",
                "description": "Certified enterprise dependency intelligence for business impact, financial reconciliation, and graph confidence.",
                "narrative": certification["executive_summary"],
                "metrics": [
                    {
                        "label": "Graph Confidence",
                        "value": f"{graph_confidence}%",
                        "description": "Certified graph confidence",
                        "icon": "health",
                        "status": _graph_health_status(graph_confidence),
                    },
                    {
                        "label": "Relationships",
                        "value": f"{summary_relationships:,} of {expected_relationships:,}",
                        "description": "Mapped dependency relationships",
                        "icon": "graph",
                        "status": _graph_health_status(float(relationship_coverage or 0)),
                    },
                    {
                        "label": "Relationship Coverage",
                        "value": f"{float(relationship_coverage or 0):.1f}%",
                        "description": "Expected graph relationships mapped",
                        "icon": "governance",
                        "status": _graph_health_status(float(relationship_coverage or 0)),
                    },
                    {
                        "label": "Critical Dependencies",
                        "value": f"{int(dependency_summary.get('critical_dependencies') or 0):,}",
                        "description": "High-impact dependency signals",
                        "icon": "risk",
                        "status": "critical" if dependency_summary.get("critical_dependencies") else "healthy",
                    },
                    {
                        "label": "Highest Blast Radius",
                        "value": dependency_summary.get("highest_blast_radius") or "Unknown",
                        "description": f"Impact: {_money(dependency_summary.get('estimated_impact'))}",
                        "icon": "alert",
                        "status": "critical" if dependency_summary.get("risk") == "Critical" else "warning",
                    },
                    {
                        "label": "Applications",
                        "value": f"{int(business_context.get('applications') or 0):,}",
                        "description": "Application nodes in business context",
                        "icon": "technology",
                        "status": "info",
                    },
                    {
                        "label": "Technologies",
                        "value": f"{int(business_context.get('technologies') or 0):,}",
                        "description": "Technology nodes in business context",
                        "icon": "platform",
                        "status": "info",
                    },
                    {
                        "label": "Estimated Impact",
                        "value": _money(dependency_summary.get("estimated_impact")),
                        "description": "Highest blast-radius spend exposure",
                        "icon": "cost",
                        "status": "warning",
                    },
                ],
            }
        )

        render_reconciliation_panel(
            {
                **reconciliation_cards,
                "allocated_spend_display": _money(financial_model.get("allocated_spend")),
                "variance_status": reconciliation_cards.get("status", "Unknown"),
            }
        )
        render_business_context(business_context)
        render_ai_narrative(
            "AI Graph Interpretation",
            evidence.get("ai_interpretation") or "Knowledge Graph AI interpretation is unavailable.",
            description="AI-assisted interpretation of dependency coverage, blast radius, and graph maturity.",
        )

        render_section(
            "Enterprise Dependency Summary",
            "Certified rollup of business, application, technology, relationship, and blast-radius signals.",
        )
        dependency_cols = st.columns(4)
        with dependency_cols[0]:
            render_metric_card("Business Units", f"{int(business_context.get('business_units') or 0):,}", "Enterprise scope", icon="enterprise", status="info")
            render_metric_card("Business Services", f"{int(business_context.get('business_services') or 0):,}", "Service layer", icon="enterprise", status="info")
        with dependency_cols[1]:
            render_metric_card("Applications", f"{int(business_context.get('applications') or 0):,}", "Application layer", icon="technology", status="info")
            render_metric_card("Technologies", f"{int(business_context.get('technologies') or 0):,}", "Technology layer", icon="platform", status="info")
        with dependency_cols[2]:
            render_metric_card("Relationships", f"{int(business_context.get('relationships') or 0):,}", "Mapped edges", icon="graph", status="info")
            render_risk_card("Critical Dependencies", f"{int(dependency_summary.get('critical_dependencies') or 0):,}", "High-impact dependencies", icon="risk", status="critical" if dependency_summary.get("critical_dependencies") else "healthy")
        with dependency_cols[3]:
            render_risk_card("Highest Blast Radius", dependency_summary.get("highest_blast_radius") or "Unknown", f"Impact: {_money(dependency_summary.get('estimated_impact'))}", icon="alert", status="critical" if dependency_summary.get("risk") == "Critical" else "warning")
            render_metric_card("Governance Coverage", f"{float(business_context.get('mapping_coverage') or 0):.1f}%", "Relationship coverage", icon="governance", status=_graph_health_status(float(business_context.get("mapping_coverage") or 0)))

    def render_certification_evidence() -> None:
        render_evidence_panel(evidence)

    def render_graph_content() -> None:
        render_certification_summary()

        render_section(
            "Graph Intelligence Summary",
            "CIO view of what is connected, what depends on what, and where mapping is incomplete.",
        )
        summary_cols = st.columns(4)
        with summary_cols[0]:
            render_kpi_card(
                "Total Entities",
                f"{total_entities:,}",
                "Nodes across services, applications, technologies, owners, cost, risk, and vendors",
                icon="graph",
                status="info",
            )
        with summary_cols[1]:
            render_kpi_card(
                "Applications",
                f"{applications:,}",
                "Application nodes available for dependency analysis",
                icon="technology",
                status="info",
            )
        with summary_cols[2]:
            render_kpi_card(
                "Technologies",
                f"{technologies:,}",
                "Technology nodes connected to services and applications",
                icon="platform",
                status="info",
            )
        with summary_cols[3]:
            render_kpi_card(
                "Business Services",
                f"{business_services:,}",
                "Business service nodes in the graph",
                icon="enterprise",
                status="info",
            )

        relationship_cols = st.columns(4)
        with relationship_cols[0]:
            render_metric_card(
                "Relationships",
                f"{summary_relationships:,} of {expected_relationships:,}",
                f"{relationship_coverage}% relationship coverage",
                icon="graph",
                status="info" if summary_relationships else "warning",
            )
        with relationship_cols[1]:
            render_metric_card(
                "Relationship Coverage",
                f"{relationship_coverage}%",
                f"{summary_relationships:,} mapped relationships; {max(expected_relationships - summary_relationships, 0):,} expected gaps",
                icon="health",
                status=_graph_health_status(relationship_coverage),
            )
        with relationship_cols[2]:
            render_risk_card(
                "Critical Dependencies",
                f"{critical_dependencies:,}",
                "Dependencies on critical technology services",
                icon="risk",
                status="critical" if critical_dependencies else "healthy",
            )
        with relationship_cols[3]:
            render_metric_card(
                "Graph Confidence",
                f"{graph_confidence}%",
                "Confidence from entity coverage and expected relationship mapping",
                icon="health",
                status=_graph_health_status(graph_confidence),
            )

        render_section(
            "Entity Coverage",
            "Entities available for CIO dependency, ownership, and impact analysis.",
        )
        entity_cols = st.columns(3)
        with entity_cols[0]:
            render_metric_card(
                "Business Services",
                f"{business_services:,}",
                "Services that can be traced to applications and technologies",
                icon="enterprise",
                status="info",
            )
        with entity_cols[1]:
            render_metric_card(
                "Applications",
                f"{applications:,}",
                "Applications connected into the graph",
                icon="technology",
                status="info",
            )
        with entity_cols[2]:
            render_metric_card(
                "Technologies",
                f"{technologies:,}",
                "Infrastructure, SaaS, AI, and platform technologies",
                icon="platform",
                status="info",
            )

        render_section(
            "Dependency Explorer",
            "Select a business service, application, and technology to see connected impact.",
        )
        levels = KnowledgeGraphService.get_explorer_levels()
        col1, col2, col3 = st.columns([0.9, 0.9, 1.2])

        with col1:
            selected_service = st.selectbox(
                "1. Select Business Service",
                levels["business_services"] or ["Order Processing"],
                index=0,
            )

        levels = KnowledgeGraphService.get_explorer_levels(business_service=selected_service)
        with col2:
            selected_application = st.selectbox(
                "2. Select Application",
                levels["applications"] or ["Checkout"],
                index=0,
            )

        levels = KnowledgeGraphService.get_explorer_levels(
            business_service=selected_service,
            application=selected_application,
        )
        with col3:
            selected_technology = st.selectbox(
                "3. Select Technology",
                levels["technologies"] or ["AWS"],
                index=0,
            )

        detail_df = pd.DataFrame(levels["details"])
        selected_detail = _selected_technology_detail(detail_df, selected_technology)
        impact = KnowledgeGraphService.get_impact_analysis(selected_technology)
        blast = KnowledgeGraphService.get_cost_blast_radius(selected_application)

        render_section(
            "Impact Summary",
            "4. View Impact",
            divider=False,
        )
        if selected_detail:
            impact_cols = st.columns(3)
            with impact_cols[0]:
                render_metric_card(
                    "Technology",
                    selected_technology,
                    f"Application: {selected_application}",
                    icon="technology",
                    status="info",
                )
            with impact_cols[1]:
                render_metric_card(
                    "Business Service",
                    selected_service,
                    f"Owner: {selected_detail.get('Owner') or 'Unassigned'}",
                    icon="enterprise",
                    status="info",
                )
            with impact_cols[2]:
                render_risk_card(
                    "Risk",
                    selected_detail.get("Risk") or impact["Risk"],
                    f"Estimated Spend Impact: {_money(impact['Impacted Spend'])}",
                    icon="risk",
                    status="critical" if (selected_detail.get("Risk") or impact["Risk"]) == "Critical" else "warning",
                )
        else:
            render_insight_card(
                "Impact Summary",
                description=(
                    "Some relationship details are not yet mapped. This means the graph knows the selected "
                    "dependency exists, but owner, cost, renewal, or vendor context is incomplete."
                ),
                status="warning",
            )

        render_section(
            "Failure Impact Analysis",
            "What breaks if the selected technology fails, and what business impact does it create?",
        )
        failure_cols = st.columns(3)
        with failure_cols[0]:
            render_metric_card(
                "Impacted Applications",
                f"{impact['Applications']:,}",
                "Applications downstream from the selected technology",
                icon="technology",
                status="warning" if impact["Applications"] else "healthy",
            )
        with failure_cols[1]:
            render_metric_card(
                "Impacted Business Services",
                f"{impact['Business Services']:,}",
                "Business services that may be disrupted",
                icon="enterprise",
                status="critical" if impact["Business Services"] else "healthy",
            )
        with failure_cols[2]:
            render_risk_card(
                "Estimated Spend Impact",
                _money(impact["Impacted Spend"]),
                "Mapped spend tied to the dependency path",
                icon="cost",
                status="critical" if impact["Risk"] == "Critical" else "warning",
            )

        impacted_path = [node for node in impact["Path"] if node != selected_technology]
        impacted_text = ", ".join(impacted_path[:4]) if impacted_path else selected_application
        render_insight_card(
            "Failure Impact Narrative",
            description=(
                f"If {selected_technology} is unavailable, {impacted_text} may be impacted, "
                f"with estimated spend exposure of {_money(impact['Impacted Spend'])}."
            ),
            status="critical" if impact["Risk"] == "Critical" else "warning",
        )

        with st.expander("Technical Dependency Evidence"):
            st.subheader("Cost Blast Radius")
            blast_df = pd.DataFrame([{"KPI": key, "Value": _money(value)} for key, value in blast.items()])
            _show_dataframe(blast_df, "No cost blast radius is available.")

            st.subheader("Dependency Tree")
            st.code(_tree_text(KnowledgeGraphService.get_dependency_tree(selected_application)), language="text")

            st.subheader("Owner, Cost, Risk, Renewal, Vendor")
            _show_dataframe(
                _format_money_columns(detail_df, ["Cost"]),
                "No technology detail is available.",
            )

        render_section(
            "Graph Health",
            "Mapping completeness and CIO confidence in dependency evidence.",
        )
        health_cols = st.columns(3)
        with health_cols[0]:
            render_metric_card(
                "Graph Confidence",
                f"{graph_confidence}%",
                f"{summary_relationships:,} of {expected_relationships:,} relationships mapped",
                icon="health",
                status=_graph_health_status(graph_confidence),
            )
        with health_cols[1]:
            render_metric_card(
                "Relationship Coverage",
                f"{relationship_coverage}%",
                f"{max(expected_relationships - summary_relationships, 0):,} expected relationship gaps",
                icon="graph",
                status=_graph_health_status(relationship_coverage),
            )
        with health_cols[2]:
            render_risk_card(
                "Critical Dependencies",
                f"{critical_dependencies:,}",
                "High-impact dependencies in the relationship model",
                icon="risk",
                status="critical" if critical_dependencies else "healthy",
            )

        render_section(
            "Executive Graph Insight",
            "Natural-language graph interpretation for CIO questions.",
        )
        question = st.text_input("Ask a graph question", value="What breaks if AWS fails?")
        render_insight_card(
            "Graph Question Response",
            description=KnowledgeGraphCertificationService.escape_markdown_currency(
                KnowledgeGraphService.answer_question(question)
            ),
            status=_graph_health_status(graph_confidence),
        )
        render_insight_card(
            "Knowledge Graph Value",
            description=(
                "The knowledge graph connects business services, applications, technologies, owners, vendors, "
                "cost, risk, and renewal context so the CIO can see dependency chains, weak links, business "
                "impact, and incomplete mapping before incidents or governance decisions."
            ),
            status="info",
        )

        render_section(
            "Detailed Evidence / Drilldown",
            "Raw entity and relationship evidence for graph validation.",
        )
        with st.expander("Detailed Evidence / Drilldown"):
            st.subheader("Entity Model")
            _show_dataframe(nodes_df, "No graph entities are available.")

            st.subheader("Relationship Model")
            _show_dataframe(
                rel_df[["source_type", "source_name", "relationship_type", "target_type", "target_name"]]
                if not rel_df.empty
                else rel_df,
                "No relationships are available.",
            )

        render_certification_evidence()

    render_page(
        title="Knowledge Graph",
        description="CIO graph intelligence for connected services, applications, technologies, dependencies, and impact.",
        breadcrumbs=["Home", "CIO", "Knowledge Graph"],
        content=render_graph_content,
        status=_graph_health_status(graph_confidence),
    )


if __name__ == "__main__":
    main()
