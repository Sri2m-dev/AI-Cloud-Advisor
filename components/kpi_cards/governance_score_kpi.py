import streamlit as st

def governance_score_kpi(value, delta=None, help_text=None):
    st.metric("Governance Score", value, delta=delta, help=help_text)

