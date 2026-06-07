
import streamlit as st

# --- Executive Layout: Full Width & Hard CSS Lock ---
st.set_page_config(
    page_title="AI Cloud Advisor",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100% !important;
    }
    </style>
""", unsafe_allow_html=True)

from pathlib import Path
import sys
def _hydrate_session_context():
    email = st.session_state.get("user_email")
    active_role = st.session_state.get("role")
    if not email or not active_role:
        return

    from shared.auth import sync_user_context
    context = sync_user_context(email, active_role, st.session_state.get("client_id"))
    for key, value in context.items():
        st.session_state[key] = value

def _perform_logout():
    for key in ["user_email", "username", "role", "client_id", "company", "user_type", "plan", "current_page"]:
        st.session_state.pop(key, None)
    st.rerun()

from views import cto_dashboard_old

selected_page = st.sidebar.radio(
    "Navigation",
    ["CTO Dashboard", "Cloud Accounts", "Cost Explorer"]
)

if selected_page == "CTO Dashboard":
    cto_dashboard_old.main()

