import os
import sys
import streamlit as st
from shared.session import init_session
from shared.styles import configure_page
from components.sidebar import render_sidebar

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

configure_page(page_title="Operations Workspace | AI Cloud Advisor", page_icon=":gear:")

init_session()

from shared.auth import require_role

require_role([
    "finance",
    "technical",
    "super_admin",
])

render_sidebar(role=st.session_state.get("role", "Unknown"))

from components.layout import render_page_header, render_section

render_page_header("Operations Workspace", "Engineering and CloudOps command center")

org_id = st.session_state.get("organization_id")

render_section("Active Incidents")
# TODO: Implement or migrate get_user_profile, get_active_incidents, data_table, get_cost_anomalies, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.
# Commenting out undefined function calls for now.
# get_active_incidents(org_id)
# data_table(...)
st.warning("TODO: Implement or migrate get_active_incidents, data_table, get_cost_anomalies, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.")

render_section("Anomalies")
# TODO: Implement or migrate get_user_profile, get_active_incidents, data_table, get_cost_anomalies, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.
# Commenting out undefined function calls for now.
# get_cost_anomalies(org_id)
# data_table(...)
st.warning("TODO: Implement or migrate get_cost_anomalies, data_table, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.")

render_section("Untagged Resources")
# TODO: Implement or migrate get_user_profile, get_active_incidents, data_table, get_cost_anomalies, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.
# Commenting out undefined function calls for now.
# get_untagged_resources(org_id)
# data_table(...)
st.warning("TODO: Implement or migrate get_untagged_resources, data_table, get_idle_assets, get_automation_failures, get_ingestion_health if needed.")

render_section("Idle Assets")
# TODO: Implement or migrate get_user_profile, get_active_incidents, data_table, get_cost_anomalies, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.
# Commenting out undefined function calls for now.
# get_idle_assets(org_id)
# data_table(...)
st.warning("TODO: Implement or migrate get_idle_assets, data_table, get_untagged_resources, get_automation_failures, get_ingestion_health if needed.")

render_section("Automation Failures")
# TODO: Implement or migrate get_user_profile, get_active_incidents, data_table, get_cost_anomalies, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.
# Commenting out undefined function calls for now.
# get_automation_failures(org_id)
# data_table(...)
st.warning("TODO: Implement or migrate get_automation_failures, data_table, get_untagged_resources, get_idle_assets, get_ingestion_health if needed.")

render_section("Ingestion Health")
# TODO: Implement or migrate get_user_profile, get_active_incidents, data_table, get_cost_anomalies, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.
# Commenting out undefined function calls for now.
# get_ingestion_health(org_id)
# data_table(...)
st.warning("TODO: Implement or migrate get_ingestion_health, data_table, get_untagged_resources, get_idle_assets, get_automation_failures, get_ingestion_health if needed.")

