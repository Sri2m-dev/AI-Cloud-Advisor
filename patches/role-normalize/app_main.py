import streamlit as st
from shared.styles import configure_page
from auth.role_constants import normalize_role

configure_page(
    page_title="AI Cloud Advisor",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize auth state
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# User not logged in
if not st.session_state["authenticated"]:
    st.switch_page("pages/login.py")
    st.stop()

# Get role
role = normalize_role(
    st.session_state.get("role", "")
)

# Map executive-level and technical leadership (CTO) to Executive Dashboard
if role in [
    "executive",
    "technical",
    "super_admin",
]:
    st.switch_page(
        "pages/executive_dashboard.py"
    )

# Finance -> Operations workspace per requested routing
elif role in [
    "finance",
]:
    st.switch_page(
        "pages/operations_workspace.py"
    )

# Fallback: send back to login
else:
    st.session_state.clear()
    st.switch_page(
        "pages/login.py"
    )
