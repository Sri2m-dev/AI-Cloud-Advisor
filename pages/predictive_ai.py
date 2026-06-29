from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.predictive_ai_service import PredictiveAIService


st.set_page_config(page_title="Predictive AI", layout="wide")


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()
    data = PredictiveAIService.get_predictive_recommendations(organization_id)
    st.title("Predictive AI")
    st.caption("Connect prediction, impact, simulation, reasoning, and recommendation into one preventive action flow.")
    rows = data["recommendations"]
    if rows:
        row = rows[0]
        k1, k2, k3 = st.columns(3)
        k1.metric("Prediction", row["Prediction"])
        k2.metric("Recommendation", row["Recommendation"])
        k3.metric("Confidence", f"{row['Confidence']:.1f}%")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No predictive AI recommendations are available yet.")


if __name__ == "__main__":
    main()
