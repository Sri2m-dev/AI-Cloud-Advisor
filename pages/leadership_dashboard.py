from __future__ import annotations
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pandas as pd
import plotly.express as px
import streamlit as st
from shared.session import init_session
from shared.styles import configure_page
from components.sidebar import render_sidebar

configure_page(page_title="Leadership Dashboard | AI Cloud Advisor", page_icon=":briefcase:")

init_session()

from shared.auth import require_role

require_role([
    "executive",
    "super_admin",
])

render_sidebar(role=st.session_state.get("role", "Unknown"))

from components.charts import render_chart
from components.kpi_cards import render_kpi_row
from components.layout import render_page_header, render_section
from components.tables import data_table
from services.leadership_metrics import get_leadership_dashboard_metrics

organization_id = st.query_params.get("organization_id") or st.session_state.get("organization_id")

dashboard = get_leadership_dashboard_metrics(organization_id)
kpis = dashboard["kpis"]

render_page_header("Leadership Dashboard", "Organization-wide performance, risk, and customer health")

render_kpi_row(
    [
        {"label": "Total Spend", "value": f"${kpis['total_spend']:,.0f}"},
        {"label": "Savings Realized", "value": f"${kpis['savings_realized']:,.0f}"},
        {"label": "SLA Compliance", "value": f"{kpis['sla_compliance']:.1f}%"},
        {"label": "Security Score", "value": f"{kpis['security_score']:.1f}%"},
        {
            "label": "Customer Health",
            "value": f"{kpis['customer_health_score']:.1f}",
            "delta": kpis["customer_health_label"],
        },
    ]
)

savings = dashboard["savings"]
savings_df = pd.DataFrame(
    [
        {"category": "Identified", "amount": savings["identified"]},
        {"category": "Realized", "amount": savings["realized"]},
        {"category": "Pending", "amount": savings["pending"]},
    ]
)
if not savings_df.empty:
    fig_savings = px.bar(savings_df, x="category", y="amount", title="Savings Tracking")
    render_chart("Savings Tracking", fig_savings)
st.write(f"**Realization Rate:** {savings['realization_rate']:.1f}%")

sla_trend = dashboard["sla"]["trend"]
if sla_trend:
    fig_sla = px.line(pd.DataFrame(sla_trend), x="date", y="sla_compliance", title="SLA Compliance Trend")
    render_chart("SLA Compliance Trend", fig_sla)
else:
    st.info("No SLA trend data available.")
st.write(f"**SLA Breaches:** {dashboard['sla']['breaches']}")

security = dashboard["security"]
security_by_severity = dashboard["security_by_severity"]
if security_by_severity:
    fig_security = px.pie(pd.DataFrame(security_by_severity), names="severity", values="count", title="Open Findings by Severity")
    render_chart("Open Findings by Severity", fig_security)
else:
    st.info("No open security findings.")
st.write(f"**Critical Findings:** {security['critical']}")
st.write(f"**High Findings:** {security['high']}")

spend_by_cloud = dashboard["spend_by_cloud"]
if spend_by_cloud:
    fig_cloud = px.pie(pd.DataFrame(spend_by_cloud), names="cloud", values="spend", title="Spend by Cloud")
    render_chart("Spend by Cloud", fig_cloud)
else:
    st.info("No spend mix data available.")

render_section("Customer Health Scoring")
customer_health = dashboard["customer_health"]
st.write(f"**Health Status:** {customer_health['label']}")
st.write(f"**Platform Health Component:** {customer_health['platform_health']:.1f}%")

health_rows = dashboard["health_rows"]
if health_rows:
    data_table(health_rows)
else:
    st.info("No workspace health signals available.")

