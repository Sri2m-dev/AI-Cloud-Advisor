import streamlit as st

def cloud_provider_filter(options, default=None):
    return st.selectbox("Cloud Provider", options, index=options.index(default) if default in options else 0)

