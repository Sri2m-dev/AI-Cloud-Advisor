from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from agents.orchestrator import AgentOrchestrator
from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from repositories.goal_repository import GoalRepository


st.set_page_config(page_title="Multi-Agent Collaboration", layout="wide")

EXAMPLES = [
    "Reduce Azure spend by 20% without affecting production.",
    "Reduce cloud spend by 15% while maintaining production availability.",
    "Prepare migration plan from Oracle to PostgreSQL.",
    "Improve DR readiness for customer-facing applications.",
]


def _currency(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


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

    st.title("Multi-Agent Collaboration")
    st.caption("Hub-and-spoke collaboration with shared enterprise context, specialist opinions, consensus, and full traceability.")

    left, right = st.columns([1.1, 0.9])
    with left:
        goal = st.text_area("Business Goal", value=st.session_state.get("collaboration_goal", EXAMPLES[0]), height=100)
        cols = st.columns(2)
        for index, example in enumerate(EXAMPLES):
            if cols[index % 2].button(example[:42], key=f"collab_example_{index}", use_container_width=True):
                st.session_state["collaboration_goal"] = example
                st.rerun()
        run = st.button("Start Collaboration Preview", type="primary", use_container_width=True)
    with right:
        st.subheader("Collaboration Rules")
        st.write("- No agent calls another agent directly.")
        st.write("- The orchestrator routes every request and response.")
        st.write("- Every agent receives the same enterprise context.")
        st.write("- Consensus creates one governed execution plan.")

    if run:
        st.session_state["last_collaboration"] = AgentOrchestrator.collaborate_on_goal(
            goal,
            organization_id=organization_id,
            created_by=user.get("email") or "multi_agent_collaboration",
            persist=True,
        )

    sessions = GoalRepository.list_collaboration_sessions(organization_id)
    messages = GoalRepository.list_agent_messages(organization_id)
    decisions = GoalRepository.list_agent_decisions(organization_id)
    consensus_rows = GoalRepository.list_agent_consensus(organization_id)
    active = st.session_state.get("last_collaboration")

    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Active Sessions", len(sessions) + (1 if active else 0))
    k2.metric("Agent Messages", len(messages) + (len(active.get("messages", [])) if active else 0))
    k3.metric("Agent Decisions", len(decisions) + (len(active.get("agent_contributions", [])) if active else 0))
    k4.metric("Consensus Records", len(consensus_rows) + (1 if active else 0))

    if active:
        consensus = active["consensus"]
        unified = active["unified_enterprise_plan"]
        st.subheader("Executive Summary")
        st.success(active["executive_summary"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Consensus State", consensus["Consensus State"])
        c2.metric("Confidence", f"{consensus['Confidence']:.1f}%")
        c3.metric("Expected Savings", _currency(unified["Expected Savings"]))
        c4.metric("Business Risk", unified["Business Risk"])

        st.subheader("Participating Agents")
        agent_rows = [
            {"Order": index, "Agent": agent, "State": "Contributed"}
            for index, agent in enumerate(active["participating_agents"], start=1)
        ]
        _show_table(agent_rows, "No participating agents yet.")

        st.subheader("Collaboration Timeline")
        timeline = pd.DataFrame(
            [
                {"Step": row["sequence"], "Sender": row["sender"], "Recipient": row["recipient"], "Status": row["status"]}
                for row in active["messages"]
            ],
        )
        if not timeline.empty:
            fig = px.line(timeline, x="Step", y="Recipient", text="Status", markers=True)
            st.plotly_chart(fig, use_container_width=True)

        left_panel, right_panel = st.columns(2)
        with left_panel:
            st.subheader("Agent Contributions")
            contribution_rows = [
                {
                    "Agent": row["Agent"],
                    "Recommendation": row["Recommendation"],
                    "Vote": row["Vote"],
                    "Risk": row["Risk"],
                    "Confidence": row["Confidence"],
                    "Blocking Issues": "; ".join(row.get("Blocking Issues") or []),
                }
                for row in active["agent_contributions"]
            ]
            _show_table(contribution_rows, "No agent contributions yet.")
        with right_panel:
            st.subheader("Consensus")
            st.write(f"Recommendation: **{consensus['Enterprise Recommendation']}**")
            st.write(consensus["Reason"])
            _show_table(consensus["Votes"], "No votes have been recorded.")
            if consensus["Blocking Issues"]:
                st.warning("Blocking issues: " + "; ".join(consensus["Blocking Issues"]))

        st.subheader("Unified Enterprise Plan")
        plan_rows = [
            {"Field": key, "Value": value}
            for key, value in unified.items()
            if key != "Execution Blueprint"
        ]
        _show_table(plan_rows, "No unified plan is available.")

        st.subheader("Enterprise Agent Scorecard")
        _show_table(active.get("agent_scorecard", []), "No agent scorecard is available.")

        st.subheader("Collaboration Log")
        log_rows = [
            {
                "Sequence": row["sequence"],
                "Sender": row["sender"],
                "Recipient": row["recipient"],
                "Request": row["request"],
                "Status": row["status"],
            }
            for row in active["messages"]
        ]
        _show_table(log_rows, "No collaboration messages are available.")
    else:
        st.subheader("Active Sessions")
        _show_table(sessions, "No collaboration sessions have been started yet.")


if __name__ == "__main__":
    main()
