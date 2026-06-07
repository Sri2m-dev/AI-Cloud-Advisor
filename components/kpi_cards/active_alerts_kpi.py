import streamlit as st

def active_alerts_kpi(value, delta=None, help_text=None):
    st.metric("Active Alerts", value, delta=delta, help=help_text)

