import os
import sys
import streamlit as st
import pandas as pd

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.session import init_session
from shared.styles import configure_page
from shared.auth import require_role
from components.sidebar import render_sidebar
from components.layout import render_page_header

from services.reporting_service import (
    get_executive_summary,
    get_recommendation_summary,
    get_approval_summary,
    get_saas_summary,
    get_report_history,
)

configure_page(
    page_title="Reports Center",
    page_icon="📊"
)

init_session()

require_role([
    "executive",
    "technical",
    "finance",
    "super_admin",
])

render_sidebar(
    role=st.session_state.get(
        "role",
        "Unknown"
    )
)

render_page_header(
    "Reports Center",
    "Executive and Operational Reporting"
)

st.markdown("---")

# Executive Summary

st.subheader("Executive Summary")

summary = get_executive_summary()

if summary:

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Spend",
            summary.get("total_spend", 0)
        )

    with col2:
        st.metric(
            "Anomalies",
            summary.get("anomaly_count", 0)
        )

    with col3:
        st.metric(
            "Optimization",
            summary.get("optimization", 0)
        )

    with col4:
        st.metric(
            "Governance Score",
            summary.get("governance_score", 0)
        )

st.markdown("---")

# Recommendations

st.subheader("Recommendations")

recommendations = get_recommendation_summary()

if recommendations:
    st.dataframe(
        pd.DataFrame(
            recommendations.items(),
            columns=["Status", "Count"]
        ),
        use_container_width=True
    )

st.markdown("---")

# Approvals

st.subheader("Approval Summary")

approvals = get_approval_summary()

if approvals:
    st.dataframe(
        pd.DataFrame(
            approvals.items(),
            columns=["Status", "Count"]
        ),
        use_container_width=True
    )

st.markdown("---")

# SaaS

st.subheader("SaaS Summary")

saas = get_saas_summary()

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "Licensed Users",
        saas.get("total_users", 0)
    )

with col2:
    st.metric(
        "Total SaaS Spend",
        saas.get("total_cost", 0)
    )

st.markdown("---")

# Report History

st.subheader("Report History")

history = get_report_history()

if history:
    st.dataframe(
        pd.DataFrame(history),
        use_container_width=True
    )
else:
    st.info("No reports generated yet")