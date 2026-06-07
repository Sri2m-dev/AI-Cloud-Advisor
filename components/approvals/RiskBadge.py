import streamlit as st

def RiskBadge(risk: str):
    """
    Display a risk classification badge.
    """
    color = {
        "Low": "green",
        "Medium": "orange",
        "High": "red"
    }.get(risk, "gray")
    st.markdown(f"<span style='background-color:{color};color:white;padding:2px 8px;border-radius:8px;font-size:90%;'>Risk: {risk}</span>", unsafe_allow_html=True)

