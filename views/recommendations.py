from datetime import date

import pandas as pd
import streamlit as st

from database.db import (
    can_manage_recommendation,
    list_recommendation_events,
    list_recommendations,
    update_recommendation_details,
    update_recommendation_status,
)
from services.recommendation_workflow import seed_ai_advisor_recommendations


STATUS_OPTIONS = ["new", "accepted", "snoozed", "dismissed", "completed"]
PRIORITY_OPTIONS = ["high", "medium", "low"]


def render_recommendations_page():
    if not st.session_state.get("authenticated"):
        st.warning("Please login from the main page")
        st.stop()

    username = st.session_state.get("username", "guest")
    role = st.session_state.get("role", "user")
    action_col1, action_col2, action_col3 = st.columns([1, 1.2, 2.2])
    if action_col1.button("Back to Dashboard", key="recommendations_back_to_dashboard", use_container_width=True):
        st.session_state["selected_page"] = "Dashboard"
        st.rerun()
    if action_col2.button("Generate AI Recommendations", key="recommendations_generate_ai", use_container_width=True):
        seeded_recommendations = seed_ai_advisor_recommendations(username)
        st.success(f"Added {len(seeded_recommendations)} AI-generated workflow item(s) to AI Recommendations.")
        st.rerun()
    action_col3.caption("This is the full AI recommendation workflow surface. Generate and manage recommendations here; the dashboard only shows a compact summary.")
    st.title("AI Recommendations")
    st.write("Generate, review, assign, and manage AI-driven optimization recommendations in one place.")

    workflow_items = list_recommendations(username=username, limit=200)
    if role not in {"admin", "premium"}:
        workflow_items = [item for item in workflow_items if can_manage_recommendation(item, username, action="view")]
    if not workflow_items:
        st.info("No recommendations yet. Use Generate AI Recommendations to create workflow items here.")
        return

    open_items = [item for item in workflow_items if item.get("status") in {"new", "accepted", "snoozed"}]
    completed_items = [item for item in workflow_items if item.get("status") == "completed"]
    tracked_savings = sum(float(item.get("estimated_savings") or 0) for item in workflow_items)

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Open", len(open_items))
    metric_col2.metric("Completed", len(completed_items))
    metric_col3.metric("Assigned to Me", sum(1 for item in workflow_items if item.get("owner") == username))
    metric_col4.metric("Tracked Savings", f"${tracked_savings:,.0f}")

    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1.2])
    with filter_col1:
        selected_status = st.selectbox("Status", ["all", *STATUS_OPTIONS], key="recommendation_inbox_status")
    with filter_col2:
        selected_priority = st.selectbox("Priority", ["all", *PRIORITY_OPTIONS], key="recommendation_inbox_priority")
    with filter_col3:
        assigned_scope = st.selectbox(
            "Assignment",
            ["all", "assigned to me", "unassigned"],
            key="recommendation_inbox_assignment",
        )

    filtered_items = workflow_items
    if selected_status != "all":
        filtered_items = [item for item in filtered_items if item.get("status") == selected_status]
    if selected_priority != "all":
        filtered_items = [item for item in filtered_items if str(item.get("priority") or "medium").lower() == selected_priority]
    if assigned_scope == "assigned to me":
        filtered_items = [item for item in filtered_items if item.get("owner") == username]
    elif assigned_scope == "unassigned":
        filtered_items = [item for item in filtered_items if not item.get("owner")]

    summary_rows = [
        {
            "ID": item["id"],
            "Title": item.get("title"),
            "Category": item.get("category") or "general",
            "Status": item.get("status") or "new",
            "Priority": item.get("priority") or "medium",
            "Owner": item.get("owner") or "Unassigned",
            "Potential Savings ($/month)": float(item.get("estimated_savings") or 0),
            "Due": item.get("due_date") or "Not set",
            "Source": item.get("source") or "unknown",
        }
        for item in filtered_items
    ]
    if summary_rows:
        st.caption("All recommendation sources are unified here, including AI-generated, forecast, dashboard, and optimization workflow items.")
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No workflow items match the current filters.")
        return

    for item in filtered_items[:15]:
        title = item.get("title") or f"Recommendation {item['id']}"
        status = item.get("status") or "new"
        with st.expander(f"{title} [{status}]"):
            can_edit_details = can_manage_recommendation(item, username, action="details")
            can_accept = can_manage_recommendation(item, username, action="accept")
            st.write(item.get("description") or "No description available.")
            info_col1, info_col2, info_col3 = st.columns(3)
            info_col1.write(f"Category: {item.get('category') or 'general'}")
            info_col1.write(f"Source: {item.get('source') or 'unknown'}")
            info_col2.write(f"Potential Savings: ${float(item.get('estimated_savings') or 0):,.2f}")
            info_col2.write(f"Owner: {item.get('owner') or 'Unassigned'}")
            info_col3.write(f"Due: {item.get('due_date') or 'Not set'}")
            info_col3.write(f"Resource: {item.get('resource') or 'Not specified'}")

            edit_col1, edit_col2, edit_col3 = st.columns(3)
            owner_value = edit_col1.text_input(
                "Owner",
                value=item.get("owner") or "",
                key=f"rec_owner_{item['id']}",
                disabled=role not in {"admin", "premium"},
            )
            current_priority = str(item.get("priority") or "medium").lower()
            priority_value = edit_col2.selectbox(
                "Priority",
                PRIORITY_OPTIONS,
                index=PRIORITY_OPTIONS.index(current_priority) if current_priority in PRIORITY_OPTIONS else 1,
                key=f"rec_priority_{item['id']}",
            )
            due_date_value = edit_col3.date_input(
                "Due date",
                value=pd.to_datetime(item.get("due_date")).date() if item.get("due_date") else date.today(),
                key=f"rec_due_{item['id']}",
                disabled=not can_edit_details,
            )

            if can_edit_details:
                if st.button("Save Details", key=f"rec_save_{item['id']}", use_container_width=True):
                    updated = update_recommendation_details(
                        recommendation_id=item["id"],
                        username=username,
                        owner=owner_value or None,
                        priority=priority_value,
                        due_date=due_date_value.isoformat() if due_date_value else None,
                        notes="Updated from recommendations inbox",
                    )
                    if updated:
                        st.rerun()
                    st.error("You do not have permission to update this recommendation.")
            else:
                st.caption("You can only edit details for recommendations assigned to you.")

            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            if action_col1.button("Accept", key=f"rec_accept_{item['id']}", use_container_width=True, disabled=not can_accept):
                updated = update_recommendation_status(
                    item["id"],
                    "accepted",
                    username=username,
                    owner=username if role not in {"admin", "premium"} else None,
                    notes="Accepted from recommendations inbox",
                )
                if updated:
                    st.rerun()
                st.error("You do not have permission to accept this recommendation.")
            if action_col2.button("Snooze", key=f"rec_snooze_{item['id']}", use_container_width=True, disabled=not can_edit_details):
                updated = update_recommendation_status(item["id"], "snoozed", username=username, notes="Snoozed from recommendations inbox")
                if updated:
                    st.rerun()
                st.error("You do not have permission to snooze this recommendation.")
            if action_col3.button("Complete", key=f"rec_complete_{item['id']}", use_container_width=True, disabled=not can_edit_details):
                updated = update_recommendation_status(item["id"], "completed", username=username, notes="Completed from recommendations inbox")
                if updated:
                    st.rerun()
                st.error("You do not have permission to complete this recommendation.")
            dismiss_reason = action_col4.text_input(
                "Dismiss reason",
                value=item.get("dismiss_reason") or "",
                key=f"rec_dismiss_reason_{item['id']}",
                placeholder="Optional",
                disabled=not can_edit_details,
            )
            if st.button("Dismiss", key=f"rec_dismiss_{item['id']}", use_container_width=True, disabled=not can_edit_details):
                updated = update_recommendation_status(
                    item["id"],
                    "dismissed",
                    username=username,
                    dismiss_reason=dismiss_reason or None,
                    notes=dismiss_reason or "Dismissed from recommendations inbox",
                )
                if updated:
                    st.rerun()
                st.error("You do not have permission to dismiss this recommendation.")

            event_rows = list_recommendation_events(item["id"], limit=10)
            if event_rows:
                st.caption("Recent Activity")
                history_frame = pd.DataFrame(
                    [
                        {
                            "When": event.get("created_at"),
                            "User": event.get("username") or "system",
                            "Action": event.get("action"),
                            "Notes": event.get("notes") or "",
                        }
                        for event in event_rows
                    ]
                )
                st.dataframe(history_frame, use_container_width=True, hide_index=True)
