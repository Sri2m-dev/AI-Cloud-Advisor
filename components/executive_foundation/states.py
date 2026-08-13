from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from html import escape

import streamlit as st


class ComponentState(str, Enum):
    LOADING = "loading"
    EMPTY = "empty"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    UNAUTHORIZED = "unauthorized"
    STALE = "stale"
    CONFLICTED = "conflicted"
    ERROR = "error"


@dataclass(frozen=True)
class StatePresentation:
    title: str
    description: str
    color: str


_PRESENTATIONS = {
    ComponentState.LOADING: StatePresentation(
        "Loading", "Retrieving governed presentation data.", "var(--nexora-status-info)"
    ),
    ComponentState.EMPTY: StatePresentation(
        "Nothing in this scope",
        "No items match the current authorized scope.",
        "var(--nexora-status-unknown)",
    ),
    ComponentState.PARTIAL: StatePresentation(
        "Partial coverage",
        "Available information is shown; some governed inputs are missing.",
        "var(--nexora-status-partial)",
    ),
    ComponentState.UNKNOWN: StatePresentation(
        "Unknown",
        "The available evidence cannot support a conclusion.",
        "var(--nexora-status-unknown)",
    ),
    ComponentState.UNAUTHORIZED: StatePresentation(
        "Not authorized",
        "Your current entitlement does not permit this view.",
        "var(--nexora-status-blocked)",
    ),
    ComponentState.STALE: StatePresentation(
        "Data is stale",
        "The latest observation is outside the approved freshness window.",
        "var(--nexora-status-stale)",
    ),
    ComponentState.CONFLICTED: StatePresentation(
        "Sources conflict",
        "Governed sources disagree; no precedence has been assumed.",
        "var(--nexora-status-conflicted)",
    ),
    ComponentState.ERROR: StatePresentation(
        "Unable to display",
        "The component could not load safely. Try again or use the reference below.",
        "var(--nexora-status-critical)",
    ),
}


def state_html(
    state: ComponentState,
    *,
    title: str | None = None,
    description: str | None = None,
    metadata: str | None = None,
) -> str:
    presentation = _PRESENTATIONS[state]
    safe_title = escape(title or presentation.title)
    safe_description = escape(description or presentation.description)
    safe_metadata = (
        f'<span class="nexora-state__meta">{escape(metadata)}</span>' if metadata else ""
    )
    role = (
        "alert"
        if state in {ComponentState.ERROR, ComponentState.UNAUTHORIZED, ComponentState.CONFLICTED}
        else "status"
    )
    skeleton = (
        '<div class="nexora-skeleton" aria-hidden="true"></div>'
        '<div class="nexora-skeleton" style="width:68%" aria-hidden="true"></div>'
        if state is ComponentState.LOADING
        else ""
    )
    return (
        f'<section class="nexora-state" style="--nexora-state-color:{presentation.color}" '
        f'role="{role}" aria-live="polite"><h3>{safe_title}</h3>'
        f"<p>{safe_description}</p>{skeleton}{safe_metadata}</section>"
    )


def render_component_state(
    state: ComponentState | str,
    *,
    title: str | None = None,
    description: str | None = None,
    metadata: str | None = None,
) -> None:
    resolved = state if isinstance(state, ComponentState) else ComponentState(state)
    st.markdown(
        state_html(resolved, title=title, description=description, metadata=metadata),
        unsafe_allow_html=True,
    )
