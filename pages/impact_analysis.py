from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.enterprise_intelligence import render_common_asset_search, render_empty_state, render_intelligence_workspace
from components.sidebar_navigation import render_sidebar_navigation
from graph.graph_traversal import TraversalType
from services.impact_analysis_service import ImpactAnalysisService


st.set_page_config(page_title="Impact Analysis", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical", "finance"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Impact Analysis is available to leadership, operations, governance, and finance roles.")
        st.stop()


def _currency(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _number(value: Any) -> str:
    try:
        return f"{float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "0"


def _show_table(rows: list[dict[str, Any]], empty_message: str) -> None:
    if not rows:
        st.info(empty_message)
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _tree_chart(rows: list[dict[str, Any]]) -> go.Figure | None:
    if len(rows) <= 1:
        return None
    labels = [f"{row['Entity']} ({row['Type']})" for row in rows[:40]]
    parents = [""]
    for row in rows[1:40]:
        parent_depth = max(int(row["Depth"]) - 1, 0)
        parent = next(
            (
                f"{candidate['Entity']} ({candidate['Type']})"
                for candidate in reversed(rows[: rows.index(row)])
                if int(candidate["Depth"]) == parent_depth
            ),
            labels[0],
        )
        parents.append(parent)
    fig = go.Figure(go.Treemap(labels=labels, parents=parents, branchvalues="total"))
    fig.update_layout(height=430, margin={"l": 4, "r": 4, "t": 12, "b": 4})
    return fig


def _hierarchy_chart(rows: list[dict[str, Any]]) -> go.Figure | None:
    if not rows:
        return None
    label_by_entity = {row["Entity"]: f"{row['Level']}: {row['Entity']}" for row in rows}
    fig = go.Figure(
        go.Treemap(
            labels=[label_by_entity[row["Entity"]] for row in rows],
            parents=[label_by_entity.get(row.get("Parent"), "") for row in rows],
            values=[row.get("Impact Weight", 1) for row in rows],
            marker={
                "colors": [row.get("Impact Weight", 1) for row in rows],
                "colorscale": "RdYlGn_r",
            },
        )
    )
    fig.update_layout(height=460, margin={"l": 4, "r": 4, "t": 12, "b": 4})
    return fig


def _heat_map_chart(rows: list[dict[str, Any]]) -> go.Figure | None:
    if not rows:
        return None
    top_rows = rows[:20]
    fig = go.Figure(
        go.Bar(
            x=[row["Impact Score"] for row in top_rows],
            y=[f"{row['Entity']} ({row['Category']})" for row in top_rows],
            orientation="h",
            marker={
                "color": [row["Impact Score"] for row in top_rows],
                "colorscale": "RdYlGn_r",
                "cmin": 0,
                "cmax": 100,
            },
            text=[row["Risk"] for row in top_rows],
        )
    )
    fig.update_layout(
        height=520,
        xaxis_title="Impact Score",
        yaxis={"autorange": "reversed"},
        margin={"l": 8, "r": 8, "t": 16, "b": 32},
    )
    return fig


def _blast_radius_chart(rows: list[dict[str, Any]]) -> go.Figure | None:
    if not rows:
        return None
    fig = go.Figure(
        go.Sunburst(
            labels=[row["Node"] for row in rows],
            parents=[row["Parent"] for row in rows],
            values=[row["Value"] for row in rows],
            branchvalues="remainder",
            hovertext=[row["Display"] for row in rows],
            maxdepth=6,
        )
    )
    fig.update_layout(height=430, margin={"l": 4, "r": 4, "t": 12, "b": 4})
    return fig


def _risk_gauge(score: float, label: str) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": label},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#1f77b4"},
                "steps": [
                    {"range": [0, 45], "color": "#d8f3dc"},
                    {"range": [45, 70], "color": "#fff3b0"},
                    {"range": [70, 85], "color": "#ffd6a5"},
                    {"range": [85, 100], "color": "#ffadad"},
                ],
            },
        )
    )
    fig.update_layout(height=300, margin={"l": 16, "r": 16, "t": 48, "b": 16})
    return fig


def _render_downloads(analysis: dict[str, Any]) -> None:
    pdf_bytes = ImpactAnalysisService.build_pdf(analysis)
    excel_bytes = ImpactAnalysisService.build_excel(analysis)
    pptx_bytes = ImpactAnalysisService.build_powerpoint(analysis)
    safe_name = analysis["asset"].lower().replace(" ", "_").replace("/", "_")

    e1, e2, e3 = st.columns(3)
    e1.download_button(
        "Export PDF",
        data=pdf_bytes,
        file_name=f"impact_analysis_{safe_name}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    e2.download_button(
        "Export Excel",
        data=excel_bytes,
        file_name=f"impact_analysis_{safe_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    e3.download_button(
        "Export PowerPoint",
        data=pptx_bytes,
        file_name=f"impact_analysis_{safe_name}.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        use_container_width=True,
    )


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    dashboard = ImpactAnalysisService.get_dashboard(organization_id)
    kpis = dashboard["kpis"]

    st.title("Impact Analysis")
    st.caption("Enterprise impact intelligence across technology, applications, services, cost, risk, owners, approvals, and automation readiness.")
    render_intelligence_workspace("Impact Analysis")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Assets Analysed", _number(kpis["Assets Analysed"]))
    k2.metric("Critical Assets", _number(kpis["Critical Assets"]))
    k3.metric("Business Services", _number(kpis["Business Services"]))
    k4.metric("Revenue Exposure", _currency(kpis["Revenue Exposure"]))

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Applications", _number(kpis["Applications"]))
    k6.metric("Departments", _number(kpis["Departments"]))
    k7.metric("Estimated Risk", _number(kpis["Estimated Risk"]))
    k8.metric("Average Impact Score", f"{float(kpis['Average Impact Score'] or 0):.1f}")

    st.divider()
    st.subheader("Search")
    assets = dashboard["assets"]
    type_options = ["All", "Technology", "Application", "Business Service", "Department", "Owner", "Cloud Provider", "Enterprise Asset"]
    f1, f3 = st.columns([2, 2])
    selected_type = f1.selectbox("Asset Type", type_options)
    allowed = None if selected_type == "All" else {selected_type}
    selected_asset, selected_asset_type = render_common_asset_search(
        organization_id,
        "impact_analysis",
        default=st.session_state.get("enterprise_intelligence_asset", "AWS"),
        allowed_types=allowed,
    )
    traversal = f3.selectbox(
        "Traversal",
        [item.value for item in TraversalType if item != TraversalType.SHORTEST_PATH],
        index=4,
    )

    analysis = ImpactAnalysisService.analyze_asset(
        selected_asset,
        selected_asset_type if selected_type == "All" else selected_type,
        organization_id,
        traversal_type=traversal,
    )

    st.divider()
    st.subheader("Impact Summary")
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.metric("Asset", analysis["asset"])
    s2.metric("Impact Score", f"{analysis['impact_score']:.1f}")
    s3.metric("Risk", analysis["risk_level"])
    s4.metric("Applications", _number(analysis["business_impact"]["Applications Impacted"]))
    s5.metric("Business Services", _number(analysis["business_impact"]["Business Services"]))
    s6.metric("Annual Cost", _currency(analysis["financial_impact"]["Annual Cost"]))

    st.write(analysis["executive_summary"])

    st.subheader("Why Critical")
    why_cols = st.columns(3)
    for index, reason in enumerate(analysis.get("why_critical", [])[:6]):
        with why_cols[index % 3]:
            st.metric(
                reason["Driver"],
                reason["Reason"],
                f"Contribution {reason['Contribution']}",
            )

    st.divider()
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Enterprise Impact Hierarchy")
        fig = _hierarchy_chart(analysis.get("impact_hierarchy", []))
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            render_empty_state("No impact hierarchy is available.", "This asset needs mapped application, business service, department, or owner relationships.")
        for level in [
            "Technology",
            "Infrastructure",
            "Application",
            "Business Service",
            "Business Capability",
            "Department",
            "Executive",
            "Revenue",
            "Compliance",
            "Customers",
        ]:
            level_rows = [
                row for row in analysis.get("impact_hierarchy", []) if row["Level"] == level
            ]
            if level_rows:
                with st.expander(
                    level,
                    expanded=level in {"Technology", "Application", "Business Service"},
                ):
                    _show_table(level_rows, f"No {level.lower()} rows are available.")

    with right:
        st.subheader("Blast Radius")
        blast_fig = _blast_radius_chart(analysis.get("blast_radius", []))
        if blast_fig:
            st.plotly_chart(blast_fig, use_container_width=True)
        else:
            render_empty_state("No blast radius view is available.", "Run impact analysis after adding business and financial mappings.")

        st.subheader("Overall Risk")
        st.plotly_chart(_risk_gauge(float(analysis["risk_score"]), analysis["risk_level"]), use_container_width=True)

    st.divider()
    heat_col, risk_col = st.columns([3, 2])
    with heat_col:
        st.subheader("Impact Heat Map")
        heat_map = _heat_map_chart(analysis.get("impact_heat_map", []))
        if heat_map:
            st.plotly_chart(heat_map, use_container_width=True)
        else:
            render_empty_state("No heat map data is available.", "No impacted applications, services, departments, or resources were found.")
    with risk_col:
        st.subheader("Risk Analysis")
        _show_table([analysis["risk_analysis"]], "No risk analysis is available.")

    st.divider()
    b1, b2 = st.columns(2)
    with b1:
        st.subheader("Business Impact")
        business = analysis["business_impact"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Applications", _number(business["Applications Impacted"]))
        c2.metric("Services", _number(business["Business Services"]))
        c3.metric("Customers", _number(business["Customers"]))
        c4, c5, c6 = st.columns(3)
        c4.metric("Revenue", _currency(business["Revenue"]))
        c5.metric("Revenue / Day", _currency(business["Revenue Per Day"]))
        c6.metric("Approvals", _number(business["Approvals Required"]))

    with b2:
        st.subheader("Financial Impact")
        financial = analysis["financial_impact"]
        f1, f2, f3 = st.columns(3)
        f1.metric("Cloud Spend", _currency(financial["Cloud Spend"]))
        f2.metric("Savings", _currency(financial["Savings"]))
        f3.metric("License Cost", _currency(financial["License Cost"]))
        f4, f5 = st.columns(2)
        f4.metric("Support Cost", _currency(financial["Support Cost"]))
        f5.metric("Revenue Risk", _currency(financial["Estimated Revenue Risk"]))

    st.divider()
    st.subheader("Explainable AI")
    st.write(analysis["ai_context"]["prompt_context"])
    ai1, ai2, ai3, ai4 = st.columns(4)
    ai1.metric("Confidence", "95%")
    ai2.metric("Automation", analysis["risk_analysis"]["Automation Readiness"])
    ai3.metric("Recommendations", _number(len([row for row in analysis["impacted_nodes"] if row["node_type"] == "Recommendation"])))
    ai4.metric("Approvals", _number(analysis["risk_analysis"]["Approvals"]))
    st.code(
        " -> ".join(
            f"{row['Entity']} ({row['Type']})"
            for row in analysis["dependency_tree"][:8]
        ),
        language="text",
    )
    _show_table(analysis.get("explainability", []), "No explainability data is available.")

    st.divider()
    st.subheader("Approval Intelligence")
    _show_table(analysis.get("approval_intelligence", []), "No approval intelligence is available.")

    st.divider()
    st.subheader("Dependency Tree")
    dep_fig = _tree_chart(analysis["dependency_tree"])
    if dep_fig:
        st.plotly_chart(dep_fig, use_container_width=True)
    _show_table(analysis["dependency_tree"], "No dependency rows are available.")

    with st.expander("AI context payload"):
        st.json(analysis["ai_context"])

    st.divider()
    st.subheader("Executive Reports")
    _render_downloads(analysis)

    st.divider()
    st.subheader("Top Enterprise Impacts")
    _show_table(dashboard["top_impacts"], "No enterprise impact ranking is available.")


if __name__ == "__main__":
    main()
