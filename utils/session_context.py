import streamlit as st

def initialize_session():
    defaults = {
        "authenticated": False,
        "user": None,
        "role": None,
        "org": None,
        "tenant": None,
        "permissions": []
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

