from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.learning_engine import LearningEngine


st.set_page_config(page_title="Learning Analytics", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "finance", "technical"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Learning Analytics is available to leadership, finance, and operations roles.")
        st.stop()


def _pct(value: Any) -> str:
    try:
        return f"{float(value or 0):,.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _money(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _show_table(rows: list[dict[str, Any]], empty_message: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty_message)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    dashboard = LearningEngine.get_learning_dashboard(organization_id)
    kpis = dashboard["kpis"]

    st.title("Learning Analytics")
    st.caption("Outcome feedback, confidence learning, agent scorecards, workflow improvements, and reusable knowledge memory.")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Learning Score", f"{dashboard['learning_score']:.1f}")
    k2.metric("Accepted", kpis["Recommendations Accepted"])
    k3.metric("Rejected", kpis["Recommendations Rejected"])
    k4.metric("Savings Accuracy", _pct(kpis["Average Savings Accuracy"]))
    k5.metric("Workflow Success", _pct(kpis["Workflow Success Rate"]))
    k6.metric("Rollback Rate", _pct(kpis["Rollback Rate"]))

    st.info(dashboard["executive_summary"])

    st.divider()
    left, right = st.columns([1.25, 0.9])
    with left:
        st.subheader("Outcome Analysis")
        outcomes = [
            {
                **row,
                "Expected Savings": _money(row["Expected Savings"]),
                "Actual Savings": _money(row["Actual Savings"]),
                "Variance": _money(row["Variance"]),
                "Prediction Accuracy": _pct(row["Prediction Accuracy"]),
                "Recommendation Quality": _pct(row["Recommendation Quality"]),
                "Operational Success": _pct(row["Operational Success"]),
            }
            for row in dashboard["outcomes"]
        ]
        _show_table(outcomes, "No learning outcomes are available.")
    with right:
        st.subheader("Recommendation Trends")
        feedback = pd.DataFrame(dashboard["recommendation_feedback"])
        if not feedback.empty:
            trend = feedback.groupby("Status", dropna=False).size().reset_index(name="Count")
            fig = px.bar(trend, x="Status", y="Count", color="Status")
            st.plotly_chart(fig, use_container_width=True)
        _show_table(dashboard["recommendation_feedback"], "No recommendation feedback is available.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Agent Scorecards")
        _show_table(dashboard["agent_scorecards"], "No agent scorecards are available.")
        scores = pd.DataFrame(dashboard["agent_scorecards"])
        if not scores.empty:
            fig = px.bar(scores, x="Agent", y="Learning Score", color="Execution Success")
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("Confidence Improvement")
        confidence = pd.DataFrame(dashboard["confidence_trend"])
        if not confidence.empty:
            fig = px.line(confidence, x="Measured At", y="After", color="Metric", markers=True)
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
        _show_table(dashboard["confidence_trend"], "No confidence history is available.")

    st.divider()
    w1, w2 = st.columns(2)
    with w1:
        st.subheader("Workflow Learning")
        _show_table(dashboard["workflow_feedback"], "No workflow feedback is available.")
    with w2:
        st.subheader("Template Improvements")
        _show_table(dashboard["template_improvements"], "No template improvements are available.")

    st.divider()
    i1, i2 = st.columns(2)
    with i1:
        st.subheader("Learning Insights")
        for insight in dashboard["learning_insights"]:
            st.write(f"**{insight['Title']}**")
            st.write(insight["Insight"])
            st.caption(insight["Recommended Action"])
        if not dashboard["learning_insights"]:
            st.info("No learning insights are available.")
    with i2:
        st.subheader("Knowledge Memory")
        for memory in dashboard["knowledge_memory"]:
            st.write(f"- {memory}")
        if not dashboard["knowledge_memory"]:
            st.info("No knowledge memory has been captured yet.")


if __name__ == "__main__":
    main()
