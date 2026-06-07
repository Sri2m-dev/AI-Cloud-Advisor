import streamlit as st

def date_range_filter(label, default=None):
    return st.date_input(label, value=default)

