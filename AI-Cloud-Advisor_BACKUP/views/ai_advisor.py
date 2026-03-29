import streamlit as st
import pandas as pd
import os
from services.ai_finops_llm import generate_ai_recommendations

def ai_advisor_page():
    # Protect page
    if not st.session_state.get("authenticated"):
        st.warning("Please login from the main page")
        st.stop()

    # Set OpenAI API key from Streamlit secrets
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

    st.title("🤖 AI FinOps Advisor")
    st.write("AI-driven cloud cost optimization recommendations")

    cost_data = pd.DataFrame({
        "Service": ["EC2", "S3", "RDS", "Lambda"],
        "Cost": [5000, 2000, 3000, 450]
    })

    if st.button("Generate AI Recommendations"):
        with st.spinner("Analyzing cloud costs..."):
            recommendations = generate_ai_recommendations(cost_data)
        st.success("Optimization Recommendations")
        st.write(recommendations)
