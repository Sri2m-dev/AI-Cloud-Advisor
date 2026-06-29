from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page
from shared.layout import render_page_header
from components.sidebar_navigation import render_sidebar_navigation

from repositories.service_explorer_repository import (
    ServiceExplorerRepository,
)


configure_page(
    page_title="Cloud Strategy | Nexora",
    page_icon="☁️",
)

init_session()

require_role([
    "executive",
    "cio",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

render_page_header(
    "Cloud Strategy",
    "CIO view of cloud portfolio, provider mix, service concentration, and strategic optimization focus",
)

kpis = ServiceExplorerRepository.get_kpis()
service_data = ServiceExplorerRepository.get_service_classification()
optimization_data = ServiceExplorerRepository.get_optimization_opportunities()
anomaly_data = ServiceExplorerRepository.get_cost_anomalies()

service_df = pd.DataFrame(service_data or [])
optimization_df = pd.DataFrame(optimization_data or [])
anomaly_df = pd.DataFrame(anomaly_data or [])

total_spend = float(kpis.get("total_spend", 0) or 0)

provider_df = pd.DataFrame()

if not service_df.empty and {"cloud", "total_cost"}.issubset(service_df.columns):
    provider_df = (
        service_df
        .copy()
        .assign(
            total_cost=pd.to_numeric(
                service_df["total_cost"],
                errors="coerce",
            ).fillna(0)
        )
        .groupby("cloud", as_index=False)["total_cost"]
        .sum()
        .sort_values("total_cost", ascending=False)
    )

aws_spend = 0
azure_spend = 0
gcp_spend = 0

if not provider_df.empty:
    for _, row in provider_df.iterrows():
        cloud = str(row.get("cloud", "")).lower()
        value = float(row.get("total_cost", 0) or 0)

        if cloud == "aws":
            aws_spend = value
        elif cloud == "azure":
            azure_spend = value
        elif cloud == "gcp":
            gcp_spend = value

critical_services = int(kpis.get("critical_services", 0) or 0)
active_anomalies = int(kpis.get("active_anomalies", 0) or 0)
optimization_candidates = int(kpis.get("optimization_candidates", 0) or 0)

cloud_health_score = max(
    0,
    min(
        100,
        100 - (critical_services * 5) - (active_anomalies * 4),
    ),
)

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Cloud Spend", f"${total_spend:,.0f}")
k2.metric("AWS Spend", f"${aws_spend:,.0f}")
k3.metric("Azure Spend", f"${azure_spend:,.0f}")
k4.metric("GCP Spend", f"${gcp_spend:,.0f}")
k5.metric("Cloud Health Score", f"{cloud_health_score}%")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Cloud Portfolio Allocation")

    if not provider_df.empty:
        fig = px.pie(
            provider_df,
            names="cloud",
            values="total_cost",
            title="Cloud Spend by Provider",
            hole=0.4,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No provider spend data available.")

with right:
    st.subheader("Top Strategic Cost Drivers")

    if not service_df.empty and {"service_name", "total_cost"}.issubset(service_df.columns):
        top_services = (
            service_df
            .copy()
            .assign(
                total_cost=pd.to_numeric(
                    service_df["total_cost"],
                    errors="coerce",
                ).fillna(0)
            )
            .sort_values("total_cost", ascending=False)
            .head(8)
        )

        fig = px.bar(
            top_services,
            x="service_name",
            y="total_cost",
            color="cloud" if "cloud" in top_services.columns else None,
            title="Top Cloud Cost Drivers",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No service cost driver data available.")

st.divider()

st.subheader("Strategic Cloud Position")

primary_cloud = "N/A"
highest_service = "N/A"
optimization_focus = "N/A"

if not provider_df.empty:
    primary_cloud = str(provider_df.iloc[0]["cloud"]).upper()

if not service_df.empty and {"service_name", "total_cost"}.issubset(service_df.columns):
    highest_service = str(
        service_df
        .copy()
        .assign(
            total_cost=pd.to_numeric(
                service_df["total_cost"],
                errors="coerce",
            ).fillna(0)
        )
        .sort_values("total_cost", ascending=False)
        .iloc[0]["service_name"]
    )

if not optimization_df.empty and "service_name" in optimization_df.columns:
    optimization_focus = str(
        optimization_df
        .head(1)
        .iloc[0]["service_name"]
    )

c1, c2, c3, c4 = st.columns(4)

c1.metric("Primary Cloud", primary_cloud)
c2.metric("Critical Services", critical_services)
c3.metric("Highest Cost Driver", highest_service)
c4.metric("Optimization Focus", optimization_focus)

st.divider()

st.subheader("Cloud Risk Summary")

normal_count = 0
warning_count = 0
critical_count = 0
anomaly_count = 0

if not anomaly_df.empty:
    status_column = next(
        (
            column
            for column in ["anomaly_status", "status", "severity", "risk_level"]
            if column in anomaly_df.columns
        ),
        None,
    )

    if status_column:
        statuses = anomaly_df[status_column].fillna("").astype(str).str.lower()
        normal_count = int(statuses.isin(["normal", "low", "healthy"]).sum())
        warning_count = int(statuses.isin(["warning", "medium", "moderate"]).sum())
        critical_count = int(statuses.isin(["critical", "high", "sev1", "p1"]).sum())
        anomaly_count = int(statuses.isin(["anomaly", "spike"]).sum())

r1, r2, r3, r4, r5 = st.columns(5)

r1.metric("Normal", normal_count)
r2.metric("Warnings", warning_count)
r3.metric("Critical", critical_count)
r4.metric("Anomalies", anomaly_count)
r5.metric("Optimization Candidates", optimization_candidates)

st.divider()

st.subheader("CIO Cloud Strategy Narrative")

cloud_share = (
    aws_spend / total_spend * 100
    if total_spend and aws_spend
    else 0
)

st.info(
    f"""
Cloud spend currently stands at **${total_spend:,.0f}**.

The primary cloud provider is **{primary_cloud}**, with AWS contributing approximately **{cloud_share:.0f}%** of cloud spend where applicable.

The highest cost driver is **{highest_service}**, and the current optimization focus area is **{optimization_focus}**.

There are **{critical_services} critical services**, **{active_anomalies} active anomalies**, and **{optimization_candidates} optimization candidates** requiring technology leadership attention.
"""
)
