from __future__ import annotations

from typing import Any

from components.shared.executive_summary import render_executive_summary


def render_portfolio_summary(title: str, metrics: list[dict[str, Any]], narrative: str | None = None) -> None:
    render_executive_summary(
        {
            "title": title,
            "description": "Portfolio-level operating summary.",
            "narrative": narrative,
            "metrics": metrics,
        }
    )
