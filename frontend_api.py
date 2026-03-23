import requests
import streamlit as st

def get_cost_data():
    try:
        response = requests.get("http://127.0.0.1:8000/cost")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None
