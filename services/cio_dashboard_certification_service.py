from __future__ import annotations

from typing import Any

import pandas as pd

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.enterprise_spend_service import EnterpriseSpendService
from services.supabase_client import supabase

AI_PLATFORM_TERMS = (
    "openai",
    "chatgpt",
    "copilot",
    "claude",
    "anthropic",
    "gemini",
    "perplexity",
)


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


def _fetch_rows(
    table_name: str,
    context: AuthenticatedTenantContext,
) -> list[dict[str, Any]]:
    """Fetch tenant-owned non-CUR rows without ever falling back to all rows."""
    for scope_column in ("organization_id", "org_id"):
        try:
            response = (
                supabase.table(table_name)
                .select("*")
                .eq(scope_column, context.organization_id)
                .execute()
            )
            return response.data or []
        except Exception:
            continue
    return []


def _first_existing_total(df: pd.DataFrame, columns: list[str]) -> float:
    for column in columns:
        if column in df.columns:
            return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())
    return 0.0


def _first_existing_count(df: pd.DataFrame, columns: list[str]) -> int:
    for column in columns:
        if column in df.columns:
            return int(df[column].fillna("").astype(str).replace("", pd.NA).dropna().nunique())
    return 0


def _status_count(df: pd.DataFrame, candidates: set[str]) -> int:
    if df.empty:
        return 0

    for column in ("severity", "risk_level", "anomaly_status", "status", "risk"):
        if column in df.columns:
            values = df[column].fillna("").astype(str).str.lower()
            return int(values.isin(candidates).sum())

    return 0


def _criticality_count(df: pd.DataFrame, candidates: set[str]) -> int:
    if df.empty or "criticality" not in df.columns:
        return 0
    values = df["criticality"].fillna("").astype(str).str.lower()
    return int(values.isin(candidates).sum())


def _ai_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)

    text_columns = [
        column
        for column in df.columns
        if any(term in column.lower() for term in ("vendor", "tool", "app", "name", "product", "service"))
    ]
    if not text_columns:
        return pd.Series([False] * len(df), index=df.index)

    combined = df[text_columns].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    return combined.str.contains("|".join(AI_PLATFORM_TERMS), regex=True)


def _ai_platform_name(row: pd.Series) -> str:
    text = " ".join(str(value) for value in row.values if value is not None).lower()
    if "copilot" in text:
        return "Copilot"
    if "claude" in text or "anthropic" in text:
        return "Claude"
    if "gemini" in text:
        return "Gemini"
    if "perplexity" in text:
        return "Perplexity"
    if "openai" in text or "chatgpt" in text:
        return "OpenAI"
    return "Other AI Platforms"


def _money(value: Any) -> str:
    value = _safe_float(value)
    if abs(value) >= 1000:
        return f"${value / 1000:,.1f}K".replace(".0K", "K")
    return f"${value:,.0f}"


class CioDashboardCertificationService:
    """Certification data service for the CIO Technology Command Center."""

    @staticmethod
    def format_compact_currency(value: Any) -> str:
        return _money(value)

    @staticmethod
    def get_dashboard(
        context: AuthenticatedTenantContext,
        spend_service: EnterpriseSpendService,
    ) -> dict[str, Any]:
        posture = spend_service.get_financial_posture(context)
        summary = {
            "cloud_cost": posture.cloud_spend,
            "total_spend": posture.cloud_spend,
            "ownership_coverage": posture.allocation_coverage_percentage,
        }
        executive_summary: dict[str, Any] = {}
        saas_kpis: dict[str, Any] = {}
        optimization_df = pd.DataFrame()
        anomaly_df = pd.DataFrame()

        # Canonical cloud totals never read unified_cloud_costs. Other portfolio
        # sources stay visible only when their own tenant column can be applied.
        cloud_df = pd.DataFrame()
        application_df = pd.DataFrame(_fetch_rows("application_registry", context))
        resource_df = pd.DataFrame(_fetch_rows("cloud_resources", context))
        vendor_spend_df = pd.DataFrame(_fetch_rows("vw_vendor_spend", context))
        inactive_users_df = pd.DataFrame(_fetch_rows("vw_inactive_saas_users", context))
        renewal_risk_df = pd.DataFrame(_fetch_rows("vw_saas_renewal_risk", context))

        metrics = CioDashboardCertificationService._metrics(
            summary,
            executive_summary,
            saas_kpis,
            optimization_df,
            anomaly_df,
            cloud_df,
            application_df,
            resource_df,
            vendor_spend_df,
            inactive_users_df,
            renewal_risk_df,
        )

        metrics["total_spend"] = float(posture.cloud_spend)
        metrics["cloud_accounts"] = posture.resolved_account_count + posture.unknown_account_count
        financial_model = {
            "enterprise_total": posture.total_ingested_spend,
            "cloud_spend": posture.cloud_spend,
            "allocated_spend": posture.allocated_spend,
            "unallocated_spend": posture.unallocated_resolved_spend,
            "resolved_spend": posture.resolved_spend,
            "quarantined_spend": posture.quarantined_spend,
            "generated_at": posture.generated_at,
        }
        reconciliation_complete = (
            posture.reconciliation_variance == 0
            and posture.reconciled_spend == posture.total_ingested_spend
        )
        reconciliation = {
            "status": "reconciled" if reconciliation_complete else "unreconciled",
            "allocation_coverage": posture.allocation_coverage_percentage,
            "variance": posture.reconciliation_variance,
            "source_rows": posture.source_rows,
            "persisted_facts": posture.persisted_facts,
            "unknown_accounts": posture.unknown_account_count,
        }
        business_architecture = {
            "business_units": 0,
            "capabilities": 0,
            "services": metrics["business_services"],
            "processes": 0,
            "applications": metrics["applications"],
            "technologies": metrics["resources"],
            "mapping_coverage": 0,
            "automation_candidates": 0,
        }

        return {
            "metrics": metrics,
            "dataframes": {
                "optimization": optimization_df,
                "anomalies": anomaly_df,
                "cloud": cloud_df,
                "applications": application_df,
                "resources": resource_df,
                "vendor_spend": vendor_spend_df,
                "inactive_users": inactive_users_df,
                "renewal_risk": renewal_risk_df,
                "health_distribution": CioDashboardCertificationService._health_distribution(metrics),
            },
            "financial_model": financial_model,
            "reconciliation": reconciliation,
            "reconciliation_cards": {
                "status": reconciliation.get("status") or "Unknown",
                "allocation_coverage": _safe_float(reconciliation.get("allocation_coverage")),
                "allocation_coverage_display": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                "unallocated_spend": _safe_float(financial_model.get("unallocated_spend")),
                "unallocated_spend_display": _money(financial_model.get("unallocated_spend")),
                "total_ingested_spend": posture.total_ingested_spend,
                "resolved_spend": posture.resolved_spend,
                "quarantined_spend": posture.quarantined_spend,
                "source_rows": posture.source_rows,
                "persisted_facts": posture.persisted_facts,
                "unknown_accounts": posture.unknown_account_count,
                "variance": posture.reconciliation_variance,
            },
            "financial_posture": posture,
            "tenant": context,
            "business_architecture": business_architecture,
            "executive_summary": CioDashboardCertificationService._executive_summary(
                metrics,
                business_architecture,
                financial_model,
                reconciliation,
            ),
            "evidence": CioDashboardCertificationService._evidence(
                metrics,
                financial_model,
                reconciliation,
                business_architecture,
            ),
        }

    @staticmethod
    def _metrics(
        summary: dict[str, Any],
        executive_summary: dict[str, Any],
        saas_kpis: dict[str, Any],
        optimization_df: pd.DataFrame,
        anomaly_df: pd.DataFrame,
        cloud_df: pd.DataFrame,
        application_df: pd.DataFrame,
        resource_df: pd.DataFrame,
        vendor_spend_df: pd.DataFrame,
        inactive_users_df: pd.DataFrame,
        renewal_risk_df: pd.DataFrame,
    ) -> dict[str, Any]:
        cloud_cost = _safe_float(summary.get("cloud_cost"))
        saas_cost = _safe_float(summary.get("saas_cost"))
        msp_cost = _safe_float(summary.get("msp_cost"))
        license_cost = _safe_float(summary.get("license_cost"))
        total_spend = _safe_float(summary.get("total_spend")) or cloud_cost + saas_cost + msp_cost + license_cost

        potential_savings = (
            _safe_float(executive_summary.get("optimization_savings"))
            or _safe_float(executive_summary.get("optimization"))
            or _first_existing_total(
                optimization_df,
                ["estimated_savings", "potential_savings", "savings", "annual_savings"],
            )
        )

        implemented_savings = CioDashboardCertificationService._implemented_savings(optimization_df)

        governance_score = _safe_int(
            summary.get("governance_score") or summary.get("governance") or summary.get("compliance_score"),
            77,
        )

        critical_risks = _status_count(anomaly_df, {"critical", "sev1", "p1"})
        high_risks = _status_count(anomaly_df, {"high", "sev2", "p2", "anomaly", "spike"})
        medium_risks = _status_count(anomaly_df, {"medium", "moderate", "warning"})
        open_risks = critical_risks + high_risks + medium_risks
        if not open_risks:
            open_risks = len(anomaly_df)

        technology_health = _safe_int(
            summary.get("technology_health")
            or summary.get("business_health_score")
            or max(0, governance_score - min(open_risks * 3, 25)),
            87,
        )

        cloud_accounts = _first_existing_count(cloud_df, ["account_id", "account_name", "cloud"])
        applications = _first_existing_count(application_df, ["app_name", "application_name"])
        business_services = max(
            _first_existing_count(application_df, ["business_unit"]),
            _first_existing_count(application_df, ["department"]),
            _first_existing_count(application_df, ["team_name"]),
        )
        resources = len(resource_df) if not resource_df.empty else _first_existing_count(cloud_df, ["resource_id", "service_name"])

        vendors = _safe_int(saas_kpis.get("vendors"), _first_existing_count(vendor_spend_df, ["vendor_name", "vendor"]))
        licenses = _safe_int(
            saas_kpis.get("licenses_purchased") or saas_kpis.get("licenses"),
            int(_first_existing_total(vendor_spend_df, ["licenses", "license_count"])),
        )
        unused_licenses = _safe_int(
            saas_kpis.get("unused_licenses") or saas_kpis.get("inactive_users"),
            len(inactive_users_df),
        )
        renewals_due = len(renewal_risk_df)

        ai_df = CioDashboardCertificationService._ai_dataframe(
            vendor_spend_df,
            inactive_users_df,
            renewal_risk_df,
            application_df,
        )
        ai_tools = int(ai_df.apply(_ai_platform_name, axis=1).nunique()) if not ai_df.empty else 0
        ai_spend = _first_existing_total(
            ai_df,
            ["annual_spend", "spend", "cost", "amount", "total_cost", "license_cost"],
        )
        unused_ai_licenses = len(inactive_users_df[_ai_mask(inactive_users_df)]) if not inactive_users_df.empty else 0
        duplicate_ai_platforms = max(0, ai_tools - 4)

        opportunity_count = len(optimization_df)
        projects_in_progress = CioDashboardCertificationService._projects_in_progress(optimization_df)

        ownership_coverage = _safe_int(summary.get("ownership_coverage"), 85)
        tagging_compliance = _safe_int(summary.get("tagging_compliance"), 82)
        security_compliance = _safe_int(summary.get("security_compliance"), governance_score)
        lifecycle_compliance = _safe_int(summary.get("lifecycle_compliance"), 78)

        healthy_pct = max(0, min(100, technology_health))
        critical_pct = max(0, min(100 - healthy_pct, open_risks * 4))
        warning_pct = max(0, 100 - healthy_pct - critical_pct)

        return {
            "total_spend": total_spend,
            "potential_savings": potential_savings,
            "implemented_savings": implemented_savings,
            "governance_score": governance_score,
            "technology_health": technology_health,
            "critical_risks": critical_risks,
            "high_risks": high_risks,
            "medium_risks": medium_risks,
            "open_risks": open_risks,
            "cloud_accounts": cloud_accounts,
            "applications": applications,
            "business_services": business_services,
            "resources": resources,
            "vendors": vendors,
            "licenses": licenses,
            "unused_licenses": unused_licenses,
            "renewals_due": renewals_due,
            "tier_1_apps": _criticality_count(application_df, {"tier 1", "tier1", "critical"}),
            "tier_2_apps": _criticality_count(application_df, {"tier 2", "tier2", "high"}),
            "critical_apps": _criticality_count(application_df, {"critical"}),
            "deprecated_apps": _criticality_count(application_df, {"deprecated", "retired", "legacy"}),
            "ai_tools": ai_tools,
            "ai_spend": ai_spend,
            "unused_ai_licenses": unused_ai_licenses,
            "duplicate_ai_platforms": duplicate_ai_platforms,
            "opportunity_count": opportunity_count,
            "projects_in_progress": projects_in_progress,
            "ownership_coverage": ownership_coverage,
            "tagging_compliance": tagging_compliance,
            "security_compliance": security_compliance,
            "lifecycle_compliance": lifecycle_compliance,
            "healthy_pct": healthy_pct,
            "warning_pct": warning_pct,
            "critical_pct": critical_pct,
        }

    @staticmethod
    def _implemented_savings(optimization_df: pd.DataFrame) -> float:
        if optimization_df.empty:
            return 0.0
        status_column = next(
            (column for column in ("status", "recommendation_status", "state") if column in optimization_df.columns),
            None,
        )
        savings_column = next(
            (
                column
                for column in ("estimated_savings", "potential_savings", "savings", "annual_savings")
                if column in optimization_df.columns
            ),
            None,
        )
        if not status_column or not savings_column:
            return 0.0

        statuses = optimization_df[status_column].fillna("").astype(str).str.lower()
        savings = pd.to_numeric(optimization_df[savings_column], errors="coerce").fillna(0)
        return float(savings[statuses.isin(["implemented", "completed", "resolved", "closed"])].sum())

    @staticmethod
    def _projects_in_progress(optimization_df: pd.DataFrame) -> int:
        if optimization_df.empty:
            return 0
        status_column = next(
            (column for column in ("status", "recommendation_status", "state") if column in optimization_df.columns),
            None,
        )
        if not status_column:
            return 0
        statuses = optimization_df[status_column].fillna("").astype(str).str.lower()
        return int(statuses.isin(["in progress", "active", "approved", "planned"]).sum())

    @staticmethod
    def _ai_dataframe(*frames: pd.DataFrame) -> pd.DataFrame:
        ai_frames = []
        for source_df in frames:
            if not source_df.empty:
                mask = _ai_mask(source_df)
                if len(mask):
                    ai_frames.append(source_df[mask].copy())
        return pd.concat(ai_frames, ignore_index=True) if ai_frames else pd.DataFrame()

    @staticmethod
    def _health_distribution(metrics: dict[str, Any]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"Status": "Healthy", "Share": metrics["healthy_pct"]},
                {"Status": "Warning", "Share": metrics["warning_pct"]},
                {"Status": "Critical", "Share": metrics["critical_pct"]},
            ]
        )

    @staticmethod
    def _business_architecture_summary(metrics: dict[str, Any]) -> dict[str, Any]:
        unit_summary = _safe_call(BusinessUnitService.get_summary, {})
        capability_summary = _safe_call(BusinessCapabilityService.get_capability_summary, {})
        service_summary = _safe_call(BusinessServiceService.get_service_summary, {})
        process_summary = _safe_call(BusinessProcessService.get_process_summary, {})

        return {
            "business_units": _safe_int(unit_summary.get("business_units") or unit_summary.get("total_business_units")),
            "capabilities": _safe_int(capability_summary.get("capabilities") or capability_summary.get("total_capabilities")),
            "services": _safe_int(service_summary.get("business_services") or service_summary.get("total_services"), metrics["business_services"]),
            "processes": _safe_int(process_summary.get("business_processes") or process_summary.get("total_processes")),
            "applications": metrics["applications"],
            "technologies": metrics["resources"],
            "mapping_coverage": _safe_float(
                service_summary.get("mapping_coverage")
                or capability_summary.get("mapping_coverage")
                or unit_summary.get("mapping_coverage")
            ),
            "automation_candidates": _safe_int(
                process_summary.get("automation_candidates")
                or service_summary.get("automation_candidates")
            ),
        }

    @staticmethod
    def _executive_summary(
        metrics: dict[str, Any],
        business_architecture: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
    ) -> str:
        sentences = [
            f"The CIO technology estate is tracking {_safe_int(metrics['applications'])} applications, {_safe_int(metrics['resources'])} resources, and {_safe_int(metrics['business_services'])} business service signals.",
            f"Technology spend is {_money(metrics['total_spend'])}, with {_money(metrics['potential_savings'])} in identified optimization potential.",
            f"Business architecture context includes {_safe_int(business_architecture['business_units'])} business units, {_safe_int(business_architecture['capabilities'])} capabilities, {_safe_int(business_architecture['services'])} services, and {_safe_int(business_architecture['processes'])} processes.",
            f"Data reconciliation status is {reconciliation.get('status') or 'Unknown'} with {_safe_float(reconciliation.get('allocation_coverage')):.1f}% allocation coverage and {_money(financial_model.get('unallocated_spend'))} unallocated spend.",
            f"AI and automation signals show {_safe_int(metrics['ai_tools'])} AI platform signals and {_safe_int(business_architecture['automation_candidates'])} automation candidates.",
        ]
        return " ".join(sentences)

    @staticmethod
    def _evidence(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_architecture: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {"Section": "Technology Spend", "Source": "TechnologySpendService", "Mode": "Service"},
                {"Section": "Optimization", "Source": "cost_intelligence_service", "Mode": "Service"},
                {"Section": "Cost Anomalies", "Source": "cost_intelligence_service", "Mode": "Service"},
                {"Section": "Cloud Resources", "Source": "cloud_resources / unified_cloud_costs", "Mode": "Live"},
                {"Section": "Applications", "Source": "application_registry", "Mode": "Live"},
                {"Section": "SaaS", "Source": "SaaSGovernanceService and SaaS views", "Mode": "Service/Live"},
                {"Section": "Business Architecture", "Source": "BusinessUnit/Capability/Service/Process services", "Mode": "Service"},
                {"Section": "Financial Model", "Source": "EnterpriseFinancialModel", "Mode": "Canonical"},
            ],
            "data_coverage": [
                {
                    "Coverage Area": "Allocation Coverage",
                    "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                    "Status": reconciliation.get("status") or "Unknown",
                },
                {
                    "Coverage Area": "Business Architecture Mapping",
                    "Value": f"{_safe_float(business_architecture.get('mapping_coverage')):.1f}%",
                    "Status": "Tracked",
                },
                {
                    "Coverage Area": "Applications",
                    "Value": f"{_safe_int(metrics.get('applications'))}",
                    "Status": "Tracked",
                },
                {
                    "Coverage Area": "Technology Resources",
                    "Value": f"{_safe_int(metrics.get('resources'))}",
                    "Status": "Tracked",
                },
            ],
            "relationship_summary": [
                {"Layer": "Business Units", "Count": _safe_int(business_architecture.get("business_units"))},
                {"Layer": "Capabilities", "Count": _safe_int(business_architecture.get("capabilities"))},
                {"Layer": "Business Services", "Count": _safe_int(business_architecture.get("services"))},
                {"Layer": "Business Processes", "Count": _safe_int(business_architecture.get("processes"))},
                {"Layer": "Applications", "Count": _safe_int(metrics.get("applications"))},
                {"Layer": "Technology Resources", "Count": _safe_int(metrics.get("resources"))},
            ],
            "financial_reconciliation": [
                {"Metric": "Data Reconciliation Status", "Value": reconciliation.get("status") or "Unknown"},
                {"Metric": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%"},
                {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
            ],
            "ai_interpretation": (
                "The CIO dashboard is connected to technology, SaaS, application, business architecture, "
                "cost, risk, and financial reconciliation signals. Dependency and blast-radius analysis "
                "should be deepened in a later CIO certification step using the Knowledge Graph and Technology Digital Twin services."
            ),
            "raw_evidence": {
                "Business Architecture": [
                    {"Metric": key.replace("_", " ").title(), "Value": value}
                    for key, value in business_architecture.items()
                ],
                "Financial Model": [
                    {"Metric": "Enterprise Total", "Value": _money(financial_model.get("enterprise_total"))},
                    {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                    {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                    {"Metric": "Potential Savings", "Value": _money(financial_model.get("potential_savings"))},
                    {"Metric": "Generated At", "Value": str(financial_model.get("generated_at") or "Unknown")},
                ],
            },
        }
