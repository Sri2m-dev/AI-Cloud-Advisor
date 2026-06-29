from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.financial_intelligence_service import FinancialIntelligenceService


st.set_page_config(page_title="Financial Forecasting", layout="wide")


def _currency(value):
    return f"${float(value or 0):,.0f}"


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "finance")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()
    data = FinancialIntelligenceService.get_financial_forecast(organization_id)
    summary = data["summary"]
    st.title("Financial Forecasting")
    st.caption("Forecast cloud, SaaS, license, vendor, department, business unit, ROI, savings, and budget exposure.")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Predicted Spend", _currency(summary["Predicted Spend"]))
    k2.metric("15% Savings Target", _currency(summary["Savings Target 15%"]))
    k3.metric("Can Achieve 15%", summary["Can Achieve 15% Savings"])
    k4.metric("First Budget Breach", summary["First Budget Breach"])
    df = pd.DataFrame(data["savings_candidates"])
    if not df.empty:
        st.plotly_chart(px.bar(df, x="Opportunity", y="Savings Potential"), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No financial savings candidates are available yet.")


if __name__ == "__main__":
    main()
