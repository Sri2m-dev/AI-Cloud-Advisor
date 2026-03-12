import streamlit as st

# Protect page
if not st.session_state.get("authenticated"):
	st.warning("Please login from the main page")
	st.stop()

st.title("Reports & Downloads")

st.info("FinOps report generation coming soon")

st.button("Generate Executive Report")