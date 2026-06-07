"""
Reusable filter components for Streamlit dashboards.
"""
import streamlit as st

def date_range_filter(label, default=None):
    return st.date_input(label, value=default)

def select_filter(label, options, default=None, multi=False):
    if multi:
        return st.multiselect(label, options, default=default)
    else:
        return st.selectbox(label, options, index=options.index(default) if default in options else 0)

