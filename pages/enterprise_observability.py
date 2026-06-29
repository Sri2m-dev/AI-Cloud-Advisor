from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.enterprise_observability_service import EnterpriseObservabilityService


st.set_page_config(page_title="Enterprise Observability", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical"}


def _table(rows: list[dict[str, Any]], empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    if role not in ALLOWED_ROLES:
        st.error("Enterprise Observability is available to enterprise technology roles.")
        st.stop()

    dashboard = EnterpriseObservabilityService.get_dashboard(get_current_organization_id())
    kpis = dashboard["kpis"]

    st.title("Enterprise Observability")
    st.caption("Live telemetry fabric for metrics, logs, traces, alerts, events, SLOs, APM, and AI correlation.")

    cols = st.columns(7)
    cols[0].metric("Connectors", kpis["Telemetry Connectors"])
    cols[1].metric("Gold", kpis["Gold Certified"])
    cols[2].metric("Records", f"{kpis['Telemetry Records']:,}")
    cols[3].metric("Critical Alerts", kpis["Critical Alerts"])
    cols[4].metric("Signals", kpis["Signals"])
    cols[5].metric("Correlations", kpis["Correlations"])
    cols[6].metric("Avg Health", f"{kpis['Average Health']}%")

    st.info(dashboard["executive_summary"])

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Observability Connectors")
        _table(dashboard["connectors"], "No observability connectors are available.")
    with right:
        st.subheader("AI Correlations")
        _table(dashboard["correlations"], "No telemetry correlations are available.")

    st.divider()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Smartscape Entities", f"{int((dashboard.get('smartscape') or {}).get('entities') or 0):,}")
    d2.metric("Davis Root Causes", f"{int((dashboard.get('davis_ai') or {}).get('root_causes') or 0):,}")
    d3.metric("Kubernetes Health", f"{float((dashboard.get('kubernetes') or {}).get('health') or 0):.1f}%")
    d4.metric("SLO Compliance", f"{float((dashboard.get('slo_health') or {}).get('average_compliance') or 0):.1f}%")

    nr = dashboard.get("new_relic") or {}
    st.divider()
    n1, n2, n3, n4, n5, n6 = st.columns(6)
    n1.metric("New Relic APM", f"{int((nr.get('apm') or {}).get('services') or 0):,}")
    n2.metric("NR Alerts", f"{int((nr.get('alerts') or {}).get('active') or 0):,}")
    n3.metric("NR Error Rate", f"{float((nr.get('errors') or {}).get('error_rate') or 0):.1f}%")
    n4.metric("NR Service Level", f"{float((nr.get('service_levels') or {}).get('average_compliance') or 0):.1f}%")
    n5.metric("Synthetic Failures", f"{int((nr.get('synthetics') or {}).get('failures') or 0):,}")
    n6.metric("Unhealthy Workloads", f"{int((nr.get('workloads') or {}).get('unhealthy') or 0):,}")

    splunk = dashboard.get("splunk") or {}
    st.divider()
    s1, s2, s3, s4, s5, s6, s7, s8 = st.columns(8)
    s1.metric("Splunk Indexes", f"{int((splunk.get('logs') or {}).get('indexes') or 0):,}")
    s2.metric("Log Events", f"{int((splunk.get('logs') or {}).get('events') or 0):,}")
    s3.metric("Searches", f"{int((splunk.get('searches') or {}).get('count') or 0):,}")
    s4.metric("Dashboards", f"{int((splunk.get('dashboards') or {}).get('count') or 0):,}")
    s5.metric("Alerts", f"{int((splunk.get('alerts') or {}).get('active') or 0):,}")
    s6.metric("ES Notables", f"{int((splunk.get('enterprise_security') or {}).get('notable_events') or 0):,}")
    s7.metric("SOAR Cases", f"{int((splunk.get('soar') or {}).get('cases') or 0):,}")
    s8.metric("Security Risk", (splunk.get("security_risk") or {}).get("level", "Unknown"))

    gold = dashboard.get("observability_kpis") or {}
    st.divider()
    st.subheader("Gold Observability KPIs")
    g1, g2, g3, g4, g5, g6 = st.columns(6)
    g1.metric("Prometheus Targets", f"{int(gold.get('Prometheus targets') or 0):,}")
    g2.metric("PromQL Health", gold.get("PromQL query health", "0.0%"))
    g3.metric("Alertmanager", f"{int(gold.get('Alertmanager alerts') or 0):,}")
    g4.metric("Recording Rules", f"{int(gold.get('Recording rules') or 0):,}")
    g5.metric("Kubernetes Pods", f"{int(gold.get('Kubernetes metrics') or 0):,}")
    g6.metric("Grafana Dashboards", f"{int(gold.get('Grafana dashboards') or 0):,}")
    g7, g8, g9, g10, g11 = st.columns(5)
    g7.metric("Grafana Alerts", f"{int(gold.get('Grafana alerts') or 0):,}")
    g8.metric("Loki Streams", f"{int(gold.get('Loki log streams') or 0):,}")
    g9.metric("Tempo Traces", f"{int(gold.get('Tempo traces') or 0):,}")
    g10.metric("Mimir Metrics", f"{int(gold.get('Mimir metrics') or 0):,}")
    g11.metric("SLO Compliance", gold.get("SLO compliance", "0.0%"))

    st.divider()
    t1, t2 = st.columns([1.2, 0.8])
    with t1:
        st.subheader("Telemetry Fabric")
        _table(dashboard["telemetry_records"], "No telemetry records are available.")
    with t2:
        st.subheader("Enterprise Event Bus")
        _table(dashboard["event_bus"], "No events are available.")


if __name__ == "__main__":
    main()
