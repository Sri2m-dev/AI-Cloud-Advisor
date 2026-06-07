import streamlit as st

def org_filter(options, default=None):
    return st.selectbox("Organization", options, index=options.index(default) if default in options else 0)

