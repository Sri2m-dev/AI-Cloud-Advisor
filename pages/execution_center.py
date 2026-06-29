from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.safe_execution_service import SAFETY_MODES, SafeExecutionService


st.set_page_config(page_title="Execution Center", layout="wide")

EXAMPLES = [
    "Execute Oracle migration.",
    "Execute Azure spend reduction workflow.",
    "Run SaaS license optimization in mock mode.",
    "Simulate Kubernetes rightsizing execution.",
]


def _show_table(rows: list[dict[str, Any]], empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()

    st.title("Execution Center")
    st.caption("Safe execution through adapters. Mock mode is the only active execution mode in A.9.5.")

    left, right = st.columns([1.1, 0.9])
    with left:
        goal = st.text_area("Authorized Workflow or Goal", value=st.session_state.get("execution_goal", EXAMPLES[0]), height=100)
        mode = st.selectbox("Execution Mode", list(SAFETY_MODES.keys()), index=1)
        adapter = st.selectbox("Execution Adapter", ["mock", "aws", "azure", "gcp", "terraform", "ansible", "servicenow", "github_actions"])
        force_mock = st.checkbox("Use mock authorization for non-production verification", value=True)
        cols = st.columns(2)
        for index, example in enumerate(EXAMPLES):
            if cols[index % 2].button(example[:42], key=f"exec_example_{index}", use_container_width=True):
                st.session_state["execution_goal"] = example
                st.rerun()
        run = st.button("Request Execution", type="primary", use_container_width=True)
    with right:
        st.subheader("Safety Modes")
        for name, description in SAFETY_MODES.items():
            st.write(f"- **{name}:** {description}")

    if run:
        st.session_state["last_execution"] = SafeExecutionService.request_execution(
            goal,
            organization_id=organization_id,
            execution_mode=mode,
            adapter_name=adapter,
            created_by=user.get("email") or "execution_center",
            persist=True,
            force_authorized=force_mock,
        )

    dashboard = SafeExecutionService.get_dashboard(organization_id)
    execution = st.session_state.get("last_execution")

    st.divider()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Authorized Plans", len(dashboard["authorized_plans"]) + (1 if execution and execution["authorization"]["Status"] == "AUTHORIZED" else 0))
    k2.metric("Queue", len(dashboard["queue"]))
    k3.metric("Running", len(dashboard["running"]))
    k4.metric("Completed", len(dashboard["completed"]) + (1 if execution and execution["status"] == "Completed" else 0))
    k5.metric("Rollbacks", len(dashboard["rollbacks"]) + (1 if execution and execution["status"] == "Rolled Back" else 0))

    if execution:
        st.subheader("Executive Summary")
        summary = execution["summary"]
        if execution["status"] == "Blocked":
            st.warning(summary.get("Reason"))
        else:
            st.success(
                f"{summary['Status']} in {summary['Execution Mode']} mode through {summary['Adapter']} adapter. "
                f"External API calls: {summary['External API Calls']}."
            )
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Status", execution["status"])
        p2.metric("Mode", execution["execution_mode"])
        p3.metric("Adapter", execution["adapter"])
        p4.metric("Progress", f"{execution['progress']}%")

        st.subheader("Live Progress")
        events = pd.DataFrame(execution["events"])
        if not events.empty:
            fig = px.line(events, x="sequence", y="event_type", markers=True)
            st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Execution Stages")
            _show_table(execution["stages"], "No stage results are available.")
            st.subheader("Validation Results")
            _show_table(execution["validation_results"], "No validation results are available.")
        with c2:
            st.subheader("Rollback")
            _show_table([execution["rollback_execution"]] if execution.get("rollback_execution") else [], "Rollback was not required.")
            st.subheader("Execution Events")
            _show_table(execution["events"], "No execution events are available.")
    else:
        st.subheader("Authorized Plans")
        _show_table(dashboard["authorized_plans"], "No authorized plans are currently available.")
        st.subheader("Execution Queue")
        _show_table(dashboard["queue"], "No queued execution jobs.")
        st.subheader("Adapter Registry")
        _show_table(dashboard["adapters"], "No adapters are registered.")
        st.subheader("Execution History")
        _show_table(dashboard["history"], "No execution history is available.")


if __name__ == "__main__":
    main()
