from __future__ import annotations

from collections.abc import Sequence
from html import escape

import streamlit as st

from components.design_system import get_theme


def render_breadcrumbs(
    breadcrumbs: Sequence[str] | None = None,
    *,
    separator: str = "/",
    theme_mode: str = "light",
) -> None:
    if not breadcrumbs:
        return

    theme = get_theme(theme_mode)
    items = [
        f"<span style='color:{theme.colors['text_muted']};'>{escape(str(item))}</span>"
        for item in breadcrumbs
        if str(item).strip()
    ]
    if not items:
        return

    st.markdown(
        f"""
        <nav aria-label="Breadcrumbs" style="
            display:flex;
            align-items:center;
            gap:{theme.spacing["2"]};
            font-size:{theme.typography["caption"]["font_size"]};
            line-height:{theme.typography["caption"]["line_height"]};
            margin-bottom:{theme.spacing["3"]};
        ">
            {f"<span style='color:{theme.colors['border']};'>{escape(separator)}</span>".join(items)}
        </nav>
        """,
        unsafe_allow_html=True,
    )
