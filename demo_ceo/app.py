
st.write("🚀 Before dashboard call")
import streamlit as st
import os

ENV = os.getenv("APP_ENV", "demo")
st.write("ENV VALUE:", ENV)

def main():
    st.title("🚀 Demo CEO Dashboard")
