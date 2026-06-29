from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.platform_health_service import PlatformHealthService


st.set_page_config(page_title="Platform Health Dashboard", layout="wide")

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
        st.error("Platform Health Dashboard is available to enterprise operations roles.")
        st.stop()

    service = PlatformHealthService(get_current_organization_id())
    force = st.sidebar.button("Run Full Health Check", use_container_width=True)
    dashboard = service.get_platform_health(force_refresh=force)
    kpis = dashboard["kpis"]

    st.title("Platform Health Dashboard")
    st.caption("Enterprise Test Harness and readiness control tower for Nexora platform operations.")

    cols = st.columns(5)
    cols[0].metric("Platform Readiness", f"{kpis['Platform Readiness']}%")
    cols[1].metric("Overall Health", kpis["Overall Health"])
    cols[2].metric("Last Validation", kpis["Last Validation"])
    cols[3].metric("Critical Issues", kpis["Critical Issues"])
    cols[4].metric("Warnings", kpis["Warnings"])

    st.info(dashboard["executive_summary"])

    cert_tab, components_tab, scheduler_tab, ai_tab, perf_tab, security_tab, quality_tab, readiness_tab, history_tab = st.tabs(
        [
            "Certification",
            "Components",
            "Scheduler",
            "AI Health",
            "Performance",
            "Security",
            "Data Quality",
            "Readiness",
            "History",
        ],
    )

    with cert_tab:
        cert = dashboard["connector_certification"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Certified", f"{cert['certified']} / {cert['total']}")
        c2.metric("Average Health", cert["average_health"])
        c3.metric("Score", f"{cert['score']}%")
        _table(cert["rows"], "No connector certification data is available.")

    with components_tab:
        st.subheader("Platform Components")
        _table(dashboard["components"], "No platform component health data is available.")

    with scheduler_tab:
        st.subheader("Scheduler")
        _table(dashboard["scheduler"], "No scheduler health data is available.")

    with ai_tab:
        st.subheader("AI Health")
        st.metric("AI Services Score", f"{dashboard['ai_health']['score']}%")
        _table(dashboard["ai_health"]["rows"], "No AI health data is available.")

    with perf_tab:
        st.subheader("Performance")
        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric("Performance Health", f"{dashboard['performance'].get('performance_health', dashboard['performance']['score'])}%")
        p2.metric("Database Latency", dashboard["performance"].get("database_latency", "-"))
        p3.metric("Cache Hit Ratio", dashboard["performance"].get("cache_hit_ratio", "-"))
        p4.metric("Scheduler Throughput", dashboard["performance"].get("scheduler_throughput", "-"))
        p5.metric("Event Bus Throughput", dashboard["performance"].get("event_bus_throughput", "-"))
        _table(dashboard["performance"]["metrics"], "No performance metrics are available.")
        st.subheader("Cache Metrics")
        _table(dashboard["performance"].get("cache_metrics", []), "No cache metrics are available.")

    with security_tab:
        st.subheader("Security Validation")
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Security Health", f"{dashboard['security'].get('security_health', dashboard['security']['score'])}%")
        s2.metric("Credential Health", f"{dashboard['security'].get('credential_health', 0)}%")
        s3.metric("RBAC", dashboard["security"].get("rbac", "Unknown"))
        s4.metric("Tenant Isolation", dashboard["security"].get("tenant_isolation", "Unknown"))
        s5.metric("Compliance", f"{dashboard['security'].get('compliance', 0)}%")
        _table(dashboard["security"]["rows"], "No security checks are available.")
        st.subheader("Connector Security")
        _table(dashboard["security"].get("connector_security", []), "No connector security records are available.")

    with quality_tab:
        st.subheader("Data Quality")
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Data Quality Score", f"{dashboard['data_quality']['score']}%")
        q2.metric("AI Trust", f"{dashboard['data_quality'].get('ai_trust_score', 0)}%")
        q3.metric("Knowledge Graph Integrity", f"{dashboard['data_quality'].get('knowledge_graph_integrity', 0)}%")
        q4.metric("Digital Twin Completeness", f"{dashboard['data_quality'].get('digital_twin_completeness', 0)}%")
        _table(dashboard["data_quality"]["rows"], "No data quality checks are available.")
        st.subheader("Validation Domains")
        _table(dashboard["data_quality"].get("domains", []), "No validation domains are available.")

    with readiness_tab:
        st.subheader("Platform Readiness Score")
        readiness = dashboard["readiness"]
        r1, r2 = st.columns(2)
        r1.metric("Score", f"{readiness['score']}%")
        r2.metric("Classification", readiness["classification"])
        st.subheader("Weighted Area Scores")
        rows = [
            {
                "Area": area,
                "Weight": f"{weight * 100:.0f}%",
                "Score": readiness["area_scores"].get(area, 0),
            }
            for area, weight in readiness["weights"].items()
        ]
        _table(rows, "No readiness scores are available.")

    with history_tab:
        st.subheader("Health Trend")
        selected = st.selectbox("Window", ["24 hours", "7 days", "30 days"])
        _table(dashboard["health_trend"].get(selected, []), "No health trend is available.")
        st.subheader("Platform Operations Log")
        _table(dashboard["persisted_operations_log"], "No platform operations log entries are available.")


if __name__ == "__main__":
    main()
