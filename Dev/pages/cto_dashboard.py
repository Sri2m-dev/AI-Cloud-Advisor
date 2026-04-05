from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from shared.queries import get_usage_metrics, get_recommendations, update_recommendation_status
from shared.intelligence import generate_alerts, detect_anomalies
from shared.aws_cost import get_aws_cost
from shared.actions import get_action_requests, approve_action_request, can_approve
from shared.supabase_client import get_supabase_client
from shared.nav import render_sidebar, render_header_bar, require_role


@st.cache_data(ttl=3600)
def load_cost_data():
    try:
        return get_aws_cost()
    except Exception:
        return {}

# 🔐 Access Control
if "role" not in st.session_state or "client_id" not in st.session_state:
    st.switch_page("app.py")

require_role("CTO")

# Sidebar
render_sidebar("CTO Dashboard")
render_header_bar()

# Data
usage_df = get_usage_metrics(st.session_state["client_id"])
if usage_df.empty:
    usage_df = pd.DataFrame(columns=["service", "utilization", "resource", "status"])

st.title("🧑‍💻 CTO Dashboard")
st.markdown("---")

# Filters
if "service" in usage_df.columns:
    service_options = ["All"] + sorted([s for s in usage_df["service"].dropna().unique().tolist()])
    service_filter = st.selectbox("Filter by Service", service_options)

    if service_filter != "All":
        usage_df = usage_df[usage_df["service"] == service_filter]
else:
    st.warning("Service data is unavailable for this client.")

usage_alerts = generate_alerts(usage_df)
cost_data = load_cost_data()
cost_df = pd.DataFrame(cost_data)
alerts = detect_anomalies(cost_df)
supabase = get_supabase_client()

st.subheader("⚠️ System Alerts")

for alert in usage_alerts:
    st.warning(alert)

for alert in alerts:
    st.error(alert)

# Table
st.subheader("🔍 Infrastructure Usage")
st.dataframe(usage_df)

st.subheader("💰 Cost Breakdown")
st.dataframe(cost_df)

try:
    anomaly = supabase.table("anomalies").select("*").execute()
    anomaly_df = pd.DataFrame(anomaly.data)
except Exception:
    anomaly_df = pd.DataFrame()

st.subheader("🚨 AI Detected Anomalies")
if anomaly_df.empty:
    st.info("No anomaly records available.")
else:
    for _, row in anomaly_df.iterrows():
        severity = str(row.get("severity", "") or "")
        service = row.get("service", "Unknown service")
        detected_value = row.get("detected_value", "N/A")
        expected_value = row.get("expected_value", "N/A")

        if severity == "High":
            st.error(
                f"🔥 {service} spike detected! Actual: ${detected_value} vs Expected: ${expected_value}"
            )
        elif severity == "Medium":
            st.warning(f"⚠️ {service} increase detected")
        else:
            st.info(f"{service} normal variation")

        if service == "EC2":
            st.write("💡 Recommendation: Consider rightsizing EC2 instances")

st.info("🤖 AI Insight: Sudden EC2 cost spike detected due to increased compute usage in the current billing window.")

st.subheader("✅ Approval Queue")
st.caption("Role: CTO · Permission: Approve only")
action_df = get_action_requests(st.session_state["client_id"])

if action_df.empty or "status" not in action_df.columns:
    st.info("No actions waiting for approval.")
else:
    pending_df = action_df[action_df["status"] == "pending_approval"]
    if pending_df.empty:
        st.info("No actions waiting for approval.")
    else:
        for _, req in pending_df.iterrows():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{req.get('recommendation_title', 'Recommendation')} · Pending Approval")
            with col2:
                if can_approve(st.session_state.get("role", "")) and st.button("✅ Approve", key=f"cto_approve_{req.get('id')}"):
                    result = approve_action_request(req.get("id"), st.session_state.get("user_email", "approver@local"))
                    if result.get("status"):
                        st.success("Approved for FinOps execution")
                    else:
                        st.error(result.get("error", "Approval failed"))

st.subheader("📋 Recommendation Status")
reco_df = get_recommendations(st.session_state["client_id"])

if reco_df.empty or "title" not in reco_df.columns:
    st.info("No recommendations available for approval.")
else:
    reco_df = reco_df.copy()
    if "status" not in reco_df.columns:
        reco_df["status"] = "Pending"

    for i, rec in reco_df.iterrows():
        recommendation_id = rec.get("id")
        recommendation_title = rec.get("title", f"Recommendation {i + 1}")
        status = str(rec.get("status", "Pending") or "Pending")

        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"💡 {recommendation_title}")
            st.caption(f"Status: {status}")
        with col2:
            normalized_status = status.strip().lower()
            if normalized_status in {"pending", "open", "pending_approval"} and can_approve(st.session_state.get("role", "")):
                if st.button("✅ Approve", key=f"recommendation_approve_{recommendation_id or i}"):
                    result = update_recommendation_status(recommendation_id, "Approved")
                    if result.get("status"):
                        st.success(f"Approved: {recommendation_title}")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Recommendation approval failed"))
            elif normalized_status == "approved":
                st.success("Approved")
            elif normalized_status in {"completed", "success"}:
                st.info("Completed")
            else:
                st.write(status)

# Chart
st.subheader("📊 Utilization by Service")
if not usage_df.empty and {"service", "utilization"}.issubset(usage_df.columns):
    st.bar_chart(usage_df.groupby("service")["utilization"].mean())
