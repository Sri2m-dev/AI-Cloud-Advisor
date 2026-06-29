from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

from components.design_system import inject_theme
from components.layout.footer import render_footer
from components.layout.page_header import render_page_header


def render_page(
    *,
    title: str,
    description: str | None = None,
    breadcrumbs: list[str] | None = None,
    content: Callable[[], Any] | None = None,
    actions: Callable[[], Any] | None = None,
    status: str | None = None,
    theme_mode: str = "light",
    show_footer: bool = True,
    footer_version: str = "1.0",
) -> Any:
    inject_theme(theme_mode)
    st.markdown("<main class='nexora-page-shell'>", unsafe_allow_html=True)
    render_page_header(
        title,
        description,
        breadcrumbs=breadcrumbs,
        actions=actions,
        status=status,
        theme_mode=theme_mode,
    )
    result = content() if content else None
    if show_footer:
        render_footer(version=footer_version)
    st.markdown("</main>", unsafe_allow_html=True)
    return result
