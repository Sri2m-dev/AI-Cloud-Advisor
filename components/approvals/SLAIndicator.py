import streamlit as st

def SLAIndicator(sla_status: str):
    """
    Display an SLA status indicator.
    """
    color = "green" if sla_status == "OK" else "red"
    st.markdown(f"<span style='color:{color};font-weight:bold;'>SLA: {sla_status}</span>", unsafe_allow_html=True)

