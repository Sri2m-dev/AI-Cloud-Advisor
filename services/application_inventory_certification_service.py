from __future__ import annotations

from typing import Any

import streamlit as st

import pandas as pd

from services.application_portfolio_service import ApplicationPortfolioService
from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
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
        return f"${amount / 1_000:.1f}K".replace(".0K", "K")
    return f"${amount:,.0f}"


def _first_text(values: list[Any], default: str = "-") -> str:
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {"nan", "none", "unassigned"}:
            return text
    return default


class ApplicationInventoryCertificationService:
    """Certification service for the Application Inventory page."""

    @staticmethod
    def format_money(value: Any) -> str:
        return _money(value)

    @staticmethod
    def escape_markdown_currency(text: str) -> str:
        return str(text or "").replace("$", r"\$")

    @staticmethod
    def health_status(score: float) -> str:
        if score >= 90:
            return "healthy"
        if score >= 75:
            return "warning"
        return "critical"

    @staticmethod
    def format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        formatted = df.copy()
        for column in columns:
            if column in formatted.columns:
                formatted[column] = formatted[column].apply(_money)
        return formatted

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_dashboard() -> dict[str, Any]:
        summary = ApplicationPortfolioService.get_application_summary()
        portfolio_df = ApplicationPortfolioService.application_portfolio_dataframe()
        cost_df = ApplicationPortfolioService.cost_allocation_dataframe()
        dependency_df = ApplicationPortfolioService.dependency_graph_dataframe()
        dependency_summary_df = ApplicationPortfolioService.dependency_summary_dataframe()
        unallocated_df = ApplicationPortfolioService.unallocated_spend_dataframe()
        risk_df = ApplicationPortfolioService.risk_summary_dataframe()
        application_map_df = ApplicationInventoryCertificationService.application_dependency_map(
            dependency_df,
            portfolio_df,
            cost_df,
        )

        metrics = ApplicationInventoryCertificationService._metrics(summary, portfolio_df, cost_df, risk_df)
        cost_ownership_df = ApplicationInventoryCertificationService.application_cost_ownership_map(
            portfolio_df,
            cost_df,
            metrics["unmapped_spend"],
        )
        financial_model = EnterpriseFinancialModel.get_enterprise_summary()
        reconciliation = EnterpriseFinancialModel.get_reconciliation_status()
        business_context = ApplicationInventoryCertificationService._business_context(metrics)

        dataframes = {
            "portfolio": portfolio_df,
            "cost": cost_df,
            "dependency": dependency_df,
            "dependency_summary": dependency_summary_df,
            "unallocated": unallocated_df,
            "risk": risk_df,
            "application_map": application_map_df,
            "cost_ownership": cost_ownership_df,
        }

        return {
            "summary": summary,
            "metrics": metrics,
            "dataframes": dataframes,
            "financial_model": financial_model,
            "reconciliation": reconciliation,
            "reconciliation_cards": {
                "status": reconciliation.get("status") or "Unknown",
                "allocation_coverage": _safe_float(reconciliation.get("allocation_coverage")),
                "allocation_coverage_display": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                "variance": _safe_float(reconciliation.get("variance")),
                "variance_display": _money(reconciliation.get("variance")),
                "allocated_spend": _safe_float(financial_model.get("allocated_spend")),
                "allocated_spend_display": _money(financial_model.get("allocated_spend")),
                "unallocated_spend": _safe_float(financial_model.get("unallocated_spend")),
                "unallocated_spend_display": _money(financial_model.get("unallocated_spend")),
            },
            "business_context": business_context,
            "executive_summary": ApplicationInventoryCertificationService._executive_summary(
                metrics,
                financial_model,
                reconciliation,
                business_context,
            ),
            "evidence": ApplicationInventoryCertificationService._evidence(
                metrics,
                financial_model,
                reconciliation,
                business_context,
                dataframes,
            ),
        }

    @staticmethod
    def application_dependency_map(
        dependency_df: pd.DataFrame,
        portfolio_df: pd.DataFrame,
        cost_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if dependency_df.empty:
            return pd.DataFrame(columns=["Application", "Business Service", "Technology", "Type", "Owner", "Spend"])

        owner_lookup = {}
        if not portfolio_df.empty and {"Application", "Owner"}.issubset(portfolio_df.columns):
            owner_lookup = {
                str(row["Application"]).lower(): row["Owner"]
                for _, row in portfolio_df.iterrows()
            }

        spend_lookup = {}
        if not cost_df.empty and {"App", "Total"}.issubset(cost_df.columns):
            spend_lookup = {
                str(row["App"]).lower(): row["Total"]
                for _, row in cost_df.iterrows()
            }

        rows = []
        for _, row in dependency_df.iterrows():
            target_type = str(row.get("Target Type") or "").lower()
            if target_type != "technology":
                continue

            application = _first_text([row.get("Source")], "Unknown Application")
            business_service = application if application != "Unknown Application" else _first_text(
                portfolio_df["Application"].tolist() if not portfolio_df.empty and "Application" in portfolio_df.columns else [],
                "Unknown Business Service",
            )
            rows.append(
                {
                    "Application": application,
                    "Business Service": business_service,
                    "Technology": _first_text([row.get("Target")], "Unknown Technology"),
                    "Type": _first_text([row.get("Dependency Type")], "Technology"),
                    "Owner": owner_lookup.get(application.lower(), "Unassigned"),
                    "Spend": spend_lookup.get(application.lower(), 0),
                }
            )

        return pd.DataFrame(rows)

    @staticmethod
    def application_cost_ownership_map(
        portfolio_df: pd.DataFrame,
        cost_df: pd.DataFrame,
        unallocated_spend: float,
    ) -> pd.DataFrame:
        if portfolio_df.empty:
            return pd.DataFrame(
                columns=[
                    "Application",
                    "Business Owner",
                    "Technical Owner",
                    "Business Unit",
                    "Department",
                    "Allocated Spend",
                    "Unallocated Spend",
                    "Criticality",
                    "Health",
                ]
            )

        spend_lookup = {}
        if not cost_df.empty and {"App", "Total"}.issubset(cost_df.columns):
            spend_lookup = {
                str(row["App"]).lower(): row["Total"]
                for _, row in cost_df.iterrows()
            }

        rows = []
        for _, row in portfolio_df.iterrows():
            application = _first_text([row.get("Application")], "Unknown Application")
            owner = _first_text([row.get("Owner")], "Unassigned")
            business_unit = _first_text([row.get("Business Unit")], "Unassigned")
            allocated = _safe_float(spend_lookup.get(application.lower()))
            criticality = _first_text([row.get("Criticality")], "Standard")
            has_owner = owner != "Unassigned"
            has_spend = allocated > 0

            if has_owner and has_spend:
                health = "Healthy"
            elif has_owner or has_spend:
                health = "Needs Review"
            else:
                health = "Attention Required"

            rows.append(
                {
                    "Application": application,
                    "Business Owner": owner,
                    "Technical Owner": "Unassigned",
                    "Business Unit": business_unit,
                    "Department": business_unit,
                    "Allocated Spend": allocated,
                    "Unallocated Spend": 0 if has_spend or len(portfolio_df) != 1 else unallocated_spend,
                    "Criticality": criticality,
                    "Health": health,
                }
            )

        return pd.DataFrame(rows)

    @staticmethod
    def _metrics(
        summary: dict[str, Any],
        portfolio_df: pd.DataFrame,
        cost_df: pd.DataFrame,
        risk_df: pd.DataFrame,
    ) -> dict[str, Any]:
        total_applications = _safe_int(summary.get("applications"))
        application_spend = _safe_float(summary.get("allocated_spend"))
        unmapped_spend = _safe_float(summary.get("unallocated_spend"))
        total_spend_scope = application_spend + unmapped_spend
        mapped_applications = int((cost_df["Total"] > 0).sum()) if not cost_df.empty and "Total" in cost_df.columns else 0
        unmapped_applications = max(total_applications - mapped_applications, 0)
        owner_gaps = (
            int(portfolio_df["Owner"].astype(str).str.lower().isin(["", "unassigned", "none", "nan"]).sum())
            if not portfolio_df.empty and "Owner" in portfolio_df.columns
            else 0
        )
        high_risk_applications = len(risk_df)
        average_health_score = round(
            (
                (mapped_applications / total_applications * 45 if total_applications else 0)
                + ((total_applications - owner_gaps) / total_applications * 35 if total_applications else 0)
                + (20 if high_risk_applications == 0 else max(0, 20 - high_risk_applications * 5))
            ),
            1,
        )
        allocation_coverage = round((application_spend / total_spend_scope) * 100, 1) if total_spend_scope else 0

        return {
            "total_applications": total_applications,
            "business_critical_apps": _safe_int(summary.get("critical_applications")),
            "application_spend": application_spend,
            "unmapped_spend": unmapped_spend,
            "total_spend_scope": total_spend_scope,
            "mapped_applications": mapped_applications,
            "unmapped_applications": unmapped_applications,
            "owner_gaps": owner_gaps,
            "high_risk_applications": high_risk_applications,
            "average_health_score": average_health_score,
            "allocation_coverage": allocation_coverage,
            "technology_dependencies": _safe_int(summary.get("technology_dependencies")),
            "applications_with_owners": max(total_applications - owner_gaps, 0),
            "needs_cio_attention": owner_gaps + unmapped_applications + high_risk_applications,
        }

    @staticmethod
    def _business_context(metrics: dict[str, Any]) -> dict[str, Any]:
        unit_summary = _safe_call(BusinessUnitService.get_summary, {})
        capability_summary = _safe_call(BusinessCapabilityService.get_capability_summary, {})
        service_summary = _safe_call(BusinessServiceService.get_service_summary, {})
        process_summary = _safe_call(BusinessProcessService.get_process_summary, {})

        return {
            "business_units": _safe_int(unit_summary.get("business_units") or unit_summary.get("total_business_units")),
            "capabilities": _safe_int(capability_summary.get("capabilities") or capability_summary.get("total_capabilities")),
            "business_services": _safe_int(service_summary.get("business_services") or service_summary.get("total_services")),
            "business_processes": _safe_int(process_summary.get("business_processes") or process_summary.get("total_processes")),
            "applications": _safe_int(metrics.get("total_applications")),
            "technologies": _safe_int(metrics.get("technology_dependencies")),
            "mapping_coverage": _safe_float(
                service_summary.get("mapping_coverage")
                or capability_summary.get("mapping_coverage")
                or unit_summary.get("mapping_coverage")
                or metrics.get("allocation_coverage")
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
            f"Application Inventory tracks {_safe_int(metrics.get('total_applications'))} active applications, including {_safe_int(metrics.get('business_critical_apps'))} business-critical application.",
            f"Portfolio health is {_safe_float(metrics.get('average_health_score')):.1f}% with {_safe_int(metrics.get('high_risk_applications'))} active risk signals and {_safe_int(metrics.get('technology_dependencies'))} technology dependencies.",
            f"Allocated application spend is {_money(metrics.get('application_spend'))}, while unmapped technology spend is {_money(metrics.get('unmapped_spend'))}.",
            f"Business architecture context includes {_safe_int(business_context.get('business_units'))} business units, {_safe_int(business_context.get('capabilities'))} capabilities, {_safe_int(business_context.get('business_services'))} services, and {_safe_int(business_context.get('business_processes'))} processes.",
            f"Data reconciliation status is {reconciliation.get('status') or 'Unknown'} with {_safe_float(reconciliation.get('allocation_coverage')):.1f}% allocation coverage and {_money(financial_model.get('unallocated_spend'))} unallocated spend.",
        ]
        return ApplicationInventoryCertificationService.escape_markdown_currency(" ".join(sentences))

    @staticmethod
    def _evidence(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
        dataframes: dict[str, pd.DataFrame],
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {"Section": "Application Portfolio", "Source": "ApplicationPortfolioService", "Mode": "Service"},
                {"Section": "Cost Allocation", "Source": "ApplicationPortfolioService.get_application_cost_allocation", "Mode": "Service"},
                {"Section": "Dependencies", "Source": "ApplicationPortfolioService.get_dependency_graph", "Mode": "Service"},
                {"Section": "Business Architecture", "Source": "BusinessUnit/Capability/Service/Process services", "Mode": "Service"},
                {"Section": "Financial Model", "Source": "EnterpriseFinancialModel", "Mode": "Canonical"},
            ],
            "data_coverage": [
                {"Coverage Area": "Applications", "Value": f"{_safe_int(metrics.get('total_applications')):,}", "Status": "Tracked"},
                {"Coverage Area": "Mapped Applications", "Value": f"{_safe_int(metrics.get('mapped_applications')):,}", "Status": "Tracked"},
                {"Coverage Area": "Allocation Coverage", "Value": f"{_safe_float(metrics.get('allocation_coverage')):.1f}%", "Status": "Tracked"},
                {"Coverage Area": "Owner Gaps", "Value": f"{_safe_int(metrics.get('owner_gaps')):,}", "Status": "Needs Review" if metrics.get("owner_gaps") else "Healthy"},
                {"Coverage Area": "Financial Reconciliation", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%", "Status": reconciliation.get("status") or "Unknown"},
            ],
            "relationship_summary": [
                {"Layer": "Business Units", "Count": _safe_int(business_context.get("business_units"))},
                {"Layer": "Capabilities", "Count": _safe_int(business_context.get("capabilities"))},
                {"Layer": "Business Services", "Count": _safe_int(business_context.get("business_services"))},
                {"Layer": "Business Processes", "Count": _safe_int(business_context.get("business_processes"))},
                {"Layer": "Applications", "Count": _safe_int(metrics.get("total_applications"))},
                {"Layer": "Technology Dependencies", "Count": _safe_int(metrics.get("technology_dependencies"))},
            ],
            "financial_reconciliation": [
                {"Metric": "Data Reconciliation Status", "Value": reconciliation.get("status") or "Unknown"},
                {"Metric": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%"},
                {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                {"Metric": "Allocated Application Spend", "Value": _money(metrics.get("application_spend"))},
                {"Metric": "Unmapped Technology Spend", "Value": _money(metrics.get("unmapped_spend"))},
            ],
            "ai_interpretation": (
                "Application Inventory is certification-ready because it separates allocated application spend "
                "from unmapped technology spend, exposes ownership and dependency gaps, and provides clear CIO "
                "evidence for application accountability. The next maturity step is explicit capability and "
                "process mapping for every application."
            ),
            "raw_evidence": {
                "Application Portfolio": [
                    {"Metric": "Portfolio Rows", "Value": len(dataframes.get("portfolio", pd.DataFrame()))},
                    {"Metric": "Cost Allocation Rows", "Value": len(dataframes.get("cost", pd.DataFrame()))},
                    {"Metric": "Dependency Rows", "Value": len(dataframes.get("dependency", pd.DataFrame()))},
                    {"Metric": "Risk Rows", "Value": len(dataframes.get("risk", pd.DataFrame()))},
                ],
                "Application Metrics": [
                    {"Metric": "Total Applications", "Value": _safe_int(metrics.get("total_applications"))},
                    {"Metric": "Critical Applications", "Value": _safe_int(metrics.get("business_critical_apps"))},
                    {"Metric": "Mapped Applications", "Value": _safe_int(metrics.get("mapped_applications"))},
                    {"Metric": "Unmapped Applications", "Value": _safe_int(metrics.get("unmapped_applications"))},
                    {"Metric": "Technology Dependencies", "Value": _safe_int(metrics.get("technology_dependencies"))},
                ],
                "Financial Model": [
                    {"Metric": "Enterprise Total", "Value": _money(financial_model.get("enterprise_total"))},
                    {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                    {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                    {"Metric": "Generated At", "Value": str(financial_model.get("generated_at") or "Unknown")},
                ],
            },
        }

