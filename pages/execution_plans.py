from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from repositories.goal_repository import GoalRepository


st.set_page_config(page_title="Execution Plans", layout="wide")


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
    plans = GoalRepository.list_execution_plans(organization_id)

    st.title("Execution Plans")
    st.caption("Review agent-generated blueprints. A.9.1 keeps execution disabled until future approval workflows are added.")
    if not plans:
        st.info("No execution plans have been saved yet. Create one from Goal Center.")
        return
    rows = [
        {
            "Goal ID": row.get("goal_id"),
            "Status": row.get("status"),
            "Estimated Savings": _currency(row.get("estimated_savings")),
            "Risk": row.get("risk"),
            "Approvals": ", ".join(row.get("approvals") or []),
            "Created": row.get("created_at"),
        }
        for row in plans
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
