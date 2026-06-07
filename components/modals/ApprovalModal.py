import streamlit as st
from typing import Callable

def ApprovalModal(visible: bool, on_approve: Callable, on_reject: Callable, title: str = "Approval Required", message: str = "Are you sure you want to approve this request?", user_role: str = None):
    """
    Display a modal for approval actions, hidden for CEO.
    """
    if not visible:
        return
    st.markdown(f"### {title}")
    st.write(message)
    if user_role and str(user_role).lower() == "ceo":
        st.info("Read-only: CEO cannot approve or reject.")
        return
    col1, col2 = st.columns(2)
    if col1.button("Approve"):
        on_approve()
    if col2.button("Reject"):
        on_reject()

