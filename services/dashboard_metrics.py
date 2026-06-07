"""Business metrics for the Executive Dashboard."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd
import streamlit as st

from repositories.dashboard_repository import DashboardRepository


DETAIL_COLUMNS = ["details", "actions", "workflow", "assign", "snooze"]


def _to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _status_series(df: pd.DataFrame) -> pd.Series:
    return (
        df["status"]
        .fillna("")
        .astype(str)
        .str.upper()
    )


def _numeric_series(
    df: pd.DataFrame,
    preferred: str,
    fallback: str | None = None,
) -> pd.Series:
    if preferred in df.columns:
        return pd.to_numeric(df[preferred], errors="coerce").fillna(0)

    if fallback and fallback in df.columns:
        return pd.to_numeric(df[fallback], errors="coerce").fillna(0)

    return pd.Series(dtype="float64")


def _calculate_total_spend(cost_df: pd.DataFrame) -> float:
    if cost_df.empty:
        return 0.0

    spend = _numeric_series(cost_df, "cost", "amount")
    return round(float(spend.sum()), 2)


def _calculate_governance_score(
    recommendations_df: pd.DataFrame,
    approvals_df: pd.DataFrame,
) -> dict[str, Any]:

    if recommendations_df.empty:
        idle_count = 0
        gov_violations = 0
        optimization_coverage = 0.0
        savings_realization = 0.0

    else:

        rec_type = (
            recommendations_df.get(
                "recommendation_type",
                pd.Series(dtype="object"),
            )
            .fillna("")
            .astype(str)
        )

        title = (
            recommendations_df.get(
                "title",
                pd.Series(dtype="object"),
            )
            .fillna("")
            .astype(str)
        )

        idle_count = len(
            recommendations_df[
                (rec_type == "Cost Optimization")
                & (title == "Idle Resource Detected")
            ]
        )

        gov_violations = len(
            recommendations_df[
                rec_type == "Governance"
            ]
        )

        statuses = _status_series(recommendations_df)

        completed_statuses = [
            "APPROVED",
            "IMPLEMENTED",
            "COMPLETED",
            "RESOLVED",
        ]

        completed = recommendations_df[
            statuses.isin(completed_statuses)
        ]

        optimization_coverage = round(
            len(completed)
            / max(len(recommendations_df), 1),
            2,
        )

        if (
            not completed.empty
            and "estimated_savings" in completed.columns
        ):
            savings = pd.to_numeric(
                completed["estimated_savings"],
                errors="coerce",
            ).fillna(0)

            savings_realization = float(
                savings.sum()
            )

        else:
            savings_realization = 0.0

    sla_compliance = _calculate_sla_compliance(
        approvals_df
    )

    idle_score = max(
        0,
        1 - idle_count / 10,
    )

    governance_score = max(
        0,
        1 - gov_violations / 10,
    )

    savings_score = min(
        1.0,
        savings_realization / 10000,
    )

    final_score = round(
        (
            idle_score
            + governance_score
            + optimization_coverage
            + sla_compliance
            + savings_score
        )
        / 5,
        2,
    )

    return {
        "overall_score": round(final_score * 100, 0),
        "idle_score": round(idle_score * 100, 0),
        "governance_score": round(governance_score * 100, 0),
        "optimization_coverage": round(optimization_coverage * 100, 0),
        "sla_compliance": round(sla_compliance * 100, 0),
        "savings_realization": round(savings_score * 100, 0),
    }


def _calculate_sla_compliance(
    approvals_df: pd.DataFrame,
) -> float:

    if approvals_df.empty:
        return 0.0

    if not {
        "created_at",
        "completed_at",
    }.issubset(approvals_df.columns):
        return 0.0

    completed = approvals_df.dropna(
        subset=["completed_at"]
    ).copy()

    if completed.empty:
        return 0.0

    completed["created_at"] = pd.to_datetime(
        completed["created_at"],
        errors="coerce",
    )

    completed["completed_at"] = pd.to_datetime(
        completed["completed_at"],
        errors="coerce",
    )

    completed = completed.dropna(
        subset=["created_at", "completed_at"]
    )

    if completed.empty:
        return 0.0

    sla_met = (
        completed["completed_at"]
        - completed["created_at"]
    ) <= timedelta(days=3)

    return round(
        float(sla_met.sum())
        / len(completed),
        2,
    )


def _spend_by_cloud(cost_df: pd.DataFrame):
    if cost_df.empty or "cloud" not in cost_df.columns:
        return []

    working = cost_df.copy()
    working["spend"] = _numeric_series(
        working,
        "cost",
        "amount",
    )

    return (
        working.groupby("cloud")["spend"]
        .sum()
        .reset_index()
        .to_dict("records")
    )


def _daily_spend_trend(cost_df: pd.DataFrame):
    if cost_df.empty or "usage_date" not in cost_df.columns:
        return []

    working = cost_df.copy()

    working["date"] = pd.to_datetime(
        working["usage_date"],
        errors="coerce",
    ).dt.date

    working["spend"] = _numeric_series(
        working,
        "cost",
        "amount",
    )

    working = working.dropna(
        subset=["date"]
    )

    if working.empty:
        return []

    return (
        working.groupby("date")["spend"]
        .sum()
        .reset_index()
        .to_dict("records")
    )


def _top_services(cost_df: pd.DataFrame):
    if cost_df.empty:
        return []

    if "service_name" not in cost_df.columns:
        return []

    working = cost_df.copy()

    working["spend"] = _numeric_series(
        working,
        "cost",
        "amount",
    )

    return (
        working.groupby("service_name")["spend"]
        .sum()
        .reset_index()
        .rename(columns={"service_name": "service"})
        .sort_values(by="spend", ascending=False)
        .head(10)
        .to_dict("records")
    )


def _recommendation_breakdown(
    recommendations_df: pd.DataFrame,
):
    if recommendations_df.empty:
        return []

    type_column = (
        "type"
        if "type" in recommendations_df.columns
        else "recommendation_type"
    )

    if type_column not in recommendations_df.columns:
        return []

    return (
        recommendations_df[type_column]
        .fillna("Other")
        .astype(str)
        .value_counts()
        .rename_axis("type")
        .reset_index(name="count")
        .to_dict("records")
    )


def _top_recommendations(
    recommendations_df: pd.DataFrame,
):
    if recommendations_df.empty:
        return pd.DataFrame()

    if "estimated_savings" not in recommendations_df.columns:
        return pd.DataFrame()

    working = recommendations_df.copy()

    working["estimated_savings"] = pd.to_numeric(
        working["estimated_savings"],
        errors="coerce",
    ).fillna(0)

    if "service" in working.columns:
        working = working[
            working["service"].notna()
        ]

    if "description" in working.columns:
        working = working[
            working["description"].notna()
        ]

    return (
        working.sort_values(
            by="estimated_savings",
            ascending=False,
        )
        .head(5)
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_executive_dashboard_metrics(
    organization_id: str,
) -> dict[str, Any]:

    recommendations = DashboardRepository.fetch_recommendations(
        organization_id
    )

    cost_rows = DashboardRepository.fetch_cost_rows(
        organization_id
    )

    approval_queue = DashboardRepository.fetch_approval_queue(
        organization_id
    )

    anomalies = DashboardRepository.fetch_anomalies(
        organization_id
    )

    recommendations_df = _to_frame(recommendations)
    cost_df = _to_frame(cost_rows)
    approvals_df = _to_frame(approval_queue)

    total_spend = _calculate_total_spend(cost_df)

    governance_score = _calculate_governance_score(
        recommendations_df,
        approvals_df,
    )

    pending_recommendations = 0
    completed_savings = 0.0
    savings_opportunity = 0.0

    if (
        not recommendations_df.empty
        and "status" in recommendations_df.columns
    ):

        statuses = _status_series(
            recommendations_df
        )

        pending_statuses = [
            "NEW",
            "PENDING_APPROVAL",
            "ASSIGNED",
            "IN_PROGRESS",
        ]

        completed_statuses = [
            "APPROVED",
            "IMPLEMENTED",
            "COMPLETED",
            "RESOLVED",
        ]

        pending_recommendations = int(
            statuses.isin(
                pending_statuses
            ).sum()
        )

        if (
            "estimated_savings"
            in recommendations_df.columns
        ):

            savings = pd.to_numeric(
                recommendations_df[
                    "estimated_savings"
                ],
                errors="coerce",
            ).fillna(0)

            completed_savings = float(
                savings[
                    statuses.isin(
                        completed_statuses
                    )
                ].sum()
            )

            savings_opportunity = float(
                savings[
                    statuses.isin(
                        pending_statuses
                    )
                ].sum()
            )

    return {
        "recommendations_df": recommendations_df,
        "total_spend": total_spend,
        "governance_score": governance_score,
        "governance_metrics": {
            "compliance": governance_score["governance_score"],
            "optimization": governance_score["optimization_coverage"],
            "sla": governance_score["sla_compliance"],
            "idle_resources": governance_score["idle_score"],
            "security": governance_score["governance_score"],
        },
        "pending_recommendations": pending_recommendations,
        "completed_savings": completed_savings,
        "savings_opportunity": savings_opportunity,
        "spend_by_cloud": _spend_by_cloud(cost_df),
        "daily_spend_trend": _daily_spend_trend(cost_df),
        "top_services": _top_services(cost_df),
        "recommendation_breakdown": _recommendation_breakdown(recommendations_df),
        "anomalies": anomalies,
        "top_recommendations": _top_recommendations(recommendations_df),
    }