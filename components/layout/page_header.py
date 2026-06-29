from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

from components.design_system import get_theme
from components.layout.section import render_status_badge


def render_page_header(
    title: str,
    description: str | None = None,
    *,
    subtitle: str | None = None,
    breadcrumbs: list[str] | None = None,
    actions: Callable[[], Any] | None = None,
    status: str | None = None,
    theme_mode: str = "light",
) -> None:
    theme = get_theme(theme_mode)
    text_muted = theme.colors["text_muted"]
    border = theme.colors["border"]
    description = description or subtitle
    crumbs = breadcrumbs or ["Home", title]
    crumb_text = " / ".join(str(item) for item in crumbs if item)

    st.markdown(
        f"""
        <div class="nexora-page-header" style="
            border-bottom: 1px solid {border};
            padding: 0.25rem 0 1rem 0;
            margin-bottom: 1rem;
        ">
            <div style="color:{text_muted};font-size:0.8125rem;line-height:1.25rem;">{crumb_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    title_col, action_col = st.columns([0.72, 0.28])
    with title_col:
        title_bits = [title]
        if status:
            st.title(title)
            render_status_badge(status)
        else:
            st.title(" ".join(title_bits))
        if description:
            st.caption(description)
    with action_col:
        if actions:
            actions()
