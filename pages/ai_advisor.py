import streamlit as st

st.title("🤖 AI Cloud Advisor")

st.write("Recommended Optimizations")

recommendations = [
    "Downsize EC2 m5.2xlarge to m5.xlarge",
    "Move S3 Standard → S3 Intelligent Tiering",
    "Purchase Reserved Instances for RDS",
]

for r in recommendations:
    st.success(r)
