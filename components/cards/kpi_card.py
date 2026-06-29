from __future__ import annotations

from collections.abc import Callable, Sequence
from html import escape
from typing import Any

import streamlit as st

from components.design_system import get_theme
from components.design_system.colors import status_color
from components.design_system.icons import icon as resolve_icon
from components.layout import render_status_badge


ActionList = Sequence[str] | Callable[[], Any] | None


def _text(value: Any) -> str:
    return escape(str(value)) if value is not None else ""


def _trend_color(trend: str | None, delta: str | None, theme_mode: str) -> str:
    value = f"{trend or ''} {delta or ''}".strip().lower()
    theme = get_theme(theme_mode)
    if value.startswith("+") or "up" in value or "improv" in value:
        return theme.colors["success"]
    if value.startswith("-") or "down" in value or "degrad" in value:
        return theme.colors["error"]
    return theme.colors["text_muted"]


def _container(border: bool = True):
    try:
        return st.container(border=border)
    except TypeError:
        return st.container()


def _render_action_list(actions: ActionList, key_prefix: str) -> None:
    if actions is None:
        return
    if callable(actions):
        actions()
        return

    action_labels = [actions] if isinstance(actions, str) else list(actions)
    if not action_labels:
        return

    columns = st.columns(min(len(action_labels), 3))
    for index, label in enumerate(action_labels):
        with columns[index % len(columns)]:
            st.button(str(label), key=f"{key_prefix}_{index}", use_container_width=True)


def _render_card(
    *,
    title: str,
    value: Any | None = None,
    subtitle: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    status: str | None = None,
    trend: str | None = None,
    delta: str | None = None,
    footer: str | None = None,
    actions: ActionList = None,
    card_type: str = "kpi",
    theme_mode: str = "light",
) -> None:
    theme = get_theme(theme_mode)
    icon_name = resolve_icon(icon or card_type, icon or card_type)
    status_line = status or "info"
    accent = status_color(status_line)
    trend_text = " ".join(part for part in [trend, delta] if part)
    supporting_text = description or subtitle
    key_prefix = f"{card_type}_{abs(hash((title, value, footer))) % 100000}"

    with _container(border=True):
        st.markdown(
            f"""
            <div class="nexora-card-content" style="
                border-left: 4px solid {accent};
                padding-left: {theme.spacing["3"]};
            ">
                <div style="
                    display:flex;
                    align-items:flex-start;
                    justify-content:space-between;
                    gap:{theme.spacing["3"]};
                ">
                    <div>
                        <div style="
                            color:{theme.colors["text_muted"]};
                            font-size:{theme.typography["caption"]["font_size"]};
                            font-weight:600;
                            line-height:{theme.typography["caption"]["line_height"]};
                        ">{_text(title)}</div>
                        <div style="
                            color:{theme.colors["text"]};
                            font-size:{theme.typography["h2"]["font_size"]};
                            line-height:{theme.typography["h2"]["line_height"]};
                            font-weight:700;
                            margin-top:{theme.spacing["1"]};
                        ">{_text(value)}</div>
                    </div>
                    <div style="
                        min-width:34px;
                        min-height:34px;
                        border-radius:{theme.radius["md"]};
                        background:{theme.colors["surface_alt"]};
                        color:{theme.colors["primary"]};
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        font-size:0.72rem;
                        font-weight:700;
                        text-transform:uppercase;
                    " title="{_text(icon_name)}">{_text(icon_name[:2])}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if supporting_text:
            st.caption(supporting_text)
        if status or trend_text:
            cols = st.columns([0.46, 0.54])
            with cols[0]:
                if status:
                    render_status_badge(status)
            with cols[1]:
                if trend_text:
                    st.markdown(
                        f"<span style='color:{_trend_color(trend, delta, theme_mode)}; font-weight:600;'>{_text(trend_text)}</span>",
                        unsafe_allow_html=True,
                    )
        if footer:
            st.caption(footer)
        _render_action_list(actions, key_prefix)


def render_kpi_card(
    title: str,
    value: Any,
    subtitle: str | None = None,
    *,
    description: str | None = None,
    icon: str | None = None,
    status: str | None = None,
    trend: str | None = None,
    delta: str | None = None,
    footer: str | None = None,
    actions: ActionList = None,
    theme_mode: str = "light",
) -> None:
    _render_card(
        title=title,
        value=value,
        subtitle=subtitle,
        description=description,
        icon=icon,
        status=status,
        trend=trend,
        delta=delta,
        footer=footer,
        actions=actions,
        card_type="kpi",
        theme_mode=theme_mode,
    )
