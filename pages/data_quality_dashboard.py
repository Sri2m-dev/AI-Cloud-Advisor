from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.data_quality_service import DataQualityService


st.set_page_config(page_title="Data Quality Dashboard", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical"}


def _table(rows: list[dict[str, Any]] | dict[str, Any], empty: str) -> None:
    if isinstance(rows, dict):
        rows = [{"Metric": key, "Value": value} for key, value in rows.items()]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    if role not in ALLOWED_ROLES:
        st.error("Data Quality Dashboard is available to enterprise operations roles.")
        st.stop()

    service = DataQualityService(get_current_organization_id())
    force = st.sidebar.button("Run Data Quality Validation", use_container_width=True)
    dashboard = service.run_full_validation(persist=force or "data_quality_dashboard" not in st.session_state)
    st.session_state["data_quality_dashboard"] = dashboard
    kpis = dashboard["kpis"]

    st.title("Data Quality Dashboard")
    st.caption("Enterprise Data Quality, Fabric Validation, AI Trust Score, and validation event visibility.")

    cols = st.columns(7)
    cols[0].metric("Data Quality", f"{kpis['Overall Data Quality']}%")
    cols[1].metric("Health", kpis["Health"])
    cols[2].metric("Rules", kpis["Validation Rules"])
    cols[3].metric("Passed", kpis["Passed"])
    cols[4].metric("Failed", kpis["Failed"])
    cols[5].metric("Warnings", kpis["Warnings"])
    cols[6].metric("AI Trust", f"{kpis['AI Trust Score']}%")

    tabs = st.tabs(["Domains", "Violations", "Freshness", "AI Trust", "Recommendations", "Event Bus", "History"])

    with tabs[0]:
        st.subheader("Validation Domains")
        _table(dashboard["domains"], "No validation domains are available.")
        st.subheader("Validation Rules")
        _table(dashboard["rules"], "No validation rules are available.")

    with tabs[1]:
        st.subheader("Rule Violations")
        _table(dashboard["rule_violations"], "No data quality violations are open.")
        st.subheader("Knowledge Graph Validation")
        _table(dashboard["graph_validation"], "No graph validation records are available.")
        st.subheader("Cost Validation")
        _table(dashboard["cost_validation"], "No cost validation records are available.")

    with tabs[2]:
        st.subheader("Data Freshness")
        _table(dashboard["freshness"], "No freshness records are available.")
        st.subheader("Telemetry Validation")
        _table(dashboard["telemetry_validation"], "No telemetry validation records are available.")

    with tabs[3]:
        st.subheader("AI Trust Score")
        _table(dashboard["ai_trust_score"], "No AI Trust Score is available.")

    with tabs[4]:
        st.subheader("Recommendations")
        _table(dashboard["recommendations"], "No data quality recommendations are available.")

    with tabs[5]:
        st.subheader("Enterprise Event Bus")
        _table(dashboard["event_bus"], "No data quality events have been published.")

    with tabs[6]:
        st.subheader("Quality Trend")
        _table(dashboard["trend"], "No data quality trend is available.")
        st.subheader("Historical Snapshots")
        _table(dashboard.get("history", []), "No data quality history is available.")


if __name__ == "__main__":
    main()
