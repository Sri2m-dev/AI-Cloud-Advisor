from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from html import escape

import streamlit as st


class BadgeKind(str, Enum):
    STATUS = "status"
    AUTHORITY = "authority"
    CONFIDENCE = "confidence"
    MATERIALITY = "materiality"
    EVIDENCE = "evidence"


@dataclass(frozen=True)
class BadgeSpec:
    kind: BadgeKind
    label: str
    value: str | None = None
    tone: str = "unknown"
    description: str | None = None


_STATUS_ICON = {
    "healthy": "✓",
    "informational": "i",
    "info": "i",
    "watch": "◷",
    "warning": "!",
    "critical": "!",
    "blocked": "×",
    "unknown": "?",
    "partial": "◐",
    "stale": "◷",
    "conflicted": "⇄",
    "unsupported": "—",
}


def _color(spec: BadgeSpec) -> str:
    if spec.kind is BadgeKind.STATUS:
        return f"var(--nexora-status-{spec.tone}, var(--nexora-status-unknown))"
    return f"var(--nexora-{spec.kind.value})"


def badge_html(spec: BadgeSpec) -> str:
    label = escape(spec.label)
    value = f": {escape(spec.value)}" if spec.value else ""
    description = escape(spec.description or f"{spec.kind.value}: {spec.label}{value}")
    icon = _STATUS_ICON.get(
        spec.tone,
        {
            BadgeKind.AUTHORITY: "§",
            BadgeKind.CONFIDENCE: "≈",
            BadgeKind.MATERIALITY: "◆",
            BadgeKind.EVIDENCE: "◈",
        }.get(spec.kind, "•"),
    )
    return (
        f'<span class="nexora-badge" style="color:{_color(spec)}" '
        f'role="status" aria-label="{description}" title="{description}">'
        f'<span class="nexora-badge__icon" aria-hidden="true">{icon}</span>'
        f"<span>{label}{value}</span></span>"
    )


def render_badge(spec: BadgeSpec) -> None:
    st.markdown(badge_html(spec), unsafe_allow_html=True)


def render_status_badge(
    label: str, *, tone: str | None = None, description: str | None = None
) -> None:
    render_badge(
        BadgeSpec(
            BadgeKind.STATUS, label, tone=(tone or label).strip().lower(), description=description
        )
    )


def render_authority_badge(label: str, *, description: str | None = None) -> None:
    render_badge(BadgeSpec(BadgeKind.AUTHORITY, label, description=description))


def render_confidence_badge(
    label: str, *, value: str | None = None, description: str | None = None
) -> None:
    render_badge(BadgeSpec(BadgeKind.CONFIDENCE, label, value, description=description))


def render_materiality_badge(label: str, *, description: str | None = None) -> None:
    render_badge(BadgeSpec(BadgeKind.MATERIALITY, label, description=description))


def render_evidence_badge(
    label: str, *, value: str | None = None, description: str | None = None
) -> None:
    render_badge(BadgeSpec(BadgeKind.EVIDENCE, label, value, description=description))
