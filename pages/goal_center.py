from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from agents.orchestrator import AgentOrchestrator
from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation


st.set_page_config(page_title="Goal Center", layout="wide")

EXAMPLE_GOALS = [
    "Reduce cloud spend by 15% while maintaining production availability.",
    "Improve DR readiness for critical customer-facing applications.",
    "Remove unused SaaS licenses without disrupting active users.",
    "Reduce Oracle licensing exposure before renewal.",
    "Increase Kubernetes utilization safely.",
    "Improve governance score by fixing missing ownership.",
    "Prepare migration plan from Oracle to PostgreSQL.",
]


def _currency(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()

    st.title("Goal Center")
    st.caption("Convert a business objective into an agent-selected execution blueprint. Production execution is disabled in A.9.1.")

    left, right = st.columns([1.1, 0.9])
    with left:
        goal = st.text_area(
            "Business Goal",
            value=st.session_state.get("agentic_goal", EXAMPLE_GOALS[0]),
            height=110,
        )
        cols = st.columns(3)
        for index, example in enumerate(EXAMPLE_GOALS[:6]):
            if cols[index % 3].button(example.split(" by ")[0][:32], key=f"goal_example_{index}", use_container_width=True):
                st.session_state["agentic_goal"] = example
                st.rerun()
        plan_clicked = st.button("Create Execution Preview", type="primary", use_container_width=True)
    with right:
        st.subheader("Planning Guardrails")
        st.write("- No production actions are executed.")
        st.write("- Every plan includes approvals, rollback, validation, risk, and confidence.")
        st.write("- Existing intelligence modules provide the evidence base.")

    if plan_clicked or st.session_state.get("last_goal_plan"):
        if plan_clicked:
            st.session_state["last_goal_plan"] = AgentOrchestrator.plan_goal(
                goal,
                organization_id=organization_id,
                created_by=user.get("email") or "goal_center",
                persist=True,
            )
        plan = st.session_state["last_goal_plan"]
        preview = plan["execution_preview"]

        st.divider()
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Classification", plan["classification"])
        k2.metric("Target", plan["target"])
        k3.metric("Estimated Duration", preview["Estimated Duration"])
        k4.metric("Expected Savings", _currency(preview["Expected Savings"]))
        k5.metric("Confidence", f"{preview['Confidence']:.1f}%")

        st.subheader("Agent Selection")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Order": index,
                        "Agent": row["agent_name"],
                        "Status": row["status"],
                        "Capabilities": ", ".join(row.get("capabilities") or []),
                    }
                    for index, row in enumerate(plan["agents"], start=1)
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Execution Preview")
        e1, e2, e3 = st.columns(3)
        e1.metric("Risk", preview["Risk"])
        e2.metric("Approvals", len(preview["Approvals"]))
        e3.metric("Execution", preview["Production Execution"])
        st.dataframe(pd.DataFrame(plan["tasks"]), use_container_width=True, hide_index=True)

        st.subheader("Blueprint Controls")
        blueprint = plan["execution_blueprint"]
        st.write(f"Status: **{blueprint['status']}**")
        st.write(blueprint["note"])
        c1, c2 = st.columns(2)
        with c1:
            st.write("Approvals")
            for approval in blueprint["approvals"]:
                st.write(f"- {approval}")
            st.write("Rollback")
            for item in blueprint["rollback"]:
                st.write(f"- {item}")
        with c2:
            st.write("Validation")
            for item in blueprint["validation"]:
                st.write(f"- {item}")


if __name__ == "__main__":
    main()
