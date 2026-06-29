from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id, get_current_user_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.workflow_execution_service import WorkflowExecutionService


st.set_page_config(page_title="AI Execution Center", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical", "finance"}
ACTION_ROLES = {"super_admin", "client_admin", "technical"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("AI Execution Center is available to operations, governance, CIO, executive, and finance roles.")
        st.stop()


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"${amount:,.2f}"


def _percent(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:.1f}%"


def _table(rows: list[dict[str, Any]], empty_message: str, money_columns: list[str] | None = None) -> None:
    if not rows:
        st.info(empty_message)
        return
    df = pd.DataFrame(rows)
    for column in money_columns or []:
        if column in df.columns:
            df[column] = df[column].apply(_money)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _action_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Action": row.get("action_id"),
            "Status": row.get("execution_status"),
            "Title": row.get("title"),
            "Team": row.get("assigned_team"),
            "Engineer": row.get("assigned_to"),
            "Readiness": row.get("automation_readiness"),
            "Progress": f"{int(row.get('execution_progress') or 0)}%",
            "Expected": row.get("expected_savings"),
            "Actual": row.get("actual_savings"),
            "ROI": f"{float(row.get('roi_realization_percent') or 0):.1f}%",
        }
        for row in rows
    ]


def _render_kanban(kanban: dict[str, list[dict[str, Any]]]) -> None:
    labels = {
        WorkflowExecutionService.STATUS_READY: "READY",
        WorkflowExecutionService.STATUS_ASSIGNED: "ASSIGNED",
        WorkflowExecutionService.STATUS_IN_PROGRESS: "IN PROGRESS",
        WorkflowExecutionService.STATUS_WAITING_VALIDATION: "VALIDATION",
        WorkflowExecutionService.STATUS_COMPLETED: "COMPLETED",
        WorkflowExecutionService.STATUS_FAILED: "FAILED",
    }
    columns = st.columns(3)
    for index, status in enumerate(WorkflowExecutionService.KANBAN_STATUSES):
        with columns[index % 3]:
            st.subheader(labels[status])
            rows = kanban.get(status) or []
            if not rows:
                st.caption("No actions")
            for row in rows[:6]:
                st.write(f"**{row.get('action_id')}**")
                st.write(row.get("title"))
                st.caption(
                    f"{row.get('assigned_team')} | {row.get('automation_readiness')} | "
                    f"{int(row.get('execution_progress') or 0)}%"
                )
                st.divider()


def _render_action_controls(action: dict[str, Any], organization_id: str, actor: str, can_act: bool) -> None:
    if not can_act:
        st.info("This role can inspect execution details but cannot change action state.")
        return

    st.subheader("Lifecycle Actions")
    with st.form("execution_action_form"):
        assigned_to = st.text_input("Assigned Engineer", value=str(action.get("assigned_to") or ""))
        assigned_team = st.text_input("Assigned Team", value=str(action.get("assigned_team") or ""))
        assigned_role = st.text_input("Assigned Role", value=str(action.get("assigned_role") or ""))
        progress = st.slider("Progress", 0, 100, int(action.get("execution_progress") or 0))
        evidence_url = st.text_input("Evidence URL", value=str(action.get("evidence_url") or ""))
        notes = st.text_area("Implementation Notes", value=str(action.get("implementation_notes") or ""))
        actual_savings = st.number_input("Actual Savings", min_value=0.0, value=float(action.get("actual_savings") or 0), step=100.0)
        actual_risk = st.number_input(
            "Actual Risk Reduction %",
            min_value=0.0,
            max_value=100.0,
            value=float(action.get("actual_risk_reduction") or 0),
            step=1.0,
        )
        submitted = st.form_submit_button("Update Progress")
        if submitted:
            WorkflowExecutionService.reassign_action(
                action["action_id"],
                assigned_to or None,
                assigned_team or None,
                assigned_role or None,
                organization_id,
                actor,
            )
            WorkflowExecutionService.update_progress(action["action_id"], progress, notes or None, organization_id, actor)
            if evidence_url:
                WorkflowExecutionService.upload_evidence(action["action_id"], evidence_url, notes or None, organization_id, actor)
            st.success("Action detail updated.")
            st.rerun()

    b1, b2, b3, b4 = st.columns(4)
    if b1.button("Assign", use_container_width=True):
        st.write(
            WorkflowExecutionService.assign_action(
                action["action_id"],
                assigned_to or None,
                assigned_team or None,
                assigned_role or None,
                organization_id,
                actor,
            )
        )
        st.rerun()
    if b2.button("Start", use_container_width=True):
        st.write(WorkflowExecutionService.start_execution(action["action_id"], organization_id, actor))
        st.rerun()
    if b3.button("Complete", use_container_width=True):
        st.write(
            WorkflowExecutionService.complete_execution(
                action["action_id"],
                notes or None,
                actual_savings,
                actual_risk,
                organization_id,
                actor,
            )
        )
        st.rerun()
    if b4.button("Validate", use_container_width=True):
        st.write(
            WorkflowExecutionService.validate_execution(
                action["action_id"],
                actor,
                actual_savings,
                actual_risk,
                evidence_url or None,
                organization_id,
                actor,
            )
        )
        st.rerun()

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Close", use_container_width=True):
        st.write(WorkflowExecutionService.close_action(action["action_id"], organization_id, actor))
        st.rerun()
    if c2.button("Pause", use_container_width=True):
        st.write(WorkflowExecutionService.pause_execution(action["action_id"], notes or None, organization_id, actor))
        st.rerun()
    if c3.button("Fail", use_container_width=True):
        st.write(WorkflowExecutionService.fail_action(action["action_id"], notes or None, organization_id, actor))
        st.rerun()
    if c4.button("Rollback", use_container_width=True):
        st.write(WorkflowExecutionService.rollback_action(action["action_id"], notes or None, organization_id, actor))
        st.rerun()


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    actor = get_current_user_id()
    can_act = role in ACTION_ROLES

    dashboard = WorkflowExecutionService.get_dashboard(organization_id)
    summary = dashboard["summary"]
    actions = dashboard["actions"]

    st.title("AI Execution Center")
    st.caption("Managed lifecycle for AI workflow actions: assignment, execution, validation, evidence, ROI, and closure.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Pending Execution", f"{int(summary.get('pending_execution') or 0):,}")
    k2.metric("Assigned", f"{int(summary.get('assigned') or 0):,}")
    k3.metric("In Progress", f"{int(summary.get('in_progress') or 0):,}")
    k4.metric("Waiting Validation", f"{int(summary.get('waiting_validation') or 0):,}")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Completed Today", f"{int(summary.get('completed_today') or 0):,}")
    k6.metric("Failed", f"{int(summary.get('failed') or 0):,}")
    k7.metric("Average Resolution", f"{float(summary.get('average_resolution_time_minutes') or 0):.1f} min")
    k8.metric("Automation", _percent(summary.get("automation_percent")))

    k9, k10 = st.columns(2)
    k9.metric("Realized Savings", _money(summary.get("realized_savings")))
    k10.metric("Risk Reduction", _percent(summary.get("risk_reduction")))

    st.divider()
    st.subheader("Kanban Board")
    _render_kanban(dashboard["kanban"])

    st.divider()
    st.subheader("Execution Queue")
    filter_cols = st.columns(5)
    status_filter = filter_cols[0].selectbox("Status", ["All", *WorkflowExecutionService.KANBAN_STATUSES])
    team_filter = filter_cols[1].selectbox("Team", ["All", *sorted({row.get("assigned_team") for row in actions if row.get("assigned_team")})])
    readiness_filter = filter_cols[2].selectbox(
        "Readiness",
        ["All", *sorted({row.get("automation_readiness") for row in actions if row.get("automation_readiness")})],
    )
    owner_filter = filter_cols[3].selectbox("Owner", ["All", *sorted({row.get("owner") for row in actions if row.get("owner")})])
    priority_filter = filter_cols[4].selectbox("Risk", ["All", *sorted({row.get("risk_level") for row in actions if row.get("risk_level")})])

    filtered = actions
    if status_filter != "All":
        filtered = [row for row in filtered if row.get("execution_status") == status_filter]
    if team_filter != "All":
        filtered = [row for row in filtered if row.get("assigned_team") == team_filter]
    if readiness_filter != "All":
        filtered = [row for row in filtered if row.get("automation_readiness") == readiness_filter]
    if owner_filter != "All":
        filtered = [row for row in filtered if row.get("owner") == owner_filter]
    if priority_filter != "All":
        filtered = [row for row in filtered if row.get("risk_level") == priority_filter]

    _table(_action_rows(filtered), "No execution actions match the selected filters.", ["Expected", "Actual"])

    if not actions:
        return

    st.divider()
    st.subheader("Action Detail")
    selected_action_id = st.selectbox("Action", [row["action_id"] for row in actions])
    selected = WorkflowExecutionService.get_action(selected_action_id, organization_id)
    if not selected:
        st.warning("Selected action could not be loaded.")
        return

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Current Status", selected.get("execution_status"))
    d2.metric("Assigned Team", selected.get("assigned_team"))
    d3.metric("Progress", f"{int(selected.get('execution_progress') or 0)}%")
    d4.metric("ROI Realization", _percent(selected.get("roi_realization_percent")))

    st.write(f"**{selected.get('title')}**")
    st.caption(selected.get("description") or "")

    detail_left, detail_right = st.columns(2)
    with detail_left:
        st.subheader("Expected vs Actual")
        _table(
            [
                {
                    "Expected Savings": selected.get("expected_savings"),
                    "Actual Savings": selected.get("actual_savings"),
                    "Expected Risk Reduction": selected.get("expected_risk_reduction"),
                    "Actual Risk Reduction": selected.get("actual_risk_reduction"),
                    "Duration Minutes": selected.get("execution_duration_minutes"),
                }
            ],
            "No ROI data is available.",
            ["Expected Savings", "Actual Savings"],
        )

        st.subheader("Evidence")
        st.write(selected.get("evidence_url") or "No evidence URL recorded.")
        st.write(selected.get("implementation_notes") or "No implementation notes recorded.")

    with detail_right:
        history = WorkflowExecutionService.get_execution_history(selected_action_id, organization_id)
        st.subheader("Execution Timeline")
        _table(
            [
                {
                    "Time": row.get("created_at"),
                    "From": row.get("from_status"),
                    "To": row.get("to_status"),
                    "Event": row.get("event_type"),
                    "Actor": row.get("actor"),
                    "Message": row.get("message"),
                }
                for row in history
            ],
            "No execution history is available yet.",
        )

    _render_action_controls(selected, organization_id, actor, can_act)


if __name__ == "__main__":
    main()
