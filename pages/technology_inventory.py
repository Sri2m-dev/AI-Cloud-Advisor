import streamlit as st
import pandas as pd
import plotly.express as px

from components.cards import (
    render_health_card,
    render_kpi_card,
    render_metric_card,
    render_risk_card,
)
from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.shared import (
    render_ai_narrative,
    render_business_context,
    render_evidence_panel,
    render_executive_summary,
    render_reconciliation_panel,
)
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from auth.guards import require_login
from auth.role_constants import normalize_role
from services.technology_inventory_certification_service import TechnologyInventoryCertificationService
from shared.streamlit_compat import dataframe, plotly_chart


st.set_page_config(page_title="Technology Portfolio", layout="wide")


def _money(value) -> str:
    return TechnologyInventoryCertificationService.format_money(value)


def _percent_status(value: float) -> str:
    return TechnologyInventoryCertificationService.percent_status(value)


def main():
    user = require_login()

    role = normalize_role(
        st.session_state.get("role")
        or user.get("role")
        or "cio"
    )

    render_enterprise_sidebar(
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
        active_page=PAGE_PATHS["Technology Portfolio"],
    )

    dashboard = TechnologyInventoryCertificationService.get_dashboard()
    metrics = dashboard["metrics"]
    dataframes = dashboard["dataframes"]
    financial_model = dashboard["financial_model"]
    reconciliation_cards = dashboard["reconciliation_cards"]
    business_context = dashboard["business_context"]
    evidence = dashboard["evidence"]

    inventory_df = dataframes["inventory"]
    vendor_spend_df = dataframes["vendor_spend"]
    relationships_df = dataframes["relationships"]

    total_technologies = metrics["total_technologies"]
    annual_spend = metrics["annual_spend"]
    ownership_coverage = metrics["ownership_coverage"]
    business_owner_coverage = metrics["business_owner_coverage"]
    technical_owner_coverage = metrics["technical_owner_coverage"]
    data_quality_score = metrics["data_quality_score"]
    departments_covered = metrics["departments_covered"]
    vendor_count = metrics["vendor_count"]
    mapped_owners = metrics["mapped_owners"]
    owner_gaps = metrics["owner_gaps"]
    business_critical_technologies = metrics["business_critical_technologies"]
    relationship_count = metrics["relationship_count"]
    governance_status = metrics["governance_status"]
    top_department = metrics["top_department"]
    top_department_spend = metrics["top_department_spend"]

    def render_certification_summary():
        render_executive_summary(
            {
                "title": "Executive Summary",
                "description": "Certified CIO view of inventory ownership, financial reconciliation, and business architecture exposure.",
                "narrative": dashboard["executive_summary"],
                "metrics": [
                    {
                        "label": "Technologies",
                        "value": f"{total_technologies:,}",
                        "description": "Tracked technology portfolio records",
                        "icon": "technology",
                        "status": "info",
                    },
                    {
                        "label": "Annual Spend",
                        "value": _money(annual_spend),
                        "description": "Spend represented in inventory",
                        "icon": "cost",
                        "status": "info",
                    },
                    {
                        "label": "Owner Coverage",
                        "value": f"{ownership_coverage:.1f}%",
                        "description": "Department ownership coverage",
                        "icon": "governance",
                        "status": _percent_status(ownership_coverage),
                    },
                    {
                        "label": "Data Quality",
                        "value": f"{data_quality_score}%",
                        "description": "Average owner and department coverage",
                        "icon": "health",
                        "status": _percent_status(data_quality_score),
                    },
                    {
                        "label": "Owner Gaps",
                        "value": f"{owner_gaps:,}",
                        "description": "Records needing ownership cleanup",
                        "icon": "risk",
                        "status": "critical" if owner_gaps else "healthy",
                    },
                    {
                        "label": "Relationships",
                        "value": f"{relationship_count:,}",
                        "description": "Dependency and relationship rows",
                        "icon": "graph",
                        "status": "info" if relationship_count else "warning",
                    },
                    {
                        "label": "Vendors",
                        "value": f"{vendor_count:,}",
                        "description": "Distinct technology vendors",
                        "icon": "enterprise",
                        "status": "info",
                    },
                    {
                        "label": "Business Critical",
                        "value": f"{business_critical_technologies:,}",
                        "description": "Criticality flags detected",
                        "icon": "governance",
                        "status": "warning" if business_critical_technologies else "info",
                    },
                ],
            }
        )

        render_reconciliation_panel(
            {
                **reconciliation_cards,
                "allocated_spend_display": _money(financial_model.get("allocated_spend")),
                "variance_status": reconciliation_cards.get("status", "Unknown"),
            }
        )
        render_business_context(business_context)

    def render_certification_evidence():
        render_evidence_panel(evidence)

    def render_inventory_content():
        if inventory_df.empty:
            st.info("No technology portfolio data available.")
            return

        render_certification_summary()

        render_section(
            "CIO Inventory Summary",
            "Unified view of Cloud, SaaS, MSP, vendors, departments, and technology relationships.",
        )
        summary_cols = st.columns(4)
        with summary_cols[0]:
            render_kpi_card(
                "Total Technologies",
                f"{total_technologies:,}",
                "Tracked portfolio records",
                icon="technology",
                status="info",
            )
        with summary_cols[1]:
            render_health_card(
                "Mapped Owners",
                f"{mapped_owners:,}",
                "Technologies with business or technical ownership",
                icon="success",
                status=_percent_status(max(business_owner_coverage, technical_owner_coverage)),
            )
        with summary_cols[2]:
            render_risk_card(
                "Owner Gaps",
                f"{owner_gaps:,}",
                "Technologies missing clear owner coverage",
                icon="risk",
                status="critical" if owner_gaps else "healthy",
            )
        with summary_cols[3]:
            render_kpi_card(
                "Business Critical Technologies",
                f"{business_critical_technologies:,}",
                "Criticality flags detected in inventory",
                icon="governance",
                status="warning" if business_critical_technologies else "info",
            )

        portfolio_cols = st.columns(4)
        with portfolio_cols[0]:
            render_metric_card(
                "Vendors",
                f"{vendor_count:,}",
                "Distinct vendors in the inventory",
                icon="enterprise",
                status="info",
            )
        with portfolio_cols[1]:
            render_metric_card(
                "Departments",
                f"{departments_covered:,}",
                "Departments assigned to technology records",
                icon="organization",
                status="info",
            )
        with portfolio_cols[2]:
            render_metric_card(
                "Relationships",
                f"{relationship_count:,}",
                "Technology dependency and relationship rows",
                icon="graph",
                status="info" if relationship_count else "warning",
            )
        with portfolio_cols[3]:
            render_health_card(
                "Data Quality Score",
                f"{data_quality_score}%",
                "Average department, business owner, and technical owner coverage",
                icon="health",
                status=_percent_status(data_quality_score),
            )

        render_section(
            "Ownership & Accountability",
            "Owner mapping coverage across departments, business owners, and technical owners.",
        )
        ownership_cols = st.columns(4)
        with ownership_cols[0]:
            render_health_card(
                "Department Assignment",
                f"{ownership_coverage}%",
                "Technology records with department ownership",
                status=_percent_status(ownership_coverage),
            )
        with ownership_cols[1]:
            render_health_card(
                "Business Ownership",
                f"{business_owner_coverage}%",
                "Technology records with business owners",
                status=_percent_status(business_owner_coverage),
            )
        with ownership_cols[2]:
            render_health_card(
                "Technical Ownership",
                f"{technical_owner_coverage}%",
                "Technology records with technical owners",
                status=_percent_status(technical_owner_coverage),
            )
        with ownership_cols[3]:
            render_metric_card(
                "Governance Status",
                governance_status,
                "Readiness of portfolio ownership controls",
                icon="governance",
                status="healthy" if governance_status == "Healthy" else "warning" if governance_status == "Needs Review" else "critical",
            )

        render_section(
            "Vendor / Platform Distribution",
            "Spend and technology-type distribution across the portfolio.",
        )
        landscape_cols = st.columns(2)
        with landscape_cols[0]:
            if "technology_type" in inventory_df.columns:
                type_df = inventory_df.groupby("technology_type", as_index=False)["annual_cost"].sum()
                fig = px.pie(type_df, names="technology_type", values="annual_cost", hole=0.45)
                plotly_chart(fig)
            else:
                st.info("No technology type distribution data available.")

        with landscape_cols[1]:
            if not vendor_spend_df.empty:
                fig = px.bar(vendor_spend_df, x="vendor_name", y="annual_spend", text_auto=True)
                plotly_chart(fig)
            else:
                st.info("No vendor spend data available.")

        render_section(
            "Critical Technology Coverage",
            "CIO coverage of business-critical inventory and relationship context.",
        )
        critical_cols = st.columns(3)
        with critical_cols[0]:
            render_risk_card(
                "Business Critical",
                f"{business_critical_technologies:,}",
                "Critical technology records identified",
                status="warning" if business_critical_technologies else "info",
            )
        with critical_cols[1]:
            render_metric_card(
                "Annual Spend",
                _money(annual_spend),
                "Annual spend represented in technology inventory",
                icon="cost",
                status="info",
            )
        with critical_cols[2]:
            render_metric_card(
                "Relationship Coverage",
                f"{relationship_count:,}",
                "Relationship rows available for graph and impact views",
                icon="graph",
                status="info" if relationship_count else "warning",
            )

        render_section(
            "Governance & Data Quality",
            "Inventory readiness for CIO governance, graph exploration, and enterprise scoring.",
        )
        governance_cols = st.columns(3)
        with governance_cols[0]:
            render_health_card(
                "Data Quality Score",
                f"{data_quality_score}%",
                "Composite owner coverage quality",
                status=_percent_status(data_quality_score),
            )
        with governance_cols[1]:
            render_risk_card(
                "Owner Gaps",
                f"{owner_gaps:,}",
                "Records needing ownership cleanup",
                status="critical" if owner_gaps else "healthy",
            )
        with governance_cols[2]:
            render_metric_card(
                "Departments Covered",
                f"{departments_covered:,}",
                "Portfolio ownership breadth",
                icon="organization",
                status="info",
            )

        render_ai_narrative(
            "Executive Inventory Insight",
            (
                f"Technology governance coverage is currently {ownership_coverage}%. "
                f"The portfolio contains {total_technologies:,} tracked technologies across "
                f"{departments_covered:,} departments and {vendor_count:,} vendors. "
                f"{mapped_owners:,} technologies have mapped owner coverage, while {owner_gaps:,} "
                f"records need ownership cleanup. "
                f"{top_department or 'No department'} currently manages the highest technology spend at "
                f"{_money(top_department_spend)}. "
                "The portfolio is ready to support CIO governance, technology graph exploration, "
                "SaaS governance, and enterprise governance scoring."
            ),
            description="CIO narrative generated from current inventory, ownership, and relationship signals.",
        )

        render_section(
            "Detailed Evidence / Drilldown",
            "Source tables for ownership, department allocation, portfolio records, and relationships.",
        )
        with st.expander("Detailed Evidence / Drilldown"):
            st.subheader("Technology Ownership Matrix")

            ownership_columns = [
                "technology_name",
                "technology_type",
                "vendor_name",
                "owner_department",
                "business_owner",
                "technical_owner",
                "annual_cost",
                "status",
            ]

            existing_columns = [col for col in ownership_columns if col in inventory_df.columns]

            if not inventory_df.empty and existing_columns:
                ownership_df = inventory_df[existing_columns].copy()
                ownership_df = ownership_df.rename(
                    columns={
                        "technology_name": "Technology",
                        "technology_type": "Type",
                        "vendor_name": "Vendor",
                        "owner_department": "Department",
                        "business_owner": "Business Owner",
                        "technical_owner": "Technical Owner",
                        "annual_cost": "Annual Cost",
                        "status": "Status",
                    }
                )
                dataframe(ownership_df)
            else:
                st.info("No technology ownership data available.")

            st.subheader("Department Technology Allocation")

            if not inventory_df.empty and "owner_department" in inventory_df.columns:
                department_allocation_df = (
                    inventory_df.groupby("owner_department", dropna=False)
                    .agg(
                        Technologies=("technology_name", "count"),
                        Annual_Spend=("annual_cost", "sum"),
                    )
                    .reset_index()
                    .rename(
                        columns={
                            "owner_department": "Department",
                            "Annual_Spend": "Annual Spend",
                        }
                    )
                )

                dataframe(department_allocation_df)
            else:
                st.info("No department allocation data available.")

            st.subheader("Technology Portfolio")
            display_cols = [
                "technology_name",
                "technology_type",
                "vendor_name",
                "category",
                "owner_department",
                "business_owner",
                "technical_owner",
                "annual_cost",
                "status",
                "source_system",
            ]
            available_cols = [c for c in display_cols if c in inventory_df.columns]
            dataframe(inventory_df[available_cols], hide_index=True)

            st.subheader("Technology Relationships")
            if not relationships_df.empty:
                dataframe(relationships_df, hide_index=True)
            else:
                st.info("No technology relationships configured yet.")

        render_certification_evidence()

    render_page(
        title="Technology Inventory",
        description="CIO view of portfolio ownership, vendor distribution, critical technology coverage, and data quality.",
        breadcrumbs=["Home", "CIO", "Technology Inventory"],
        content=render_inventory_content,
        status=_percent_status(data_quality_score),
    )


if __name__ == "__main__":
    main()
