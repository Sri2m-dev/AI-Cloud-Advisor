import streamlit as st
from typing import Callable

def ConfirmationModal(visible: bool, on_confirm: Callable, on_cancel: Callable, title: str = "Confirm Action", message: str = "Are you sure?"):
    """
    Display a confirmation modal dialog.
    """
    if visible:
        st.markdown(f"### {title}")
        st.write(message)
        col1, col2 = st.columns(2)
        if col1.button("Confirm"):
            on_confirm()
        if col2.button("Cancel"):
            on_cancel()

