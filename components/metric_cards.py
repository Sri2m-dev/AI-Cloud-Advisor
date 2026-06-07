"""
Reusable metric card components for Streamlit dashboards.
"""
import streamlit as st

def metric_card(label, value, delta=None, help_text=None, color="default"):
    """
    Display a metric card with optional delta and help text.
    """
    st.metric(label, value, delta=delta, help=help_text)

