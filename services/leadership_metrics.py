"""Business metrics for leadership dashboards."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd
import streamlit as st

from repositories.leadership_repository import LeadershipDashboardRepository


def _to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _numeric(df: pd.DataFrame, preferred: str, fallback: str | None = None) -> pd.Series:
    if preferred in df.columns:
        return pd.to_numeric(df[preferred], errors="coerce").fillna(0)
    if fallback and fallback in df.columns:
        return pd.to_numeric(df[fallback], errors="coerce").fillna(0)
    return pd.Series(dtype="float64")


def _status(df: pd.DataFrame) -> pd.Series:
    if "status" not in df.columns:
        return pd.Series(dtype="object")
    return df["status"].fillna("").astype(str).str.upper()


def _total_spend(cost_df: pd.DataFrame) -> float:
    if cost_df.empty:
        return 0.0
    return float(_numeric(cost_df, "cost", "amount").sum())


def _savings_summary(recommendations_df: pd.DataFrame) -> dict[str, float]:
    if recommendations_df.empty or "estimated_savings" not in recommendations_df.columns:
        return {"identified": 0.0, "realized": 0.0, "pending": 0.0, "realization_rate": 0.0}

    savings = pd.to_numeric(recommendations_df["estimated_savings"], errors="coerce").fillna(0)
    statuses = _status(recommendations_df)
    realized_mask = statuses.isin(["COMPLETED", "IMPLEMENTED", "CLOSED", "APPROVED"])
    pending_mask = statuses.isin(["PENDING", "PENDING_APPROVAL", "NEW", "ESCALATED"])
    identified = float(savings.sum())
    realized = float(savings[realized_mask].sum())
    pending = float(savings[pending_mask].sum())
    return {
        "identified": identified,
        "realized": realized,
        "pending": pending,
        "realization_rate": round((realized / identified) * 100, 1) if identified else 0.0,
    }


def _sla_summary(approvals_df: pd.DataFrame) -> dict[str, Any]:
    if approvals_df.empty:
        return {"compliance": 100.0, "breaches": 0, "trend": []}

    working = approvals_df.copy()
    working["created_at"] = pd.to_datetime(working.get("created_at"), errors="coerce")
    completed_source = pd.to_datetime(working.get("completed_at"), errors="coerce")
    if "approved_at" in working.columns:
        approved_source = pd.to_datetime(working["approved_at"], errors="coerce")
        completed_source = completed_source.fillna(approved_source)
    working["completed_at"] = completed_source

    if "sla_due" in working.columns:
        working["sla_due"] = pd.to_datetime(working["sla_due"], errors="coerce")
        met = working["completed_at"].notna() & working["sla_due"].notna() & (working["completed_at"] <= working["sla_due"])
        breached = working["sla_due"].notna() & (~met)
    else:
        elapsed = working["completed_at"] - working["created_at"]
        met = elapsed <= timedelta(days=3)
        breached = working["completed_at"].notna() & (~met)

    valid = working["created_at"].notna()
    compliance = round(float(met[valid].sum()) / max(int(valid.sum()), 1) * 100, 1)
    working["date"] = working["created_at"].dt.date
    trend_df = (
        working[valid]
        .assign(sla_met=met)
        .groupby("date", dropna=True)["sla_met"]
        .mean()
        .mul(100)
        .reset_index(name="sla_compliance")
    )
    return {
        "compliance": compliance,
        "breaches": int(breached.sum()),
        "trend": trend_df.to_dict("records"),
    }


def _security_posture(security_df: pd.DataFrame, alerts_df: pd.DataFrame) -> dict[str, Any]:
    if security_df.empty and alerts_df.empty:
        return {"score": 100.0, "critical": 0, "high": 0, "open_findings": 0, "by_severity": []}

    if security_df.empty:
        open_findings = security_df
    elif "status" in security_df.columns:
        finding_status = _status(security_df)
        open_findings = security_df[finding_status.isin(["", "OPEN", "ACTIVE", "NEW"])]
    else:
        open_findings = security_df
    severity = open_findings.get("severity", pd.Series(dtype="object")).fillna("Unknown").astype(str).str.upper()
    critical = int((severity == "CRITICAL").sum())
    high = int((severity == "HIGH").sum())

    alert_severity = alerts_df.get("severity", pd.Series(dtype="object")).fillna("").astype(str).str.upper() if not alerts_df.empty else pd.Series(dtype="object")
    critical_alerts = int((alert_severity == "CRITICAL").sum())
    high_alerts = int((alert_severity == "HIGH").sum())

    score = max(0.0, 100.0 - critical * 12 - high * 6 - critical_alerts * 8 - high_alerts * 4)
    by_severity = severity.value_counts().rename_axis("severity").reset_index(name="count").to_dict("records")
    return {
        "score": round(score, 1),
        "critical": critical + critical_alerts,
        "high": high + high_alerts,
        "open_findings": int(len(open_findings)),
        "by_severity": by_severity,
    }


def _customer_health_score(
    *,
    governance_score: float,
    sla_compliance: float,
    security_score: float,
    savings_realization_rate: float,
    health_df: pd.DataFrame,
) -> dict[str, Any]:
    health_component = 100.0
    if not health_df.empty:
        status = health_df.get("status", pd.Series(dtype="object")).fillna("").astype(str).str.lower()
        error_penalty = int(status.isin(["error", "failed", "critical"]).sum()) * 8
        stale_penalty = int(status.isin(["stale", "warning"]).sum()) * 4
        health_component = max(0.0, 100.0 - error_penalty - stale_penalty)

    governance_component = governance_score if governance_score > 0 else 100.0
    score = (
        governance_component * 0.25
        + sla_compliance * 0.20
        + security_score * 0.25
        + min(savings_realization_rate, 100.0) * 0.15
        + health_component * 0.15
    )
    if score >= 85:
        label = "Healthy"
    elif score >= 70:
        label = "Watch"
    else:
        label = "At Risk"
    return {"score": round(score, 1), "label": label, "platform_health": round(health_component, 1)}


def _latest_governance_score(governance_df: pd.DataFrame) -> float:
    if governance_df.empty:
        return 0.0
    for column in ("smoothed_score", "raw_score"):
        if column in governance_df.columns:
            value = pd.to_numeric(governance_df[column], errors="coerce").dropna()
            if not value.empty:
                return float(value.iloc[0])
    return 0.0


@st.cache_data(ttl=300, show_spinner=False)
def get_leadership_dashboard_metrics(organization_id: str) -> dict[str, Any]:
    cost_df = _to_frame(LeadershipDashboardRepository.fetch_cost_rows(organization_id))
    recommendations_df = _to_frame(LeadershipDashboardRepository.fetch_recommendations(organization_id))
    approvals_df = _to_frame(LeadershipDashboardRepository.fetch_approvals(organization_id))
    security_df = _to_frame(LeadershipDashboardRepository.fetch_security_findings(organization_id))
    health_df = _to_frame(LeadershipDashboardRepository.fetch_workspace_health(organization_id))
    alerts_df = _to_frame(LeadershipDashboardRepository.fetch_alert_history(organization_id))
    governance_df = _to_frame(LeadershipDashboardRepository.fetch_governance_scores(organization_id))

    total_spend = _total_spend(cost_df)
    savings = _savings_summary(recommendations_df)
    sla = _sla_summary(approvals_df)
    security = _security_posture(security_df, alerts_df)
    governance_score = _latest_governance_score(governance_df)
    customer_health = _customer_health_score(
        governance_score=governance_score,
        sla_compliance=sla["compliance"],
        security_score=security["score"],
        savings_realization_rate=savings["realization_rate"],
        health_df=health_df,
    )

    spend_by_cloud = []
    if not cost_df.empty and "cloud" in cost_df.columns:
        working = cost_df.copy()
        working["spend"] = _numeric(working, "cost", "amount")
        spend_by_cloud = working.groupby("cloud", dropna=False)["spend"].sum().reset_index().to_dict("records")

    health_rows = []
    if not health_df.empty:
        health_rows = health_df.head(12).to_dict("records")

    return {
        "kpis": {
            "total_spend": total_spend,
            "governance_score": governance_score,
            "savings_identified": savings["identified"],
            "savings_realized": savings["realized"],
            "sla_compliance": sla["compliance"],
            "security_score": security["score"],
            "customer_health_score": customer_health["score"],
            "customer_health_label": customer_health["label"],
        },
        "savings": savings,
        "sla": sla,
        "security": security,
        "customer_health": customer_health,
        "spend_by_cloud": spend_by_cloud,
        "security_by_severity": security["by_severity"],
        "health_rows": health_rows,
    }

