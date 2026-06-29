from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.risk_prediction_service import RiskPredictionService


st.set_page_config(page_title="Risk Prediction", layout="wide")


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()
    data = RiskPredictionService.predict_risks(organization_id)
    st.title("Risk Prediction")
    st.caption("Predict infrastructure failures, budget overruns, license shortages, compliance failures, technology failure, application risk, vendor risk, and operational risk.")
    k1, k2, k3 = st.columns(3)
    k1.metric("Predicted Risks", f"{data['summary']['Predicted Risks']:,}")
    k2.metric("Predicted Failures", f"{data['summary']['Predicted Failures']:,}")
    k3.metric("Highest Risk", data["summary"]["Highest Risk"])
    df = pd.DataFrame(data["predictions"])
    if not df.empty:
        st.plotly_chart(px.bar(df.head(20), x="Failure Probability", y="Entity", color="Risk Category", orientation="h"), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No predictive risk rows are available yet.")


if __name__ == "__main__":
    main()
