import os
import sys
import streamlit as st
from shared.session import init_session
from shared.styles import configure_page
from components.sidebar import render_sidebar

# Ensure repo root on path for local imports
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

configure_page(
    page_title="Audit Timeline | AI Cloud Advisor",
    page_icon=":spiral_calendar:",
)

# Initialize default session values
init_session()

from shared.auth import require_role

require_role([
    "executive",
    "technical",
    "finance",
    "super_admin",
])

render_sidebar(role=st.session_state.get("role", "Unknown"))

from components.layout import render_page_header, render_section
from components.tables import data_table
from services.audit_timeline_service import (
    get_approvals_assignments_timeline,
    get_governance_changes_timeline,
    get_workflow_transitions_timeline,
    get_ai_recommendation_actions_timeline,
    get_kpi_changes_timeline,
    get_alerts_reports_timeline,
)

org_id = st.session_state.get("organization_id")

render_page_header("Audit Timeline", "Track approvals, assignments, governance, and AI actions")

render_section("Approvals & Assignments")
approvals_assignments_resp = get_approvals_assignments_timeline(org_id)
if not approvals_assignments_resp["success"]:
    st.warning(f"Error: {approvals_assignments_resp.get('errors', 'Unknown error')}")
data_table(approvals_assignments_resp["data"])

render_section("Governance Changes")
governance_changes_resp = get_governance_changes_timeline(org_id)
if not governance_changes_resp["success"]:
    st.warning(f"Error: {governance_changes_resp.get('errors', 'Unknown error')}")
data_table(governance_changes_resp["data"])

render_section("Workflow Transitions")
workflow_transitions_resp = get_workflow_transitions_timeline(org_id)
if not workflow_transitions_resp["success"]:
    st.warning(f"Error: {workflow_transitions_resp.get('errors', 'Unknown error')}")
data_table(workflow_transitions_resp["data"])

render_section("AI Recommendation Actions")
ai_actions_resp = get_ai_recommendation_actions_timeline(org_id)
if not ai_actions_resp["success"]:
    st.warning(f"Error: {ai_actions_resp.get('errors', 'Unknown error')}")
data_table(ai_actions_resp["data"])

render_section("KPI Changes")
kpi_changes_resp = get_kpi_changes_timeline(org_id)
if not kpi_changes_resp["success"]:
    st.warning(f"Error: {kpi_changes_resp.get('errors', 'Unknown error')}")
data_table(kpi_changes_resp["data"])

render_section("Alerts & Reports")
alerts_reports_resp = get_alerts_reports_timeline(org_id)
if not alerts_reports_resp["success"]:
    st.warning(f"Error: {alerts_reports_resp.get('errors', 'Unknown error')}")
data_table(alerts_reports_resp["data"])

