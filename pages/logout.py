import streamlit as st
from shared.session import init_session
from core.logging.audit_logger import AuditLogger
from services import audit_service

init_session()

st.set_page_config(page_title="Logout | Nexora", page_icon=":unlock:", layout="centered")
st.title("🔓 Logout")

if "user" in st.session_state and st.session_state.user:
    user_email = st.session_state.user.get("email") if isinstance(st.session_state.user, dict) else str(st.session_state.user)
    org_id = st.session_state.get("organization_id")
    
    AuditLogger.log_event(
        trace_id="logout",
        user_id=user_email or "unknown",
        action="logout",
        resource="LogoutPage",
        status="success"
    )
    
    # Also log using the new audit service
    audit_service.log_user_logout(
        user_id=user_email or "unknown",
        org_id=org_id
    )
    
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.session_state["role"] = None
    st.session_state["organization_id"] = None
    st.success("You have been logged out.")
    st.rerun()
else:
    st.info("You are not logged in.")

