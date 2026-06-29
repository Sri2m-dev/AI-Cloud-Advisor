from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from repositories.leadership_repository import LeadershipDashboardRepository


def _df(rows) -> pd.DataFrame:
    return pd.DataFrame(rows or [])


def _to_float(value, default=0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _sum_column(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


@st.cache_data(ttl=300, show_spinner=False)
def get_leadership_dashboard_metrics(organization_id: str | None = None) -> dict[str, Any]:

    enterprise_spend = LeadershipDashboardRepository.get_enterprise_spend()
    spend_breakdown = LeadershipDashboardRepository.get_enterprise_spend_breakdown()
    savings_row = LeadershipDashboardRepository.get_savings()

    approvals_df = _df(LeadershipDashboardRepository.get_approval_requests())
    optimization_df = _df(LeadershipDashboardRepository.get_optimization_opportunities())
    anomalies_df = _df(LeadershipDashboardRepository.get_cost_anomalies())
    recommendations_df = _df(LeadershipDashboardRepository.get_recommendations())

    total_spend = _to_float(enterprise_spend.get("total_spend", 0))

    cloud_cost = _to_float(spend_breakdown.get("cloud_cost", 0))
    saas_cost = _to_float(spend_breakdown.get("saas_cost", 0))
    msp_cost = _to_float(spend_breakdown.get("msp_cost", 0))
    license_cost = _to_float(spend_breakdown.get("license_cost", 0))

    identified_savings = _to_float(savings_row.get("savings", 0))
    optimized_cost = _to_float(savings_row.get("optimized_cost", 0))
    realized_savings = max(total_spend - optimized_cost, 0) if optimized_cost else 0
    pending_savings = max(identified_savings - realized_savings, 0)

    pending_approvals = 0
    if not approvals_df.empty and "status" in approvals_df.columns:
        pending_approvals = int(
            approvals_df["status"]
            .fillna("")
            .astype(str)
            .str.upper()
            .isin(["PENDING", "PENDING_APPROVAL"])
            .sum()
        )

    active_anomalies = len(anomalies_df)
    optimization_items = len(optimization_df)

    governance_score = 79.0
    security_score = max(0.0, 100.0 - active_anomalies * 0.5)
    sla_compliance = 100.0 if pending_approvals <= 3 else 85.0

    customer_health_score = round(
        governance_score * 0.35
        + security_score * 0.25
        + sla_compliance * 0.20
        + 90.0 * 0.20,
        1,
    )

    if customer_health_score >= 85:
        customer_health_label = "Healthy"
    elif customer_health_score >= 70:
        customer_health_label = "Watch"
    else:
        customer_health_label = "At Risk"

    spend_by_cloud = []
    if not optimization_df.empty and {"cloud", "total_cost"}.issubset(optimization_df.columns):
        working = optimization_df.copy()
        working["spend"] = pd.to_numeric(
            working["total_cost"],
            errors="coerce",
        ).fillna(0)
        spend_by_cloud = (
            working
            .groupby("cloud", dropna=False)["spend"]
            .sum()
            .reset_index()
            .to_dict("records")
        )

    return {
        "kpis": {
            "total_spend": total_spend,
            "cloud_cost": cloud_cost,
            "saas_cost": saas_cost,
            "msp_cost": msp_cost,
            "license_cost": license_cost,
            "savings_identified": identified_savings,
            "savings_realized": realized_savings,
            "sla_compliance": sla_compliance,
            "security_score": security_score,
            "governance_score": governance_score,
            "customer_health_score": customer_health_score,
            "customer_health_label": customer_health_label,
            "pending_approvals": pending_approvals,
            "active_anomalies": active_anomalies,
            "optimization_items": optimization_items,
        },
        "savings": {
            "identified": identified_savings,
            "realized": realized_savings,
            "pending": pending_savings,
            "realization_rate": round(
                realized_savings / identified_savings * 100,
                1,
            ) if identified_savings else 0.0,
        },
        "sla": {
            "compliance": sla_compliance,
            "breaches": 0,
            "trend": [],
        },
        "security": {
            "score": security_score,
            "critical": 0,
            "high": 0,
            "open_findings": active_anomalies,
        },
        "customer_health": {
            "score": customer_health_score,
            "label": customer_health_label,
            "platform_health": security_score,
        },
        "spend_by_cloud": spend_by_cloud,
        "security_by_severity": [],
        "health_rows": [],
        "approvals": approvals_df.to_dict("records"),
        "optimization_opportunities": optimization_df.to_dict("records"),
        "anomalies": anomalies_df.to_dict("records"),
        "recommendations": recommendations_df.to_dict("records"),
    }