from datetime import date

import pandas as pd
import streamlit as st

from database.db import (
    can_manage_recommendation,
    is_recommendation_manager_role,
    list_recommendation_events,
    list_recommendations,
    list_users,
    update_recommendation_details,
    update_recommendation_status,
)
from services.recommendation_workflow import seed_ai_advisor_recommendations


STATUS_OPTIONS = ["new", "accepted", "snoozed", "dismissed", "completed"]
PRIORITY_OPTIONS = ["high", "medium", "low"]


def _format_confidence(value):
    if value is None or value == "":
        return "Not scored"
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "Not scored"


def _format_due_date(value):
    return value or "Not set"


def _badge_styles(kind, value):
    normalized = str(value or "").lower()
    if kind == "status":
        return {
            "new": ("#E8F1FB", "#155B9A"),
            "accepted": ("#E6F6EC", "#1E7A3C"),
            "snoozed": ("#F6F0E6", "#8A5A00"),
            "dismissed": ("#F8E8E8", "#9A2B2B"),
            "completed": ("#E7F5F3", "#0F6B5B"),
        }.get(normalized, ("#EEF2F6", "#44546A"))
    return {
        "high": ("#FBE7E7", "#A12622"),
        "medium": ("#FFF4D6", "#8A5A00"),
        "low": ("#EAF4EA", "#2F6B2F"),
    }.get(normalized, ("#EEF2F6", "#44546A"))


def _render_badge(column, text, kind):
    background, foreground = _badge_styles(kind, text)
    column.markdown(
        (
            f"<div style='display:inline-block;padding:0.18rem 0.5rem;border-radius:999px;"
            f"background:{background};color:{foreground};font-size:0.82rem;font-weight:600;'>"
            f"{text}</div>"
        ),
        unsafe_allow_html=True,
    )


def render_recommendations_page():
    if not st.session_state.get("authenticated"):
        st.warning("Please login from the main page")
        st.stop()

    st.markdown(
        """
        <style>
        [data-testid="stMetric"] {
            margin-bottom: 0.15rem;
        }
        .recommendations-helper {
            margin: 0.35rem 0 0.8rem 0;
            padding-bottom: 0.45rem;
            border-bottom: 1px solid #e5e7eb;
            color: #6b7280;
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    username = st.session_state.get("username", "guest")
    role = st.session_state.get("role", "user")
    can_manage = is_recommendation_manager_role(role)
    available_assignees = [user.get("username") for user in list_users(viewer_username=username) if user.get("username")]
    assignee_options = ["Unassigned", *available_assignees]
    header_col1, header_col2 = st.columns([4.2, 1.2])
    with header_col1:
        st.title("AI Recommendations")
        st.caption("Generate, review, assign, and manage AI-driven optimization recommendations in one place.")
    with header_col2:
        st.write("")
        st.write("")
        generate_clicked = st.button("Generate AI Recommendations", key="recommendations_generate_ai", use_container_width=True)
    if generate_clicked:
        seeded_recommendations = seed_ai_advisor_recommendations(username)
        st.success(f"Added {len(seeded_recommendations)} AI-generated workflow item(s) to AI Recommendations.")
        st.rerun()

    workflow_items = list_recommendations(username=username, limit=200)
    if not can_manage:
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

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1, 1, 1.2, 1.4])
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
    with filter_col4:
        search_term = st.text_input(
            "Search",
            value="",
            key="recommendation_inbox_search",
            placeholder="Title, category, source, owner...",
        ).strip().lower()

    st.markdown(
        '<div class="recommendations-helper">All recommendation sources are unified here, including AI-generated, dashboard, forecast, FinOps, and optimization workflow items.</div>',
        unsafe_allow_html=True,
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
    if search_term:
        filtered_items = [
            item
            for item in filtered_items
            if search_term in " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("category") or ""),
                    str(item.get("source") or ""),
                    str(item.get("owner") or ""),
                    str(item.get("description") or ""),
                ]
            ).lower()
        ]

    if not filtered_items:
        st.caption("No workflow items match the current filters.")
        return

    st.markdown("### Recommendation Queue")
    queue_items = filtered_items[:15]
    selected_id = st.session_state.get("recommendation_selected_id")
    if selected_id not in {item["id"] for item in queue_items} and queue_items:
        selected_id = queue_items[0]["id"]
        st.session_state["recommendation_selected_id"] = selected_id

    with st.container(border=True):
        header_cols = st.columns([0.45, 2.25, 0.95, 0.85, 0.8, 0.95, 0.9, 0.85, 0.9, 1.25, 0.65, 0.65])
        header_labels = ["ID", "Title", "Category", "State", "Prio", "Savings", "Conf", "Due", "Source", "Owner", "Set", "View"]
        for column, label in zip(header_cols, header_labels):
            column.markdown(f"**{label}**")

        for item in queue_items:
            can_edit_details = can_manage_recommendation(item, username, action="details")
            current_owner = item.get("owner") or "Unassigned"
            if current_owner not in assignee_options:
                assignee_options = [*assignee_options, current_owner]
            row_cols = st.columns([0.45, 2.25, 0.95, 0.85, 0.8, 0.95, 0.9, 0.85, 0.9, 1.25, 0.65, 0.65])
            row_cols[0].write(item["id"])
            row_cols[1].write(item.get("title") or f"Recommendation {item['id']}")
            row_cols[2].write(item.get("category") or "general")
            _render_badge(row_cols[3], (item.get("status") or "new").title(), "status")
            _render_badge(row_cols[4], (item.get("priority") or "medium").title(), "priority")
            row_cols[5].write(f"${float(item.get('estimated_savings') or 0):,.0f}")
            row_cols[6].write(_format_confidence(item.get("confidence_score")))
            row_cols[7].write(_format_due_date(item.get("due_date")))
            row_cols[8].write(item.get("source") or "unknown")
            owner_value = row_cols[9].selectbox(
                "Assignee",
                assignee_options,
                index=assignee_options.index(current_owner) if current_owner in assignee_options else 0,
                key=f"rec_owner_{item['id']}",
                disabled=not can_manage,
                label_visibility="collapsed",
            )
            if row_cols[10].button("Set", key=f"rec_save_{item['id']}", use_container_width=True, disabled=not can_edit_details):
                updated = update_recommendation_details(
                    recommendation_id=item["id"],
                    username=username,
                    owner=None if owner_value == "Unassigned" else owner_value,
                    clear_owner=owner_value == "Unassigned",
                    notes="Updated assignee from recommendation queue",
                )
                if updated:
                    st.rerun()
                st.error("You do not have permission to update this recommendation.")
            if row_cols[11].button("View", key=f"rec_open_{item['id']}", use_container_width=True):
                st.session_state["recommendation_selected_id"] = item["id"]
                st.rerun()

    selected_item = next((item for item in filtered_items if item["id"] == st.session_state.get("recommendation_selected_id")), None)
    if not selected_item:
        return

    st.markdown("### Recommendation Details")
    title = selected_item.get("title") or f"Recommendation {selected_item['id']}"
    status = selected_item.get("status") or "new"
    can_edit_details = can_manage_recommendation(selected_item, username, action="details")
    can_accept = can_manage_recommendation(selected_item, username, action="accept")

    with st.container(border=True):
        detail_col1, detail_col2, detail_col3, detail_col4 = st.columns([2.8, 1, 1, 1.1])
        detail_col1.markdown(f"**{title}**")
        detail_col1.caption(selected_item.get("description") or "No description available.")
        _render_badge(detail_col2, status.title(), "status")
        _render_badge(detail_col3, str(selected_item.get("priority") or "medium").title(), "priority")
        detail_col4.metric("Savings", f"${float(selected_item.get('estimated_savings') or 0):,.0f}")

        manage_col1, manage_col2, manage_col3 = st.columns(3)
        current_owner = selected_item.get("owner") or "Unassigned"
        if current_owner not in assignee_options:
            assignee_options = [*assignee_options, current_owner]
        owner_value = manage_col1.selectbox(
            "Assignee",
            assignee_options,
            index=assignee_options.index(current_owner) if current_owner in assignee_options else 0,
            key=f"rec_detail_owner_{selected_item['id']}",
            disabled=not can_manage,
        )
        current_priority = str(selected_item.get("priority") or "medium").lower()
        priority_value = manage_col2.selectbox(
            "Priority",
            PRIORITY_OPTIONS,
            index=PRIORITY_OPTIONS.index(current_priority) if current_priority in PRIORITY_OPTIONS else 1,
            key=f"rec_detail_priority_{selected_item['id']}",
        )
        due_date_value = manage_col3.date_input(
            "Due date",
            value=pd.to_datetime(selected_item.get("due_date")).date() if selected_item.get("due_date") else date.today(),
            key=f"rec_detail_due_{selected_item['id']}",
            disabled=not can_edit_details,
        )

        if can_edit_details:
            if st.button("Save Details", key=f"rec_detail_save_{selected_item['id']}", use_container_width=True):
                updated = update_recommendation_details(
                    recommendation_id=selected_item["id"],
                    username=username,
                    owner=None if owner_value == "Unassigned" else owner_value,
                    clear_owner=owner_value == "Unassigned",
                    priority=priority_value,
                    due_date=due_date_value.isoformat() if due_date_value else None,
                    notes="Updated from recommendation detail panel",
                )
                if updated:
                    st.rerun()
                st.error("You do not have permission to update this recommendation.")
        else:
            st.caption("Only admin and premium users can reassign recommendations. Other users can self-assign by accepting an unowned item.")

        info_col1, info_col2, info_col3, info_col4 = st.columns(4)
        info_col1.write(f"Category: {selected_item.get('category') or 'general'}")
        info_col1.write(f"Source: {selected_item.get('source') or 'unknown'}")
        info_col2.write(f"Potential Savings: ${float(selected_item.get('estimated_savings') or 0):,.2f}")
        info_col2.write(f"Owner: {selected_item.get('owner') or 'Unassigned'}")
        info_col3.write(f"Due: {_format_due_date(selected_item.get('due_date'))}")
        info_col3.write(f"Resource: {selected_item.get('resource') or 'Not specified'}")
        info_col4.write(f"Confidence: {_format_confidence(selected_item.get('confidence_score'))}")
        info_col4.write(f"Effort: {str(selected_item.get('effort_level') or 'TBD').title()}")

        rationale = selected_item.get("rationale")
        action_steps = selected_item.get("action_steps") or []
        if rationale:
            st.caption("Why this exists")
            st.write(rationale)
        if action_steps:
            st.caption("Recommended actions")
            for index, step in enumerate(action_steps, start=1):
                st.write(f"{index}. {step}")

        action_col1, action_col2, action_col3, action_col4 = st.columns(4)
        if action_col1.button("Accept", key=f"rec_accept_{selected_item['id']}", use_container_width=True, disabled=not can_accept):
            updated = update_recommendation_status(
                selected_item["id"],
                "accepted",
                username=username,
                owner=username if not can_manage else None,
                notes="Accepted from recommendations inbox",
            )
            if updated:
                st.rerun()
            st.error("You do not have permission to accept this recommendation.")
        if action_col2.button("Snooze", key=f"rec_snooze_{selected_item['id']}", use_container_width=True, disabled=not can_edit_details):
            updated = update_recommendation_status(selected_item["id"], "snoozed", username=username, notes="Snoozed from recommendations inbox")
            if updated:
                st.rerun()
            st.error("You do not have permission to snooze this recommendation.")
        if action_col3.button("Complete", key=f"rec_complete_{selected_item['id']}", use_container_width=True, disabled=not can_edit_details):
            updated = update_recommendation_status(selected_item["id"], "completed", username=username, notes="Completed from recommendations inbox")
            if updated:
                st.rerun()
            st.error("You do not have permission to complete this recommendation.")
        dismiss_reason = action_col4.text_input(
            "Dismiss reason",
            value=selected_item.get("dismiss_reason") or "",
            key=f"rec_dismiss_reason_{selected_item['id']}",
            placeholder="Optional",
            disabled=not can_edit_details,
        )
        if st.button("Dismiss", key=f"rec_dismiss_{selected_item['id']}", use_container_width=True, disabled=not can_edit_details):
            updated = update_recommendation_status(
                selected_item["id"],
                "dismissed",
                username=username,
                dismiss_reason=dismiss_reason or None,
                notes=dismiss_reason or "Dismissed from recommendations inbox",
            )
            if updated:
                st.rerun()
            st.error("You do not have permission to dismiss this recommendation.")

        event_rows = list_recommendation_events(selected_item["id"], limit=10)
        if event_rows:
            with st.expander("Recent Activity", expanded=False):
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
