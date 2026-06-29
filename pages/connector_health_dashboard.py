from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.enterprise_connector_platform_service import EnterpriseConnectorPlatformService


st.set_page_config(page_title="Connector Health Dashboard", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Connector Health Dashboard is available to enterprise technology roles.")
        st.stop()


def _table(rows: list[dict[str, Any]], empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    dashboard = EnterpriseConnectorPlatformService.get_health_dashboard(organization_id)
    kpis = dashboard["kpis"]

    st.title("Connector Health Dashboard")
    st.caption("Authentication, sync freshness, data quality, and Enterprise Data Fabric observability.")

    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    k1.metric("Connectors", kpis["Total Connectors"])
    k2.metric("Connected", kpis["Connected"])
    k3.metric("Unhealthy", kpis["Unhealthy"])
    k4.metric("Fabric Records", kpis["Fabric Records"])
    k5.metric("Quality Events", kpis["Quality Events"])
    k6.metric("Avg Health", f"{kpis['Average Health']}%")
    k7.metric("Gold Certified", kpis.get("Gold Certified", 0))

    st.info(dashboard["executive_summary"])

    st.divider()
    left, right = st.columns([1.2, 0.8])
    with left:
        st.subheader("Connector Health")
        _table(dashboard["connectors"], "No connector health rows are available.")
    with right:
        st.subheader("Health by Connector")
        rows = pd.DataFrame(dashboard["connectors"])
        if not rows.empty:
            fig = px.bar(rows, x="Connector", y="Health", color="Status")
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    s1, s2 = st.columns(2)
    with s1:
        st.subheader("Recent Sync Runs")
        _table(dashboard["sync_runs"], "No sync runs are available.")
    with s2:
        st.subheader("Data Quality & Observability")
        _table(dashboard["quality_events"], "No quality events are available.")

    st.divider()
    r1, r2 = st.columns(2)
    with r1:
        st.subheader("Resources by Type")
        resource_rows = [
            {
                "Connector": row.get("connector_name"),
                "Resource Type": row.get("resource_type"),
                "Count": row.get("resource_count"),
                "Region": row.get("region"),
                "Health": row.get("health_score"),
            }
            for row in dashboard.get("resource_summary", [])
        ]
        _table(resource_rows, "No resource summary is available yet.")
    with r2:
        st.subheader("API Quota Usage")
        api_rows = [
            {
                "Connector": row.get("connector_name"),
                "API": row.get("api_name"),
                "Quota Used": f"{float(row.get('quota_used') or 0):.1f}%",
                "Calls": row.get("calls"),
                "Throttled": row.get("throttled_calls"),
                "Measured": row.get("measured_at"),
            }
            for row in dashboard.get("api_usage", [])
        ]
        _table(api_rows, "No API usage metrics are available yet.")

    st.divider()
    st.subheader("Connector Certification")
    certification_rows = [
        {
            "Connector": row.get("connector_name"),
            "Version": row.get("connector_version"),
            "Level": row.get("certification_level"),
            "Authentication": row.get("authentication"),
            "Records Synced": row.get("records_synced"),
            "Health": row.get("health_score"),
            "Coverage": ", ".join(name.title() for name, enabled in (row.get("coverage") or {}).items() if enabled),
        }
        for row in dashboard.get("certifications", [])
    ]
    _table(certification_rows, "No persisted certification reports are available yet.")

    h1, h2 = st.columns(2)
    with h1:
        st.subheader("Certification History")
        history_rows = [
            {
                "Connector": row.get("connector_name"),
                "Version": row.get("connector_version"),
                "Level": row.get("certification_level"),
                "Health": row.get("health_score"),
                "Certified": row.get("certified_at"),
            }
            for row in dashboard.get("certification_history", [])
        ]
        _table(history_rows, "No certification history is available yet.")
    with h2:
        st.subheader("Health Metrics")
        metric_rows = [
            {
                "Connector": row.get("connector_name"),
                "Health": row.get("health_score"),
                "Auth": row.get("authentication_status"),
                "Sync": row.get("sync_status"),
                "Freshness": row.get("data_freshness"),
                "Records": row.get("records_discovered"),
                "Duration": row.get("sync_duration"),
            }
            for row in dashboard.get("health_metrics", [])
        ]
        _table(metric_rows, "No health metric history is available yet.")

    st.divider()
    st.subheader("Enterprise Data Fabric")
    fabric_rows = [
        {
            "Fabric Key": row.get("fabric_key"),
            "Source": row.get("source_system"),
            "Entity Type": row.get("entity_type"),
            "Display Name": row.get("display_name"),
            "Quality": row.get("quality_score"),
            "Updated": row.get("updated_at") or row.get("created_at"),
        }
        for row in dashboard["fabric_records"]
    ]
    _table(fabric_rows, "No normalized fabric records are available.")


if __name__ == "__main__":
    main()
