from __future__ import annotations

import pandas as pd
import streamlit as st

from agents.registry import AgentRegistry
from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation


st.set_page_config(page_title="Agent Registry", layout="wide")


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()
    agents = AgentRegistry.list_agents(organization_id)

    st.title("Agent Registry")
    st.caption("Governed registry of available agents, capabilities, owners, versions, and enablement state.")
    k1, k2, k3 = st.columns(3)
    k1.metric("Registered Agents", len(agents))
    k2.metric("Enabled", len([row for row in agents if row.get("enabled", True)]))
    k3.metric("Production", len([row for row in agents if row.get("status") == "Production"]))
    st.dataframe(pd.DataFrame(agents), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
