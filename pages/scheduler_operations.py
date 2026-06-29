from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.enterprise_scheduler_service import EnterpriseSchedulerService


st.set_page_config(page_title="Scheduler Operations", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "technical"}


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
        st.error("Scheduler Operations is available to platform operations roles.")
        st.stop()

    service = EnterpriseSchedulerService(get_current_organization_id())

    st.title("Scheduler Operations")
    st.caption("Priority queue, rate limiting, retry engine, dead-letter queue, and connector sync diagnostics.")

    actions = st.columns([1, 1, 1, 1])
    connector = actions[0].selectbox("Connector", ["AWS", "Azure", "GCP", "Microsoft 365", "ServiceNow", "GitHub", "Jira", "Datadog", "Splunk", "Prometheus", "Grafana"])
    if actions[1].button("Schedule", use_container_width=True):
        service.schedule_connector_sync(connector, schedule="Hourly", priority=3)
        st.success(f"{connector} sync queued.")
    if actions[2].button("Run Now", use_container_width=True):
        result = service.manual_run(connector)
        st.success(f"{connector} run status: {result.get('status')}")
    if actions[3].button("Simulate Failure", use_container_width=True):
        result = service.manual_run(connector, simulate_failure=True)
        st.warning(f"{connector} failure handled: {result.get('status')}")

    dashboard = service.get_scheduler_dashboard()
    kpis = dashboard["kpis"]

    cols = st.columns(8)
    cols[0].metric("Active", kpis["Active Jobs"])
    cols[1].metric("Queued", kpis["Queued Jobs"])
    cols[2].metric("Failed", kpis["Failed Jobs"])
    cols[3].metric("Retrying", kpis["Retrying Jobs"])
    cols[4].metric("Dead Letter", kpis["Dead Letter"])
    cols[5].metric("Success Rate", kpis["Success Rate"])
    cols[6].metric("Avg Duration", kpis["Average Duration"])
    cols[7].metric("Next Runs", kpis["Next Scheduled"])

    tabs = st.tabs(["Jobs", "Dead Letter", "History", "Rate Limits", "Dependencies", "Operations Log"])

    with tabs[0]:
        st.subheader("Active Jobs")
        _table(dashboard["active_jobs"], "No active jobs.")
        st.subheader("Queued Jobs")
        _table(dashboard["queued_jobs"], "No queued jobs.")
        st.subheader("Failed Jobs")
        _table(dashboard["failed_jobs"], "No failed jobs.")
        st.subheader("Retrying Jobs")
        _table(dashboard["retrying_jobs"], "No retrying jobs.")
        st.subheader("Next Scheduled Runs")
        _table(dashboard["next_scheduled_runs"], "No scheduled runs.")

    with tabs[1]:
        st.subheader("Dead-letter Queue")
        _table(dashboard["dead_letter_queue"], "No dead-letter jobs.")
        st.subheader("Retry Attempts")
        _table(dashboard["retry_attempts"], "No retry attempts.")

    with tabs[2]:
        st.subheader("Connector Sync History")
        _table(dashboard["connector_sync_history"], "No connector sync history.")
        st.subheader("Scheduler Health")
        _table(dashboard["health"], "No scheduler health data.")

    with tabs[3]:
        st.subheader("Connector Rate Limits")
        _table(dashboard["rate_limits"], "No rate limits configured.")

    with tabs[4]:
        st.subheader("Dependency Ordering")
        _table(dashboard["dependency_ordering"], "No dependency ordering configured.")

    with tabs[5]:
        st.subheader("Operations Log")
        _table(dashboard["operation_log"], "No scheduler operation log entries.")


if __name__ == "__main__":
    main()
