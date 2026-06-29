from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.sidebar_navigation import render_sidebar_navigation
from services.reporting_service import get_executive_summary
from services.supabase_client import supabase
from services.technology_spend_service import TechnologySpendService
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page


def fetch_rows(table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data or []
    except Exception:
        return []


def numeric_total(df, columns):
    for column in columns:
        if column in df.columns:
            return float(
                pd.to_numeric(df[column], errors="coerce")
                .fillna(0)
                .sum()
            )
    return 0.0


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def compact_currency(value):
    value = safe_float(value)
    if abs(value) >= 1000:
        return f"${value / 1000:,.1f}K".replace(".0K", "K")
    return f"${value:,.0f}"


def kpi_card(label, value, note=None):
    st.markdown(
        f"""
        <div style="
            border:1px solid #E5E7EB;
            border-radius:14px;
            padding:18px 20px;
            background:#FFFFFF;
            min-height:105px;
            box-shadow:0 1px 2px rgba(0,0,0,0.04);
        ">
            <div style="font-size:13px;color:#6B7280;margin-bottom:8px;">{label}</div>
            <div style="font-size:27px;font-weight:700;color:#111827;">{value}</div>
            <div style="font-size:12px;color:#6B7280;margin-top:6px;">{note or ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def panel_card(title, items):
    rows = "".join(
        f"""
        <div style="
            display:flex;
            justify-content:space-between;
            gap:16px;
            padding:9px 0;
            border-top:1px solid #F3F4F6;
        ">
            <span style="font-size:14px;color:#6B7280;">{label}</span>
            <span style="font-size:17px;font-weight:700;color:#111827;">{value}</span>
        </div>
        """
        for label, value in items
    )
    st.markdown(
        f"""
        <div style="
            border:1px solid #E5E7EB;
            border-radius:14px;
            padding:18px 20px;
            background:#FFFFFF;
            min-height:190px;
            box-shadow:0 1px 2px rgba(0,0,0,0.04);
        ">
            <div style="font-size:18px;font-weight:700;color:#111827;margin-bottom:8px;">{title}</div>
            {rows}
        </div>
        """,
        unsafe_allow_html=True,
    )


def attention_item(status, text):
    colors = {
        "green": "#16A34A",
        "yellow": "#D97706",
        "red": "#DC2626",
    }
    color = colors.get(status, "#6B7280")
    return f"""
        <div style="display:flex;align-items:flex-start;gap:10px;padding:9px 0;">
            <span style="
                width:11px;
                height:11px;
                border-radius:999px;
                background:{color};
                display:inline-block;
                margin-top:6px;
                flex:0 0 11px;
            "></span>
            <span style="font-size:15px;color:#111827;">{text}</span>
        </div>
    """


def render_attention_panel(items):
    st.markdown(
        f"""
        <div style="
            border:1px solid #E5E7EB;
            border-radius:14px;
            padding:18px 20px;
            background:#FFFFFF;
            box-shadow:0 1px 2px rgba(0,0,0,0.04);
        ">
            {''.join(items)}
        </div>
        """,
        unsafe_allow_html=True,
    )


configure_page(
    page_title="FinOps Dashboard | Nexora",
    page_icon="$",
)

init_session()

require_role([
    "finance",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

st.title("FinOps Dashboard")
st.caption(
    "Technology financial management, budgeting and forecasting"
)

kpis = TechnologySpendService.get_kpis()
executive_summary = get_executive_summary() or {}

budget_df = pd.DataFrame(fetch_rows("mart_budget_vs_actual"))
forecast_df = pd.DataFrame(fetch_rows("mart_enterprise_forecast"))
recommendations_df = pd.DataFrame(fetch_rows("recommendations"))

total_spend = safe_float(kpis.get("total_spend"))
cloud_cost = safe_float(kpis.get("cloud_cost"))
saas_cost = safe_float(kpis.get("saas_cost"))
msp_cost = safe_float(kpis.get("msp_cost"))
license_cost = safe_float(kpis.get("license_cost"))

budget_total = numeric_total(
    budget_df,
    ["budget", "budget_amount", "planned_cost"],
)

actual_total = numeric_total(
    budget_df,
    ["actual", "actual_cost", "total_cost", "cost"],
)

if not actual_total:
    actual_total = total_spend

budget_variance = actual_total - budget_total

forecast_total = numeric_total(
    forecast_df,
    [
        "projected_monthly_spend",
        "forecast_spend",
        "forecast_cost",
        "amount",
    ],
)

savings_identified = (
    safe_float(executive_summary.get("optimization_savings"))
    or safe_float(executive_summary.get("optimization"))
)

savings_realized = safe_float(executive_summary.get("savings_realized"))

if not savings_realized and not recommendations_df.empty and "estimated_savings" in recommendations_df.columns:
    statuses = (
        recommendations_df.get("status", pd.Series(dtype="object"))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    savings = pd.to_numeric(
        recommendations_df["estimated_savings"],
        errors="coerce",
    ).fillna(0)
    savings_realized = float(
        savings[
            statuses.isin(["IMPLEMENTED", "COMPLETED", "RESOLVED", "CLOSED"])
        ].sum()
    )

variance_status = "green" if budget_variance <= 0 else "yellow"
if budget_total and budget_variance > budget_total * 0.1:
    variance_status = "red"

st.markdown("### Financial KPIs")

kpi_cols = st.columns(5)
with kpi_cols[0]:
    kpi_card("Total Technology Spend", compact_currency(total_spend), "Cloud + SaaS + MSP + Licenses")
with kpi_cols[1]:
    kpi_card("Budget Variance", compact_currency(budget_variance), "Actual minus budget")
with kpi_cols[2]:
    kpi_card("Forecasted Spend", compact_currency(forecast_total), "Projected technology spend")
with kpi_cols[3]:
    kpi_card("Optimization Potential", compact_currency(savings_identified), "Identified savings")
with kpi_cols[4]:
    kpi_card("Savings Realized", compact_currency(savings_realized), "Implemented savings")

st.divider()

st.markdown("### Financial Attention Required")

render_attention_panel([
    attention_item(
        variance_status,
        "Technology spend is within budget"
        if budget_variance <= 0
        else f"Budget variance requires review: {compact_currency(budget_variance)} over plan",
    ),
    attention_item(
        "yellow" if forecast_total and forecast_total > actual_total else "green",
        f"Forecasted spend is {compact_currency(forecast_total)}"
        if forecast_total
        else "No forecast exposure currently available",
    ),
    attention_item(
        "yellow" if savings_identified else "green",
        f"{compact_currency(savings_identified)} optimization potential identified"
        if savings_identified
        else "No material optimization opportunity currently identified",
    ),
    attention_item(
        "green" if savings_realized else "yellow",
        f"{compact_currency(savings_realized)} savings realized"
        if savings_realized
        else "Savings realization needs follow-up",
    ),
    attention_item(
        "green",
        "Technology spend remains allocated across Cloud, SaaS, MSP and Licenses",
    ),
])

st.divider()

st.markdown("### Technology Spend Allocation")

allocation_df = pd.DataFrame([
    {"Category": "Cloud", "Amount": cloud_cost},
    {"Category": "SaaS", "Amount": saas_cost},
    {"Category": "MSP", "Amount": msp_cost},
    {"Category": "License", "Amount": license_cost},
])

allocation_display_df = allocation_df.copy()
allocation_display_df["Amount"] = allocation_display_df["Amount"].apply(compact_currency)

alloc_left, alloc_right = st.columns([1, 2])

with alloc_left:
    st.dataframe(
        allocation_display_df.rename(columns={"Amount": "Spend"}),
        use_container_width=True,
        hide_index=True,
    )

with alloc_right:
    fig = px.pie(
        allocation_df,
        names="Category",
        values="Amount",
        hole=0.45,
        title="Technology Spend Allocation",
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.markdown("### Budget vs Actual / Forecast")

budget_col, forecast_col = st.columns(2)

with budget_col:
    budget_chart_df = pd.DataFrame([
        {"Category": "Budget", "Amount": budget_total},
        {"Category": "Actual", "Amount": actual_total},
    ])
    fig = px.bar(
        budget_chart_df,
        x="Category",
        y="Amount",
        text="Amount",
        title="Budget vs Actual",
    )
    st.plotly_chart(fig, use_container_width=True)

with forecast_col:
    panel_card(
        "Forecast Summary",
        [
            ("Budget", compact_currency(budget_total)),
            ("Actual", compact_currency(actual_total)),
            ("Forecasted Spend", compact_currency(forecast_total)),
            ("Variance", compact_currency(budget_variance)),
        ],
    )

st.divider()

st.markdown("### Optimization Program")

optimization_cols = st.columns(4)
with optimization_cols[0]:
    kpi_card("Optimization Potential", compact_currency(savings_identified), "Identified savings")
with optimization_cols[1]:
    kpi_card("Savings Realized", compact_currency(savings_realized), "Implemented savings")
with optimization_cols[2]:
    kpi_card("SaaS + License", compact_currency(saas_cost + license_cost), "Subscription and license spend")
with optimization_cols[3]:
    kpi_card("MSP + Cloud", compact_currency(msp_cost + cloud_cost), "Infrastructure and services spend")

st.divider()

st.markdown("### Recommended Financial Actions")

render_attention_panel([
    attention_item(
        "red" if variance_status == "red" else "yellow" if budget_variance > 0 else "green",
        "Review budget variance and update forecast assumptions"
        if budget_variance > 0
        else "Maintain current budget controls",
    ),
    attention_item(
        "yellow" if savings_identified else "green",
        "Prioritize optimization opportunities with finance-approved savings targets"
        if savings_identified
        else "Continue monitoring optimization pipeline",
    ),
    attention_item(
        "yellow",
        "Review SaaS and license spend for consolidation opportunities",
    ),
    attention_item(
        "green" if savings_realized else "yellow",
        "Track realized savings against forecasted benefits",
    ),
    attention_item(
        "green",
        "Keep technology financial management across Cloud, SaaS, MSP and License spend",
    ),
])
