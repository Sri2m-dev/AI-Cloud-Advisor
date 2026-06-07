import streamlit as st
from typing import Callable

def EscalationModal(visible: bool, on_escalate: Callable, on_cancel: Callable, title: str = "Escalate Request", message: str = "Do you want to escalate this request?"):
    """
    Display a modal for escalation actions.
    """
    if visible:
        st.markdown(f"### {title}")
        st.write(message)
        col1, col2 = st.columns(2)
        if col1.button("Escalate"):
            on_escalate()
        if col2.button("Cancel"):
            on_cancel()

