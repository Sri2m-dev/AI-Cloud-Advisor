import streamlit as st

def tile(title, icon, description, key, badge=None):
    label = f"{icon} {title}"
    if badge:
        label += f"  ({badge})"
    clicked = st.button(label, key=key, use_container_width=True)
    st.caption(description)
    return clicked

