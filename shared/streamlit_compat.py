from __future__ import annotations

from typing import Any

import streamlit as st


def dataframe(data: Any, **kwargs: Any) -> None:
    """Render a dataframe using the current Streamlit width API with fallback."""
    try:
        st.dataframe(data, width=kwargs.pop("width", "stretch"), **kwargs)
    except TypeError:
        st.dataframe(data, use_container_width=True, **kwargs)


def plotly_chart(fig: Any, **kwargs: Any) -> None:
    """Render a Plotly chart using the current Streamlit width API with fallback."""
    try:
        st.plotly_chart(fig, width=kwargs.pop("width", "stretch"), **kwargs)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, **kwargs)


def line_chart(data: Any, **kwargs: Any) -> None:
    """Render a line chart using the current Streamlit width API with fallback."""
    try:
        st.line_chart(data, width=kwargs.pop("width", "stretch"), **kwargs)
    except TypeError:
        st.line_chart(data, use_container_width=True, **kwargs)


def bar_chart(data: Any, **kwargs: Any) -> None:
    """Render a bar chart using the current Streamlit width API with fallback."""
    try:
        st.bar_chart(data, width=kwargs.pop("width", "stretch"), **kwargs)
    except TypeError:
        st.bar_chart(data, use_container_width=True, **kwargs)
