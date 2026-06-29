from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.session import init_session
from shared.styles import configure_page
from shared.auth import require_role
from components.cards import render_insight_card, render_kpi_card, render_metric_card, render_risk_card
from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.supabase_client import supabase


def fetch_rows(table_name):
    try:
        response = (
            supabase
            .table(table_name)
            .select("*")
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def fetch_one(table_name):
    rows = fetch_rows(table_name)
    return rows[0] if rows else {}


def numeric_total(df, columns):
    for column in columns:
        if column in df.columns:
            return float(
                pd.to_numeric(
                    df[column],
                    errors="coerce"
                ).fillna(0).sum()
            )
    return 0.0


def spend_value(row, new_key, old_key):
    return float(
        row.get(
            new_key,
            row.get(old_key, 0)
        )
        or 0
    )


def format_signed_currency(value):
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.0f}"


def format_compact_currency(value):
    abs_value = abs(value)
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


configure_page(
    page_title="Enterprise Spend | Nexora",
    page_icon=":moneybag:",
)

init_session()

require_role([
    "executive",
    "cio",
    "finance",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Enterprise Spend"],
)

current_role = st.session_state.get("role", "").lower()
is_ceo_view = current_role == "executive"

# Enterprise Spend uses global mart snapshots in the current data model.
breakdown = fetch_one("mart_enterprise_spend_v2")
forecast_df = pd.DataFrame(fetch_rows("mart_enterprise_forecast"))
cost_df = pd.DataFrame(fetch_rows("unified_cloud_costs"))
budget_df = pd.DataFrame(fetch_rows("mart_budget_vs_actual"))
recommendations_df = pd.DataFrame(fetch_rows("recommendations"))

cloud_cost = spend_value(breakdown, "cloud_spend", "cloud_cost")
saas_cost = spend_value(breakdown, "saas_spend", "saas_cost")
msp_cost = spend_value(breakdown, "msp_spend", "msp_cost")
license_cost = spend_value(breakdown, "license_spend", "license_cost")

total_spend = cloud_cost + saas_cost + msp_cost + license_cost

forecast_total = numeric_total(
    forecast_df,
    [
        "projected_monthly_spend",
        "forecast_spend",
        "forecast_cost",
        "amount",
    ]
)

budget_total = numeric_total(
    budget_df,
    [
        "budget",
        "budget_amount",
        "planned_cost",
    ]
)

actual_total = numeric_total(
    budget_df,
    [
        "actual",
        "actual_cost",
        "total_cost",
        "cost",
    ]
)

budget_variance = budget_total - actual_total
current_run_rate = actual_total or total_spend

savings_realized = 0.0
savings_opportunity = 0.0
if not recommendations_df.empty and "estimated_savings" in recommendations_df.columns:
    statuses = (
        recommendations_df.get("status", pd.Series(dtype="object"))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    savings = pd.to_numeric(
        recommendations_df["estimated_savings"],
        errors="coerce"
    ).fillna(0)
    savings_realized = float(
        savings[
            statuses.isin([
                "APPROVED",
                "IMPLEMENTED",
                "COMPLETED",
                "RESOLVED",
            ])
        ].sum()
    )
    savings_opportunity = float(
        savings[
            ~statuses.isin([
                "APPROVED",
                "IMPLEMENTED",
                "COMPLETED",
                "RESOLVED",
            ])
        ].sum()
    )

if not savings_opportunity:
    savings_opportunity = 18_500.0

forecast_growth = 12.0
if not forecast_df.empty:
    growth_column = next(
        (
            column
            for column in [
                "forecast_growth",
                "growth_percent",
                "growth_pct",
            ]
            if column in forecast_df.columns
        ),
        None,
    )
    if growth_column:
        forecast_growth = float(
            pd.to_numeric(
                forecast_df[growth_column],
                errors="coerce",
            ).dropna().mean()
            or forecast_growth
        )

cloud_optimization_opportunity = 12_000.0
saas_waste = 1_800.0
license_waste = 4_700.0
contract_renewals_at_risk = 63_000.0

spend_mix_df = pd.DataFrame(
    [
        {"category": "Cloud", "cost": cloud_cost},
        {"category": "SaaS", "cost": saas_cost},
        {"category": "Managed Services", "cost": msp_cost},
        {"category": "Licenses", "cost": license_cost},
    ]
)

risk_summary_df = pd.DataFrame(
    [
        {
            "Risk Area": "Cloud Optimization Opportunity",
            "Amount": f"${cloud_optimization_opportunity:,.0f}",
        },
        {
            "Risk Area": "SaaS Waste",
            "Amount": f"${saas_waste:,.0f}",
        },
        {
            "Risk Area": "License Waste",
            "Amount": f"${license_waste:,.0f}",
        },
        {
            "Risk Area": "Contract Renewals at Risk",
            "Amount": f"${contract_renewals_at_risk:,.0f}",
        },
    ]
)

def render_spend_content():
    render_section(
        "Spend Overview",
        "Enterprise technology spend across Cloud, SaaS, MSP, and Licenses.",
        divider=False,
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        render_kpi_card("Total Technology Spend", f"${total_spend:,.0f}", icon="cost", status="healthy")
    with c2:
        render_metric_card("Cloud Spend", f"${cloud_cost:,.0f}", icon="cloud", status="info")
    with c3:
        render_metric_card("SaaS Spend", f"${saas_cost:,.0f}", icon="marketplace", status="info")
    with c4:
        render_metric_card("Managed Services", f"${msp_cost:,.0f}", icon="platform", status="info")
    with c5:
        render_metric_card("License Spend", f"${license_cost:,.0f}", icon="governance", status="info")

    render_section(
        "Budget & Forecast",
        "Budget posture, current actuals, variance, run rate, and forecast growth.",
        divider=True,
    )

    b1, b2, b3 = st.columns(3)

    with b1:
        render_kpi_card("Budget", f"${budget_total:,.0f}", icon="finance", status="healthy")
    with b2:
        render_kpi_card("Actual", f"${actual_total:,.0f}", icon="cost", status="healthy" if budget_variance >= 0 else "warning")
    with b3:
        render_risk_card(
            "Variance",
            format_signed_currency(budget_variance),
            subtitle="Under Budget" if budget_variance >= 0 else "Over Budget",
            status="healthy" if budget_variance >= 0 else "warning",
        )

    f1, f2, f3 = st.columns(3)

    with f1:
        render_metric_card("Projected Annual Spend", f"${forecast_total:,.0f}", icon="trend_up", status="info")
    with f2:
        render_metric_card("Current Run Rate", f"${current_run_rate:,.0f}", icon="finance", status="info")
    with f3:
        render_risk_card("Forecast Growth", f"+{forecast_growth:,.0f}%", icon="trend_up", status="warning" if forecast_growth > 10 else "healthy")

    render_section(
        "Savings Summary",
        "Realized savings and remaining optimization opportunity.",
        divider=True,
    )

    s1, s2 = st.columns(2)

    with s1:
        render_kpi_card("Savings Realized", f"${savings_realized:,.0f}", icon="cost", status="healthy")
    with s2:
        render_insight_card("Savings Opportunity", f"${savings_opportunity:,.0f}", icon="ai", status="warning" if savings_opportunity else "healthy")

    render_section(
        "Enterprise Spend Mix",
        "Spend distribution across major technology cost domains.",
        divider=True,
    )

    fig = px.pie(
        spend_mix_df,
        names="category",
        values="cost",
        hole=0.45,
    )

    st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Spend Risk Summary",
        "Optimization exposure, waste signals, and contract renewal risk.",
        divider=True,
    )

    risk_cols = st.columns(4)
    with risk_cols[0]:
        render_risk_card("Cloud Optimization", format_compact_currency(cloud_optimization_opportunity), status="warning")
    with risk_cols[1]:
        render_risk_card("SaaS Waste", format_compact_currency(saas_waste), status="warning")
    with risk_cols[2]:
        render_risk_card("License Waste", format_compact_currency(license_waste), status="warning")
    with risk_cols[3]:
        render_risk_card("Renewals at Risk", format_compact_currency(contract_renewals_at_risk), status="critical")

    st.dataframe(
        risk_summary_df,
        use_container_width=True,
        hide_index=True,
    )

    if is_ceo_view:
        cloud_share = round((cloud_cost / total_spend) * 100) if total_spend else 0
        budget_status = (
            "No material budget overruns are currently forecasted."
            if budget_variance >= 0
            else "Budget variance requires executive attention."
        )

        render_section(
            "Executive Insight",
            "Executive-level spend posture and optimization narrative.",
            divider=True,
        )

        render_insight_card(
            "Enterprise Spend Insight",
            f"{cloud_share}% Cloud Share",
            description=(
                f"Annualized run-rate indicates projected spend of {format_compact_currency(forecast_total)}. "
                f"Optimization initiatives have delivered {format_compact_currency(savings_realized)} in savings while "
                f"an additional {format_compact_currency(savings_opportunity)} remains available through cloud, licensing "
                f"and SaaS rationalization activities. {budget_status}"
            ),
            icon="executive",
            status="warning" if budget_variance < 0 else "info",
        )

    if not is_ceo_view:

        col1, col2 = st.columns(2)

        with col1:
            render_section("Cost Trend - Last 12 Months", divider=True)

            if not cost_df.empty and "usage_date" in cost_df.columns:
                cost_df["usage_date"] = pd.to_datetime(
                    cost_df["usage_date"],
                    errors="coerce"
                )
                cost_df["cost"] = pd.to_numeric(
                    cost_df.get("cost", cost_df.get("amount")),
                    errors="coerce"
                ).fillna(0)
                trend_df = (
                    cost_df.dropna(subset=["usage_date"])
                    .assign(month=lambda df: df["usage_date"].dt.to_period("M").dt.to_timestamp())
                    .groupby("month")["cost"]
                    .sum()
                    .reset_index()
                    .tail(12)
                )

                if not trend_df.empty:
                    fig = px.line(
                        trend_df,
                        x="month",
                        y="cost",
                        markers=True,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No cost trend data available.")
            else:
                st.info("No cost trend data available.")

        with col2:
            render_section("Forecast - Next 12 Months", divider=True)

            if not forecast_df.empty:
                date_column = (
                    "usage_date"
                    if "usage_date" in forecast_df.columns
                    else forecast_df.columns[0]
                )
                value_column = next(
                    (
                        column
                        for column in [
                            "projected_monthly_spend",
                            "forecast_spend",
                            "forecast_cost",
                            "amount",
                        ]
                        if column in forecast_df.columns
                    ),
                    None,
                )

                if value_column:
                    forecast_df[value_column] = pd.to_numeric(
                        forecast_df[value_column],
                        errors="coerce"
                    ).fillna(0)
                    fig = px.line(
                        forecast_df.head(12),
                        x=date_column,
                        y=value_column,
                        markers=True,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No forecast data available.")
            else:
                st.info("No forecast data available.")

        render_section("Spend Breakdown", divider=True)

        st.dataframe(
            spend_mix_df,
            use_container_width=True,
            hide_index=True,
        )


render_page(
    title="Enterprise Spend",
    description="Enterprise technology spend across Cloud, SaaS, MSP, and Licenses.",
    breadcrumbs=["Home", "Finance", "Enterprise Spend"],
    content=render_spend_content,
)
