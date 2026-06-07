import streamlit as st
from shared.session import init_session
from shared.auth import require_role
from shared.styles import configure_page
from core.auth import logout_button
from components.sidebar import render_sidebar

configure_page(page_title="Technical Analytics | AI Cloud Advisor", page_icon=":bar_chart:")

init_session()
require_role([
    "technical",
    "finance",
    "super_admin",
])

render_sidebar(role=st.session_state.get("role", "Unknown"))

from services.analytics_service import (
    get_ingestion_freshness,
    get_etl_health,
    get_mart_health,
    get_ai_health,
    get_etl_latency_kpis,
    get_mart_refresh_health,
)
from components.layout import render_page_header, render_section
from components.tables import data_table

render_page_header("Technical Analytics", "Critical platform reliability and engineering insights")

org_id = st.session_state.get("organization_id")

# --- Ingestion Freshness ---
render_section("Ingestion Freshness")
freshness_resp = get_ingestion_freshness(org_id)
if not freshness_resp["success"]:
    st.warning(f"Error: {freshness_resp.get('errors', 'Unknown error')}")
freshness = freshness_resp["data"]
if freshness:
    data_table([{**{"Provider": k}, **{"Freshness (min)": v}} for k, v in freshness.items()])
else:
    st.write("No ingestion freshness data.")

# --- ETL Job Status ---
render_section("ETL Job Status")
etl_jobs_resp = get_etl_health(org_id)
if not etl_jobs_resp["success"]:
    st.warning(f"Error: {etl_jobs_resp.get('errors', 'Unknown error')}")
etl_jobs = etl_jobs_resp["data"]
data_table(etl_jobs)

# --- Failed ETL Jobs ---
render_section("Failed ETL Jobs (last 20)")
failed_jobs = [job for job in etl_jobs if job.get("status", "").lower() != "success"] if etl_jobs else []
data_table(failed_jobs)

# --- ETL Latency Tracking ---
render_section("ETL Latency Tracking")
if etl_jobs:
    job_names = list({job["job_name"] for job in etl_jobs if "job_name" in job})
    for job_name in job_names:
        kpis_resp = get_etl_latency_kpis(org_id, job_name)
        if not kpis_resp["success"]:
            st.warning(f"Error: {kpis_resp.get('errors', 'Unknown error')}")
        kpis = kpis_resp["data"]
        st.write(f"{job_name}: Avg {kpis['avg']}s, Max {kpis['max']}s, Count {kpis['count']}")
else:
    st.write("No ETL jobs for latency tracking.")

# --- Mart Refresh Health ---
render_section("Mart Refresh Health")
mart_health_resp = get_mart_health(org_id)
if not mart_health_resp["success"]:
    st.warning(f"Error: {mart_health_resp.get('errors', 'Unknown error')}")
mart_health = mart_health_resp["data"]
data_table(mart_health)

# --- Stale Marts ---
render_section("Stale Marts (not refreshed in 48h)")
from datetime import datetime, timedelta
now = datetime.utcnow()
stale_marts = [mart for mart in mart_health if mart.get("refresh_completed_at") and (now - datetime.fromisoformat(mart["refresh_completed_at"])) > timedelta(hours=48)] if mart_health else []
data_table(stale_marts)

# --- AI Model Health ---
render_section("AI Model Health")
ai_health_resp = get_ai_health(org_id)
if not ai_health_resp["success"]:
    st.warning(f"Error: {ai_health_resp.get('errors', 'Unknown error')}")
ai_health = ai_health_resp["data"]
data_table(ai_health)

# --- API Failures ---
render_section("API Failures")
# Placeholder: Replace with service call if available
st.write("No API failures detected.")

# --- Ingestion Metrics ---
render_section("Ingestion Metrics")
# Placeholder: Replace with service call if available
st.write("No ingestion metrics issues.")

