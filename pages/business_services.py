import pandas as pd
import plotly.express as px
import streamlit as st

from components.sidebar_navigation import render_sidebar_navigation
from services.application_service import ApplicationService
from shared.auth import require_role
from shared.layout import render_page_header
from shared.session import init_session
from shared.styles import configure_page


def _money(value) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


configure_page(
    page_title="Business Services",
    page_icon="B",
)

init_session()

require_role([
    "executive",
    "cio",
    "super_admin",
])

role = st.session_state.get("role", "cio")
render_sidebar_navigation(role)

render_page_header(
    "Business Services",
    "Business unit, department, team, application, and service cost intelligence",
)

portfolio = ApplicationService.portfolio_dataframe()
matrix = ApplicationService.business_service_matrix_dataframe()
service_cost = ApplicationService.service_cost_dataframe()
service_risk = ApplicationService.service_risk_dataframe()
owner_accountability = ApplicationService.owner_accountability_dataframe()
cost_center_view = ApplicationService.cost_center_dataframe()
critical_applications = ApplicationService.critical_applications_dataframe()

business_units = 0
departments = 0
teams = 0
applications = 0
total_spend = 0.0

if not portfolio.empty:
    business_units = portfolio.loc[portfolio["Business Unit"] != "Unknown", "Business Unit"].nunique()
    departments = portfolio.loc[portfolio["Department"] != "Unknown", "Department"].nunique()
    teams = portfolio.loc[portfolio["Team"] != "Unknown", "Team"].nunique()
    applications = portfolio["Application"].nunique()
    total_spend = float(portfolio["Application Spend"].sum())

st.subheader("Business Service KPIs")

kpi_cols = st.columns(5)
kpi_cols[0].metric("Business Units", f"{business_units:,}")
kpi_cols[1].metric("Departments", f"{departments:,}")
kpi_cols[2].metric("Teams", f"{teams:,}")
kpi_cols[3].metric("Applications", f"{applications:,}")
kpi_cols[4].metric("Total Spend", _money(total_spend))

st.divider()

st.subheader("Business Service Matrix")
if not portfolio.empty:
    service_matrix = (
        portfolio[
            (portfolio["Business Unit"] != "Unknown")
            | (portfolio["Department"] != "Unknown")
        ]
        .groupby(["Business Unit", "Department"], as_index=False)
        .agg(
            Applications=("Application", "nunique"),
            Spend=("Application Spend", "sum"),
        )
        .sort_values("Spend", ascending=False)
    )
    _show_dataframe(
        service_matrix,
        "No business service matrix data is currently available.",
    )
else:
    st.info("No business service matrix data is currently available.")

st.caption("Detailed application-to-service attribution")
_show_dataframe(
    matrix,
    "No detailed business service matrix data is currently available.",
)

st.divider()

st.subheader("Service Cost View")
if not service_cost.empty and {"Service", "Total Spend"}.issubset(service_cost.columns):
    fig = px.bar(
        service_cost,
        x="Service",
        y="Total Spend",
        color="Service Type" if "Service Type" in service_cost.columns else None,
        title="Service Cost View",
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
    )

_show_dataframe(
    service_cost,
    "No service cost data is currently available.",
)

st.divider()

st.subheader("Service Risk View")
if not service_risk.empty:
    risk_columns = [
        column for column in [
            "Service Type",
            "Service",
            "Critical Applications",
            "High Spend Apps",
            "Owner Gaps",
        ]
        if column in service_risk.columns
    ]
    _show_dataframe(
        service_risk[risk_columns],
        "No service risk data is currently available.",
    )
else:
    st.info("No service risk data is currently available.")

st.divider()

st.subheader("Owner Accountability")
_show_dataframe(
    owner_accountability,
    "No owner accountability data is currently available.",
)

st.divider()

st.subheader("Cost Center View")
if not cost_center_view.empty and {"Cost Center", "Spend"}.issubset(cost_center_view.columns):
    fig = px.bar(
        cost_center_view,
        x="Cost Center",
        y="Spend",
        title="Cost Center Spend",
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
    )

_show_dataframe(
    cost_center_view,
    "No cost center data is currently available.",
)

st.divider()

st.subheader("Critical Applications")
_show_dataframe(
    critical_applications,
    "No critical applications are currently identified.",
)

st.divider()

st.subheader("High Spend Apps")
if not portfolio.empty:
    spend_threshold = portfolio["Application Spend"].quantile(0.75)
    high_spend = portfolio[portfolio["Application Spend"] >= spend_threshold]
    _show_dataframe(
        high_spend,
        "No high spend applications are currently identified.",
    )
else:
    st.info("No high spend applications are currently identified.")

st.divider()

st.subheader("Owner Gaps")
if not portfolio.empty:
    owner_gaps = portfolio[portfolio["Owner"].isin(["Unknown", "Unassigned"])]
    _show_dataframe(
        owner_gaps,
        "No owner gaps are currently identified.",
    )
else:
    st.info("No owner gaps are currently identified.")
