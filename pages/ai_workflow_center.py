from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.ai_workflow_service import AIWorkflowService


st.set_page_config(page_title="AI Workflow Center", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive"}
ACTION_ROLES = {"super_admin", "client_admin"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("AI Workflow Center is available to Super Admins, Client Admins, CIOs, and Executives.")
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
            "Action ID": row.get("action_id"),
            "Decision": row.get("decision_id"),
            "Recommendation": row.get("recommendation_id"),
            "Type": row.get("action_type"),
            "Title": row.get("title"),
            "Owner": row.get("owner"),
            "Approval": row.get("approval_status"),
            "Execution": row.get("execution_status"),
            "Automation": row.get("automation_eligible"),
            "Risk": row.get("risk_level"),
            "Confidence": row.get("confidence"),
            "Expected Savings": row.get("expected_savings"),
            "Risk Reduction": row.get("expected_risk_reduction"),
        }
        for row in rows
    ]


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    can_act = role in ACTION_ROLES

    st.title("AI Workflow Center")
    st.caption("Approval-first workflow queue for AI decisions, action candidates, execution status, and audit history.")

    left, right = st.columns([0.72, 0.28])
    with left:
        if st.button("Generate Workflow Actions", use_container_width=True):
            result = AIWorkflowService.generate_workflow_actions(organization_id)
            st.success(
                f"Generated {result.get('workflow_actions', 0)} workflow actions. "
                f"Persistence: {result.get('persistence', {}).get('status')}"
            )
    with right:
        st.caption("Executives and CIOs have read-only access. Super Admins and Client Admins can approve, reject, and execute.")

    dashboard = AIWorkflowService.get_dashboard(organization_id)
    summary = dashboard["summary"]

    st.subheader("Workflow Summary")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Actions", f"{int(summary.get('total_actions') or 0):,}")
    k2.metric("Pending Approval", f"{int(summary.get('pending_approval') or 0):,}")
    k3.metric("Approved", f"{int(summary.get('approved') or 0):,}")
    k4.metric("Rejected", f"{int(summary.get('rejected') or 0):,}")
    k5.metric("Executed", f"{int(summary.get('executed') or 0):,}")

    k6, k7, k8, k9 = st.columns(4)
    k6.metric("Failed", f"{int(summary.get('failed') or 0):,}")
    k7.metric("Automation Eligible", f"{int(summary.get('automation_eligible') or 0):,}")
    k8.metric("Expected Savings", _money(summary.get("expected_savings")))
    k9.metric("Expected Risk Reduction", _percent(summary.get("expected_risk_reduction")))

    st.divider()
    pending_rows = dashboard["pending_approval_queue"]
    st.subheader("Pending Approval Queue")
    _table(_action_rows(pending_rows), "No workflow actions are pending approval.", ["Expected Savings"])

    if pending_rows:
        selected_action = st.selectbox("Selected Action", [row["action_id"] for row in pending_rows])
        selected = next((row for row in pending_rows if row["action_id"] == selected_action), None)
        if selected:
            st.json(
                {
                    "action_id": selected.get("action_id"),
                    "guardrails": (selected.get("payload") or {}).get("guardrails", []),
                    "audit_safe": (selected.get("payload") or {}).get("audit_safe"),
                    "payload": selected.get("payload"),
                }
            )

        if can_act:
            a1, a2, a3 = st.columns(3)
            if a1.button("Approve", use_container_width=True):
                st.success(AIWorkflowService.approve_action(selected_action, organization_id).get("message"))
                st.rerun()
            reason = st.text_input("Reject Reason", placeholder="Optional reason for rejection")
            if a2.button("Reject", use_container_width=True):
                st.warning(AIWorkflowService.reject_action(selected_action, reason or None, organization_id).get("message"))
                st.rerun()
            if a3.button("Execute", use_container_width=True):
                result = AIWorkflowService.execute_action(selected_action, organization_id)
                if result.get("status") == "SUCCESS":
                    st.success(result.get("message"))
                else:
                    st.error(result.get("message"))
                st.rerun()
        else:
            st.info("This role can review workflow actions but cannot approve, reject, or execute them.")

    st.divider()
    t1, t2 = st.columns(2)
    with t1:
        st.subheader("Auto-Remediation Candidates")
        _table(
            _action_rows(dashboard["auto_remediation_candidates"]),
            "No auto-remediation candidates are currently available.",
            ["Expected Savings"],
        )

        st.subheader("Executed Actions")
        _table(_action_rows(dashboard["executed_actions"]), "No workflow actions have executed yet.", ["Expected Savings"])

    with t2:
        st.subheader("Failed Actions")
        _table(_action_rows(dashboard["failed_actions"]), "No workflow actions have failed.", ["Expected Savings"])

        st.subheader("Audit Trail")
        _table(dashboard["audit_trail"], "No workflow audit events are available yet.")


if __name__ == "__main__":
    main()
