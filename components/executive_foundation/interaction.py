from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from html import escape

import streamlit as st

from components.executive_foundation.badges import BadgeKind, BadgeSpec, badge_html
from components.executive_foundation.narrative import SemanticStability, stability_badge_html
from components.executive_foundation.states import ComponentState, state_html


class InteractionKind(str, Enum):
    SEARCH = "search"
    COMMAND = "command"
    FILTER = "filter"
    PERSONA = "persona"
    DATE_TIME = "date-time"
    DRILL_DOWN = "drill-down"
    BREADCRUMB = "breadcrumb"
    TIMELINE = "timeline"
    AI_HANDOFF = "ai-handoff"
    SCENARIO_LAUNCH = "scenario-launch"
    RECOMMENDATION_ACTION = "recommendation-action"
    DECISION_STATUS = "decision-status"
    SAVED_VIEW = "saved-view"
    EXPORT = "export"


@dataclass(frozen=True)
class InteractionOption:
    label: str
    value: str
    selected: bool = False
    enabled: bool = True
    description: str | None = None


@dataclass(frozen=True)
class InteractionView:
    title: str
    kind: InteractionKind
    purpose: str
    options: tuple[InteractionOption, ...] = field(default_factory=tuple)
    context: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    primary_intent: str | None = None
    authority: str = "Presentation intent only"
    status: str = "Available"
    stability: SemanticStability = SemanticStability.CONTROLLED
    state: ComponentState | None = None
    state_reason: str | None = None


def interaction_html(view: InteractionView) -> str:
    if view.state:
        return state_html(
            view.state,
            title=view.title,
            description=view.state_reason,
            metadata=f"Interaction · {view.kind.value}",
        )
    options = "".join(
        f'<span class="nexora-interaction__option" aria-disabled="{str(not item.enabled).lower()}" '
        f'aria-current="{str(item.selected).lower()}" '
        f'title="{escape(item.description or item.label)}">'
        f"{escape(item.label)}</span>"
        for item in view.options
    )
    context = "".join(
        f'<span class="nexora-interaction__context"><strong>{escape(label)}:</strong> '
        f"{escape(value)}</span>"
        for label, value in view.context
    )
    intent = (
        f'<span class="nexora-interaction__intent">Intent: {escape(view.primary_intent)}</span>'
        if view.primary_intent
        else ""
    )
    return (
        f'<section class="nexora-interaction nexora-interaction--{view.kind.value}" '
        f'aria-label="{escape(view.title)}"><div class="nexora-interaction__header">'
        f"<h3>{escape(view.title)}</h3>{stability_badge_html(view.stability)}</div>"
        f'<p>{escape(view.purpose)}</p><div class="nexora-interaction__options">{options}</div>'
        f'<div class="nexora-interaction__context-row">{context}</div>{intent}'
        f'<div class="nexora-interaction__authority">'
        f'{badge_html(BadgeSpec(BadgeKind.STATUS, view.status, tone="info"))}'
        f'{badge_html(BadgeSpec(BadgeKind.AUTHORITY, view.authority))}</div></section>'
    )


def render_interaction(view: InteractionView) -> None:
    st.markdown(interaction_html(view), unsafe_allow_html=True)


def render_executive_search(view: InteractionView) -> None:
    render_interaction(_with_kind(view, InteractionKind.SEARCH))


def render_command_bar(view: InteractionView) -> None:
    render_interaction(_with_kind(view, InteractionKind.COMMAND))


def render_filter_panel(view: InteractionView) -> None:
    render_interaction(_with_kind(view, InteractionKind.FILTER))


def render_ai_handoff(view: InteractionView) -> None:
    render_interaction(_with_kind(view, InteractionKind.AI_HANDOFF))


def render_scenario_launch(view: InteractionView) -> None:
    render_interaction(_with_kind(view, InteractionKind.SCENARIO_LAUNCH))


def _with_kind(view: InteractionView, kind: InteractionKind) -> InteractionView:
    values = {name: getattr(view, name) for name in view.__dataclass_fields__}
    values["kind"] = kind
    return InteractionView(**values)
