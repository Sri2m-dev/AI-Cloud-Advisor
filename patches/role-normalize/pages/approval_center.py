import os
import sys
import streamlit as st
from shared.session import init_session
from shared.styles import configure_page

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

configure_page(page_title="Approval Center | AI Cloud Advisor", page_icon=":white_check_mark:")

init_session()

from shared.auth import require_role

require_role([
    "executive",
    "technical",
    "super_admin",
])

from core.auth import logout_button
from components.layout import render_page_header, render_section
from components.recommendation_table import render_recommendation_table

logout_button()

username = st.session_state.get("user")
user_role = st.session_state.get("role")

from core.errors.error_handler import handle_error
from services.approval_service import get_approval_center_snapshot
from services.approval_service import get_workflow_transitions
from services.audit_service import get_audit_logs

try:
    render_page_header("Approval Center", "Orchestrate, approve, and audit all recommendations")

    def render_governance_workflow_engine():
        snapshot = get_approval_center_snapshot(username)

        # --- FILTERS ---
        st.markdown("### Filter Recommendations")
        filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(5)
        with filter_col1:
            priority_filter = st.selectbox("Priority", ["All", "High", "Medium", "Low"])
        with filter_col2:
            status_filter = st.selectbox("Status", ["All", "Pending", "Approved", "Rejected", "Escalated", "Completed", "Snoozed"])
        with filter_col3:
            rec_type_filter = st.selectbox("Recommendation Type", ["All", "Cost", "Security", "Tagging", "Idle", "Other"])
        with filter_col4:
            owner_filter = st.text_input("Assigned Owner", "")
        with filter_col5:
            cloud_filter = st.selectbox("Cloud Provider", ["All", "AWS", "Azure", "GCP"])

        def apply_filters(recs):
            if not recs:
                return []
            filtered = recs
            if priority_filter != "All":
                filtered = [r for r in filtered if str(r.get("priority", "")).lower() == priority_filter.lower()]
            if status_filter != "All":
                filtered = [r for r in filtered if str(r.get("status", "")).lower() == status_filter.lower()]
            if rec_type_filter != "All":
                filtered = [r for r in filtered if str(r.get("type", "")).lower() == rec_type_filter.lower()]
            if owner_filter.strip():
                filtered = [r for r in filtered if owner_filter.lower() in str(r.get("assigned_owner", "")).lower()]
            if cloud_filter != "All":
                filtered = [r for r in filtered if str(r.get("cloud", "")).lower() == cloud_filter.lower()]
            return filtered

        # Section: Pending Approvals
        render_section("Pending Approvals")
        pending_approvals = snapshot.get("pending_candidates", []) if snapshot else []
        filtered_pending = apply_filters(pending_approvals)
        if filtered_pending:
            render_recommendation_table(filtered_pending, empty_message="No pending approvals.")
        else:
            st.write("No pending approvals.")

        # Section: Assigned Recommendations
        render_section("Assigned Recommendations")
        assigned = snapshot.get("assigned_recommendations", []) if snapshot else []
        filtered_assigned = apply_filters(assigned)
        if filtered_assigned:
            render_recommendation_table(filtered_assigned, empty_message="No assigned recommendations.")
        else:
            st.write("No assigned recommendations.")

        # Section: Escalated Recommendations
        render_section("Escalated Recommendations")
        escalated = snapshot.get("escalated_recommendations", []) if snapshot else []
        filtered_escalated = apply_filters(escalated)
        if filtered_escalated:
            render_recommendation_table(filtered_escalated, empty_message="No escalated approvals.")
        else:
            st.write("No escalated recommendations.")

        # Section: Snoozed Recommendations
        render_section("Snoozed Recommendations")
        snoozed = snapshot.get("snoozed_recommendations", []) if snapshot else []
        filtered_snoozed = apply_filters(snoozed)
        if filtered_snoozed:
            render_recommendation_table(filtered_snoozed, empty_message="No snoozed recommendations.")
        else:
            st.write("No snoozed recommendations.")

        # Section: Completed Recommendations
        render_section("Completed Recommendations")
        completed = snapshot.get("completed_recommendations", []) if snapshot else []
        filtered_completed = apply_filters(completed)
        if filtered_completed:
            render_recommendation_table(filtered_completed, empty_message="No completed recommendations.")
        else:
            st.write("No completed recommendations.")

        # Section: Audit Timeline
        render_section("Audit Timeline")
        audit_logs = get_audit_logs(username)
        if audit_logs:
            render_recommendation_table(audit_logs, empty_message="No audit logs found.")
        else:
            st.write("No audit logs found.")

    def render_operational_approval_workspace():
        snapshot = get_approval_center_snapshot(username)
        pending_approvals = snapshot.get("pending_candidates", []) if snapshot else []
        render_section("Pending Approvals")
        if pending_approvals:
            render_recommendation_table(pending_approvals, empty_message="No pending approvals.")
        else:
            st.write("No pending approvals.")
        render_section("Approve / Reject / Assign / Escalate / Snooze")
        st.write("(Action buttons and workflow controls for each approval go here)")
        render_section("Assignment Queue")
        st.write("(Assignment queue logic to be implemented)")
        render_section("Workflow Transitions")
        st.info("Source: recommendation_transition_log")
        transitions = get_workflow_transitions(username)
        if transitions:
            render_recommendation_table(transitions, empty_message="No workflow transitions found.")
        else:
            st.write("No workflow transitions found.")

    def render_approval_view_by_role(role):
        role = (role or "").lower()
        if role == "ceo":
            # CEO: Executive Governance Summary (no workflow controls)
            snapshot = get_approval_center_snapshot(username)
            pending_approvals = snapshot.get("pending_candidates", []) if snapshot else []
            render_section("Executive Governance Summary")
            st.metric("Pending Approvals", len(pending_approvals))
            sla_breaches = [a for a in pending_approvals if a.get("sla_breached")] if pending_approvals else []
            st.metric("SLA Breaches", len(sla_breaches))
            render_section("Governance Trends")
            trends = snapshot.get("governance_trends") if snapshot else None
            if trends:
                render_recommendation_table(trends, empty_message="No governance trends data.")
            else:
                st.write("No governance trends data.")
            render_section("Approval Aging")
            if pending_approvals:
                aging = sorted(pending_approvals, key=lambda x: x.get("age_days", 0), reverse=True)
                render_recommendation_table(aging[:10], empty_message="No aging approvals.")
            else:
                st.write("No aging approvals.")
            render_section("Risk Summaries")
            risks = snapshot.get("risk_summaries") if snapshot else None
            if risks:
                render_recommendation_table(risks, empty_message="No risk summary data.")
            else:
                st.write("No risk summary data.")
        elif role in [
            "superadmin",
            "customeradmin",
            "finopsmanager",
            "approval",
            "governance",
            "leadership",
            "executive",
            "admin",
            "manager",
            "ops",
        ]:
            # Operations/Managers: Full workflow controls
            snapshot = get_approval_center_snapshot(username)
            pending_approvals = snapshot.get("pending_candidates", []) if snapshot else []
            render_section("Pending Approvals")
            if pending_approvals:
                render_recommendation_table(pending_approvals, empty_message="No pending approvals.")
            else:
                st.write("No pending approvals.")
            render_section("Approve / Reject / Assign / Escalate / Snooze")
            st.write("(Action buttons and workflow controls for each approval go here)")
            render_section("Assignment Queue")
            st.write("(Assignment queue logic to be implemented)")
            render_section("Workflow Transitions")
            st.info("Source: recommendation_transition_log")
            transitions = get_workflow_transitions(username)
            if transitions:
                render_recommendation_table(transitions, empty_message="No workflow transitions found.")
            else:
                st.write("No workflow transitions found.")
        else:
            st.write("Unknown or unauthorized role. Please contact your administrator.")

    render_approval_view_by_role(user_role)
except Exception as e:
    handle_error(e)




# --- Approval Workflow Table ---
from services.approval_service import get_approvals
import pandas as pd

st.markdown("---")
render_section("Approval Workflow Table")
approvals = get_approvals()
if approvals:
    df = pd.DataFrame(approvals)
    render_recommendation_table(df, empty_message="No approvals found.")
    selected = st.selectbox(
        "Select Recommendation",
        df["recommendation_id"]
    )
    action = st.selectbox(
        "Action",
        [
            "APPROVE",
            "REJECT",
            "ESCALATE"
        ]
    )
    if st.button("Submit Action"):
        st.success(
            f"{action} submitted successfully"
        )
else:
    st.info("No approvals found.")

render_section("Audit Logs")
org_id = st.session_state.get("organization_id")
audit_logs = get_audit_logs(org_id)
if audit_logs:
    render_recommendation_table(audit_logs, empty_message="No audit logs found.")
else:
    st.write("No audit logs found.")
