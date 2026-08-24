from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from html import escape

import streamlit as st

from components.executive_foundation.badges import BadgeKind, BadgeSpec, badge_html
from components.executive_foundation.states import ComponentState, state_html


class KpiKind(str, Enum):
    EXECUTIVE = "executive"
    FINANCIAL = "financial"
    HEALTH = "health"
    RISK = "risk"
    TREND = "trend"
    DECISION = "decision"


class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TrendView:
    """Upstream-supplied trend label; no direction or delta is derived here."""

    label: str
    direction: TrendDirection = TrendDirection.UNKNOWN
    period: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class DeltaView:
    """Already-formatted delta and its upstream semantic tone."""

    value: str
    baseline: str
    tone: str = "neutral"
    description: str | None = None


@dataclass(frozen=True)
class ThresholdView:
    """Approved upstream threshold state; the UI never evaluates boundaries."""

    label: str
    position: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class SparklinePlaceholder:
    """Presentation-only placeholder metadata; not a calculated chart series."""

    label: str = "Trend visualization"
    description: str = "Presentation placeholder; no time-series data supplied."


@dataclass(frozen=True)
class KpiView:
    title: str
    value: str
    meaning: str
    source: str
    period: str
    freshness: str
    kind: KpiKind = KpiKind.EXECUTIVE
    unit: str | None = None
    status: str | None = None
    delta: DeltaView | None = None
    trend: TrendView | None = None
    confidence: str | None = None
    coverage: str | None = None
    evidence: str | None = None
    materiality: str | None = None
    authority: str | None = None
    threshold: ThresholdView | None = None
    sparkline: SparklinePlaceholder | None = None
    state: ComponentState | None = None
    state_reason: str | None = None
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def _trend_html(view: TrendView) -> str:
    icons = {
        TrendDirection.UP: "↑",
        TrendDirection.DOWN: "↓",
        TrendDirection.STABLE: "→",
        TrendDirection.UNKNOWN: "?",
    }
    period = f" · {escape(view.period)}" if view.period else ""
    description = escape(view.description or f"Trend: {view.label}{period}")
    return (
        f'<span class="nexora-trend nexora-trend--{view.direction.value}" '
        f'aria-label="{description}" title="{description}">'
        f'<span aria-hidden="true">{icons[view.direction]}</span> '
        f"{escape(view.label)}{period}</span>"
    )


def _delta_html(view: DeltaView) -> str:
    description = escape(view.description or f"Delta {view.value} versus {view.baseline}")
    return (
        f'<span class="nexora-delta nexora-delta--{escape(view.tone)}" '
        f'aria-label="{description}" title="{description}">'
        f"{escape(view.value)} <small>vs {escape(view.baseline)}</small></span>"
    )


def _threshold_html(view: ThresholdView) -> str:
    position = f" · {escape(view.position)}" if view.position else ""
    description = escape(view.description or f"Threshold state: {view.label}{position}")
    return (
        f'<div class="nexora-threshold" role="img" aria-label="{description}" '
        f'title="{description}"><span>{escape(view.label)}{position}</span>'
        '<div class="nexora-threshold__track" aria-hidden="true"></div></div>'
    )


def _sparkline_html(view: SparklinePlaceholder) -> str:
    return (
        f'<div class="nexora-sparkline" role="img" aria-label="{escape(view.description)}">'
        '<span aria-hidden="true">━━╱━━╲━━╱━━</span>'
        f"<small>{escape(view.label)}</small></div>"
    )


def kpi_card_html(view: KpiView) -> str:
    if view.state:
        return state_html(
            view.state,
            title=view.title,
            description=view.state_reason,
            metadata=f"{view.source} · {view.period}",
        )

    value = escape(view.value)
    unit = f'<span class="nexora-kpi__unit">{escape(view.unit)}</span>' if view.unit else ""
    status = (
        badge_html(BadgeSpec(BadgeKind.STATUS, view.status, tone=view.status.lower()))
        if view.status
        else ""
    )
    annotations = "".join(
        item
        for item in (
            badge_html(BadgeSpec(BadgeKind.CONFIDENCE, "Confidence", view.confidence))
            if view.confidence
            else "",
            badge_html(BadgeSpec(BadgeKind.CONFIDENCE, "Coverage", view.coverage))
            if view.coverage
            else "",
            badge_html(BadgeSpec(BadgeKind.MATERIALITY, view.materiality))
            if view.materiality
            else "",
            badge_html(BadgeSpec(BadgeKind.EVIDENCE, "Evidence", view.evidence))
            if view.evidence
            else "",
            badge_html(BadgeSpec(BadgeKind.AUTHORITY, view.authority)) if view.authority else "",
        )
        if item
    )
    metadata = "".join(
        f"<span><strong>{escape(label)}:</strong> {escape(value)}</span>"
        for label, value in view.metadata
    )
    delta = _delta_html(view.delta) if view.delta else ""
    trend = _trend_html(view.trend) if view.trend else ""
    threshold = _threshold_html(view.threshold) if view.threshold else ""
    sparkline = _sparkline_html(view.sparkline) if view.sparkline else ""
    accessible = escape(
        f"{view.title}: {view.value}{(' ' + view.unit) if view.unit else ''}. "
        f"{view.meaning}. Source {view.source}, period {view.period}, freshness {view.freshness}."
    )
    return (
        f'<article class="nexora-kpi nexora-kpi--{view.kind.value}" aria-label="{accessible}">'
        f'<div class="nexora-kpi__top"><h3>{escape(view.title)}</h3>{status}</div>'
        f'<div class="nexora-kpi__value">{value}{unit}</div>'
        f'<div class="nexora-kpi__movement">{delta}{trend}</div>'
        f'<p class="nexora-kpi__meaning">{escape(view.meaning)}</p>{sparkline}{threshold}'
        f'<div class="nexora-kpi__badges">{annotations}</div>'
        '<div class="nexora-kpi__metadata">'
        f"<span><strong>Source:</strong> {escape(view.source)}</span>"
        f"<span><strong>Period:</strong> {escape(view.period)}</span>"
        f"<span><strong>Freshness:</strong> {escape(view.freshness)}</span>"
        f"{metadata}</div></article>"
    )


def render_kpi_card(view: KpiView) -> None:
    st.markdown(kpi_card_html(view), unsafe_allow_html=True)


def render_executive_kpi(view: KpiView) -> None:
    render_kpi_card(_with_kind(view, KpiKind.EXECUTIVE))


def render_financial_kpi(view: KpiView) -> None:
    render_kpi_card(_with_kind(view, KpiKind.FINANCIAL))


def render_health_kpi(view: KpiView) -> None:
    render_kpi_card(_with_kind(view, KpiKind.HEALTH))


def render_risk_kpi(view: KpiView) -> None:
    render_kpi_card(_with_kind(view, KpiKind.RISK))


def render_trend_kpi(view: KpiView) -> None:
    render_kpi_card(_with_kind(view, KpiKind.TREND))


def render_decision_kpi(view: KpiView) -> None:
    render_kpi_card(_with_kind(view, KpiKind.DECISION))


def _with_kind(view: KpiView, kind: KpiKind) -> KpiView:
    values = {name: getattr(view, name) for name in view.__dataclass_fields__}
    values["kind"] = kind
    return KpiView(**values)
