import streamlit as st

from core.logging.audit_logger import AuditLogger
from services import audit_service
from shared.session import init_session
from utils.auth import logout_user

init_session()

st.set_page_config(page_title="Logout | Nexora", page_icon=":unlock:", layout="centered")
st.title("🔓 Logout")

if st.session_state.get("authenticated") or st.session_state.get("user"):
    user_email = st.session_state.user.get("email") if isinstance(st.session_state.user, dict) else str(st.session_state.user)
    org_id = st.session_state.get("organization_id") or st.session_state.get("org_id")

    try:
        logout_user()
    except Exception:
        st.warning("Local session cleared, but Supabase sign-out could not be confirmed.")

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
    st.success("You have been logged out.")
    st.rerun()
else:
    logout_user()
    st.info("You are not logged in.")
