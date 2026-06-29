from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from repositories.goal_repository import GoalRepository


st.set_page_config(page_title="Learning Center", layout="wide")


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()
    goals = GoalRepository.list_goals(organization_id)

    st.title("Learning Center")
    st.caption("Passive learning signals for agent planning quality, confidence, and future optimization.")
    classifications: dict[str, int] = {}
    for row in goals:
        key = row.get("classification") or "Unknown"
        classifications[key] = classifications.get(key, 0) + 1
    rows = [{"Classification": key, "Goals": value} for key, value in sorted(classifications.items())]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Learning signals will appear after goal plans are created.")
    st.subheader("Learning Guardrails")
    st.write("- Learning is passive in A.9.1.")
    st.write("- Agent behavior is not automatically changed by plan outcomes yet.")
    st.write("- Future sprints can compare planned savings, approvals, execution results, and realized outcomes.")


if __name__ == "__main__":
    main()
