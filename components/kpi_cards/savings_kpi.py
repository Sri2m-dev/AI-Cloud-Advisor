import streamlit as st

def savings_kpi(value, delta=None, help_text=None):
    st.metric("Total Savings", value, delta=delta, help=help_text)

