from shared.streamlit_compat import plotly_chart


def render_plotly_chart(fig, safe_chart_fn, fallback_message="Visualization initializing", use_container_width=True):
    """Render a Plotly figure through the app's safe_chart wrapper."""
    safe_chart_fn(
        lambda: plotly_chart(fig),
        fallback_message,
    )

