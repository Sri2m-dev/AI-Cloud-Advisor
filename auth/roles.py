
import streamlit as st
import logging
from .jwt_utils import verify_jwt

def require_jwt():
    token = st.session_state.get("jwt")
    if not token:
        st.warning("Please log in.")
        st.rerun()
    user = verify_jwt(token)
    if user == "expired":
        st.warning("Session expired. Please login again.")
        st.session_state.pop("jwt", None)
        st.rerun()
    if not user:
        st.warning("Session invalid. Please login again.")
        st.session_state.pop("jwt", None)
        st.rerun()
    return user

def require_role(allowed_roles):
    user = require_jwt()
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
    if user["role"] not in allowed_roles:
        logging.warning(f"Unauthorized access attempt by {user['username']} for role(s) {allowed_roles}")
        st.error("Unauthorized")
        st.stop()
    return user
