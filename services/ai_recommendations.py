from openai import OpenAI
import streamlit as st

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def generate_finops_recommendation(cost_summary, region):
    prompt = f"""
You are a FinOps and Cloud Optimization expert.

Analyze this AWS cost breakdown and recommend optimization:

Region: {region}
Cost Summary: {cost_summary}

Provide:
1. Cost optimization recommendations
2. Possible architectural improvements
3. Estimated cost savings
"""
    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )
    return response.output_text
