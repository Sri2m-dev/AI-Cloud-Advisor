
import streamlit as st
import os

ENV = os.getenv("APP_ENV", "demo")
st.write("ENV VALUE:", ENV)

# -----------------------
# DATA
# -----------------------
def load_demo_ceo_data():
    import pandas as pd
    return pd.DataFrame({
        'business_unit': ['A', 'B', 'C'],
        'monthly_spend': [10000, 15000, 12000],
        'percentage': [40, 35, 25]
    })

def load_real_data():
    import pandas as pd
    return pd.DataFrame()

if ENV == "demo":
    df = load_demo_ceo_data()
else:
    df = load_real_data()

# -----------------------
# UI
# -----------------------
def show_dashboard(df):
    st.title("🔥 FUNCTION HIT")
    st.dataframe(df)

st.write("🚀 Before dashboard call")
show_dashboard(df)
st.write("✅ After dashboard call")
