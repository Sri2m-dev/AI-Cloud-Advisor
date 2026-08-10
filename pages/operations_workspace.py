from __future__ import annotations

# ruff: noqa: E402, I001

import os
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.session import init_session
from shared.styles import configure_page
from shared.auth import require_role
from components.sidebar_navigation import render_sidebar_navigation
from components.layout import render_page_header

from services.operations_workspace_service import (
    OperationsWorkspaceService,
)

configure_page(
    page_title="Operations Workspace",
    page_icon="⚙️",
)

init_session()

require_role(
    [
        "finance",
        "technical",
        "operations",
        "super_admin",
    ]
)

role = st.session_state.get("role", "Unknown")
organization_id = st.session_state.get("organization_id")
operations_workspace = OperationsWorkspaceService()
render_sidebar_navigation(role)

render_page_header("Operations Workspace", "Cloud Operations and Engineering Command Center")

# --------------------------------------------------
# SUMMARY KPIs
# --------------------------------------------------

summary = operations_workspace.get_summary(organization_id)

c1, c2, c3, c4 = st.columns(4)

c1.metric("Approvals", summary.get("approvals", 0))

c2.metric("Recommendations", summary.get("recommendations", 0))

c3.metric("Anomalies", summary.get("anomalies", 0))

c4.metric("Audit Events", summary.get("audit_events", 0))

st.divider()

# --------------------------------------------------
# APPROVAL REQUESTS
# --------------------------------------------------

st.subheader("Approval Requests")

approvals = operations_workspace.get_approval_requests(organization_id)

if approvals:
    st.dataframe(pd.DataFrame(approvals), use_container_width=True, hide_index=True)

else:
    st.info("No approval requests found.")

# --------------------------------------------------
# RECOMMENDATIONS
# --------------------------------------------------

st.subheader("Optimization Recommendations")

recommendations = operations_workspace.get_recommendations(organization_id)

if recommendations:
    st.dataframe(pd.DataFrame(recommendations), use_container_width=True, hide_index=True)

else:
    st.info("No recommendations available.")

# --------------------------------------------------
# COST ANOMALIES
# --------------------------------------------------

st.subheader("Cost Anomalies")

anomalies = operations_workspace.get_cost_anomalies(organization_id)

if anomalies:
    st.dataframe(pd.DataFrame(anomalies), use_container_width=True, hide_index=True)

else:
    st.info("No anomalies detected.")

# --------------------------------------------------
# AUDIT EVENTS
# --------------------------------------------------

st.subheader("Recent Audit Events")

audit_events = operations_workspace.get_audit_events(organization_id)

if audit_events:
    st.dataframe(pd.DataFrame(audit_events), use_container_width=True, hide_index=True)

else:
    st.info("No audit events found.")

# --------------------------------------------------
# CLOUD COST DATA
# --------------------------------------------------

st.subheader("Cloud Cost Records")

costs = operations_workspace.get_cloud_costs(organization_id)

if costs:
    cost_df = pd.DataFrame(costs)

    st.dataframe(cost_df.head(100), use_container_width=True, hide_index=True)

else:
    st.info("No cloud cost data available.")
