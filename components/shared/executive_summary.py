from __future__ import annotations

from typing import Any

import streamlit as st

from components.cards import render_metric_card
from components.layout import render_section


def render_executive_summary(summary: dict[str, Any], *, columns: int = 4) -> None:
    render_section(
        summary.get("title") or "Executive Summary",
        summary.get("description") or "Certified executive summary and primary operating signals.",
        divider=False,
    )
    narrative = summary.get("narrative")
    if narrative:
        st.write(narrative)

    metrics = summary.get("metrics") or []
    if not metrics:
        return
    for index in range(0, len(metrics), columns):
        cols = st.columns(min(columns, len(metrics) - index))
        for col, metric in zip(cols, metrics[index : index + columns]):
            with col:
                render_metric_card(
                    metric.get("label") or metric.get("title") or "Metric",
                    metric.get("value", "0"),
                    description=metric.get("description"),
                    icon=metric.get("icon") or "platform",
                    status=metric.get("status") or "info",
                )
