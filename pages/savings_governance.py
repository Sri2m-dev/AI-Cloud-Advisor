from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.savings_governance_service import SavingsGovernanceService


st.set_page_config(page_title="Savings Governance", layout="wide")


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if amount >= 1_000:
        value_k = amount / 1_000
        return f"${value_k:,.0f}K" if value_k.is_integer() else f"${value_k:,.1f}K"
    return f"${amount:,.0f}"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    formatted = df.copy()
    for column in columns:
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(_money)
    return formatted


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "finance")
    render_sidebar_navigation(role)

    st.title("Savings Governance")
    st.caption("Optimization lifecycle, implementation accountability, and realized savings governance")

    kpis = SavingsGovernanceService.get_kpis()

    st.subheader("KPI Row")
    cols = st.columns(6)
    cols[0].metric("Identified Savings", _money(kpis["total_identified_savings"]))
    cols[1].metric("Approved Savings", _money(kpis["approved_savings"]))
    cols[2].metric("Implemented Savings", _money(kpis["implemented_savings"]))
    cols[3].metric("Realized Savings", _money(kpis["realized_savings"]))
    cols[4].metric("Pipeline Value", _money(kpis["pipeline_value"]))
    cols[5].metric("Realization Rate", f"{kpis['realization_rate']:.0f}%")

    st.divider()
    st.subheader("Savings Funnel")
    funnel_df = SavingsGovernanceService.funnel_dataframe()
    if not funnel_df.empty:
        fig = px.funnel(funnel_df, x="Savings", y="Stage", title=None)
        fig.update_layout(margin={"l": 10, "r": 10, "t": 10, "b": 10}, height=320)
        st.plotly_chart(fig, use_container_width=True)
    _show_dataframe(_format_money_columns(funnel_df, ["Savings"]), "No savings funnel data is available.")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Savings by Domain")
        domain_df = SavingsGovernanceService.domain_dataframe()
        if not domain_df.empty:
            st.plotly_chart(px.bar(domain_df, x="Domain", y="Savings", color="Domain"), use_container_width=True)
        _show_dataframe(_format_money_columns(domain_df, ["Savings"]), "No domain savings data is available.")

    with right:
        st.subheader("Savings by Owner")
        owner_df = SavingsGovernanceService.owner_dataframe()
        if not owner_df.empty:
            st.plotly_chart(px.bar(owner_df, x="Owner", y="Savings", color="Owner"), use_container_width=True)
        _show_dataframe(_format_money_columns(owner_df, ["Savings"]), "No owner savings data is available.")

    st.divider()
    st.subheader("Implementation Backlog")
    _show_dataframe(
        _format_money_columns(SavingsGovernanceService.backlog_dataframe(), ["Potential Savings"]),
        "No implementation backlog is available.",
    )

    st.divider()
    st.subheader("Realized Savings Trend")
    trend_df = SavingsGovernanceService.trend_dataframe()
    if not trend_df.empty:
        st.plotly_chart(px.line(trend_df, x="Month", y="Realized Savings", markers=True), use_container_width=True)
    _show_dataframe(_format_money_columns(trend_df, ["Realized Savings"]), "No realized savings trend is available.")

    st.divider()
    st.subheader("Executive Narrative")
    st.info(SavingsGovernanceService.get_executive_narrative())


if __name__ == "__main__":
    main()
