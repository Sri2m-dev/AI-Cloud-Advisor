# core/error/error_boundary.py
"""
Enterprise error boundary for Streamlit dashboards.
Prevents raw tracebacks in UI and provides graceful fallback messaging.
"""
import streamlit as st
import logging

def error_boundary(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.exception("Dashboard error: %s", e)
            st.warning("Data temporarily unavailable")
            return None
    return wrapper

