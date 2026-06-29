from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import streamlit as st

from components.design_system import get_theme
from components.design_system.colors import status_color


def render_status_badge(status: str, *, label: str | None = None) -> None:
    color = status_color(status)
    text = label or status
    st.markdown(
        f"""
        <span style="
            display:inline-flex;
            align-items:center;
            min-height:24px;
            padding:2px 10px;
            border-radius:999px;
            background:{color};
            color:white;
            font-size:0.8125rem;
            font-weight:600;
        ">{text}</span>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(
    title: str = "No data available",
    description: str | None = None,
    *,
    action: Callable[[], Any] | None = None,
) -> None:
    st.markdown(
        """
        <div class="nexora-empty-state" style="
            border:1px dashed var(--nexora-border);
            border-radius:8px;
            padding:1.25rem;
            background:var(--nexora-surface);
        ">
        """,
        unsafe_allow_html=True,
    )
    st.write(f"**{title}**")
    if description:
        st.caption(description)
    if action:
        action()
    st.markdown("</div>", unsafe_allow_html=True)


def render_section(
    title: str,
    description: str | None = None,
    *,
    actions: Callable[[], Any] | None = None,
    status: str | None = None,
    divider: bool = True,
    theme_mode: str = "light",
) -> None:
    theme = get_theme(theme_mode)
    if divider:
        st.divider()
    cols = st.columns([0.72, 0.28])
    with cols[0]:
        st.subheader(title)
        if description:
            st.caption(description)
        if status:
            render_status_badge(status)
    with cols[1]:
        if actions:
            actions()
    st.markdown(
        f"<div style='height:{theme.spacing['2']}'></div>",
        unsafe_allow_html=True,
    )


@contextmanager
def render_section_container(
    title: str,
    description: str | None = None,
    *,
    border: bool = True,
    actions: Callable[[], Any] | None = None,
    theme_mode: str = "light",
) -> Iterator[Any]:
    render_section(title, description, actions=actions, divider=False, theme_mode=theme_mode)
    try:
        container = st.container(border=border)
    except TypeError:
        container = st.container()
    with container:
        yield container
