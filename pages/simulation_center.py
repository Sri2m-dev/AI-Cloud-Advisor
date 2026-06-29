from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.enterprise_intelligence import render_common_asset_search, render_demo_scenarios, render_empty_state, render_intelligence_workspace
from components.sidebar_navigation import render_sidebar_navigation
from services.simulation_service import SimulationService


st.set_page_config(page_title="Simulation Center", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical", "finance"}


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


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Simulation Center is available to leadership, architecture, finance, and operations roles.")
        st.stop()


def _show_table(rows: list[dict[str, Any]], empty_message: str) -> None:
    if not rows:
        st.info(empty_message)
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


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
    fig.update_layout(height=320, margin={"l": 16, "r": 16, "t": 48, "b": 16})
    return fig


def _risk_breakdown_chart(rows: list[dict[str, Any]]) -> go.Figure | None:
    if not rows:
        return None
    fig = go.Figure(
        go.Bar(
            x=[row["Score"] for row in rows],
            y=[row["Category"] for row in rows],
            orientation="h",
            marker={"color": [row["Score"] for row in rows], "colorscale": "RdYlGn_r", "cmin": 0, "cmax": 100},
            text=[f"{row['Weight']:.0f}%" for row in rows],
        )
    )
    fig.update_layout(height=340, xaxis_title="Risk Score", yaxis={"autorange": "reversed"}, margin={"l": 8, "r": 8, "t": 16, "b": 32})
    return fig


def _download_exports(simulation: dict[str, Any]) -> None:
    safe_name = simulation["simulation_name"].lower().replace(" ", "_").replace("/", "_")
    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "Export PDF",
        data=SimulationService.build_pdf(simulation),
        file_name=f"simulation_{safe_name}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    c2.download_button(
        "Export Excel",
        data=SimulationService.build_excel(simulation),
        file_name=f"simulation_{safe_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    c3.download_button(
        "Export PowerPoint",
        data=SimulationService.build_powerpoint(simulation),
        file_name=f"simulation_{safe_name}.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        use_container_width=True,
    )


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    dashboard = SimulationService.get_dashboard(organization_id)
    kpis = dashboard["kpis"]

    st.title("Enterprise Simulation Center")
    st.caption("Model what-if technology, cloud, SaaS, application, database, and financial scenarios before execution.")
    render_intelligence_workspace("Simulation Center")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Active Simulations", _number(kpis["Active Simulations"]))
    k2.metric("Potential Savings", _currency(kpis["Potential Savings"]))
    k3.metric("High Risk", _number(kpis["High Risk Scenarios"]))
    k4.metric("Approved", _number(kpis["Approved Simulations"]))
    k5.metric("Rejected", _number(kpis["Rejected Simulations"]))
    k6.metric("Avg Confidence", f"{float(kpis['Average Confidence'] or 0):.1f}%")

    st.divider()
    st.subheader("Scenario Builder")
    scenario_catalog = dashboard["scenario_catalog"]
    demo = render_demo_scenarios("simulation")

    f1, f2, f3 = st.columns(3)
    with f1:
        selected_asset, _selected_asset_type = render_common_asset_search(
            organization_id,
            "simulation_center",
            default=(demo or {}).get("Asset", st.session_state.get("enterprise_intelligence_asset", "AWS")),
        )
    scenario_type = f2.selectbox(
        "Scenario Type",
        list(scenario_catalog.keys()),
        index=list(scenario_catalog.keys()).index((demo or {}).get("Scenario Type", "Infrastructure"))
        if (demo or {}).get("Scenario Type") in scenario_catalog
        else 0,
    )
    scenario_options = scenario_catalog[scenario_type]
    scenario = f3.selectbox(
        "Scenario",
        scenario_options,
        index=scenario_options.index((demo or {}).get("Scenario", scenario_options[0]))
        if (demo or {}).get("Scenario") in scenario_options
        else 0,
    )

    f4, f5, f6 = st.columns(3)
    environment = f4.selectbox("Environment", ["Production", "UAT", "Development", "DR"])
    simulation_date = f5.date_input("Date", value=date.today())
    simulation_mode = f6.selectbox("Simulation Mode", ["Executive Decision", "Technical Validation", "Financial Review", "Change Approval"])

    if st.button("Run Simulation", type="primary", use_container_width=True):
        st.session_state["latest_simulation"] = SimulationService.run_simulation(
            asset=selected_asset,
            scenario_type=scenario_type,
            scenario=scenario,
            organization_id=organization_id,
            environment=environment,
            simulation_mode=simulation_mode,
            simulation_date=simulation_date.isoformat(),
            created_by=user.get("email") or st.session_state.get("email") or "unknown",
        )

    simulation = st.session_state.get("latest_simulation")
    if not simulation:
        st.divider()
        st.subheader("Active Simulations")
        if dashboard["runs"]:
            _show_table(dashboard["runs"], "No simulation history is available yet.")
        else:
            render_empty_state(
                "No simulation history is available yet.",
                "Run a demo scenario such as AWS outage, Oracle migration, SaaS license reduction, or Datadog replacement.",
            )
        return

    st.divider()
    st.subheader("Simulation Summary")
    st.write(simulation["executive_summary"])
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.metric("Applications", _number(simulation["business_impact"]["Applications Impacted"]))
    s2.metric("Services", _number(simulation["business_impact"]["Business Services"]))
    s3.metric("Departments", _number(simulation["business_impact"]["Departments"]))
    s4.metric("Customers", _number(simulation["business_impact"]["Customers"]))
    s5.metric("Revenue / Day", _currency(simulation["business_impact"]["Revenue Exposure Per Day"]))
    s6.metric("Risk", simulation["risk_analysis"]["level"])

    st.divider()
    r1, r2 = st.columns([2, 3])
    with r1:
        st.subheader("Risk Dashboard")
        st.plotly_chart(_risk_gauge(simulation["risk_analysis"]["score"], simulation["risk_analysis"]["level"]), use_container_width=True)
    with r2:
        st.subheader("Risk Breakdown")
        breakdown = _risk_breakdown_chart(simulation["risk_analysis"]["breakdown"])
        if breakdown:
            st.plotly_chart(breakdown, use_container_width=True)

    st.divider()
    f1, f2 = st.columns(2)
    with f1:
        st.subheader("Financial Analysis")
        financial = simulation["financial_analysis"]
        a, b, c = st.columns(3)
        a.metric("Current", _currency(financial["Current Annual Cost"]))
        b.metric("Projected", _currency(financial["Projected Annual Cost"]))
        c.metric("Savings", _currency(financial["Expected Annual Savings"]))
        d, e, f = st.columns(3)
        d.metric("Migration", _currency(financial["Migration Cost"]))
        e.metric("ROI", f"{financial['ROI %']:.1f}%")
        f.metric("Payback", f"{financial['Payback Months']:.1f} mo")
    with f2:
        st.subheader("AI Recommendation")
        st.write(simulation["ai_recommendation"]["AI Summary"])
        st.metric("Recommendation", simulation["ai_recommendation"]["Recommendation"])
        st.metric("Confidence", f"{simulation['ai_recommendation']['Confidence']}%")
        st.write(simulation["ai_recommendation"]["Alternative"])

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Approval Analysis")
        _show_table(simulation["approval_analysis"], "No approvals are required.")
    with c2:
        st.subheader("Technical Impact")
        _show_table([simulation["technical_impact"]], "No technical impact is available.")

    st.divider()
    st.subheader("Executive Report")
    _download_exports(simulation)

    st.divider()
    st.subheader("Simulation History")
    _show_table(dashboard["runs"], "No simulation history is available yet.")


if __name__ == "__main__":
    main()
