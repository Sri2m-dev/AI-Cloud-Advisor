from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

import streamlit as st

from components.executive_foundation.badges import BadgeKind, BadgeSpec, badge_html
from components.executive_foundation.states import ComponentState, state_html


@dataclass(frozen=True)
class CitationView:
    label: str
    reference: str
    source: str
    excerpt: str | None = None
    authorized: bool = True


@dataclass(frozen=True)
class EvidenceItemView:
    title: str
    source: str
    observed_at: str
    version: str
    confidence: str
    freshness: str
    classification: str
    authority: str
    citation: CitationView | None = None
    state: ComponentState | None = None
    state_reason: str | None = None


@dataclass(frozen=True)
class EvidenceSummaryView:
    sources: str
    coverage: str
    freshness: str
    confidence: str
    authority: str
    unknowns: str = "None disclosed"
    conflicts: str = "None disclosed"
    state: ComponentState | None = None
    state_reason: str | None = None


@dataclass(frozen=True)
class EvidenceEventView:
    title: str
    occurred_at: str
    observed_at: str
    source: str
    authority: str
    evidence_reference: str


@dataclass(frozen=True)
class EvidenceDrawerView:
    subject: str
    summary: EvidenceSummaryView
    sources: tuple[EvidenceItemView, ...] = field(default_factory=tuple)
    lineage: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    raw_evidence_note: str = "Raw evidence is available only when separately entitled."
    state: ComponentState | None = None
    state_reason: str | None = None


def indicator_html(label: str, value: str, *, kind: str, description: str | None = None) -> str:
    safe_kind = (
        kind
        if kind in {"freshness", "coverage", "unknown", "conflict", "authority", "version"}
        else "evidence"
    )
    text = escape(description or f"{label}: {value}")
    return (
        f'<span class="nexora-evidence-indicator nexora-evidence-indicator--{safe_kind}" '
        f'role="status" aria-label="{text}" title="{text}"><strong>{escape(label)}:</strong> '
        f"{escape(value)}</span>"
    )


def citation_html(view: CitationView) -> str:
    if not view.authorized:
        return state_html(
            ComponentState.UNAUTHORIZED,
            title="Citation unavailable",
            description="Citation content and identifiers are not disclosed for this entitlement.",
        )
    excerpt = f"<blockquote>{escape(view.excerpt)}</blockquote>" if view.excerpt else ""
    return (
        '<cite class="nexora-citation">'
        f'<span class="nexora-citation__label">{escape(view.label)}</span>{excerpt}'
        f"<span><strong>Source:</strong> {escape(view.source)}</span>"
        f"<code>{escape(view.reference)}</code></cite>"
    )


def evidence_card_html(view: EvidenceItemView) -> str:
    if view.state:
        return state_html(
            view.state,
            title=view.title,
            description=view.state_reason,
            metadata="Evidence presentation state",
        )
    citation = citation_html(view.citation) if view.citation else ""
    return (
        f'<article class="nexora-evidence-card" aria-label="Evidence: {escape(view.title)}">'
        f"<h3>{escape(view.title)}</h3>"
        '<div class="nexora-evidence-grid">'
        f'{indicator_html("Source", view.source, kind="evidence")}'
        f'{indicator_html("Observed", view.observed_at, kind="freshness")}'
        f'{indicator_html("Version", view.version, kind="version")}'
        f'{indicator_html("Confidence", view.confidence, kind="coverage")}'
        f'{indicator_html("Freshness", view.freshness, kind="freshness")}'
        f'{indicator_html("Classification", view.classification, kind="authority")}'
        f'{indicator_html("Authority", view.authority, kind="authority")}</div>{citation}</article>'
    )


def evidence_summary_html(view: EvidenceSummaryView) -> str:
    if view.state:
        return state_html(view.state, title="Evidence summary", description=view.state_reason)
    values = (
        ("Sources", view.sources, "evidence"),
        ("Coverage", view.coverage, "coverage"),
        ("Freshness", view.freshness, "freshness"),
        ("Confidence", view.confidence, "coverage"),
        ("Authority", view.authority, "authority"),
        ("Unknowns", view.unknowns, "unknown"),
        ("Conflicts", view.conflicts, "conflict"),
    )
    content = "".join(indicator_html(label, value, kind=kind) for label, value, kind in values)
    return (
        '<section class="nexora-evidence-summary" aria-label="Evidence summary">'
        f"{content}</section>"
    )


def evidence_timeline_html(
    events: tuple[EvidenceEventView, ...],
    *,
    state: ComponentState | None = None,
    state_reason: str | None = None,
) -> str:
    if state:
        return state_html(state, title="Evidence timeline", description=state_reason)
    items = "".join(
        f'<li><div class="nexora-evidence-timeline__marker" aria-hidden="true"></div>'
        f"<div><h3>{escape(event.title)}</h3><p>Occurred {escape(event.occurred_at)} · "
        f"Observed {escape(event.observed_at)}</p><p>{escape(event.source)} · "
        f"{escape(event.authority)} · {escape(event.evidence_reference)}</p></div></li>"
        for event in events
    )
    return f'<ol class="nexora-evidence-timeline" aria-label="Evidence chronology">{items}</ol>'


def source_badge_html(source: str) -> str:
    return badge_html(
        BadgeSpec(BadgeKind.EVIDENCE, source, description=f"Evidence source: {source}")
    )


def render_evidence_card(view: EvidenceItemView) -> None:
    st.markdown(evidence_card_html(view), unsafe_allow_html=True)


def render_evidence_summary(view: EvidenceSummaryView) -> None:
    st.markdown(evidence_summary_html(view), unsafe_allow_html=True)


def render_evidence_timeline(
    events: tuple[EvidenceEventView, ...],
    *,
    state: ComponentState | None = None,
    state_reason: str | None = None,
) -> None:
    st.markdown(
        evidence_timeline_html(events, state=state, state_reason=state_reason),
        unsafe_allow_html=True,
    )


def render_citation(view: CitationView) -> None:
    st.markdown(citation_html(view), unsafe_allow_html=True)


def render_source_badge(source: str) -> None:
    st.markdown(source_badge_html(source), unsafe_allow_html=True)


def render_evidence_drawer(view: EvidenceDrawerView) -> None:
    if view.state:
        st.markdown(
            state_html(view.state, title="Evidence", description=view.state_reason),
            unsafe_allow_html=True,
        )
        return
    st.subheader(f"Evidence · {view.subject}")
    tabs = st.tabs(["Summary", "Sources", "Lineage", "Assumptions", "Unknowns", "Raw evidence"])
    with tabs[0]:
        render_evidence_summary(view.summary)
    with tabs[1]:
        for item in view.sources:
            render_evidence_card(item)
    with tabs[2]:
        st.markdown(
            _list_html(view.lineage, "No authorized lineage supplied."), unsafe_allow_html=True
        )
    with tabs[3]:
        st.markdown(
            _list_html(view.assumptions, "No assumptions supplied."), unsafe_allow_html=True
        )
    with tabs[4]:
        st.markdown(_list_html(view.unknowns, "No unknowns disclosed."), unsafe_allow_html=True)
    with tabs[5]:
        st.info(view.raw_evidence_note)


def _list_html(items: tuple[str, ...], empty: str) -> str:
    if not items:
        return f'<p class="nexora-evidence-empty">{escape(empty)}</p>'
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"
