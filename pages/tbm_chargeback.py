from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.tbm_service import TBMService


st.set_page_config(page_title="TBM & Chargeback", layout="wide")


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
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


def _format_kpi_table(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    money_kpis = {"Total Allocated Spend", "Unallocated Spend"}
    formatted["Value"] = formatted.apply(
        lambda row: _money(row["Value"]) if row["KPI"] in money_kpis else row["Value"],
        axis=1,
    )
    return formatted


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)

    st.title("TBM & Chargeback")
    st.caption("Technology Business Management costing, showback, and chargeback readiness")

    kpis = TBMService.get_kpis()

    st.subheader("TBM KPIs")
    cols = st.columns(6)
    cols[0].metric("Total Allocated Spend", _money(kpis["total_allocated_spend"]))
    cols[1].metric("Unallocated Spend", _money(kpis["unallocated_spend"]))
    cols[2].metric("Business Units", f"{kpis['business_units']:,}")
    cols[3].metric("Applications", f"{kpis['applications']:,}")
    cols[4].metric("Services", f"{kpis['services']:,}")
    cols[5].metric("Chargeback Readiness", kpis["chargeback_readiness"])
    _show_dataframe(_format_kpi_table(TBMService.kpi_dataframe()), "No TBM KPIs are available.")

    st.divider()
    st.subheader("Business Unit Costing")
    _show_dataframe(
        _format_money_columns(
            TBMService.business_unit_costing_dataframe(),
            ["Allocated Spend", "Technology Exposure"],
        ),
        "No business unit costing is available.",
    )

    st.divider()
    st.subheader("Application TCO")
    _show_dataframe(
        _format_money_columns(
            TBMService.application_tco_dataframe(),
            ["Cloud", "SaaS", "AI", "MSP", "License", "Total Cost"],
        ),
        "No application TCO is available.",
    )

    st.divider()
    st.subheader("Business Service Costing")
    _show_dataframe(
        _format_money_columns(
            TBMService.business_service_costing_dataframe(),
            ["Technology Exposure", "Annual Cost"],
        ),
        "No business service costing is available.",
    )

    st.divider()
    st.subheader("Showback / Chargeback")
    _show_dataframe(
        _format_money_columns(
            TBMService.showback_chargeback_dataframe(),
            ["Allocated Cost", "Unallocated Cost"],
        ),
        "No showback or chargeback recommendations are available.",
    )

    st.divider()
    st.subheader("Executive Narrative")
    st.info(TBMService.get_executive_narrative())


if __name__ == "__main__":
    main()
