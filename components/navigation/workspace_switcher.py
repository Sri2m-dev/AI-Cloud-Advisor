from __future__ import annotations

from collections.abc import Sequence

import streamlit as st


def render_workspace_switcher(
    workspaces: Sequence[str] | None = None,
    *,
    key: str = "workspace",
) -> str:
    options = list(workspaces or ["Demo Enterprise"])
    current = st.session_state.get("organization_name") or options[0]
    if current not in options:
        options.insert(0, current)
    selected = st.selectbox("Workspace", options, index=options.index(current), key=key)
    st.session_state["organization_name"] = selected
    return selected
