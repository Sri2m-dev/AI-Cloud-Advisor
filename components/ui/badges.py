# components/ui/badges.py
"""
Enterprise-safe badge rendering wrapper for Streamlit dashboards.
Prevents runtime errors if streamlit_extras is not installed.
"""

try:
    from streamlit_extras.badges import badge
    def render_badge(*args, **kwargs):
        badge(*args, **kwargs)
except ImportError:
    def render_badge(*args, **kwargs):
        pass

