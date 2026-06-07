import streamlit as st


def render_streamlit_kpi_row(metrics):
    """Render a row of Streamlit metric cards from a metric spec list."""
    if not metrics:
        return
    cols = st.columns(len(metrics))
    for col, metric in zip(cols, metrics):
        with col:
            st.metric(
                metric.get("label", ""),
                metric.get("value", ""),
                delta=metric.get("delta"),
                delta_color=metric.get("delta_color", "normal"),
            )


def render_safe_kpi_row(metrics, safe_metric_fn):
    """Render a row of safe metrics using the provided safe_metric function."""
    if not metrics:
        return
    cols = st.columns(len(metrics))
    for col, metric in zip(cols, metrics):
        with col:
            safe_metric_fn(
                metric.get("label", ""),
                metric.get("value", ""),
                metric.get("delta"),
            )

