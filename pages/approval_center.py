import os
import sys
import streamlit as st
from shared.session import init_session
from shared.styles import configure_page
from components.sidebar import render_sidebar
from auth.role_constants import normalize_role

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

render_sidebar(role=st.session_state.get("role", "Unknown"))

from components.layout import render_page_header, render_section
from components.recommendation_table import render_recommendation_table
from services.approval_service import (
    get_approvals,
    approve_request,
    reject_request,
    escalate_request,
    get_approval_center_snapshot,
    get_workflow_transitions,
)
from services.audit_service import get_org_events
import pandas as pd

username = st.session_state.get("user")
user_role = st.session_state.get("role")
org_id = st.session_state.get("organization_id")

from core.errors.error_handler import handle_error

try:
    render_page_header(
        "Approval Center",
        "Live approval workflow with audit logging"
    )

    # ==============================================================================
    # Live Approvals Section
    # ==============================================================================
    
    render_section("📋 Live Approvals from Supabase")
    
    # Fetch live data
    all_approvals = get_approvals(limit=200)
    
    if all_approvals:
        # Create interactive table with action buttons
        st.subheader(f"Total Approvals: {len(all_approvals)}")
        
        # Status distribution
        status_counts = {}
        for approval in all_approvals:
            status = approval.get("status", "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Display metrics
        metric_cols = st.columns(len(status_counts))
        for idx, (status, count) in enumerate(status_counts.items()):
            with metric_cols[idx]:
                st.metric(status, count)
        
        st.markdown("---")
        
        # Filter options
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            status_filter = st.selectbox(
                "Filter by Status",
                ["All"] + list(set(a.get("status") for a in all_approvals))
            )
        with filter_col2:
            priority_filter = st.selectbox(
                "Filter by Priority",
                ["All"] + list(set(a.get("priority") for a in all_approvals if a.get("priority")))
            )
        with filter_col3:
            search_title = st.text_input("Search by title", "")
        
        # Apply filters
        filtered_approvals = all_approvals
        if status_filter != "All":
            filtered_approvals = [a for a in filtered_approvals if a.get("status") == status_filter]
        if priority_filter != "All":
            filtered_approvals = [a for a in filtered_approvals if a.get("priority") == priority_filter]
        if search_title:
            filtered_approvals = [a for a in filtered_approvals if search_title.lower() in a.get("title", "").lower()]
        
        st.markdown(f"**Showing {len(filtered_approvals)} of {len(all_approvals)} approvals**")
        
        # Display approvals with action buttons
        for idx, approval in enumerate(filtered_approvals):
            approval_id = approval.get("id")
            title = approval.get("title", f"Approval {approval_id}")
            status = approval.get("status", "UNKNOWN")
            priority = approval.get("priority", "N/A")
            description = approval.get("description", "")
            created_by = approval.get("created_by", "Unknown")
            created_at = approval.get("created_at", "N/A")
            
            # Create expander for each approval
            with st.expander(f"📌 {title} - [{status}] - Priority: {priority}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Status**: {status}")
                    st.write(f"**Priority**: {priority}")
                    st.write(f"**Created by**: {created_by}")
                    st.write(f"**Created at**: {created_at}")
                    
                    if description:
                        st.write(f"**Description**: {description}")
                    
                    if approval.get("approval_comments"):
                        st.info(f"**Comments**: {approval.get('approval_comments')}")
                
                with col2:
                    st.write("")  # Spacing
                
                st.markdown("---")
                
                # Action buttons (only for PENDING approvals)
                if status == "PENDING":
                    action_col1, action_col2, action_col3 = st.columns(3)
                    
                    with action_col1:
                        comments = st.text_input(
                            "Approval comments (optional)",
                            key=f"comments_{idx}_{approval_id}"
                        )
                        if st.button("✅ Approve", key=f"approve_{idx}_{approval_id}"):
                            result = approve_request(
                                approval_id=approval_id,
                                approved_by=username,
                                comments=comments,
                                user_role=user_role,
                                org_id=org_id,
                            )
                            if "error" not in result:
                                st.success(f"✅ Approval '{title}' approved successfully!")
                                st.rerun()
                            else:
                                st.error(f"❌ Error approving: {result.get('error')}")
                    
                    with action_col2:
                        reason = st.text_input(
                            "Rejection reason",
                            key=f"reason_{idx}_{approval_id}"
                        )
                        if st.button("❌ Reject", key=f"reject_{idx}_{approval_id}"):
                            if reason:
                                result = reject_request(
                                    approval_id=approval_id,
                                    rejected_by=username,
                                    reason=reason,
                                    user_role=user_role,
                                    org_id=org_id,
                                )
                                if "error" not in result:
                                    st.success(f"❌ Approval '{title}' rejected!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Error rejecting: {result.get('error')}")
                            else:
                                st.warning("Please provide a rejection reason")
                    
                    with action_col3:
                        escalate_to = st.text_input(
                            "Escalate to user ID",
                            key=f"escalate_to_{idx}_{approval_id}"
                        )
                        reason = st.text_input(
                            "Escalation reason",
                            key=f"escalation_reason_{idx}_{approval_id}"
                        )
                        if st.button("⬆️ Escalate", key=f"escalate_{idx}_{approval_id}"):
                            if escalate_to and reason:
                                result = escalate_request(
                                    approval_id=approval_id,
                                    escalated_by=username,
                                    escalate_to=escalate_to,
                                    reason=reason,
                                    user_role=user_role,
                                    org_id=org_id,
                                )
                                if "error" not in result:
                                    st.success(f"⬆️ Approval '{title}' escalated!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Error escalating: {result.get('error')}")
                            else:
                                st.warning("Please provide escalation details")
                else:
                    st.info(f"This approval is already {status} and cannot be modified.")
    
    else:
        st.info("No approvals found in the system.")
    
    st.markdown("---")
    
    # ==============================================================================
    # Approval Statistics
    # ==============================================================================
    
    render_section("📊 Approval Statistics")
    
    pending = [a for a in all_approvals if a.get("status") == "PENDING"]
    approved = [a for a in all_approvals if a.get("status") == "APPROVED"]
    rejected = [a for a in all_approvals if a.get("status") == "REJECTED"]
    escalated = [a for a in all_approvals if a.get("status") == "ESCALATED"]
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("⏳ Pending", len(pending), delta=None)
    with stat_col2:
        st.metric("✅ Approved", len(approved), delta=None)
    with stat_col3:
        st.metric("❌ Rejected", len(rejected), delta=None)
    with stat_col4:
        st.metric("⬆️ Escalated", len(escalated), delta=None)
    
    st.markdown("---")
    
    # ==============================================================================
    # Audit Trail
    # ==============================================================================
    
    render_section("📝 Audit Trail")
    
    audit_events = get_org_events(org_id=org_id, limit=50)
    
    if audit_events:
        audit_df = pd.DataFrame([
            {
                "Timestamp": event.get("timestamp", "N/A"),
                "Event Type": event.get("event_type", "N/A"),
                "User": event.get("user_id", "N/A"),
                "Action": event.get("action", "N/A"),
                "Resource": event.get("resource_id", "N/A"),
                "Status": event.get("status", "N/A"),
            }
            for event in audit_events
        ])
        st.dataframe(audit_df, use_container_width=True, hide_index=True)
    else:
        st.info("No audit events found.")
    
    st.markdown("---")
    
    # ==============================================================================
    # Workflow Transitions Reference
    # ==============================================================================
    
    render_section("🔄 Workflow State Transitions")
    
    transitions = get_workflow_transitions()
    if transitions:
        transitions_df = pd.DataFrame(transitions)
        st.dataframe(transitions_df, use_container_width=True, hide_index=True)
    else:
        st.info("No workflow transitions available.")

except Exception as e:
    handle_error(e)
