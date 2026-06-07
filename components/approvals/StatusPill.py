import streamlit as st

def StatusPill(status: str):
    """
    Display a status pill for approval status.
    """
    color = {
        "Approved": "green",
        "Pending": "orange",
        "Rejected": "red",
        "Escalated": "purple"
    }.get(status, "gray")
    st.markdown(f"<span style='background-color:{color};color:white;padding:2px 10px;border-radius:12px;font-size:90%;'>{status}</span>", unsafe_allow_html=True)

