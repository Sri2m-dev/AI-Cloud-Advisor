import streamlit as st


def render_plotly_chart(fig, safe_chart_fn, fallback_message="Visualization initializing", use_container_width=True):
    """Render a Plotly figure through the app's safe_chart wrapper."""
    safe_chart_fn(
        lambda: st.plotly_chart(fig, use_container_width=use_container_width),
        fallback_message,
    )

