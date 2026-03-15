from datetime import date

import pandas as pd
import streamlit as st

from database.db import (
    can_manage_recommendation,
    list_recommendations,
    save_recommendation,
    update_recommendation_details,
    update_recommendation_status,
)


def _seed_optimization_recommendations(username):
    recommendations = [
        {
            "category": "rightsizing",
            "title": "Rightsize EC2 compute cluster",
            "description": "Several EC2 instances are consistently underutilized and can be moved to a smaller instance family.",
            "resource": "aws-prod:EC2",
            "estimated_savings": 4200,
            "priority": "high",
            "confidence_score": 0.9,
            "rationale": "Consistent under-utilization makes this a strong candidate for near-term savings without waiting for a new billing cycle.",
            "effort_level": "medium",
            "action_steps": [
                "Validate CPU and memory headroom for the target workloads.",
                "Select the next smaller instance class for each low-risk node.",
                "Resize in a maintenance window and verify performance after deployment.",
            ],
        },
        {
            "category": "database",
            "title": "Rightsize RDS instances",
            "description": "RDS CPU and memory utilization suggest the database tier is oversized for current demand.",
            "resource": "aws-prod:RDS",
            "estimated_savings": 2100,
            "priority": "high",
            "confidence_score": 0.84,
            "rationale": "Database sizing signals are stable enough that a controlled rightsize review is likely to return savings.",
            "effort_level": "medium",
            "action_steps": [
                "Review recent utilization, storage growth, and connection peaks.",
                "Select a smaller instance tier with rollback criteria defined.",
                "Apply the resize during a maintenance window and confirm service health.",
            ],
        },
        {
            "category": "storage",
            "title": "Remove unattached EBS volumes",
            "description": "Unused EBS volumes are accruing storage charges with no active attachment history.",
            "resource": "aws-dev:EBS",
            "estimated_savings": 800,
            "priority": "medium",
            "confidence_score": 0.94,
            "rationale": "Detached storage with no recent attachment history is one of the clearest low-risk cleanup opportunities.",
            "effort_level": "low",
            "action_steps": [
                "Confirm the volumes are detached and not part of a pending recovery workflow.",
                "Snapshot any data that must be retained before deletion.",
                "Delete the orphaned volumes and monitor the next billing cycle for the reduction.",
            ],
        },
        {
            "category": "lifecycle",
            "title": "Move cold S3 data to infrequent access",
            "description": "Older S3 objects are good candidates for lifecycle transitions to lower-cost storage classes.",
            "resource": "aws-analytics:S3",
            "estimated_savings": 1200,
            "priority": "medium",
            "confidence_score": 0.82,
            "rationale": "Object age and access patterns suggest lifecycle automation will reduce spend with limited operational risk.",
            "effort_level": "low",
            "action_steps": [
                "Identify buckets with old objects and low read frequency.",
                "Define lifecycle transitions that match retention and retrieval needs.",
                "Roll out the policy and validate storage-class mix over the next week.",
            ],
        },
    ]
    for item in recommendations:
        save_recommendation(
            username=username,
            category=item["category"],
            title=item["title"],
            description=item["description"],
            source="optimization_insights",
            resource=item["resource"],
            estimated_savings=item["estimated_savings"],
            priority=item["priority"],
            confidence_score=item["confidence_score"],
            rationale=item["rationale"],
            effort_level=item["effort_level"],
            action_steps=item["action_steps"],
        )


def render_optimization_insights_page():
    if not st.session_state.get("authenticated"):
        st.warning("Please login from the main page")
        st.stop()

    username = st.session_state.get("username", "guest")
    role = st.session_state.get("role", "user")
    st.title("Optimization Insights")
    st.write("Review cost-saving opportunities and manage them as workflow items.")

    opportunities = pd.DataFrame(
        {
            "Resource": ["EC2 Instances", "RDS Instances", "EBS Volumes", "S3 Storage"],
            "Potential Savings ($)": [4200, 2100, 800, 1200],
            "Priority": ["High", "High", "Medium", "Medium"],
        }
    )
    st.subheader("Top Optimization Opportunities")
    st.dataframe(opportunities, use_container_width=True, hide_index=True)

    if st.button("Save Opportunities to Workflow", use_container_width=True):
        _seed_optimization_recommendations(username)
        st.success("Optimization opportunities saved to the workflow inbox.")
        st.rerun()

    workflow_items = list_recommendations(username=username, source="optimization_insights", limit=20)
    if role not in {"admin", "premium"}:
        workflow_items = [item for item in workflow_items if can_manage_recommendation(item, username, action="view")]
    if not workflow_items:
        st.info("No optimization workflow items yet. Save the current opportunities to start tracking them.")
        return

    summary_col1, summary_col2, summary_col3 = st.columns(3)
    summary_col1.metric("Open", sum(1 for item in workflow_items if item.get("status") in {"new", "accepted"}))
    summary_col2.metric("Completed", sum(1 for item in workflow_items if item.get("status") == "completed"))
    summary_col3.metric(
        "Potential Savings",
        f"${sum(float(item.get('estimated_savings') or 0) for item in workflow_items):,.0f}",
    )

    for item in workflow_items:
        with st.container(border=True):
            can_edit_details = can_manage_recommendation(item, username, action="details")
            can_accept = can_manage_recommendation(item, username, action="accept")
            header_col, status_col = st.columns([3, 1])
            header_col.markdown(f"**{item['title']}**")
            header_col.caption(item.get("description") or "")
            status_col.metric("Status", item.get("status", "new").title())

            meta_col1, meta_col2, meta_col3 = st.columns(3)
            owner_value = meta_col1.text_input(
                "Owner",
                value=item.get("owner") or "",
                key=f"opt_owner_{item['id']}",
                disabled=role not in {"admin", "premium"},
            )
            priority_options = ["high", "medium", "low"]
            current_priority = str(item.get("priority") or "medium").lower()
            priority_value = meta_col2.selectbox(
                "Priority",
                priority_options,
                index=priority_options.index(current_priority) if current_priority in priority_options else 1,
                key=f"opt_priority_{item['id']}",
            )
            due_date_value = meta_col3.date_input(
                "Due date",
                value=pd.to_datetime(item.get("due_date")).date() if item.get("due_date") else date.today(),
                key=f"opt_due_{item['id']}",
                disabled=not can_edit_details,
            )

            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            if action_col1.button("Save Details", key=f"opt_save_{item['id']}", use_container_width=True, disabled=not can_edit_details):
                updated = update_recommendation_details(
                    recommendation_id=item["id"],
                    username=username,
                    owner=owner_value or None,
                    priority=priority_value,
                    due_date=due_date_value.isoformat() if due_date_value else None,
                    notes="Updated from optimization insights",
                )
                if updated:
                    st.rerun()
                st.error("You do not have permission to update this recommendation.")
            if action_col2.button("Accept", key=f"opt_accept_{item['id']}", use_container_width=True, disabled=not can_accept):
                updated = update_recommendation_status(
                    item["id"],
                    "accepted",
                    username=username,
                    owner=username if role not in {"admin", "premium"} else None,
                    notes="Accepted from optimization insights",
                )
                if updated:
                    st.rerun()
                st.error("You do not have permission to accept this recommendation.")
            if action_col3.button("Complete", key=f"opt_complete_{item['id']}", use_container_width=True, disabled=not can_edit_details):
                updated = update_recommendation_status(item["id"], "completed", username=username, notes="Completed from optimization insights")
                if updated:
                    st.rerun()
                st.error("You do not have permission to complete this recommendation.")
            if action_col4.button("Snooze", key=f"opt_snooze_{item['id']}", use_container_width=True, disabled=not can_edit_details):
                updated = update_recommendation_status(item["id"], "snoozed", username=username, notes="Snoozed from optimization insights")
                if updated:
                    st.rerun()
                st.error("You do not have permission to snooze this recommendation.")
