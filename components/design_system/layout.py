from __future__ import annotations

from typing import Any, Final

import streamlit as st

from components.design_system.spacing import SPACING


BREAKPOINTS: Final[dict[str, str]] = {
    "sm": "640px",
    "md": "768px",
    "lg": "1024px",
    "xl": "1280px",
    "2xl": "1536px",
}

CONTENT_WIDTHS: Final[dict[str, str]] = {
    "narrow": "960px",
    "default": "1180px",
    "wide": "1440px",
    "full": "100%",
}

GRID: Final[dict[str, str]] = {
    "two": "repeat(2, minmax(0, 1fr))",
    "three": "repeat(3, minmax(0, 1fr))",
    "four": "repeat(4, minmax(0, 1fr))",
}


def page_shell(
    title: str,
    description: str | None = None,
    breadcrumbs: list[str] | None = None,
    width: str = "wide",
) -> None:
    crumbs = " / ".join(breadcrumbs or ["Nexora", title])
    st.caption(crumbs)
    st.title(title)
    if description:
        st.caption(description)
    st.markdown(f"<div style='height:{SPACING['4']}'></div>", unsafe_allow_html=True)


def responsive_columns(count: int, gap: str = "small") -> list[Any]:
    return st.columns(count, gap=gap)
