from __future__ import annotations

from typing import Any

from components.cards.kpi_card import ActionList, _render_card


def render_approval_card(
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
        icon=icon or "approval",
        status=status or "watch",
        trend=trend,
        delta=delta,
        footer=footer,
        actions=actions,
        card_type="approval",
        theme_mode=theme_mode,
    )
