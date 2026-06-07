import streamlit as st
from datetime import datetime


def render_audit_timeline(events):
    """
    Render a vertical audit timeline of events.
    events: List of dicts with keys: timestamp, action, actor (optional)
    """
    st.markdown(
        """
        <div style='margin-top: 2em; margin-bottom: 2em; padding: 18px 24px 10px 24px; background: #fff; border-radius: 10px; box-shadow: 0 1px 6px rgba(0,0,0,0.06);'>
            <h4 style='margin-bottom: 0.7em; font-size: 1.15em; font-weight: 600; color: #333;'>Audit Timeline</h4>
        """,
        unsafe_allow_html=True,
    )

    if not events:
        st.info("No audit events found.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown("### Audit Timeline")
    for event in sorted(events, key=lambda e: e.get("timestamp", "")):
        time_str = event.get("timestamp")
        # Try to format timestamp if it's a datetime or ISO string
        if isinstance(time_str, datetime):
            time_fmt = time_str.strftime("[%I:%M %p]")
        else:
            try:
                time_fmt = f"[{datetime.fromisoformat(time_str).strftime('%I:%M %p')} ]"
            except Exception:
                time_fmt = f"[{time_str}]"

        action = event.get("action", "")
        actor = event.get("actor", "")
        if actor:
            st.markdown(f"{time_fmt}  • **{action}**  <br><small>by {actor}</small>", unsafe_allow_html=True)
        else:
            st.markdown(f"{time_fmt}  • **{action}**", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

