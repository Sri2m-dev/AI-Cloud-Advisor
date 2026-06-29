from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id, get_current_user_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.execution_runner import ExecutionRunner
from services.workflow_execution_service import WorkflowExecutionService


st.set_page_config(page_title="Automation Center", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical"}
ACTION_ROLES = {"super_admin", "client_admin", "technical"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Automation Center is available to cloud operations and leadership roles.")
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


def _action_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Action": row.get("action_id"),
            "Status": row.get("execution_status"),
            "Title": row.get("title"),
            "Team": row.get("assigned_team"),
            "Provider Mode": row.get("automation_readiness"),
            "Risk": row.get("risk_level"),
            "Projected": row.get("expected_savings"),
            "Verified": row.get("actual_savings"),
            "Confidence": row.get("confidence"),
        }
        for row in rows
    ]


def _table(rows: list[dict[str, Any]], empty_message: str, money_columns: list[str] | None = None) -> None:
    if not rows:
        st.info(empty_message)
        return
    df = pd.DataFrame(rows)
    for column in money_columns or []:
        if column in df.columns:
            df[column] = df[column].apply(_money)
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    actor = get_current_user_id()
    can_act = role in ACTION_ROLES

    dashboard = ExecutionRunner.get_dashboard(organization_id)
    summary = dashboard["summary"]

    st.title("Automation Center")
    st.caption("Safe simulation, policy validation, provider-adapter execution, rollback readiness, and savings verification.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Ready for Execution", f"{int(summary.get('ready_for_execution') or 0):,}")
    k2.metric("Simulation Queue", f"{int(summary.get('simulation_queue') or 0):,}")
    k3.metric("Running Executions", f"{int(summary.get('running_executions') or 0):,}")
    k4.metric("Failed Executions", f"{int(summary.get('failed_executions') or 0):,}")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Completed", f"{int(summary.get('completed') or 0):,}")
    k6.metric("Rollback Queue", f"{int(summary.get('rollback_queue') or 0):,}")
    k7.metric("Projected Savings", _money(summary.get("projected_savings")))
    k8.metric("Verified Savings", _money(summary.get("verified_savings")))

    k9, k10, k11 = st.columns(3)
    k9.metric("Success Rate", _percent(summary.get("success_rate")))
    k10.metric("Rollback %", _percent(summary.get("rollback_percent")))
    k11.metric("Policy Compliance", _percent(summary.get("policy_compliance")))

    st.divider()
    tabs = st.tabs(["Simulation Queue", "Ready for Execution", "Running", "Failed", "Completed", "Rollback", "Execution Log"])
    with tabs[0]:
        _table(_action_rows(dashboard["simulation_queue"]), "No actions are waiting for simulation.", ["Projected", "Verified"])
    with tabs[1]:
        _table(_action_rows(dashboard["ready_for_execution"]), "No actions are ready for execution.", ["Projected", "Verified"])
    with tabs[2]:
        _table(_action_rows(dashboard["running_executions"]), "No safe executions are running.", ["Projected", "Verified"])
    with tabs[3]:
        _table(_action_rows(dashboard["failed_executions"]), "No executions have failed.", ["Projected", "Verified"])
    with tabs[4]:
        _table(_action_rows(dashboard["completed"]), "No actions have completed automation.", ["Projected", "Verified"])
    with tabs[5]:
        _table(_action_rows(dashboard["rollback_queue"]), "No actions are waiting for rollback.", ["Projected", "Verified"])
    with tabs[6]:
        _table(
            [
                {
                    "Workflow": row.get("workflow_id"),
                    "Status": row.get("status"),
                    "Provider": row.get("provider"),
                    "Resource": row.get("resource"),
                    "Projected": row.get("projected_savings"),
                    "Actual": row.get("actual_savings"),
                    "Variance": row.get("savings_variance_percent"),
                    "Executor": row.get("executor"),
                    "Created": row.get("created_at"),
                }
                for row in dashboard["logs"]
            ],
            "No execution log records are available yet.",
            ["Projected", "Actual"],
        )

    st.divider()
    all_actions = [
        *dashboard["simulation_queue"],
        *dashboard["ready_for_execution"],
        *dashboard["running_executions"],
        *dashboard["failed_executions"],
        *dashboard["completed"],
        *dashboard["rollback_queue"],
    ]
    st.subheader("Safe Automation Runner")
    if not all_actions:
        st.info("No workflow actions are currently eligible for automation operations.")
        return

    selected_id = st.selectbox("Workflow Action", [row["action_id"] for row in all_actions])
    selected = WorkflowExecutionService.get_action(selected_id, organization_id)
    if selected:
        st.write(f"**{selected.get('title')}**")
        st.caption(f"{selected.get('execution_status')} | {selected.get('assigned_team')} | {selected.get('automation_readiness')}")
        st.json(
            {
                "approval_status": selected.get("approval_status"),
                "risk": selected.get("risk_level"),
                "expected_savings": selected.get("expected_savings"),
                "actual_savings": selected.get("actual_savings"),
                "guardrails": (selected.get("payload") or {}).get("guardrails", []),
            }
        )

    if not can_act:
        st.info("This role can inspect automation readiness but cannot run simulation, execution, or rollback.")
        return

    a1, a2, a3 = st.columns(3)
    if a1.button("Run Simulation", use_container_width=True):
        st.write(ExecutionRunner.run_simulation(selected_id, organization_id, actor))
        st.rerun()
    if a2.button("Execute Safely", use_container_width=True):
        st.write(ExecutionRunner.execute_action(selected_id, organization_id, actor))
        st.rerun()
    if a3.button("Rollback", use_container_width=True):
        st.write(ExecutionRunner.rollback_action(selected_id, organization_id, actor))
        st.rerun()


if __name__ == "__main__":
    main()
