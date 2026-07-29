from __future__ import annotations

from typing import Any

import pandas as pd

from services.enterprise_financial_model import EnterpriseFinancialModel
from services.supabase_client import supabase
from auth.authenticated_tenant import AuthenticatedTenantContext
from services.enterprise_spend_service import EnterpriseSpendService


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _fetch_rows(
    table_name: str,
    context: AuthenticatedTenantContext,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    for scope_column in ("organization_id", "org_id"):
        try:
            query = (
                supabase.table(table_name)
                .select("*")
                .eq(scope_column, context.organization_id)
            )
            if limit:
                query = query.limit(limit)
            response = query.execute()
            return response.data or []
        except Exception:
            continue
    return []


def _fetch_one(
    table_name: str,
    context: AuthenticatedTenantContext,
) -> dict[str, Any]:
    rows = _fetch_rows(table_name, context, limit=1)
    return rows[0] if rows else {}


def _spend_value(row: dict[str, Any], new_key: str, old_key: str) -> float:
    return _safe_float(row.get(new_key, row.get(old_key, 0)))


def _money(value: Any) -> str:
    amount = _safe_float(value)
    if abs(amount) >= 1000:
        return f"${amount / 1000:,.1f}K".replace(".0K", "K")
    return f"${amount:,.0f}"


class ExecutiveDashboardCertificationService:
    """Certification overlay for the Executive Dashboard.

    This service intentionally wraps the canonical financial model and evidence
    metadata without changing the existing dashboard KPIs or charts.
    """

    @staticmethod
    def get_dashboard(
        context: AuthenticatedTenantContext,
        spend_service: EnterpriseSpendService,
    ) -> dict[str, Any]:
        posture = spend_service.get_financial_posture(context)
        legacy_metrics = {
            "summary": {},
            "spend_breakdown": {},
            "recommendations": [],
            "cloud_cost": float(posture.cloud_spend),
            "saas_cost": 0.0,
            "msp_cost": 0.0,
            "license_cost": 0.0,
            "total_spend": float(posture.cloud_spend),
            "potential_savings": 0.0,
            "savings_realized": 0.0,
            "governance_score": 0,
            "critical_risks": 0,
            "pending_approvals": 0,
            "budget_health": 0,
            "optimization_health": 0,
            "risk_posture": 0,
            "opportunities_found": 0,
        }
        enterprise_summary = {
            "enterprise_total": posture.total_ingested_spend,
            "cloud_spend": posture.cloud_spend,
            "allocated_spend": posture.allocated_spend,
            "unallocated_spend": posture.unallocated_resolved_spend,
            "quarantined_spend": posture.quarantined_spend,
            "potential_savings": 0,
            "generated_at": posture.generated_at,
        }
        reconciliation = {
            "status": posture.reconciliation_status,
            "allocation_coverage": posture.allocation_coverage_percentage,
            "unallocated_spend": posture.unallocated_resolved_spend,
            "variance": posture.reconciliation_variance,
            "unknown_accounts": posture.unknown_account_count,
            "source_rows": posture.source_rows,
            "persisted_facts": posture.persisted_facts,
        }
        variance_layers = []
        status = str(reconciliation.get("status") or "Unknown")
        allocation_coverage = _safe_float(reconciliation.get("allocation_coverage"))
        unallocated_spend = _safe_float(reconciliation.get("unallocated_spend"))

        return {
            "executive_summary": ExecutiveDashboardCertificationService._executive_summary(
                enterprise_summary,
                reconciliation,
            ),
            "legacy_metrics": legacy_metrics,
            "reconciliation_cards": {
                "allocation_coverage": allocation_coverage,
                "allocation_coverage_display": f"{allocation_coverage:.1f}%",
                "unallocated_spend": unallocated_spend,
                "unallocated_spend_display": _money(unallocated_spend),
                "reconciliation_status": status,
            },
            "financial_model": enterprise_summary,
            "reconciliation": reconciliation,
            "financial_posture": posture,
            "tenant": context,
            "evidence": {
                "source_data": [
                    {"Section": "Cloud Spend", "Source": "EnterpriseSpendService", "Mode": "Tenant-scoped RPC"},
                ],
                "data_coverage": ExecutiveDashboardCertificationService._data_coverage(reconciliation),
                "financial_reconciliation": [
                    {
                        "Metric": "Data Reconciliation Status",
                        "Value": status,
                        "Interpretation": ExecutiveDashboardCertificationService._status_interpretation(status),
                    },
                    {
                        "Metric": "Allocation Coverage",
                        "Value": f"{allocation_coverage:.1f}%",
                        "Interpretation": "Share of enterprise spend currently mapped to the canonical financial model.",
                    },
                    {
                        "Metric": "Unallocated Spend",
                        "Value": _money(unallocated_spend),
                        "Interpretation": "Spend that has not yet been mapped through the business-to-technology allocation chain.",
                    },
                ],
                "ai_interpretation": ExecutiveDashboardCertificationService._ai_interpretation(
                    enterprise_summary,
                    reconciliation,
                ),
                "raw_evidence": {
                    "Financial Model": ExecutiveDashboardCertificationService._financial_model_rows(enterprise_summary),
                    "Variance Layers": ExecutiveDashboardCertificationService._variance_rows(variance_layers),
                },
            },
        }

    @staticmethod
    def format_compact_currency(value: Any) -> str:
        return _money(value)

    @staticmethod
    def _legacy_metrics(context: AuthenticatedTenantContext) -> dict[str, Any]:
        summary = _fetch_one("mart_executive_summary", context)
        spend_breakdown = _fetch_one("mart_enterprise_spend_v2", context)
        recommendations = _fetch_rows("recommendations", context)

        cloud_cost = _spend_value(spend_breakdown, "cloud_spend", "cloud_cost")
        saas_cost = _spend_value(spend_breakdown, "saas_spend", "saas_cost")
        msp_cost = _spend_value(spend_breakdown, "msp_spend", "msp_cost")
        license_cost = _spend_value(spend_breakdown, "license_spend", "license_cost")

        total_spend = _safe_float(summary.get("total_spend"))
        if not total_spend:
            total_spend = cloud_cost + saas_cost + msp_cost + license_cost

        potential_savings = _safe_float(
            summary.get("optimization_savings")
            or summary.get("optimization")
            or summary.get("potential_savings")
        )

        savings_realized = _safe_float(
            summary.get("savings_realized")
            or summary.get("realized_savings")
        )

        if not savings_realized and recommendations:
            rec_df = pd.DataFrame(recommendations)
            if {"status", "estimated_savings"}.issubset(rec_df.columns):
                statuses = rec_df["status"].fillna("").astype(str).str.upper()
                savings = pd.to_numeric(rec_df["estimated_savings"], errors="coerce").fillna(0)
                savings_realized = float(
                    savings[
                        statuses.isin(["IMPLEMENTED", "COMPLETED", "RESOLVED", "CLOSED"])
                    ].sum()
                )

        governance_score = _safe_int(summary.get("governance_score"))
        critical_risks = _safe_int(summary.get("critical_risks") or summary.get("anomaly_count"))
        pending_approvals = _safe_int(summary.get("pending_approvals"))
        budget_health = _safe_int(summary.get("budget_adherence")) or 85
        optimization_health = _safe_int(summary.get("optimization_adoption")) or 85
        risk_posture = _safe_int(summary.get("risk_posture")) or max(0, 100 - critical_risks * 5)

        opportunities_found = _safe_int(
            summary.get("optimization_count")
            or summary.get("recommendation_count")
            or summary.get("opportunities_found")
        ) or len(recommendations)

        return {
            "summary": summary,
            "spend_breakdown": spend_breakdown,
            "recommendations": recommendations,
            "cloud_cost": cloud_cost,
            "saas_cost": saas_cost,
            "msp_cost": msp_cost,
            "license_cost": license_cost,
            "total_spend": total_spend,
            "potential_savings": potential_savings,
            "savings_realized": savings_realized,
            "governance_score": governance_score,
            "critical_risks": critical_risks,
            "pending_approvals": pending_approvals,
            "budget_health": budget_health,
            "optimization_health": optimization_health,
            "risk_posture": risk_posture,
            "opportunities_found": opportunities_found,
        }

    @staticmethod
    def _executive_summary(
        enterprise_summary: dict[str, Any],
        reconciliation: dict[str, Any],
    ) -> str:
        status = reconciliation.get("status") or "Unknown"
        enterprise_total = _money(enterprise_summary.get("enterprise_total"))
        allocated_spend = _money(enterprise_summary.get("allocated_spend"))
        unallocated_spend = _money(enterprise_summary.get("unallocated_spend"))
        allocation_coverage = _safe_float(enterprise_summary.get("allocation_coverage"))
        potential_savings = _money(enterprise_summary.get("potential_savings"))

        sentences = [
            f"Enterprise technology spend is currently {enterprise_total}, with {allocated_spend} allocated through the canonical financial model.",
            f"Data reconciliation status is {status}, and allocation coverage is {allocation_coverage:.1f}%.",
            f"Unallocated spend is {unallocated_spend}, which should be reviewed before using financial rollups as fully reconciled executive totals.",
            f"Identified optimization potential is {potential_savings}.",
        ]
        return " ".join(sentences)

    @staticmethod
    def _source_data() -> list[dict[str, str]]:
        return [
            {"Section": "Executive Summary", "Source": "mart_executive_summary", "Mode": "Live"},
            {"Section": "Enterprise Spend", "Source": "mart_enterprise_spend_v2", "Mode": "Live"},
            {"Section": "Recommendations", "Source": "recommendations", "Mode": "Live"},
            {"Section": "Financial Model", "Source": "EnterpriseFinancialModel", "Mode": "Canonical"},
            {"Section": "Business Architecture", "Source": "Business services/processes/application portfolio", "Mode": "Derived"},
        ]

    @staticmethod
    def _data_coverage(reconciliation: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "Coverage Area": "Allocation Coverage",
                "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                "Status": reconciliation.get("status") or "Unknown",
            },
            {
                "Coverage Area": "Business Coverage",
                "Value": f"{_safe_float(reconciliation.get('business_coverage')):.1f}%",
                "Status": "Tracked",
            },
            {
                "Coverage Area": "Application Coverage",
                "Value": f"{_safe_float(reconciliation.get('application_coverage')):.1f}%",
                "Status": "Tracked",
            },
            {
                "Coverage Area": "Technology Coverage",
                "Value": f"{_safe_float(reconciliation.get('technology_coverage')):.1f}%",
                "Status": "Tracked",
            },
        ]

    @staticmethod
    def _ai_interpretation(
        enterprise_summary: dict[str, Any],
        reconciliation: dict[str, Any],
    ) -> str:
        status = reconciliation.get("status") or "Unknown"
        allocation_coverage = _safe_float(reconciliation.get("allocation_coverage"))
        variance_layers = reconciliation.get("variance_layers") or []
        if status == EnterpriseFinancialModel.VARIANCE_DETECTED:
            return (
                f"The Executive Dashboard is operational, but financial data is not fully reconciled. "
                f"Allocation coverage is {allocation_coverage:.1f}% and {len(variance_layers)} variance layer(s) require review before certification as a fully reconciled financial source."
            )
        if status == EnterpriseFinancialModel.PARTIALLY_ALLOCATED:
            return (
                f"The Executive Dashboard has partial financial allocation coverage at {allocation_coverage:.1f}%. "
                "Executive decisions should consider unmapped spend before treating totals as final."
            )
        return (
            "The Executive Dashboard financial model is reconciled against the canonical allocation layer and is suitable for certified executive reporting."
        )

    @staticmethod
    def _status_interpretation(status: str) -> str:
        if status == EnterpriseFinancialModel.VARIANCE_DETECTED:
            return "Financial rollups are usable, but layer-level source totals do not fully match the canonical allocation model."
        if status == EnterpriseFinancialModel.PARTIALLY_ALLOCATED:
            return "Some spend is mapped to the allocation model and some remains unmapped."
        if status == EnterpriseFinancialModel.RECONCILED:
            return "Financial rollups are reconciled against the canonical allocation model."
        return "Financial data requires additional mapping before executive certification."

    @staticmethod
    def _financial_model_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"Metric": "Enterprise Total", "Value": _money(summary.get("enterprise_total"))},
            {"Metric": "Allocated Spend", "Value": _money(summary.get("allocated_spend"))},
            {"Metric": "Unallocated Spend", "Value": _money(summary.get("unallocated_spend"))},
            {"Metric": "Potential Savings", "Value": _money(summary.get("potential_savings"))},
            {"Metric": "Forecast Spend", "Value": _money(summary.get("forecast_spend"))},
            {"Metric": "Budget", "Value": _money(summary.get("budget"))},
            {"Metric": "Generated At", "Value": str(summary.get("generated_at") or "Unknown")},
        ]

    @staticmethod
    def _variance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Layer": str(row.get("layer") or "").replace("_", " ").title(),
                "Canonical Allocated Spend": _money(row.get("canonical_allocated_spend")),
                "Source Spend": _money(row.get("source_spend")),
                "Variance": _money(row.get("variance")),
                "Variance %": f"{_safe_float(row.get('variance_pct')):.1f}%",
                "Status": row.get("status") or "Unknown",
            }
            for row in rows
        ]
