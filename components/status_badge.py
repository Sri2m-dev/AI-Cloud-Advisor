import streamlit as st

def render_status_badge(status):
    """
    Render a colored badge for a given status.
    """
    color_map = {
        "Pending": "#FFD600",      # Yellow
        "Approved": "#00C853",     # Green
        "Rejected": "#D50000",     # Red
        "Escalated": "#FF6D00",    # Orange
        "Completed": "#2962FF",    # Blue
    }
    color = color_map.get(status, "#BDBDBD")  # Default: grey
    st.markdown(f"<span style='background-color: {color}; color: white; border-radius: 0.5em; padding: 0.2em 0.8em; font-size: 0.95em;'>{status}</span>", unsafe_allow_html=True)

