from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from repositories.goal_repository import GoalRepository


st.set_page_config(page_title="Agent Console", layout="wide")


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()
    goals = GoalRepository.list_goals(organization_id)
    logs = GoalRepository.list_agent_logs(organization_id)

    st.title("Agent Console")
    st.caption("Operational view of agent planning sessions, statuses, and governance traces.")
    k1, k2, k3 = st.columns(3)
    k1.metric("Goals", len(goals))
    k2.metric("Agent Logs", len(logs))
    k3.metric("Execution Enabled", "No")
    st.subheader("Recent Goals")
    if goals:
        st.dataframe(pd.DataFrame(goals), use_container_width=True, hide_index=True)
    else:
        st.info("No goal sessions are available yet.")
    st.subheader("Agent Execution Log")
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
    else:
        st.info("No agent execution logs are available yet.")


if __name__ == "__main__":
    main()
