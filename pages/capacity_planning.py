from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.capacity_intelligence_service import CapacityIntelligenceService


st.set_page_config(page_title="Capacity Planning", layout="wide")


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()
    data = CapacityIntelligenceService.forecast_capacity(organization_id)
    st.title("Capacity Planning")
    st.caption("Forecast CPU, memory, disk, storage, database, network, Kubernetes, and cloud-service thresholds.")
    c1, c2 = st.columns(2)
    c1.metric("Upcoming Capacity Issues", f"{data['summary']['Upcoming Capacity Issues']:,}")
    c2.metric("Most Urgent", data["summary"]["Most Urgent"])
    df = pd.DataFrame(data["capacity"])
    if not df.empty:
        st.plotly_chart(px.bar(df, x="Domain", y="Days To 95%", color="Current Utilization"), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No capacity forecast is available yet.")


if __name__ == "__main__":
    main()
