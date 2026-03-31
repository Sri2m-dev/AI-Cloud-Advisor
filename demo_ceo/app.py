
st.write("🚀 Before dashboard call")
import streamlit as st
import os

ENV = os.getenv("APP_ENV", "demo")
st.write("ENV VALUE:", ENV)

if ENV == "demo":
    from dashboards.demo import show_demo_dashboard
    show_demo_dashboard()
    st.success(f"LOADED: {ENV.upper()} DASHBOARD")

elif ENV == "dev":
    from dashboards.dev import show_dev_dashboard
    show_dev_dashboard()
    st.success(f"LOADED: {ENV.upper()} DASHBOARD")

else:
    st.error("Unknown environment")
