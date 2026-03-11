# 2_Optimization.py
import streamlit as st
import pandas as pd

# Idle resource detection function
def find_idle_resources(resources):
    idle = resources[
        (resources["cpu_utilization"] < 10) &
        (resources["network"] < 5)
    ]
    return idle

# Reserved Instance / Savings Plan recommendation function
def ri_recommendation(usage_hours):
    if usage_hours > 500:
        return "Recommended: Purchase Reserved Instance"
    elif usage_hours > 300:
        return "Consider Savings Plan"
    else:
        return "On-demand is optimal"
st.info("Recommendation: Remove unattached EBS volumes")