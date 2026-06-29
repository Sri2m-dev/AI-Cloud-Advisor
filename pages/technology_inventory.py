import streamlit as st
import pandas as pd
import plotly.express as px

from components.cards import (
    render_health_card,
    render_insight_card,
    render_kpi_card,
    render_metric_card,
    render_risk_card,
)
from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from auth.guards import require_login
from auth.role_constants import normalize_role
from services.supabase_client import supabase


st.set_page_config(page_title="Technology Portfolio", layout="wide")


def fetch_table(table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data or []
    except Exception:
        return []


def _money(value) -> str:
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
        return int(
            values.isin(["critical", "high", "tier 0", "tier 1", "true", "yes", "1"]).sum()
        )

    return 0


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

    inventory_df = pd.DataFrame(fetch_table("technology_inventory"))
    vendor_spend_df = pd.DataFrame(fetch_table("vw_vendor_spend"))
    relationships_df = pd.DataFrame(fetch_table("technology_relationships"))

    if not inventory_df.empty and "annual_cost" in inventory_df.columns:
        inventory_df["annual_cost"] = pd.to_numeric(
            inventory_df["annual_cost"],
            errors="coerce",
        ).fillna(0)

    total_technologies = len(inventory_df)
    annual_spend = inventory_df["annual_cost"].sum() if not inventory_df.empty else 0

    assigned_departments = inventory_df["owner_department"].notna().sum() if "owner_department" in inventory_df else 0
    assigned_business_owners = inventory_df["business_owner"].notna().sum() if "business_owner" in inventory_df else 0
    assigned_technical_owners = inventory_df["technical_owner"].notna().sum() if "technical_owner" in inventory_df else 0

    ownership_coverage = round((assigned_departments / total_technologies) * 100, 1) if total_technologies else 0
    business_owner_coverage = round((assigned_business_owners / total_technologies) * 100, 1) if total_technologies else 0
    technical_owner_coverage = round((assigned_technical_owners / total_technologies) * 100, 1) if total_technologies else 0
    data_quality_score = round(
        (ownership_coverage + business_owner_coverage + technical_owner_coverage) / 3,
        1,
    ) if total_technologies else 0

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

    if not inventory_df.empty and "owner_department" in inventory_df.columns:
        dept_summary = (
            inventory_df.groupby("owner_department")["annual_cost"]
            .sum()
            .sort_values(ascending=False)
        )
        if not dept_summary.empty:
            top_department = dept_summary.index[0]
            top_department_spend = dept_summary.iloc[0]

    def render_inventory_content():
        if inventory_df.empty:
            st.info("No technology portfolio data available.")
            return

        render_section(
            "CIO Inventory Summary",
            "Unified view of Cloud, SaaS, MSP, vendors, departments, and technology relationships.",
            divider=False,
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
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No technology type distribution data available.")

        with landscape_cols[1]:
            if not vendor_spend_df.empty:
                fig = px.bar(vendor_spend_df, x="vendor_name", y="annual_spend", text_auto=True)
                st.plotly_chart(fig, width="stretch")
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

        render_section(
            "Executive Inventory Insight",
            "CIO narrative generated from current inventory, ownership, and relationship signals.",
        )
        render_insight_card(
            "Technology Inventory Narrative",
            description=(
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
            status=_percent_status(data_quality_score),
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
                st.dataframe(ownership_df, use_container_width=True)
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

                st.dataframe(department_allocation_df, use_container_width=True)
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
            st.dataframe(inventory_df[available_cols], width="stretch", hide_index=True)

            st.subheader("Technology Relationships")
            if not relationships_df.empty:
                st.dataframe(relationships_df, width="stretch", hide_index=True)
            else:
                st.info("No technology relationships configured yet.")

    render_page(
        title="Technology Inventory",
        description="CIO view of portfolio ownership, vendor distribution, critical technology coverage, and data quality.",
        breadcrumbs=["Home", "CIO", "Technology Inventory"],
        content=render_inventory_content,
        status=_percent_status(data_quality_score),
    )


if __name__ == "__main__":
    main()
