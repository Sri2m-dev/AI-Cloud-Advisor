import streamlit as st

def spend_kpi(value, delta=None, help_text=None):
    st.metric("Total Cloud Spend", value, delta=delta, help=help_text)

