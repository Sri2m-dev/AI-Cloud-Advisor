from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from html import escape

import streamlit as st

from components.executive_foundation.badges import BadgeKind, BadgeSpec, badge_html
from components.executive_foundation.evidence import CitationView, citation_html
from components.executive_foundation.states import ComponentState, state_html


class SemanticStability(str, Enum):
    STABLE = "stable"
    CONTROLLED = "controlled"
    EXPERIMENTAL = "experimental"


class NarrativeKind(str, Enum):
    EXECUTIVE = "executive"
    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    RISK = "risk"
    INSIGHT = "insight"
    RECOMMENDATION = "recommendation"
    DECISION = "decision"
    SCENARIO = "scenario"
    FINDING = "finding"


class NarrativeLength(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


@dataclass(frozen=True)
class NarrativeView:
    title: str
    text: str
    kind: NarrativeKind
    timeframe: str
    authority: str
    status: str
    confidence: str
    evidence: str
    materiality: str = "Not assessed"
    importance: str | None = None
    expected_outcome: str | None = None
    owner: str | None = None
    approval_state: str | None = None
    evidence_version: str | None = None
    timestamp: str | None = None
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    citations: tuple[CitationView, ...] = field(default_factory=tuple)
    length: NarrativeLength = NarrativeLength.MEDIUM
    stability: SemanticStability = SemanticStability.CONTROLLED
    ai_assisted: bool = False
    state: ComponentState | None = None
    state_reason: str | None = None


def stability_badge_html(level: SemanticStability) -> str:
    return badge_html(BadgeSpec(BadgeKind.AUTHORITY, f"Stability: {level.value.title()}"))


def materiality_ribbon_html(label: str) -> str:
    return (
        f'<div class="nexora-materiality-ribbon" role="status" '
        f'aria-label="Materiality: {escape(label)}">{escape(label)}</div>'
    )


def unknown_statement_html(statement: str) -> str:
    return (
        '<aside class="nexora-unknown-statement" role="note">'
        f"<strong>Unknown:</strong> {escape(statement)}</aside>"
    )


def assumption_panel_html(assumptions: tuple[str, ...]) -> str:
    items = "".join(f"<li>{escape(item)}</li>" for item in assumptions)
    if not items:
        items = "<li>No assumptions supplied.</li>"
    return (
        '<section class="nexora-assumptions" aria-label="Supplied assumptions">'
        f"<h4>Assumptions</h4><ul>{items}</ul></section>"
    )


def citation_footer_html(citations: tuple[CitationView, ...]) -> str:
    content = "".join(citation_html(item) for item in citations)
    return (
        '<footer class="nexora-citation-footer" aria-label="Narrative citations">'
        f"{content or '<span>No citations supplied.</span>'}</footer>"
    )


def narrative_html(view: NarrativeView) -> str:
    if view.state:
        return state_html(
            view.state,
            title=view.title,
            description=view.state_reason,
            metadata=f"Narrative · {view.kind.value}",
        )
    meta = tuple(
        (label, value)
        for label, value in (
            ("Importance", view.importance),
            ("Expected outcome", view.expected_outcome),
            ("Owner", view.owner),
            ("Approval state", view.approval_state),
            ("Evidence version", view.evidence_version),
            ("Timestamp", view.timestamp),
        )
        if value
    )
    meta_html = "".join(
        f"<span><strong>{escape(label)}:</strong> {escape(value)}</span>" for label, value in meta
    )
    unknowns = "".join(unknown_statement_html(item) for item in view.unknowns)
    ai_label = (
        badge_html(BadgeSpec(BadgeKind.AUTHORITY, "AI-assisted wording"))
        if view.ai_assisted
        else ""
    )
    return (
        f'<article class="nexora-narrative nexora-narrative--{view.kind.value} '
        f'nexora-narrative--{view.length.value}">{materiality_ribbon_html(view.materiality)}'
        f'<div class="nexora-narrative__header"><h3>{escape(view.title)}</h3>'
        f'{stability_badge_html(view.stability)}{ai_label}</div>'
        f'<p class="nexora-narrative__text">{escape(view.text)}</p>'
        f'<div class="nexora-narrative__badges">'
        f'{badge_html(BadgeSpec(BadgeKind.STATUS, view.status, tone=view.status.lower()))}'
        f'{badge_html(BadgeSpec(BadgeKind.CONFIDENCE, "Confidence", view.confidence))}'
        f'{badge_html(BadgeSpec(BadgeKind.EVIDENCE, "Evidence", view.evidence))}'
        f'{badge_html(BadgeSpec(BadgeKind.AUTHORITY, view.authority))}</div>'
        f'<div class="nexora-narrative__meta"><span><strong>Timeframe:</strong> '
        f'{escape(view.timeframe)}</span>{meta_html}</div>{unknowns}'
        f'{assumption_panel_html(view.assumptions)}{citation_footer_html(view.citations)}</article>'
    )


def render_narrative(view: NarrativeView) -> None:
    st.markdown(narrative_html(view), unsafe_allow_html=True)


def render_executive_narrative(view: NarrativeView) -> None:
    render_narrative(_with_kind(view, NarrativeKind.EXECUTIVE))


def render_insight_card(view: NarrativeView) -> None:
    render_narrative(_with_kind(view, NarrativeKind.INSIGHT))


def render_recommendation_card(view: NarrativeView) -> None:
    render_narrative(_with_kind(view, NarrativeKind.RECOMMENDATION))


def render_decision_card(view: NarrativeView) -> None:
    render_narrative(_with_kind(view, NarrativeKind.DECISION))


def render_scenario_card(view: NarrativeView) -> None:
    render_narrative(_with_kind(view, NarrativeKind.SCENARIO))


def render_finding_card(view: NarrativeView) -> None:
    render_narrative(_with_kind(view, NarrativeKind.FINDING))


def _with_kind(view: NarrativeView, kind: NarrativeKind) -> NarrativeView:
    values = {name: getattr(view, name) for name in view.__dataclass_fields__}
    values["kind"] = kind
    return NarrativeView(**values)
