import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.business_service_graph_service import BusinessServiceGraphService
from services.technology_graph_service import TechnologyGraphService
from services.supabase_client import supabase


st.set_page_config(page_title="Technology Graph", layout="wide")


RISK_COLORS = {
    "Critical": "#b91c1c",
    "High": "#f97316",
    "Medium": "#facc15",
    "Low": "#2563eb",
    "Healthy": "#16a34a",
}


def fetch_table(table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data or []
    except Exception:
        return []


def normalize_text(value, fallback="Unknown"):
    text = str(value or "").strip()
    return text if text else fallback


def build_relationship_label(row):
    return (
        f"{normalize_text(row.get('source_name'))} "
        f"- {normalize_text(row.get('relationship_type'))} -> "
        f"{normalize_text(row.get('target_name'))}"
    )


def build_sankey_figure(edge_df):
    if edge_df.empty:
        return None

    graph_df = edge_df.copy()
    graph_df["source_node"] = graph_df["source_type"] + ": " + graph_df["source_name"]
    graph_df["target_node"] = graph_df["target_type"] + ": " + graph_df["target_name"]

    labels = pd.Index(
        pd.concat(
            [
                graph_df["source_node"],
                graph_df["target_node"],
            ],
            ignore_index=True,
        ).dropna().unique()
    )
    node_index = {label: index for index, label in enumerate(labels)}

    return go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node={
                    "label": labels.tolist(),
                    "pad": 14,
                    "thickness": 14,
                },
                link={
                    "source": graph_df["source_node"].map(node_index).tolist(),
                    "target": graph_df["target_node"].map(node_index).tolist(),
                    "value": [1] * len(graph_df),
                    "label": graph_df["relationship_type"].tolist(),
                },
            )
        ]
    )


def _money(value) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def _format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    formatted = df.copy()
    for column in columns:
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(_money)
    return formatted


def _heatmap_style(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return ""

    if score >= 90:
        color = "#dcfce7"
    elif score >= 80:
        color = "#dbeafe"
    elif score >= 70:
        color = "#fef9c3"
    elif score >= 60:
        color = "#ffedd5"
    else:
        color = "#fee2e2"
    return f"background-color: {color}; font-weight: 700;"


def _risk_style(value):
    color = RISK_COLORS.get(str(value))
    if not color:
        return ""

    text_color = "#111827" if str(value) == "Medium" else "#ffffff"
    return f"background-color: {color}; color: {text_color}; font-weight: 700;"


def main():
    user = require_login()

    role = normalize_role(
        st.session_state.get("role")
        or user.get("role")
        or "cio"
    )
    render_sidebar_navigation(role)

    st.title("Technology Graph Explorer")
    st.caption("Source, relationship, and target exploration across technology, departments, vendors, spend, and applications")

    business_graph_kpis = BusinessServiceGraphService.get_kpis()
    business_edges_df = BusinessServiceGraphService.graph_edges_dataframe()
    application_technology_df = BusinessServiceGraphService.application_technology_dataframe()
    technology_risk_impact_df = BusinessServiceGraphService.technology_risk_impact_dataframe()

    inventory_df = pd.DataFrame(TechnologyGraphService.get_inventory())
    relationships_df = pd.DataFrame(TechnologyGraphService.get_relationships())
    graph_kpis = TechnologyGraphService.get_kpis()
    criticality_df = TechnologyGraphService.criticality_dataframe()
    vendor_concentration_df = TechnologyGraphService.vendor_concentration_dataframe()
    department_impact_df = TechnologyGraphService.department_impact_dataframe()
    health_heatmap_df = TechnologyGraphService.health_heatmap_dataframe()

    if not inventory_df.empty and "annual_cost" in inventory_df.columns:
        inventory_df["annual_cost"] = pd.to_numeric(
            inventory_df["annual_cost"],
            errors="coerce",
        ).fillna(0)

    for column in [
        "source_type",
        "source_name",
        "relationship_type",
        "target_type",
        "target_name",
    ]:
        if column not in relationships_df.columns:
            relationships_df[column] = None
        relationships_df[column] = relationships_df[column].apply(normalize_text)

    if not business_edges_df.empty:
        for column in [
            "source_type",
            "source_name",
            "relationship_type",
            "target_type",
            "target_name",
        ]:
            if column not in business_edges_df.columns:
                business_edges_df[column] = None
            business_edges_df[column] = business_edges_df[column].apply(normalize_text)

    total_edges = len(relationships_df)

    st.subheader("Graph KPIs")
    kpi_cols = st.columns(6)
    kpi_cols[0].metric("Business Services", f"{business_graph_kpis['business_services']:,}")
    kpi_cols[1].metric("Applications", f"{business_graph_kpis['applications']:,}")
    kpi_cols[2].metric("Technologies", f"{business_graph_kpis['technologies']:,}")
    kpi_cols[3].metric("Relationships", f"{business_graph_kpis['relationships']:,}")
    kpi_cols[4].metric("Tracked Spend", _money(business_graph_kpis["annual_spend"]))
    kpi_cols[5].metric("High Impact Tech", f"{business_graph_kpis['high_impact_technologies']:,}")

    st.markdown("---")
    st.subheader("Business Service Dependency Graph")
    business_graph_fig = build_sankey_figure(business_edges_df)
    if business_graph_fig:
        st.plotly_chart(business_graph_fig, use_container_width=True)
    else:
        st.info("No business service dependency graph data is available yet.")

    st.markdown("---")
    st.subheader("Application-to-Technology Mapping")
    _show_dataframe(
        _format_money_columns(application_technology_df, ["Annual Spend"]),
        "No application-to-technology mapping is available yet.",
    )

    st.markdown("---")
    st.subheader("Technology Risk Impact")
    _show_dataframe(
        _format_money_columns(technology_risk_impact_df, ["Annual Spend"]),
        "No technology risk impact data is available yet.",
    )

    st.markdown("---")
    st.subheader("Executive Insight Narrative")
    st.info(BusinessServiceGraphService.get_executive_narrative())

    st.markdown("---")
    st.subheader("Technology Graph KPIs")
    technology_kpi_cols = st.columns(6)
    technology_kpi_cols[0].metric("Technologies", f"{graph_kpis['technologies']:,}")
    technology_kpi_cols[1].metric("Relationships", f"{total_edges}")
    technology_kpi_cols[2].metric("Tracked Spend", _money(graph_kpis["total_spend"]))
    technology_kpi_cols[3].metric("Medium+ Risk", f"{graph_kpis['medium_or_higher']:,}")
    technology_kpi_cols[4].metric("Top Vendor Share", f"{graph_kpis['top_vendor_share']:,.1f}%")
    technology_kpi_cols[5].metric("License Waste", _money(graph_kpis["total_waste"]))

    st.markdown("---")
    st.subheader("Technology Intelligence Narrative")
    st.info(TechnologyGraphService.get_executive_narrative())

    st.markdown("---")
    st.subheader("Technology Criticality Ranking")
    if not criticality_df.empty:
        fig = px.bar(
            criticality_df.head(10),
            x="Technology",
            y="Criticality",
            color="Risk",
            color_discrete_map=RISK_COLORS,
            title="Critical Technology Index",
        )
        st.plotly_chart(fig, use_container_width=True)
    _show_dataframe(
        criticality_df,
        "No technology criticality data is available.",
    )

    st.markdown("---")
    st.subheader("Vendor Concentration Analysis")
    if not vendor_concentration_df.empty:
        fig = px.bar(
            vendor_concentration_df,
            x="Vendor",
            y="Total Spend",
            color="Concentration Risk",
            title="Vendor Concentration Risk",
        )
        st.plotly_chart(fig, use_container_width=True)
    _show_dataframe(
        vendor_concentration_df,
        "No vendor concentration data is available.",
    )

    st.markdown("---")
    st.subheader("Department Impact Analysis")
    if not department_impact_df.empty:
        fig = px.bar(
            department_impact_df,
            x="Department",
            y="Department Risk Score",
            color="Annual Cost",
            title="Department Risk Score",
        )
        st.plotly_chart(fig, use_container_width=True)
    _show_dataframe(
        department_impact_df,
        "No department impact data is available.",
    )

    st.markdown("---")
    st.subheader("Technology Health Heatmap")
    if health_heatmap_df.empty:
        st.info("No technology health heatmap data is available.")
    else:
        styled_heatmap = (
            health_heatmap_df.style
            .map(_heatmap_style, subset=["Health"])
            .map(_risk_style, subset=["Risk"])
        )
        st.dataframe(
            styled_heatmap,
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    st.subheader("Graph Filters")

    if relationships_df.empty:
        st.info("No technology graph relationships are available yet.")
        return

    filter_cols = st.columns(3)
    relationship_options = ["All"] + sorted(relationships_df["relationship_type"].dropna().unique().tolist())
    source_type_options = ["All"] + sorted(relationships_df["source_type"].dropna().unique().tolist())
    target_type_options = ["All"] + sorted(relationships_df["target_type"].dropna().unique().tolist())

    selected_relationship = filter_cols[0].selectbox("Relationship", relationship_options)
    selected_source_type = filter_cols[1].selectbox("Source Type", source_type_options)
    selected_target_type = filter_cols[2].selectbox("Target Type", target_type_options)

    filtered_df = relationships_df.copy()
    if selected_relationship != "All":
        filtered_df = filtered_df[filtered_df["relationship_type"] == selected_relationship]
    if selected_source_type != "All":
        filtered_df = filtered_df[filtered_df["source_type"] == selected_source_type]
    if selected_target_type != "All":
        filtered_df = filtered_df[filtered_df["target_type"] == selected_target_type]

    st.markdown("---")
    st.subheader("Relationship Graph Preview")

    graph_fig = build_sankey_figure(filtered_df)
    if graph_fig:
        st.plotly_chart(graph_fig, use_container_width=True)
    else:
        st.info("No graph edges match the selected filters.")

    st.markdown("---")
    st.subheader("Source -> Relationship -> Target")

    edge_columns = [
        "source_type",
        "source_name",
        "relationship_type",
        "target_type",
        "target_name",
    ]
    edge_df = filtered_df[edge_columns].copy()
    edge_df["relationship_path"] = edge_df.apply(build_relationship_label, axis=1)
    st.dataframe(
        edge_df.rename(
            columns={
                "source_type": "Source Type",
                "source_name": "Source",
                "relationship_type": "Relationship",
                "target_type": "Target Type",
                "target_name": "Target",
                "relationship_path": "Path",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.subheader("Department Ownership Relationships")

    department_edges = relationships_df[
        relationships_df["target_type"].str.lower().eq("department")
    ].copy()
    if not department_edges.empty:
        dept_summary = (
            department_edges.groupby("target_name", as_index=False)
            .agg(Technologies=("source_name", "nunique"), Relationships=("id", "count"))
            .rename(columns={"target_name": "Department"})
            .sort_values("Technologies", ascending=False)
        )
        st.dataframe(dept_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No department relationships are available.")

    st.markdown("---")
    st.subheader("Vendor and Spend Relationships")

    if not inventory_df.empty and {"technology_name", "vendor_name", "annual_cost"}.issubset(inventory_df.columns):
        vendor_df = (
            inventory_df.groupby("vendor_name", dropna=False, as_index=False)
            .agg(
                Technologies=("technology_name", "nunique"),
                Annual_Spend=("annual_cost", "sum"),
            )
            .rename(columns={"vendor_name": "Vendor", "Annual_Spend": "Annual Spend"})
            .sort_values("Annual Spend", ascending=False)
        )
        fig = px.bar(vendor_df, x="Vendor", y="Annual Spend", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(vendor_df, use_container_width=True, hide_index=True)
    else:
        st.info("No vendor or spend relationship data is available.")

    st.markdown("---")
    st.subheader("Application Support Relationships")

    app_edges = relationships_df[
        relationships_df["target_type"].str.lower().eq("application")
    ].copy()
    if not app_edges.empty:
        app_summary = (
            app_edges.groupby("target_name", as_index=False)
            .agg(Supporting_Technologies=("source_name", "nunique"), Relationships=("id", "count"))
            .rename(
                columns={
                    "target_name": "Application",
                    "Supporting_Technologies": "Supporting Technologies",
                }
            )
            .sort_values("Supporting Technologies", ascending=False)
        )
        st.dataframe(app_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No application support relationships are available.")

    st.markdown("---")
    st.subheader("Future Graph View Readiness")
    st.info(
        "This explorer is structured around source nodes, relationship edge types, and target nodes. "
        "It can be promoted to an interactive graph canvas once the preferred visualization library is selected."
    )


if __name__ == "__main__":
    main()
