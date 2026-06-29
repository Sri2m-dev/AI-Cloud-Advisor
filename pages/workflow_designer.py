from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from repositories.workflow_builder_repository import WorkflowBuilderRepository
from services.workflow_builder_service import WorkflowBuilderService


st.set_page_config(page_title="Workflow Designer", layout="wide")

EXAMPLES = [
    "Build implementation plan for Oracle migration.",
    "Build workflow to reduce Azure spend by 20% without affecting production.",
    "Create CAB package for SaaS license optimization.",
    "Create disaster recovery testing workflow for critical applications.",
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

    st.title("Workflow Designer")
    st.caption("Generate an executive-ready enterprise execution blueprint from agent consensus. Production execution remains disabled.")

    left, right = st.columns([1.1, 0.9])
    with left:
        goal = st.text_area("Goal or Recommendation", value=st.session_state.get("workflow_goal", EXAMPLES[0]), height=100)
        cols = st.columns(2)
        for index, example in enumerate(EXAMPLES):
            if cols[index % 2].button(example[:44], key=f"workflow_example_{index}", use_container_width=True):
                st.session_state["workflow_goal"] = example
                st.rerun()
        build = st.button("Generate Workflow Blueprint", type="primary", use_container_width=True)
    with right:
        st.subheader("Blueprint Contents")
        st.write("- 7-stage enterprise workflow")
        st.write("- Tasks with owners, dependencies, success criteria, and rollback")
        st.write("- Approval matrix")
        st.write("- Validation checklist")
        st.write("- Executive CAB summary")

    if build:
        st.session_state["last_workflow_blueprint"] = WorkflowBuilderService.build_from_goal(
            goal,
            organization_id=organization_id,
            created_by=user.get("email") or "workflow_designer",
            persist=True,
        )

    blueprint = st.session_state.get("last_workflow_blueprint")
    existing = WorkflowBuilderRepository.list_blueprints(organization_id)

    st.divider()
    if blueprint:
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Stages", len(blueprint["stages"]))
        k2.metric("Tasks", len(blueprint["tasks"]))
        k3.metric("Approvals", len(blueprint["approvals"]))
        k4.metric("Duration", blueprint["estimated_duration"])
        k5.metric("Confidence", f"{float(blueprint['confidence']):.1f}%")

        st.subheader("Goal Summary")
        st.success(blueprint["executive_summary"])
        st.write(f"Template: **{blueprint['template']['Name']}**")
        st.write(f"Execution Enabled: **{blueprint['execution_enabled']}**")

        st.subheader("Workflow Timeline")
        stages = pd.DataFrame(blueprint["stages"])
        if not stages.empty:
            fig = px.line(stages, x="Stage", y="Name", text="Owner", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        _show_table(blueprint["stages"], "No workflow stages are available.")

        st.subheader("Tasks")
        for stage in blueprint["stages"]:
            with st.expander(f"Stage {stage['Stage']} - {stage['Name']}", expanded=stage["Stage"] <= 2):
                rows = [row for row in blueprint["tasks"] if row["Stage"] == stage["Name"]]
                _show_table(rows, "No tasks for this stage.")

        left_panel, right_panel = st.columns(2)
        with left_panel:
            st.subheader("Dependencies")
            _show_table(blueprint["dependencies"], "No dependencies are available.")
            if blueprint["dependencies"]:
                dep_df = pd.DataFrame(blueprint["dependencies"])
                fig = px.scatter(dep_df, x="Depends On", y="Task", color="Type")
                st.plotly_chart(fig, use_container_width=True)
        with right_panel:
            st.subheader("Approvals")
            _show_table(blueprint["approvals"], "No approvals are available.")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Rollback")
            _show_table(blueprint["rollback"], "No rollback plan is available.")
        with c2:
            st.subheader("Validation")
            _show_table(blueprint["validation"], "No validation checklist is available.")
    else:
        st.subheader("Recent Blueprints")
        if existing:
            rows = [
                {
                    "Goal": row.get("goal_text"),
                    "Template": row.get("template_name"),
                    "Stages": row.get("stage_count"),
                    "Tasks": row.get("task_count"),
                    "Approvals": row.get("approval_count"),
                    "Duration": row.get("estimated_duration"),
                    "Risk": row.get("business_risk"),
                    "Confidence": row.get("confidence"),
                }
                for row in existing
            ]
            _show_table(rows, "No workflow blueprints are available.")
        else:
            st.info("Generate a workflow blueprint to start.")


if __name__ == "__main__":
    main()
