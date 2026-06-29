"""
Centralized analytics service for dashboard analytics data access.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from config import DEFAULT_ORG_ID
from services.supabase_client import supabase


def _effective_org_id(org_id: str | None = None) -> str:
    return org_id or DEFAULT_ORG_ID


def _success(data: Any, message: str = "", errors: Any = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "message": message,
        "errors": errors,
    }


def _failure(data: Any, error: Exception) -> dict[str, Any]:
    return {
        "success": False,
        "data": data,
        "message": str(error),
        "errors": str(error),
    }


def _rows(
    table_name: str,
    select_columns: str = "*",
    org_id: str | None = None,
    org_column: str = "org_id",
) -> list[dict[str, Any]]:
    query = supabase.table(table_name).select(select_columns)

    if org_id:
        query = query.eq(org_column, org_id)

    response = query.execute()
    return response.data or []


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype="float64")

    return pd.to_numeric(df[column], errors="coerce").fillna(0)


class AnalyticsService:
    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_all_resources(org_id=DEFAULT_ORG_ID):
        try:
            return _rows(
                "unified_cloud_costs",
                "resource_id,cloud,service_name,usage_quantity,cost,labels,tag",
                _effective_org_id(org_id),
            )
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_total_spend(org_id=DEFAULT_ORG_ID):
        try:
            rows = _rows(
                "unified_cloud_costs",
                "cost",
                _effective_org_id(org_id),
            )
            df = pd.DataFrame(rows)

            if df.empty:
                return 0

            return round(float(_numeric_series(df, "cost").sum()), 2)
        except Exception:
            return 0

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_spend_by_cloud(org_id=DEFAULT_ORG_ID):
        try:
            return get_spend_by_cloud(org_id)
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_top_services(org_id=DEFAULT_ORG_ID):
        try:
            return get_top_services(org_id=org_id)
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_recommendations(org_id=DEFAULT_ORG_ID):
        try:
            return _rows("recommendations", "*", _effective_org_id(org_id))
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_anomalies(org_id=DEFAULT_ORG_ID):
        try:
            return _rows("cost_anomaly_org_view", "*", _effective_org_id(org_id))
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_tagging_compliance_score(org_id=DEFAULT_ORG_ID):
        try:
            rows = _rows(
                "unified_cloud_costs",
                "resource_id,labels",
                _effective_org_id(org_id),
            )

            if not rows:
                return 100

            df = pd.DataFrame(rows)
            tagged = df[
                df["labels"].notna()
                & (df["labels"].astype(str).str.len() > 2)
            ]
            return round(len(tagged) / max(len(df), 1) * 100, 2)
        except Exception:
            return 100

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_security_compliance_score(org_id=DEFAULT_ORG_ID):
        try:
            rows = _rows(
                "security_findings",
                "severity",
                _effective_org_id(org_id),
            )

            if not rows:
                return 100

            df = pd.DataFrame(rows)
            critical = df[
                df["severity"].astype(str).str.lower() == "critical"
            ]
            penalty = min(len(critical) * 10, 100)
            return max(0, 100 - penalty)
        except Exception:
            return 100

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_cost_optimization_score(org_id=DEFAULT_ORG_ID):
        try:
            rows = _rows(
                "recommendations",
                "status",
                _effective_org_id(org_id),
            )

            if not rows:
                return 100

            df = pd.DataFrame(rows)
            completed = df[
                df["status"].astype(str).str.lower().isin(
                    ["completed", "implemented", "approved"]
                )
            ]
            return round(len(completed) / max(len(df), 1) * 100, 2)
        except Exception:
            return 100

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_sla_compliance_score(org_id=DEFAULT_ORG_ID):
        try:
            rows = _rows(
                "approval_queue",
                "approval_time,sla_due",
                _effective_org_id(org_id),
            )

            if not rows:
                return 100

            df = pd.DataFrame(rows)
            df["approval_time"] = pd.to_datetime(
                df["approval_time"],
                errors="coerce",
            )
            df["sla_due"] = pd.to_datetime(df["sla_due"], errors="coerce")
            completed = df.dropna(subset=["approval_time", "sla_due"])

            if completed.empty:
                return 100

            within_sla = completed[completed["approval_time"] <= completed["sla_due"]]
            return round(len(within_sla) / max(len(completed), 1) * 100, 2)
        except Exception:
            return 100

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_idle_resource_score(org_id=DEFAULT_ORG_ID):
        try:
            rows = _rows(
                "unified_cloud_costs",
                "resource_id,usage_quantity",
                _effective_org_id(org_id),
            )

            if not rows:
                return 100

            df = pd.DataFrame(rows)
            usage = _numeric_series(df, "usage_quantity")
            idle = usage[usage == 0]
            return round((1 - len(idle) / max(len(df), 1)) * 100, 2)
        except Exception:
            return 100


@st.cache_data(ttl=300, show_spinner=False)
def get_recommendations(org_id=DEFAULT_ORG_ID):
    try:
        return _rows("recommendations", "*", _effective_org_id(org_id))
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_anomalies(org_id=DEFAULT_ORG_ID):
    try:
        return _rows("cost_anomaly_org_view", "*", _effective_org_id(org_id))
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_total_cloud_spend(org_id=DEFAULT_ORG_ID):
    try:
        rows = _rows(
            "unified_cloud_costs",
            "cloud,cost",
            _effective_org_id(org_id),
        )

        if not rows:
            return _success({"total_spend": 0.0, "cloud_count": 0})

        df = pd.DataFrame(rows)
        total_spend = float(_numeric_series(df, "cost").sum())
        cloud_count = int(df["cloud"].nunique()) if "cloud" in df.columns else 0

        return _success(
            {
                "total_spend": total_spend,
                "cloud_count": cloud_count,
            }
        )
    except Exception as exc:
        return _failure({"total_spend": 0.0, "cloud_count": 0}, exc)


@st.cache_data(ttl=300, show_spinner=False)
def get_spend_by_cloud(org_id=DEFAULT_ORG_ID):
    try:
        rows = _rows(
            "unified_cloud_costs",
            "cloud,cost",
            _effective_org_id(org_id),
        )

        if not rows:
            return []

        df = pd.DataFrame(rows)
        df["cost"] = _numeric_series(df, "cost")
        grouped = (
            df.groupby("cloud", dropna=False)["cost"]
            .sum()
            .reset_index()
            .rename(columns={"cost": "spend"})
        )

        return grouped.to_dict("records")
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_top_services(limit=10, org_id=DEFAULT_ORG_ID):
    try:
        if not isinstance(limit, int):
            org_id, limit = limit, 10

        rows = _rows(
            "unified_cloud_costs",
            "service_name,cost",
            _effective_org_id(org_id),
        )

        if not rows:
            return []

        df = pd.DataFrame(rows)
        df["cost"] = _numeric_series(df, "cost")
        grouped = (
            df.groupby("service_name", dropna=False)["cost"]
            .sum()
            .sort_values(ascending=False)
            .head(limit)
            .reset_index()
            .rename(columns={"service_name": "service", "cost": "spend"})
        )

        return grouped.to_dict("records")
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_governance_score(org_id=DEFAULT_ORG_ID):
    try:
        tagging_score = AnalyticsService.get_tagging_compliance_score(org_id)
        security_score = AnalyticsService.get_security_compliance_score(org_id)
        optimization_score = AnalyticsService.get_cost_optimization_score(org_id)
        sla_score = AnalyticsService.get_sla_compliance_score(org_id)
        idle_score = AnalyticsService.get_idle_resource_score(org_id)

        score = round(
            (
                tagging_score
                + security_score
                + optimization_score
                + sla_score
                + idle_score
            )
            / 5,
            2,
        )

        if score <= 40:
            status = "CRITICAL"
        elif score <= 60:
            status = "NEEDS IMPROVEMENT"
        elif score <= 80:
            status = "GOOD"
        else:
            status = "EXCELLENT"

        return _success(
            {
                "score": score,
                "status": status,
                "breakdown": {
                    "Tagging Compliance": tagging_score,
                    "Security Compliance": security_score,
                    "Cost Optimization": optimization_score,
                    "SLA Compliance": sla_score,
                    "Idle Resource Health": idle_score,
                },
            }
        )
    except Exception as exc:
        return _failure({"score": 0, "status": "UNKNOWN", "breakdown": {}}, exc)


@st.cache_data(ttl=300, show_spinner=False)
def get_governance_trends(org_id=DEFAULT_ORG_ID):
    try:
        score_response = get_governance_score(org_id)
        score_data = score_response.get("data", {})
        score = score_data.get("score", 0)
        current_month = datetime.utcnow().strftime("%b %Y")

        return _success(
            [
                {
                    "month": current_month,
                    "score": score,
                    "sla_compliance": AnalyticsService.get_sla_compliance_score(org_id),
                    "open_anomalies": len(get_anomalies(org_id)),
                    "unapproved_resources": 0,
                    "optimization_completion": (
                        AnalyticsService.get_cost_optimization_score(org_id)
                    ),
                    "security_findings": 0,
                }
            ]
        )
    except Exception as exc:
        return _failure([], exc)


@st.cache_data(ttl=300, show_spinner=False)
def get_open_recommendations(org_id=DEFAULT_ORG_ID):
    try:
        rows = _rows(
            "recommendations",
            "*",
            _effective_org_id(org_id),
        )
        open_rows = [
            row
            for row in rows
            if str(row.get("status", "")).lower()
            not in {"completed", "implemented", "closed", "rejected"}
        ]
        return _success(open_rows)
    except Exception as exc:
        return _failure([], exc)


@st.cache_data(ttl=300, show_spinner=False)
def get_active_anomalies(org_id=DEFAULT_ORG_ID):
    try:
        rows = get_anomalies(org_id)
        active_rows = [
            row
            for row in rows
            if str(row.get("status", "active")).lower()
            not in {"closed", "resolved", "dismissed"}
        ]
        return _success(active_rows)
    except Exception as exc:
        return _failure([], exc)


@st.cache_data(ttl=300, show_spinner=False)
def get_savings_opportunities(org_id=DEFAULT_ORG_ID):
    try:
        rows = _rows(
            "recommendations",
            "*",
            _effective_org_id(org_id),
        )
        savings_rows = [
            row
            for row in rows
            if float(
                row.get("potential_savings")
                or row.get("estimated_savings")
                or row.get("savings")
                or 0
            )
            > 0
        ]
        return _success(savings_rows)
    except Exception as exc:
        return _failure([], exc)


@st.cache_data(ttl=300, show_spinner=False)
def get_ingestion_freshness(org_id=None, client_id=None):
    return _success({})


@st.cache_data(ttl=300, show_spinner=False)
def get_etl_health(org_id=None):
    return _success([])


@st.cache_data(ttl=300, show_spinner=False)
def get_mart_health(org_id=None):
    return _success([])


@st.cache_data(ttl=300, show_spinner=False)
def get_ai_health(org_id=None):
    return _success([])


@st.cache_data(ttl=300, show_spinner=False)
def get_etl_latency_kpis(org_id=None, job_name=None):
    return _success({"avg": 0, "max": 0, "count": 0})


@st.cache_data(ttl=300, show_spinner=False)
def get_mart_refresh_health(org_id=None):
    return _success([])
