from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.performance_service import PerformanceService


st.set_page_config(page_title="Performance Dashboard", layout="wide")

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
        st.error("Performance Dashboard is available to enterprise operations roles.")
        st.stop()

    service = PerformanceService(get_current_organization_id())
    force = st.sidebar.button("Run Performance Assessment", use_container_width=True)
    dashboard = service.run_performance_assessment(persist=force or "performance_dashboard" not in st.session_state)
    st.session_state["performance_dashboard"] = dashboard
    kpis = dashboard["kpis"]

    st.title("Performance Dashboard")
    st.caption("Enterprise performance, scalability, cache, throughput, and benchmark visibility for Nexora platform operations.")

    cols = st.columns(5)
    cols[0].metric("Performance Health", f"{kpis['Performance Health']}%")
    cols[1].metric("Dashboard Load", kpis["Dashboard Load"])
    cols[2].metric("Copilot Response", kpis["Copilot Response"])
    cols[3].metric("Database Latency", kpis["Database Latency"])
    cols[4].metric("Cache Hit Ratio", kpis["Cache Hit Ratio"])

    tabs = st.tabs(["Metrics", "Throughput", "Cache", "Scalability", "Bottlenecks", "Benchmarks", "History"])

    with tabs[0]:
        st.subheader("Performance Metrics")
        _table(dashboard["metrics"], "No performance metrics are available.")
        st.subheader("Database Latency")
        _table(dashboard["slow_queries"], "No slow query data is available.")

    with tabs[1]:
        st.subheader("Connector Sync Throughput")
        _table(dashboard["throughput_metrics"], "No throughput metrics are available.")
        st.subheader("Telemetry Fabric Throughput")
        telemetry = [row for row in dashboard["throughput_metrics"] if row.get("Stream") in {"Telemetry Fabric", "Event Bus"}]
        _table(telemetry, "No telemetry throughput metrics are available.")

    with tabs[2]:
        st.subheader("Cache Efficiency")
        _table(dashboard["cache_metrics"], "No cache metrics are available.")

    with tabs[3]:
        st.subheader("Scalability Checks")
        _table(dashboard["load_tests"], "No scalability checks are available.")

    with tabs[4]:
        st.subheader("Bottlenecks")
        _table(dashboard["bottlenecks"], "No bottlenecks detected.")
        st.subheader("Recommendations")
        _table(dashboard["recommendations"], "No performance recommendations are available.")

    with tabs[5]:
        st.subheader("Benchmark Runner")
        if st.button("Run Benchmarks", use_container_width=True):
            st.session_state["performance_benchmarks"] = service.benchmark_major_modules(persist=True)
        _table(st.session_state.get("performance_benchmarks", []), "Run benchmarks to view module timings.")

    with tabs[6]:
        st.subheader("Performance Trend")
        _table(dashboard["trend"], "No performance trend is available.")
        st.subheader("Historical Runs")
        _table(dashboard.get("history", []), "No performance history is available.")


if __name__ == "__main__":
    main()
