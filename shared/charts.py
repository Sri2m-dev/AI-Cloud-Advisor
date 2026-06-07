"""Standard chart rendering for enterprise dashboards."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from shared.layout import render_section
from shared.styles import apply_enterprise_styles


DEFAULT_CHART_HEIGHT = 340


def standardize_plotly_figure(fig: Any, *, height: int = DEFAULT_CHART_HEIGHT) -> Any:
    """Apply common sizing and visual defaults to Plotly figures."""
    if fig.__class__.__module__.startswith("plotly"):
        fig.update_layout(
            height=height,
            margin=dict(t=18, b=24, l=18, r=18),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=12, color="#111827"),
            legend=dict(font=dict(size=11), title_font=dict(size=11)),
        )
        fig.update_xaxes(showgrid=False, zeroline=False, title_font=dict(size=11), tickfont=dict(size=11))
        fig.update_yaxes(gridcolor="#eef2f7", zeroline=False, title_font=dict(size=11), tickfont=dict(size=11))
    return fig


def render_chart(title: str, chart: Any, description: str | None = None, *, height: int = DEFAULT_CHART_HEIGHT) -> None:
    """Render Plotly/Altair/other charts in a standardized compact container."""
    apply_enterprise_styles()
    render_section(title, description)
    with st.container(border=True):
        module_name = chart.__class__.__module__
        if module_name.startswith("plotly"):
            st.plotly_chart(standardize_plotly_figure(chart, height=height), use_container_width=True)
        elif module_name.startswith("altair"):
            st.altair_chart(chart.properties(height=height), use_container_width=True)
        else:
            st.write(chart)


def line_chart(data: pd.DataFrame, x: str, y: str, title: str = "") -> None:
    chart = alt.Chart(data).mark_line().encode(x=x, y=y).properties(title=title)
    render_chart(title, chart)


def bar_chart(data: pd.DataFrame, x: str, y: str, title: str = "") -> None:
    chart = alt.Chart(data).mark_bar().encode(x=x, y=y).properties(title=title)
    render_chart(title, chart)

