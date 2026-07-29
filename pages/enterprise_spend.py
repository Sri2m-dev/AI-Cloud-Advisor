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
from services.enterprise_spend_certification_service import EnterpriseSpendCertificationService
from auth.authenticated_tenant import AuthenticatedTenantError
from services.enterprise_spend_composition import (
    authenticated_tenant_context,
    enterprise_spend_service,
)


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

current_role = st.session_state.get("role", "").lower()
is_ceo_view = current_role == "executive"

try:
    tenant_context = authenticated_tenant_context(st.session_state)
    dashboard = EnterpriseSpendCertificationService.get_dashboard(
        tenant_context,
        enterprise_spend_service(),
    )
except AuthenticatedTenantError as exc:
    st.error(f"Financial data unavailable: {exc}")
    st.stop()

role = st.session_state.get("role", "Unknown")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Enterprise Spend"],
)
metrics = dashboard["metrics"]
dataframes = dashboard["dataframes"]
financial_model = dashboard["financial_model"]
reconciliation = dashboard["reconciliation"]
reconciliation_cards = dashboard["reconciliation_cards"]
evidence = dashboard["evidence"]
format_signed_currency = EnterpriseSpendCertificationService.format_signed_currency
format_compact_currency = EnterpriseSpendCertificationService.format_compact_currency

forecast_df = dataframes["forecast"]
cost_df = dataframes["cost"]
spend_mix_df = dataframes["spend_mix"]
risk_summary_df = dataframes["risk_summary"]

cloud_cost = metrics["cloud_cost"]
saas_cost = metrics["saas_cost"]
msp_cost = metrics["msp_cost"]
license_cost = metrics["license_cost"]
total_spend = metrics["total_spend"]
forecast_total = metrics["forecast_total"]
budget_total = metrics["budget_total"]
actual_total = metrics["actual_total"]
budget_variance = metrics["budget_variance"]
current_run_rate = metrics["current_run_rate"]
savings_realized = metrics["savings_realized"]
savings_opportunity = metrics["savings_opportunity"]
forecast_growth = metrics["forecast_growth"]
cloud_optimization_opportunity = metrics["cloud_optimization_opportunity"]
saas_waste = metrics["saas_waste"]
license_waste = metrics["license_waste"]
contract_renewals_at_risk = metrics["contract_renewals_at_risk"]

def render_spend_content():
    posture = dashboard["financial_posture"]
    if posture.quarantined_spend:
        st.warning(
            f"{posture.quarantined_spend:,.2f} {posture.currency} of cloud spend "
            f"is reconciled but quarantined because {posture.unknown_account_count} "
            "cloud accounts require ownership approval. It is not included in "
            "business allocation."
        )
    render_section(
        "Executive Summary",
        "Executive view of enterprise spend, allocation confidence, and optimization opportunity.",
        divider=False,
    )

    render_insight_card(
        "Executive Summary",
        "Enterprise Spend",
        description=dashboard["executive_summary"],
        icon="executive",
        status="warning" if reconciliation.get("status") == "Variance Detected" else "info",
    )

    render_section(
        "Data Reconciliation Status",
        "Canonical financial model status for enterprise spend reporting.",
        divider=True,
    )

    r1, r2, r3, r4 = st.columns(4)
    with r1:
        render_insight_card(
            "Reconciliation Status",
            reconciliation_cards["status"],
            subtitle="Enterprise Financial Model",
            icon="governance",
            status="warning" if reconciliation_cards["status"] == "Variance Detected" else "healthy",
        )
    with r2:
        render_metric_card(
            "Allocation Coverage",
            reconciliation_cards["allocation_coverage_display"],
            icon="finance",
            status="healthy" if reconciliation_cards["allocation_coverage"] >= 90 else "warning",
        )
    with r3:
        render_kpi_card(
            "Allocated Spend",
            format_compact_currency(financial_model.get("allocated_spend")),
            icon="cost",
            status="healthy",
        )
    with r4:
        render_risk_card(
            "Unallocated Spend",
            format_compact_currency(financial_model.get("unallocated_spend")),
            icon="risk",
            status="warning" if reconciliation_cards["unallocated_spend"] else "healthy",
        )

    render_section(
        "Spend Overview",
        "Enterprise technology spend across Cloud, SaaS, MSP, and Licenses.",
        divider=True,
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

    render_section(
        "Evidence",
        "Source data, coverage, financial reconciliation, AI interpretation, and raw evidence supporting Enterprise Spend.",
        divider=True,
    )

    evidence_tabs = st.tabs([
        "Source Data",
        "Data Coverage",
        "Financial Reconciliation",
        "AI Interpretation",
        "Raw Evidence",
    ])

    with evidence_tabs[0]:
        st.dataframe(pd.DataFrame(evidence["source_data"]), use_container_width=True, hide_index=True)
    with evidence_tabs[1]:
        st.dataframe(pd.DataFrame(evidence["data_coverage"]), use_container_width=True, hide_index=True)
    with evidence_tabs[2]:
        st.dataframe(pd.DataFrame(evidence["financial_reconciliation"]), use_container_width=True, hide_index=True)
    with evidence_tabs[3]:
        st.write(evidence["ai_interpretation"])
    with evidence_tabs[4]:
        st.caption("Financial Model")
        st.dataframe(
            pd.DataFrame(evidence["raw_evidence"]["Financial Model"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Fallback Risk Signals")
        st.dataframe(
            pd.DataFrame(evidence["raw_evidence"]["Fallback Risk Signals"]),
            use_container_width=True,
            hide_index=True,
        )


render_page(
    title="Enterprise Spend",
    description="Enterprise technology spend across Cloud, SaaS, MSP, and Licenses.",
    breadcrumbs=["Home", "Finance", "Enterprise Spend"],
    content=render_spend_content,
)
