from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.enterprise_intelligence import render_demo_scenarios, render_empty_state, render_explanation_panel, render_intelligence_workspace
from components.sidebar_navigation import render_sidebar_navigation
from services.ai_reasoning_service import AIReasoningService


st.set_page_config(page_title="AI Reasoning Center", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical", "finance"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("AI Reasoning Center is available to leadership, architecture, finance, and operations roles.")
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


def _chain_chart(rows: list[dict[str, Any]]) -> go.Figure | None:
    if not rows:
        return None
    fig = go.Figure(
        go.Scatter(
            x=[row["Step"] for row in rows],
            y=[1 for _ in rows],
            mode="markers+text+lines",
            text=[row["Stage"] for row in rows],
            textposition="bottom center",
            marker={"size": 18, "color": "#1f77b4"},
            line={"width": 2},
        )
    )
    fig.update_yaxes(visible=False)
    fig.update_xaxes(visible=False)
    fig.update_layout(height=260, margin={"l": 8, "r": 8, "t": 16, "b": 56})
    return fig


def _confidence_chart(confidence: dict[str, Any]) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=float(confidence.get("Confidence") or 0),
            title={"text": "Confidence"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#1f77b4"},
                "steps": [
                    {"range": [0, 60], "color": "#ffadad"},
                    {"range": [60, 80], "color": "#fff3b0"},
                    {"range": [80, 100], "color": "#d8f3dc"},
                ],
            },
        )
    )
    fig.update_layout(height=300, margin={"l": 16, "r": 16, "t": 48, "b": 16})
    return fig


def _download_exports(reasoning: dict[str, Any]) -> None:
    safe_name = reasoning["asset"].lower().replace(" ", "_").replace("/", "_")
    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "Export PDF",
        data=AIReasoningService.build_pdf(reasoning),
        file_name=f"ai_reasoning_{safe_name}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    c2.download_button(
        "Export Excel",
        data=AIReasoningService.build_excel(reasoning),
        file_name=f"ai_reasoning_{safe_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    c3.download_button(
        "Export PowerPoint",
        data=AIReasoningService.build_powerpoint(reasoning),
        file_name=f"ai_reasoning_{safe_name}.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        use_container_width=True,
    )


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    dashboard = AIReasoningService.get_dashboard(organization_id)
    kpis = dashboard["kpis"]

    st.title("AI Reasoning Center")
    st.caption("Evidence-backed enterprise recommendations across policy, impact, simulation, approvals, risk, and financial context.")
    render_intelligence_workspace("AI Reasoning Center")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("AI Decisions Today", _number(kpis["AI Decisions Today"]))
    k2.metric("Accepted", _number(kpis["Recommendations Accepted"]))
    k3.metric("Avg Confidence", f"{float(kpis['Average Confidence'] or 0):.1f}%")
    k4.metric("Policy Violations", _number(kpis["Policy Violations"]))
    k5.metric("Simulations Reviewed", _number(kpis["Simulations Reviewed"]))
    k6.metric("Estimated Savings", _currency(kpis["Estimated Savings"]))

    st.divider()
    st.subheader("Ask AI")
    demo = render_demo_scenarios("reasoning")
    suggested = [
        "Can we decommission Oracle?",
        "Why is AWS critical?",
        "Should we migrate Oracle to PostgreSQL?",
        "Can we remove Datadog?",
        "What is the safest optimization?",
    ]
    cols = st.columns(len(suggested))
    selected = None
    for index, prompt in enumerate(suggested):
        if cols[index].button(prompt, use_container_width=True):
            selected = prompt
    question = st.text_input("Question", value=selected or (demo or {}).get("Question", "Can we migrate Oracle to PostgreSQL?"))

    if st.button("Run Reasoning", type="primary", use_container_width=True):
        st.session_state["latest_reasoning"] = AIReasoningService.reason(
            question=question,
            organization_id=organization_id,
            created_by=user.get("email") or st.session_state.get("email") or "unknown",
        )

    reasoning = st.session_state.get("latest_reasoning")
    if not reasoning:
        st.divider()
        st.subheader("Recent Reasoning History")
        if dashboard["history"]:
            _show_table(dashboard["history"], "No reasoning history is available yet.")
        else:
            render_empty_state(
                "No reasoning history is available yet.",
                "Ask a decision question or select a demo scenario to generate the first reasoning chain.",
            )
        return

    st.divider()
    st.subheader("Recommendation")
    st.write(reasoning["explanation"]["Why"])
    r1, r2, r3 = st.columns(3)
    r1.metric("Decision", reasoning["recommendation"]["Decision"])
    r2.metric("Primary Action", reasoning["recommendation"]["Primary Action"])
    r3.metric("Confidence", f"{reasoning['confidence']['Confidence']:.1f}%")

    st.divider()
    st.subheader("Reasoning Chain")
    chain = _chain_chart(reasoning["reasoning"])
    if chain:
        st.plotly_chart(chain, use_container_width=True)
    _show_table(reasoning["reasoning"], "No reasoning chain is available.")

    st.divider()
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Evidence")
        _show_table(reasoning["evidence"], "No evidence is available.")
        st.subheader("Policies Evaluated")
        _show_table(reasoning["policies"], "No policies were evaluated.")
    with right:
        st.subheader("Confidence Panel")
        st.plotly_chart(_confidence_chart(reasoning["confidence"]), use_container_width=True)
        st.write("Missing data")
        st.write(reasoning["confidence"]["Missing Data"] or ["None"])
        st.write("Assumptions")
        st.write(reasoning["confidence"]["Assumptions"])

    st.divider()
    st.subheader("Alternative Actions")
    _show_table(reasoning["alternatives"], "No alternatives were generated.")

    st.divider()
    st.subheader("Executive Summary")
    st.write(reasoning["expected_outcome"])
    _download_exports(reasoning)

    st.divider()
    with st.expander("Explainable AI Payload"):
        render_explanation_panel(reasoning["explanation"])
        st.json(reasoning["explanation"])


if __name__ == "__main__":
    main()
