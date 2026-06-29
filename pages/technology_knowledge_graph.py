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
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.knowledge_graph_service import KnowledgeGraphService


st.set_page_config(page_title="Technology Knowledge Graph", layout="wide")


def _money(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


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

    def render_graph_content() -> None:
        render_section(
            "Graph Intelligence Summary",
            "CIO view of what is connected, what depends on what, and where mapping is incomplete.",
            divider=False,
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
                f"{relationships:,}",
                "Edges connecting entities across the graph",
                icon="graph",
                status="info" if relationships else "warning",
            )
        with relationship_cols[1]:
            render_risk_card(
                "Critical Dependencies",
                f"{critical_dependencies:,}",
                "Dependencies on critical technology services",
                icon="risk",
                status="critical" if critical_dependencies else "healthy",
            )
        with relationship_cols[2]:
            render_risk_card(
                "Unmapped Nodes",
                f"{unmapped_nodes:,}",
                "Entities without relationship coverage",
                icon="warning",
                status="critical" if unmapped_nodes else "healthy",
            )
        with relationship_cols[3]:
            render_metric_card(
                "Graph Health Score",
                f"{graph_health_score}%",
                "Share of entities with relationship coverage",
                icon="health",
                status=_graph_health_status(graph_health_score),
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
                "Graph Health Score",
                f"{graph_health_score}%",
                "Connected entity coverage",
                icon="health",
                status=_graph_health_status(graph_health_score),
            )
        with health_cols[1]:
            render_risk_card(
                "Mapping Incomplete",
                f"{unmapped_nodes:,}",
                "Unmapped nodes requiring relationship cleanup",
                icon="warning",
                status="critical" if unmapped_nodes else "healthy",
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
            description=KnowledgeGraphService.answer_question(question),
            status=_graph_health_status(graph_health_score),
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

    render_page(
        title="Knowledge Graph",
        description="CIO graph intelligence for connected services, applications, technologies, dependencies, and impact.",
        breadcrumbs=["Home", "CIO", "Knowledge Graph"],
        content=render_graph_content,
        status=_graph_health_status(graph_health_score),
    )


if __name__ == "__main__":
    main()
