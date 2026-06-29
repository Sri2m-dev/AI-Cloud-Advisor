from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import streamlit as st

from components.design_system import get_theme
from components.navigation.notification_center import render_notification_center
from components.navigation.profile_menu import render_profile_menu
from components.navigation.search_bar import render_search_bar
from components.navigation.workspace_switcher import render_workspace_switcher


def render_topbar(
    *,
    workspaces: Sequence[str] | None = None,
    notifications: Sequence[dict[str, Any]] | None = None,
    show_search: bool = True,
    theme_mode: str = "light",
) -> None:
    theme = get_theme(theme_mode)
    st.markdown(
        f"<div style='height:{theme.spacing['2']}; border-bottom:1px solid {theme.colors['border']};'></div>",
        unsafe_allow_html=True,
    )
    columns = st.columns([0.32, 0.34, 0.12, 0.12, 0.10])
    with columns[0]:
        render_workspace_switcher(workspaces)
    with columns[1]:
        if show_search:
            render_search_bar()
    with columns[2]:
        render_notification_center(notifications)
    with columns[3]:
        render_profile_menu()
