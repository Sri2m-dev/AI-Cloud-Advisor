from __future__ import annotations

from typing import Any

import pandas as pd

from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.enterprise_financial_model import EnterpriseFinancialModel
from services.supabase_client import supabase


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


def _fetch_table(table_name: str) -> list[dict[str, Any]]:
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data or []
    except Exception:
        return []


def _money(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _percent_status(value: float) -> str:
    if value >= 90:
        return "healthy"
    if value >= 75:
        return "warning"
    return "critical"


def _count_business_critical(inventory_df: pd.DataFrame) -> int:
    if inventory_df.empty:
        return 0

    critical_columns = [
        "business_criticality",
        "criticality",
        "tier",
        "risk_tier",
        "is_business_critical",
        "is_critical",
    ]
    for column in critical_columns:
        if column not in inventory_df.columns:
            continue
        values = inventory_df[column].astype(str).str.lower()
        return int(values.isin(["critical", "high", "tier 0", "tier 1", "true", "yes", "1"]).sum())

    return 0


class TechnologyInventoryCertificationService:
    """Certification service for the Technology Inventory page."""

    @staticmethod
    def format_money(value: Any) -> str:
        return _money(value)

    @staticmethod
    def percent_status(value: float) -> str:
        return _percent_status(value)

    @staticmethod
    def get_dashboard() -> dict[str, Any]:
        inventory_df = pd.DataFrame(_fetch_table("technology_inventory"))
        vendor_spend_df = pd.DataFrame(_fetch_table("vw_vendor_spend"))
        relationships_df = pd.DataFrame(_fetch_table("technology_relationships"))

        if not inventory_df.empty and "annual_cost" in inventory_df.columns:
            inventory_df["annual_cost"] = pd.to_numeric(inventory_df["annual_cost"], errors="coerce").fillna(0)

        metrics = TechnologyInventoryCertificationService._metrics(inventory_df, relationships_df)
        financial_model = EnterpriseFinancialModel.get_enterprise_summary()
        reconciliation = EnterpriseFinancialModel.get_reconciliation_status()
        business_context = TechnologyInventoryCertificationService._business_context(metrics)

        return {
            "metrics": metrics,
            "dataframes": {
                "inventory": inventory_df,
                "vendor_spend": vendor_spend_df,
                "relationships": relationships_df,
            },
            "financial_model": financial_model,
            "reconciliation": reconciliation,
            "reconciliation_cards": {
                "status": reconciliation.get("status") or "Unknown",
                "allocation_coverage": _safe_float(reconciliation.get("allocation_coverage")),
                "allocation_coverage_display": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%",
                "unallocated_spend": _safe_float(financial_model.get("unallocated_spend")),
                "unallocated_spend_display": _money(financial_model.get("unallocated_spend")),
            },
            "business_context": business_context,
            "executive_summary": TechnologyInventoryCertificationService._executive_summary(
                metrics,
                financial_model,
                reconciliation,
                business_context,
            ),
            "evidence": TechnologyInventoryCertificationService._evidence(
                metrics,
                financial_model,
                reconciliation,
                business_context,
                inventory_df,
                vendor_spend_df,
                relationships_df,
            ),
        }

    @staticmethod
    def _metrics(inventory_df: pd.DataFrame, relationships_df: pd.DataFrame) -> dict[str, Any]:
        total_technologies = len(inventory_df)
        annual_spend = inventory_df["annual_cost"].sum() if not inventory_df.empty and "annual_cost" in inventory_df.columns else 0

        assigned_departments = inventory_df["owner_department"].notna().sum() if "owner_department" in inventory_df else 0
        assigned_business_owners = inventory_df["business_owner"].notna().sum() if "business_owner" in inventory_df else 0
        assigned_technical_owners = inventory_df["technical_owner"].notna().sum() if "technical_owner" in inventory_df else 0

        ownership_coverage = round((assigned_departments / total_technologies) * 100, 1) if total_technologies else 0
        business_owner_coverage = round((assigned_business_owners / total_technologies) * 100, 1) if total_technologies else 0
        technical_owner_coverage = round((assigned_technical_owners / total_technologies) * 100, 1) if total_technologies else 0
        data_quality_score = (
            round((ownership_coverage + business_owner_coverage + technical_owner_coverage) / 3, 1)
            if total_technologies
            else 0
        )

        departments_covered = inventory_df["owner_department"].nunique() if "owner_department" in inventory_df else 0
        business_owners = inventory_df["business_owner"].nunique() if "business_owner" in inventory_df else 0
        vendor_count = inventory_df["vendor_name"].nunique() if not inventory_df.empty and "vendor_name" in inventory_df else 0
        mapped_owners = max(assigned_business_owners, assigned_technical_owners)
        owner_gaps = max(total_technologies - mapped_owners, 0)
        business_critical_technologies = _count_business_critical(inventory_df)
        relationship_count = len(relationships_df)

        if ownership_coverage == 100 and business_owner_coverage == 100 and technical_owner_coverage == 100:
            governance_status = "Healthy"
        elif ownership_coverage >= 80:
            governance_status = "Needs Review"
        else:
            governance_status = "Critical"

        top_department = None
        top_department_spend = 0
        if not inventory_df.empty and "owner_department" in inventory_df.columns and "annual_cost" in inventory_df.columns:
            dept_summary = inventory_df.groupby("owner_department")["annual_cost"].sum().sort_values(ascending=False)
            if not dept_summary.empty:
                top_department = dept_summary.index[0]
                top_department_spend = dept_summary.iloc[0]

        return {
            "total_technologies": total_technologies,
            "annual_spend": annual_spend,
            "assigned_departments": assigned_departments,
            "assigned_business_owners": assigned_business_owners,
            "assigned_technical_owners": assigned_technical_owners,
            "ownership_coverage": ownership_coverage,
            "business_owner_coverage": business_owner_coverage,
            "technical_owner_coverage": technical_owner_coverage,
            "data_quality_score": data_quality_score,
            "departments_covered": departments_covered,
            "business_owners": business_owners,
            "vendor_count": vendor_count,
            "mapped_owners": mapped_owners,
            "owner_gaps": owner_gaps,
            "business_critical_technologies": business_critical_technologies,
            "relationship_count": relationship_count,
            "governance_status": governance_status,
            "top_department": top_department,
            "top_department_spend": top_department_spend,
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
            "technologies": _safe_int(metrics.get("total_technologies")),
            "relationships": _safe_int(metrics.get("relationship_count")),
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
            f"Technology Inventory tracks {_safe_int(metrics.get('total_technologies'))} technologies across {_safe_int(metrics.get('departments_covered'))} departments and {_safe_int(metrics.get('vendor_count'))} vendors.",
            f"Owner coverage is {_safe_float(metrics.get('ownership_coverage')):.1f}% with {_safe_int(metrics.get('owner_gaps'))} records needing ownership cleanup.",
            f"Annual spend represented in the inventory is {_money(metrics.get('annual_spend'))}.",
            f"The inventory has {_safe_int(metrics.get('relationship_count'))} relationship rows available for graph and impact analysis.",
            f"Business architecture context includes {_safe_int(business_context.get('business_units'))} business units, {_safe_int(business_context.get('capabilities'))} capabilities, {_safe_int(business_context.get('business_services'))} services, and {_safe_int(business_context.get('business_processes'))} processes.",
            f"Data reconciliation status is {reconciliation.get('status') or 'Unknown'} with {_safe_float(reconciliation.get('allocation_coverage')):.1f}% allocation coverage and {_money(financial_model.get('unallocated_spend'))} unallocated spend.",
        ]
        return " ".join(sentences).replace("$", r"\$")

    @staticmethod
    def _evidence(
        metrics: dict[str, Any],
        financial_model: dict[str, Any],
        reconciliation: dict[str, Any],
        business_context: dict[str, Any],
        inventory_df: pd.DataFrame,
        vendor_spend_df: pd.DataFrame,
        relationships_df: pd.DataFrame,
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {"Section": "Technology Inventory", "Source": "technology_inventory", "Mode": "Live"},
                {"Section": "Vendor Spend", "Source": "vw_vendor_spend", "Mode": "Live"},
                {"Section": "Relationships", "Source": "technology_relationships", "Mode": "Live"},
                {"Section": "Business Architecture", "Source": "BusinessUnit/Capability/Service/Process services", "Mode": "Service"},
                {"Section": "Financial Model", "Source": "EnterpriseFinancialModel", "Mode": "Canonical"},
            ],
            "data_coverage": [
                {"Coverage Area": "Technology Records", "Value": f"{len(inventory_df):,}", "Status": "Tracked"},
                {"Coverage Area": "Owner Coverage", "Value": f"{_safe_float(metrics.get('ownership_coverage')):.1f}%", "Status": metrics.get("governance_status")},
                {"Coverage Area": "Business Owner Coverage", "Value": f"{_safe_float(metrics.get('business_owner_coverage')):.1f}%", "Status": "Tracked"},
                {"Coverage Area": "Technical Owner Coverage", "Value": f"{_safe_float(metrics.get('technical_owner_coverage')):.1f}%", "Status": "Tracked"},
                {"Coverage Area": "Relationship Rows", "Value": f"{len(relationships_df):,}", "Status": "Tracked"},
                {"Coverage Area": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%", "Status": reconciliation.get("status") or "Unknown"},
            ],
            "relationship_summary": [
                {"Layer": "Business Units", "Count": _safe_int(business_context.get("business_units"))},
                {"Layer": "Capabilities", "Count": _safe_int(business_context.get("capabilities"))},
                {"Layer": "Business Services", "Count": _safe_int(business_context.get("business_services"))},
                {"Layer": "Business Processes", "Count": _safe_int(business_context.get("business_processes"))},
                {"Layer": "Technologies", "Count": _safe_int(metrics.get("total_technologies"))},
                {"Layer": "Technology Relationships", "Count": _safe_int(metrics.get("relationship_count"))},
            ],
            "financial_reconciliation": [
                {"Metric": "Data Reconciliation Status", "Value": reconciliation.get("status") or "Unknown"},
                {"Metric": "Allocation Coverage", "Value": f"{_safe_float(reconciliation.get('allocation_coverage')):.1f}%"},
                {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                {"Metric": "Inventory Annual Spend", "Value": _money(metrics.get("annual_spend"))},
            ],
            "ai_interpretation": (
                "Technology Inventory is ready for certified CIO governance review because it exposes ownership, "
                "vendor, spend, relationship, and data quality signals with financial reconciliation context. "
                "Certification depth can improve further when every technology record is mapped to explicit "
                "business capability and service paths."
            ),
            "raw_evidence": {
                "Inventory Summary": [
                    {"Metric": "Technology Records", "Value": len(inventory_df)},
                    {"Metric": "Vendor Spend Rows", "Value": len(vendor_spend_df)},
                    {"Metric": "Relationship Rows", "Value": len(relationships_df)},
                    {"Metric": "Owner Gaps", "Value": _safe_int(metrics.get("owner_gaps"))},
                    {"Metric": "Business Critical Technologies", "Value": _safe_int(metrics.get("business_critical_technologies"))},
                ],
                "Financial Model": [
                    {"Metric": "Enterprise Total", "Value": _money(financial_model.get("enterprise_total"))},
                    {"Metric": "Allocated Spend", "Value": _money(financial_model.get("allocated_spend"))},
                    {"Metric": "Unallocated Spend", "Value": _money(financial_model.get("unallocated_spend"))},
                    {"Metric": "Generated At", "Value": str(financial_model.get("generated_at") or "Unknown")},
                ],
            },
        }
