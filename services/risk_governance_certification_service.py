from __future__ import annotations

from typing import Any

import streamlit as st

import pandas as pd

from services.approval_service import ApprovalService
from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.cost_intelligence_service import (
    get_cost_anomalies,
    get_optimization_opportunities,
    get_recommendations,
)
from services.enterprise_financial_model import EnterpriseFinancialModel


def _safe_call(fn, fallback):
    try:
        return fn() or fallback
    except Exception:
        return fallback


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value if value is not None else fallback))
    except (TypeError, ValueError):
        return fallback


def _money(value: Any) -> str:
    amount = _safe_float(value)
    if abs(amount) >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M".replace(".0M", "M")
    if abs(amount) >= 1_000:
        value = amount / 1_000
        return f"${value:,.0f}K" if float(value).is_integer() else f"${value:,.1f}K"
    return f"${amount:,.0f}"


class RiskGovernanceCertificationService:
    """Certification service for the Risk & Governance page."""

    @staticmethod
    def format_money(value: Any) -> str:
        return _money(value)

    @staticmethod
    def escape_markdown_currency(text: str) -> str:
        return str(text or "").replace("$", r"\$")

    @staticmethod
    @st.cache_data(ttl=120, show_spinner=False)
    def get_dashboard() -> dict[str, Any]:
        empty_response = {"success": False, "data": pd.DataFrame()}
        anomaly_resp = _safe_call(get_cost_anomalies, empty_response)
        optimization_resp = _safe_call(get_optimization_opportunities, empty_response)
        recommendation_resp = _safe_call(get_recommendations, empty_response)

        anomaly_df = anomaly_resp.get("data", pd.DataFrame())
        optimization_df = optimization_resp.get("data", pd.DataFrame())
        recommendation_df = recommendation_resp.get("data", pd.DataFrame())

        approval_metrics = ApprovalService.get_dashboard_metrics()
        sla_metrics = ApprovalService.get_sla_metrics()
        metrics = RiskGovernanceCertificationService._metrics(
            anomaly_df,
            optimization_df,
            recommendation_df,
            approval_metrics,
            sla_metrics,
            [],
        )
        financial_model = _safe_call(EnterpriseFinancialModel.get_enterprise_summary, {})
        reconciliation = _safe_call(EnterpriseFinancialModel.get_reconciliation_status, {})
        business_context = RiskGovernanceCertificationService._business_context(metrics)

        dataframes = {
            "anomaly": anomaly_df,
            "optimization": optimization_df,
            "recommendation": recommendation_df,
            "pending_approvals": pd.DataFrame(),
        }

        return {
            "data_available": any(
                (
                    not anomaly_df.empty,
                    not optimization_df.empty,
                    not recommendation_df.empty,
                    bool(financial_model),
                    bool(reconciliation),
                    bool(approval_metrics.get("total")),
                )
            ),
            "metrics": metrics,
            "dataframes": dataframes,
            "approval_metrics": approval_metrics,
            "sla_metrics": sla_metrics,
            "pending_approvals": [],
            "financial_model": financial_model,
            "reconciliation": reconciliation,
            "reconciliation_cards": {
                "status": reconciliation.get("status") or "Unknown",
                "allocation_coverage": _safe_float(reconciliation.get("allocation_coverage")),
                "allocation_coverage_display": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                "allocated_spend": _safe_float(financial_model.get("allocated_spend")),
                "allocated_spend_display": _money(financial_model.get("allocated_spend")),
                "unallocated_spend": _safe_float(financial_model.get("unallocated_spend")),
                "unallocated_spend_display": _money(financial_model.get("unallocated_spend")),
                "variance_status": reconciliation.get("status") or "Unknown",
            },
            "business_context": business_context,
            "executive_summary": RiskGovernanceCertificationService._executive_summary(
                metrics,
                financial_model,
                reconciliation,
                business_context,
            ),
            "evidence": RiskGovernanceCertificationService._evidence(
                metrics,
                financial_model,
                reconciliation,
                business_context,
                dataframes,
                approval_metrics,
                sla_metrics,
            ),
        }

    @staticmethod
    def get_live_approval_queue() -> list[dict[str, Any]]:
        """Return operational approval queue detail without cache."""
        return ApprovalService.get_pending_approvals() or []

    @staticmethod
    def _metrics(
        anomaly_df: pd.DataFrame,
        optimization_df: pd.DataFrame,
        recommendation_df: pd.DataFrame,
        approval_metrics: dict[str, Any],
        sla_metrics: dict[str, Any],
        pending_approvals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        active_risks = len(anomaly_df) if not anomaly_df.empty else 0
        risk_status_column = RiskGovernanceCertificationService.risk_status_column(anomaly_df)
        critical_risks = RiskGovernanceCertificationService.critical_risk_count(
            anomaly_df, risk_status_column
        )
        optimization_items = len(optimization_df) if not optimization_df.empty else 0
        potential_savings = 0.0
        if not recommendation_df.empty and "estimated_savings" in recommendation_df.columns:
            potential_savings = (
                pd.to_numeric(
                    recommendation_df["estimated_savings"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        pending_count = _safe_int(approval_metrics.get("pending"), len(pending_approvals))
        sla_compliance = _safe_float(sla_metrics.get("sla_compliance"))
        governance_score = RiskGovernanceCertificationService.governance_score(
            critical_risks,
            pending_count,
            sla_compliance,
        )
        executive_action_required = pending_count + _safe_int(critical_risks)

        return {
            "active_risks": active_risks,
            "critical_risks": _safe_int(critical_risks),
            "risk_status_column": risk_status_column,
            "optimization_items": optimization_items,
            "potential_savings": _safe_float(potential_savings),
            "pending_count": pending_count,
            "sla_compliance": sla_compliance,
            "governance_score": governance_score,
            "executive_action_required": executive_action_required,
            "approved_count": _safe_int(approval_metrics.get("approved")),
            "rejected_count": _safe_int(approval_metrics.get("rejected")),
            "escalated_count": _safe_int(approval_metrics.get("escalated")),
            "recommendation_count": len(recommendation_df),
        }

    @staticmethod
    def risk_status_column(anomaly_df: pd.DataFrame) -> str | None:
        for column in ["anomaly_status", "status", "severity", "risk_level"]:
            if column in anomaly_df.columns:
                return column
        return None

    @staticmethod
    def critical_risk_count(anomaly_df: pd.DataFrame, risk_status_column: str | None = None) -> int:
        if not risk_status_column or anomaly_df.empty:
            return 0
        return _safe_int(
            anomaly_df[risk_status_column]
            .astype(str)
            .str.lower()
            .isin(["critical", "high", "anomaly", "spike"])
            .sum()
        )

    @staticmethod
    def governance_score(critical_risks: int, pending_count: int, sla_compliance: float) -> float:
        return max(
            0,
            min(
                100,
                100
                - (_safe_int(critical_risks) * 10)
                - (_safe_int(pending_count) * 3)
                + min(10, _safe_float(sla_compliance) / 10),
            ),
        )

    @staticmethod
    def approval_summary(approval_metrics: dict[str, Any]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"Status": "Pending", "Count": _safe_int(approval_metrics.get("pending"))},
                {"Status": "Approved", "Count": _safe_int(approval_metrics.get("approved"))},
                {"Status": "Rejected", "Count": _safe_int(approval_metrics.get("rejected"))},
                {"Status": "Escalated", "Count": _safe_int(approval_metrics.get("escalated"))},
            ]
        )

    @staticmethod
    def _business_context(metrics: dict[str, Any]) -> dict[str, Any]:
        unit_summary = _safe_call(BusinessUnitService.get_summary, {})
        capability_summary = _safe_call(BusinessCapabilityService.get_capability_summary, {})
        service_summary = _safe_call(BusinessServiceService.get_service_summary, {})
        process_summary = _safe_call(BusinessProcessService.get_process_summary, {})

        return {
            "business_units": _safe_int(
                unit_summary.get("business_units") or unit_summary.get("total_business_units")
            ),
            "capabilities": _safe_int(
                capability_summary.get("capabilities")
                or capability_summary.get("total_capabilities")
            ),
            "business_services": _safe_int(
                service_summary.get("business_services") or service_summary.get("total_services")
            ),
            "business_processes": _safe_int(
                process_summary.get("business_processes") or process_summary.get("total_processes")
            ),
            "applications": _safe_int(service_summary.get("applications")),
            "technologies": _safe_int(service_summary.get("technologies")),
            "enterprise_risks": _safe_int(metrics.get("active_risks")),
            "mapping_coverage": _safe_float(
                service_summary.get("mapping_coverage")
                or capability_summary.get("mapping_coverage")
                or unit_summary.get("mapping_coverage")
            ),
        }

    @staticmethod
    def _executive_summary(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
    ) -> str:
        sentences = [
            f"Risk & Governance shows {_safe_float(metrics.get('governance_score')):.0f}% governance confidence with {_safe_int(metrics.get('active_risks'))} active risk signals and {_safe_int(metrics.get('critical_risks'))} high-priority risks.",
            f"The decision queue has {_safe_int(metrics.get('pending_count'))} pending approval item, while SLA compliance is {_safe_float(metrics.get('sla_compliance')):.0f}%.",
            f"Governance-linked optimization includes {_safe_int(metrics.get('optimization_items'))} opportunities and {_money(metrics.get('potential_savings'))} in savings exposure.",
            f"Business architecture context includes {_safe_int(business_context.get('business_units'))} business units, {_safe_int(business_context.get('capabilities'))} capabilities, {_safe_int(business_context.get('business_services'))} services, {_safe_int(business_context.get('applications'))} applications, and {_safe_int(business_context.get('technologies'))} technologies.",
            f"Data reconciliation status is {reconciliation.get('status') or 'Unknown'} with {_safe_float(reconciliation.get('allocation_coverage')):.1f}% allocation coverage and {_money(financial_model.get('unallocated_spend'))} unallocated spend.",
        ]
        return RiskGovernanceCertificationService.escape_markdown_currency(" ".join(sentences))

    @staticmethod
    def _evidence(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
        dataframes: dict[str, pd.DataFrame],
        approval_metrics: dict[str, Any],
        sla_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {
                    "Section": "Risk Signals",
                    "Source": "CostIntelligenceService.get_cost_anomalies",
                    "Mode": "Service",
                },
                {
                    "Section": "Optimization Opportunities",
                    "Source": "CostIntelligenceService.get_optimization_opportunities",
                    "Mode": "Service",
                },
                {
                    "Section": "Recommendations",
                    "Source": "CostIntelligenceService.get_recommendations",
                    "Mode": "Service",
                },
                {"Section": "Approval Queue", "Source": "ApprovalService", "Mode": "Service"},
                {
                    "Section": "Business Architecture",
                    "Source": "BusinessUnit/Capability/Service/Process services",
                    "Mode": "Service",
                },
                {
                    "Section": "Financial Model",
                    "Source": "EnterpriseFinancialModel",
                    "Mode": "Canonical",
                },
            ],
            "data_coverage": [
                {
                    "Coverage Area": "Risk Signals",
                    "Value": f"{len(dataframes.get('anomaly', pd.DataFrame())):,}",
                    "Status": "Tracked",
                },
                {
                    "Coverage Area": "Optimization Opportunities",
                    "Value": f"{len(dataframes.get('optimization', pd.DataFrame())):,}",
                    "Status": "Tracked",
                },
                {
                    "Coverage Area": "Recommendations",
                    "Value": f"{len(dataframes.get('recommendation', pd.DataFrame())):,}",
                    "Status": "Tracked",
                },
                {
                    "Coverage Area": "Pending Approvals",
                    "Value": f"{_safe_int(metrics.get('pending_count')):,}",
                    "Status": "Tracked",
                },
                {
                    "Coverage Area": "SLA Compliance",
                    "Value": f"{_safe_float(metrics.get('sla_compliance')):.0f}%",
                    "Status": "Tracked",
                },
                {
                    "Coverage Area": "Financial Reconciliation",
                    "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                    "Status": reconciliation.get("status") or "Unknown",
                },
            ],
            "relationship_summary": [
                {
                    "Layer": "Business Units",
                    "Count": _safe_int(business_context.get("business_units")),
                },
                {"Layer": "Capabilities", "Count": _safe_int(business_context.get("capabilities"))},
                {
                    "Layer": "Business Services",
                    "Count": _safe_int(business_context.get("business_services")),
                },
                {"Layer": "Applications", "Count": _safe_int(business_context.get("applications"))},
                {"Layer": "Technologies", "Count": _safe_int(business_context.get("technologies"))},
                {"Layer": "Enterprise Risks", "Count": _safe_int(metrics.get("active_risks"))},
            ],
            "financial_reconciliation": [
                {
                    "Metric": "Data Reconciliation Status",
                    "Value": reconciliation.get("status") or "Unknown",
                },
                {
                    "Metric": "Allocation Coverage",
                    "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                },
                {
                    "Metric": "Allocated Spend",
                    "Value": _money(financial_model.get("allocated_spend")),
                },
                {
                    "Metric": "Unallocated Spend",
                    "Value": _money(financial_model.get("unallocated_spend")),
                },
                {"Metric": "Savings Exposure", "Value": _money(metrics.get("potential_savings"))},
                {"Metric": "Variance Status", "Value": reconciliation.get("status") or "Unknown"},
            ],
            "ai_interpretation": (
                "Risk & Governance is certification-ready because it connects risk signals, approval pressure, "
                "SLA posture, recommendations, and savings exposure in a CIO governance view. "
                "The next maturity step is explicit business-service and application ownership on every risk signal."
            ),
            "raw_evidence": {
                "Governance Metrics": [
                    {
                        "Metric": "Governance Confidence",
                        "Value": f"{_safe_float(metrics.get('governance_score')):.0f}%",
                    },
                    {
                        "Metric": "Active Risk Signals",
                        "Value": _safe_int(metrics.get("active_risks")),
                    },
                    {
                        "Metric": "High-Priority Risks",
                        "Value": _safe_int(metrics.get("critical_risks")),
                    },
                    {
                        "Metric": "Optimization Opportunities",
                        "Value": _safe_int(metrics.get("optimization_items")),
                    },
                    {
                        "Metric": "Savings Exposure",
                        "Value": _money(metrics.get("potential_savings")),
                    },
                ],
                "Approval Metrics": [
                    {"Metric": "Pending", "Value": _safe_int(approval_metrics.get("pending"))},
                    {"Metric": "Approved", "Value": _safe_int(approval_metrics.get("approved"))},
                    {"Metric": "Rejected", "Value": _safe_int(approval_metrics.get("rejected"))},
                    {"Metric": "Escalated", "Value": _safe_int(approval_metrics.get("escalated"))},
                    {
                        "Metric": "SLA Compliance",
                        "Value": f"{_safe_float(sla_metrics.get('sla_compliance')):.0f}%",
                    },
                ],
                "Financial Model": [
                    {
                        "Metric": "Enterprise Total",
                        "Value": _money(financial_model.get("enterprise_total")),
                    },
                    {
                        "Metric": "Allocated Spend",
                        "Value": _money(financial_model.get("allocated_spend")),
                    },
                    {
                        "Metric": "Unallocated Spend",
                        "Value": _money(financial_model.get("unallocated_spend")),
                    },
                    {
                        "Metric": "Generated At",
                        "Value": str(financial_model.get("generated_at") or "Unknown"),
                    },
                ],
            },
        }
