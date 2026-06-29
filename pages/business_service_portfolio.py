from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.sidebar_navigation import render_sidebar_navigation
from data.supabase_client import supabase
from services.business_service_cost_service import BusinessServiceCostService
from shared.auth import require_role
from shared.layout import render_page_header
from shared.session import init_session
from shared.styles import configure_page


BUSINESS_SERVICES_TABLE = "business_services"
BUSINESS_SERVICE_RELATIONSHIPS_TABLE = "business_service_relationships"


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0

    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    return f"${amount:,.0f}"


def _first_present(row: pd.Series, *columns: str, default: Any = None) -> Any:
    for column in columns:
        if column in row and pd.notna(row[column]) and str(row[column]).strip():
            return row[column]
    return default


def _first_key(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return value
    return default


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fetch_table(table_name: str) -> list[dict[str, Any]]:
    try:
        return supabase.table(table_name).select("*").execute().data or []
    except Exception:
        return []


def _fallback_services() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Service": "Checkout Service",
                "Cost": 0.0,
                "Criticality": "Critical",
                "Owner": "Srikanth Mudaliar",
                "Health": 87,
                "Risk": "Healthy",
                "Business Unit": "Retail",
                "Department": "Digital Commerce",
            }
        ]
    )


def _service_portfolio_dataframe() -> pd.DataFrame:
    rows = _fetch_table(BUSINESS_SERVICES_TABLE)
    if not rows:
        return _fallback_services()

    records: list[dict[str, Any]] = []
    for row in rows:
        annual_cost = _to_float(
            _first_key(
                row,
                "annual_cost",
                "annual_service_cost",
                "service_cost",
                "total_cost",
                "cost",
                default=0,
            )
        )
        if not annual_cost:
            annual_cost = _to_float(_first_key(row, "monthly_cost", "monthly_spend", default=0)) * 12

        records.append(
            {
                "Service": _first_key(row, "service_name", "business_service_name", "name", "service", default="Unknown Service"),
                "Cost": annual_cost,
                "Criticality": _first_key(row, "criticality", "service_criticality", default="Standard"),
                "Owner": _first_key(row, "service_owner", "owner", "business_owner", default="Unassigned"),
                "Health": _first_key(row, "health_score", "health", "service_health", default=85),
                "Risk": _first_key(row, "risk_status", "risk", "status", default="Healthy"),
                "Business Unit": _first_key(row, "business_unit", "business_unit_name", default="Unassigned"),
                "Department": _first_key(row, "department", "department_name", default="Unassigned"),
            }
        )

    services = pd.DataFrame(records)
    if services.empty:
        return _fallback_services()

    services["Cost"] = pd.to_numeric(services["Cost"], errors="coerce").fillna(0)
    services["Health"] = pd.to_numeric(services["Health"], errors="coerce").fillna(85)
    return services


def _relationships_dataframe() -> pd.DataFrame:
    rows = _fetch_table(BUSINESS_SERVICE_RELATIONSHIPS_TABLE)
    if not rows:
        return pd.DataFrame(
            [
                {"Source": "Checkout Service", "Target": "Checkout", "Relationship": "supports"},
                {"Source": "Checkout", "Target": "AWS", "Relationship": "depends_on"},
                {"Source": "Checkout", "Target": "Datadog", "Relationship": "monitored_by"},
                {"Source": "Checkout", "Target": "GitHub", "Relationship": "built_from"},
                {"Source": "Checkout", "Target": "ChatGPT Enterprise", "Relationship": "uses_ai"},
                {"Source": "Checkout", "Target": "GitHub Copilot", "Relationship": "uses_ai"},
                {"Source": "Checkout", "Target": "Managed Services", "Relationship": "operated_by"},
            ]
        )

    records: list[dict[str, Any]] = []
    for row in rows:
        source = _first_key(
            row,
            "source_name",
            "source",
            "parent_name",
            "from_name",
            "service_name",
            "business_service_name",
        )
        target = _first_key(
            row,
            "target_name",
            "target",
            "child_name",
            "to_name",
            "application_name",
            "technology_name",
            "dependent_name",
        )

        if not source and row.get("application"):
            source = _first_key(row, "service_name", "business_service_name")
            target = row.get("application")
        if not target:
            continue

        records.append(
            {
                "Source": str(source or "Unknown"),
                "Target": str(target),
                "Relationship": str(_first_key(row, "relationship_type", "relationship", "type", default="depends_on")),
            }
        )

    return pd.DataFrame(records)


def _risk_mask(services: pd.DataFrame) -> pd.Series:
    risk_text = services.get("Risk", pd.Series(dtype=str)).astype(str).str.lower()
    health = pd.to_numeric(services.get("Health", pd.Series(dtype=float)), errors="coerce").fillna(85)
    return risk_text.str.contains("risk|critical|high|warning", case=False, na=False) | (health < 80)


def _health_counts(services: pd.DataFrame) -> dict[str, int]:
    health = pd.to_numeric(services.get("Health", pd.Series(dtype=float)), errors="coerce").fillna(85)
    return {
        "Healthy": int((health >= 80).sum()),
        "Warning": int(((health >= 60) & (health < 80)).sum()),
        "Critical": int((health < 60).sum()),
    }


def _kpi_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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


def _dependency_graph(relationships: pd.DataFrame) -> go.Figure:
    if relationships.empty:
        relationships = _relationships_dataframe()

    labels = pd.unique(relationships[["Source", "Target"]].values.ravel("K")).tolist()
    label_index = {label: index for index, label in enumerate(labels)}
    sources = relationships["Source"].map(label_index).tolist()
    targets = relationships["Target"].map(label_index).tolist()
    palette = ["#1f2937", "#2563eb", "#16a34a", "#7c3aed", "#0f766e", "#b45309"]

    figure = go.Figure(
        data=[
            go.Sankey(
                arrangement="fixed",
                node={
                    "label": labels,
                    "pad": 18,
                    "thickness": 18,
                    "color": [palette[index % len(palette)] for index in range(len(labels))],
                },
                link={
                    "source": sources,
                    "target": targets,
                    "value": [1] * len(relationships),
                    "color": ["rgba(37, 99, 235, 0.25)"] * len(relationships),
                },
            )
        ]
    )
    figure.update_layout(
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        height=280,
        font={"size": 12},
    )
    return figure


def _relationship_tree(relationships: pd.DataFrame) -> str:
    if relationships.empty:
        relationships = _relationships_dataframe()

    service_edges = relationships[relationships["Source"].eq("Checkout Service")]
    application = (
        service_edges.iloc[0]["Target"]
        if not service_edges.empty
        else "Checkout"
    )
    dependencies = relationships[relationships["Source"].eq(application)]["Target"].tolist()
    if not dependencies:
        dependencies = [
            "AWS",
            "Datadog",
            "GitHub",
            "ChatGPT Enterprise",
            "GitHub Copilot",
            "Managed Services",
        ]

    lines = ["Checkout Service", "  |", f"  + {application}"]
    for dependency in dependencies:
        lines.append(f"      + {dependency}")
    return "\n".join(lines)


def _cost_waterfall_graph(waterfall: pd.DataFrame) -> go.Figure | None:
    if waterfall.empty:
        return None

    labels = pd.unique(waterfall[["Source", "Target"]].values.ravel("K")).tolist()
    label_index = {label: index for index, label in enumerate(labels)}
    palette = ["#1f2937", "#2563eb", "#16a34a", "#7c3aed", "#0f766e", "#b45309"]

    figure = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node={
                    "label": labels,
                    "pad": 18,
                    "thickness": 18,
                    "color": [palette[index % len(palette)] for index in range(len(labels))],
                },
                link={
                    "source": waterfall["Source"].map(label_index).tolist(),
                    "target": waterfall["Target"].map(label_index).tolist(),
                    "value": pd.to_numeric(waterfall["Value"], errors="coerce").fillna(1).tolist(),
                    "color": ["rgba(37, 99, 235, 0.22)"] * len(waterfall),
                },
            )
        ]
    )
    figure.update_layout(
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        height=340,
        font={"size": 12},
    )
    return figure


def _spend_attribution_tree(attribution: pd.DataFrame) -> str:
    if attribution.empty:
        return "No spend attribution available."

    lines: list[str] = []
    for service, group in attribution.groupby("Business Service", dropna=False):
        lines.append(str(service))
        sorted_group = group.sort_values("Annual Cost", ascending=False)
        for _, row in sorted_group.iterrows():
            lines.append(f"  + {row['Technology']} {_money(row['Annual Cost'])}")
    return "\n".join(lines)


configure_page(page_title="Business Service Portfolio", page_icon="B")
init_session()
require_role(["cio", "super_admin"])

role = st.session_state.get("role", "cio")
render_sidebar_navigation(role)

render_page_header(
    "Business Service Portfolio",
    "Business services, ownership, cost, dependencies and health",
)

services = _service_portfolio_dataframe()
relationships = _relationships_dataframe()
cost_kpis = BusinessServiceCostService.get_kpis()
allocation_df = BusinessServiceCostService.allocations_dataframe()
waterfall_df = BusinessServiceCostService.cost_waterfall_dataframe()
attribution_df = BusinessServiceCostService.spend_attribution_dataframe()
unallocated_df = BusinessServiceCostService.unallocated_spend_dataframe()
critical_services = services["Criticality"].astype(str).str.lower().isin({"critical", "tier 1", "tier1"}).sum()
annual_service_cost = pd.to_numeric(services["Cost"], errors="coerce").fillna(0).sum()

st.markdown("### Cost Allocation KPIs")
kpi_columns = st.columns(5)
with kpi_columns[0]:
    _kpi_card("Business Services", f"{cost_kpis['business_services']:,.0f}")
with kpi_columns[1]:
    _kpi_card("Allocated Spend", _money(cost_kpis["allocated_spend"]))
with kpi_columns[2]:
    _kpi_card("Unallocated Spend", _money(cost_kpis["unallocated_spend"]))
with kpi_columns[3]:
    _kpi_card("Critical Services", f"{cost_kpis['critical_services']:,.0f}")
with kpi_columns[4]:
    _kpi_card("Optimization Potential", _money(cost_kpis["optimization_potential"]))

st.markdown("### Service Cost Allocation")
if allocation_df.empty:
    st.info("No business service cost allocation data is available.")
else:
    allocation_table = allocation_df[
        [
            "service_name",
            "owner",
            "annual_cost",
            "application_cost",
            "technology_cost",
            "total_exposure",
            "criticality",
            "optimization_potential",
        ]
    ].copy()
    allocation_table = allocation_table.rename(
        columns={
            "service_name": "Service",
            "owner": "Owner",
            "annual_cost": "Annual Cost",
            "application_cost": "Application Cost",
            "technology_cost": "Technology Exposure",
            "total_exposure": "Total Exposure",
            "criticality": "Criticality",
            "optimization_potential": "Optimization Potential",
        }
    )
    allocation_table = _format_money_columns(
        allocation_table,
        [
            "Annual Cost",
            "Application Cost",
            "Technology Exposure",
            "Total Exposure",
            "Optimization Potential",
        ],
    )
    st.dataframe(allocation_table, use_container_width=True, hide_index=True)

st.markdown("### Cost Waterfall")
waterfall_fig = _cost_waterfall_graph(waterfall_df)
if waterfall_fig:
    st.plotly_chart(waterfall_fig, use_container_width=True)
else:
    st.info("No cost waterfall data is available.")

st.markdown("### Spend Attribution")
left_attr, right_attr = st.columns([2, 1])
with left_attr:
    attribution_table = _format_money_columns(
        attribution_df,
        ["Annual Cost"],
    )
    _show_dataframe(attribution_table, "No spend attribution data is available.")
with right_attr:
    st.code(_spend_attribution_tree(attribution_df), language="text")

st.markdown("### Unallocated Spend")
unallocated_table = _format_money_columns(
    unallocated_df,
    ["Annual Cost"],
)
_show_dataframe(unallocated_table, "No unallocated technology spend is currently identified.")

st.markdown("### Executive Narrative")
st.info(BusinessServiceCostService.get_executive_narrative())

st.markdown("### Business Service KPIs")
service_kpi_columns = st.columns(4)
with service_kpi_columns[0]:
    _kpi_card("Business Services", f"{services['Service'].nunique():,.0f}")
with service_kpi_columns[1]:
    _kpi_card("Critical Services", f"{critical_services:,.0f}")
with service_kpi_columns[2]:
    _kpi_card("Annual Service Cost", _money(annual_service_cost))
with service_kpi_columns[3]:
    _kpi_card("Relationships", f"{len(relationships):,.0f}")

st.markdown("### Service Portfolio")
portfolio_table = services[["Service", "Cost", "Criticality", "Owner"]].copy()
portfolio_table["Cost"] = portfolio_table["Cost"].apply(_money)
st.dataframe(portfolio_table, use_container_width=True, hide_index=True)

st.markdown("### Service Dependency Graph")
left, right = st.columns([2, 1])
with left:
    st.plotly_chart(_dependency_graph(relationships), use_container_width=True)
with right:
    st.code(_relationship_tree(relationships), language="text")

st.markdown("### Service Health Summary")
health_counts = _health_counts(services)
health_columns = st.columns(3)
with health_columns[0]:
    _kpi_card("Healthy", f"{health_counts['Healthy']:,.0f}")
with health_columns[1]:
    _kpi_card("Warning", f"{health_counts['Warning']:,.0f}")
with health_columns[2]:
    _kpi_card("Critical", f"{health_counts['Critical']:,.0f}")
