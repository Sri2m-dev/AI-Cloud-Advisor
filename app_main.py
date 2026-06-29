import streamlit as st
from shared.styles import configure_page
from auth.role_constants import normalize_role
from components.sidebar_navigation import DEFAULT_ROLE_PAGE

configure_page(
    page_title="NEXORA",
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

default_page = DEFAULT_ROLE_PAGE.get(role)
if default_page:
    st.switch_page(default_page)
else:
    st.session_state.clear()
    st.switch_page(
        "pages/login.py"
    )
