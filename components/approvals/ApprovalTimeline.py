import streamlit as st
from typing import List, Dict

def ApprovalTimeline(events: List[Dict]):
    """
    Display a timeline of approval events.
    """
    for event in events:
        st.write(f"{event.get('timestamp', '')}: {event.get('action', '')} by {event.get('user', '')}")

