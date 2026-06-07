import streamlit as st
import pandas as pd

from services.executive_dashboard_v2_service import (
    ExecutiveDashboardV2Service,
)

st.set_page_config(
    page_title="Executive Dashboard V2",
    layout="wide",
)

st.title("📊 Executive Dashboard V2")

data = ExecutiveDashboardV2Service.get_dashboard_data()

summary = data.get("summary", {})
budget = data.get("budget", [])
forecast = data.get("forecast", [])
savings = data.get("savings", {})

# =====================================================
# Executive KPIs
# =====================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Spend",
        f"${summary.get('total_spend', 0):,.2f}"
    )

with col2:
    st.metric(
        "Anomalies",
        summary.get("anomaly_count", 0)
    )

with col3:
    st.metric(
        "Optimization Potential",
        f"${summary.get('optimization_potential', 0):,.2f}"
    )

with col4:
    st.metric(
        "Governance Score",
        summary.get("governance_score", 0)
    )

st.divider()

# =====================================================
# Budget vs Actual
# =====================================================

st.subheader("Budget vs Actual")

try:
    budget_df = pd.DataFrame(budget)

    if not budget_df.empty:
        st.dataframe(
            budget_df,
            use_container_width=True
        )
    else:
        st.info("No budget data available.")

except Exception as e:
    st.error(f"Budget data error: {e}")

# =====================================================
# Savings
# =====================================================

st.subheader("Savings")

try:

    if isinstance(savings, dict):
        savings_df = pd.DataFrame([savings])
    else:
        savings_df = pd.DataFrame(savings)

    if not savings_df.empty:
        st.dataframe(
            savings_df,
            use_container_width=True
        )
    else:
        st.info("No savings data available.")

except Exception as e:
    st.error(f"Savings data error: {e}")

# =====================================================
# Spend Forecast
# =====================================================

st.subheader("Spend Forecast")

try:

    forecast_df = pd.DataFrame(forecast)

    if not forecast_df.empty:

        st.line_chart(
            forecast_df.set_index(
                forecast_df.columns[0]
            )[forecast_df.columns[-1]]
        )

        st.dataframe(
            forecast_df,
            use_container_width=True
        )

    else:
        st.info("No forecast data available.")

except Exception as e:
    st.error(f"Forecast data error: {e}")

# =====================================================
# Raw Executive Summary
# =====================================================

st.subheader("Executive Summary")

if summary:

    summary_df = pd.DataFrame(
        [summary]
    )

    st.dataframe(
        summary_df,
        use_container_width=True
    )