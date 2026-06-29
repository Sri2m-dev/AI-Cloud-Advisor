import pandas as pd
import plotly.express as px
import streamlit as st

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
from services.technology_health_service import TechnologyHealthService
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page


RISK_COLORS = {
    "Critical": "#b91c1c",
    "High": "#f97316",
    "Medium": "#facc15",
    "Low": "#2563eb",
    "Healthy": "#16a34a",
}


def _money(value) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def _risk_row_style(row):
    risk = str(row.get("Risk") or "")
    color = RISK_COLORS.get(risk)
    if not color:
        return [""] * len(row)

    return [
        f"border-left: 4px solid {color};"
        if column == "Risk"
        else ""
        for column in row.index
    ]


def _show_health_matrix(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No technology health matrix data is currently available.")
        return

    styled_df = (
        df.style
        .apply(_risk_row_style, axis=1)
        .map(
            lambda value: f"background-color: {RISK_COLORS.get(str(value), '#ffffff')}; color: #ffffff; font-weight: 700;"
            if str(value) in {"Critical", "High", "Low", "Healthy"}
            else (
                "background-color: #facc15; color: #111827; font-weight: 700;"
                if str(value) == "Medium"
                else ""
            ),
            subset=["Risk"],
        )
    )

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
    )


def _health_status(score: float) -> str:
    if score >= 90:
        return "healthy"
    if score >= 75:
        return "warning"
    return "critical"


def _risk_status(count: int) -> str:
    return "critical" if count else "healthy"


configure_page(
    page_title="Technology Health & Risk",
    page_icon="H",
)

init_session()

require_role([
    "executive",
    "cio",
    "super_admin",
])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Technology Health & Risk"],
)

kpis = TechnologyHealthService.get_kpis()
health_matrix = TechnologyHealthService.health_matrix_dataframe()
risk_distribution = TechnologyHealthService.risk_distribution_dataframe()
renewal_exposure = TechnologyHealthService.renewal_exposure_dataframe()
license_waste = TechnologyHealthService.license_waste_dataframe()
dependency_edges = TechnologyHealthService.dependency_edges_dataframe()



def render_technology_health_content() -> None:
    at_risk_technologies = (
        kpis["critical_technologies"]
        + kpis["high_risk_technologies"]
        + kpis["medium_risk_technologies"]
    )
    healthy_technologies = max(kpis["total_technologies"] - at_risk_technologies, 0)

    render_section(
        "CIO Technology Health Summary",
        "Portfolio-level health, risk concentration, renewal exposure, and license waste.",
        divider=False,
    )
    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_kpi_card(
            "Total Technologies",
            f"{kpis['total_technologies']:,}",
            "Tracked applications, platforms, and services",
            icon="technology",
            status="info",
        )
    with summary_cols[1]:
        render_health_card(
            "Healthy Technologies",
            f"{healthy_technologies:,}",
            "Technologies outside medium, high, and critical tiers",
            icon="success",
            status="healthy" if healthy_technologies else "warning",
        )
    with summary_cols[2]:
        render_risk_card(
            "At-Risk Technologies",
            f"{at_risk_technologies:,}",
            "Medium, high, and critical risk technologies",
            icon="risk",
            status="warning" if at_risk_technologies else "healthy",
        )
    with summary_cols[3]:
        render_risk_card(
            "Critical Technologies",
            f"{kpis['critical_technologies']:,}",
            "Technologies below critical health threshold",
            icon="alert",
            status=_risk_status(kpis["critical_technologies"]),
        )

    health_cols = st.columns(3)
    with health_cols[0]:
        render_metric_card(
            "Renewal Exposure",
            _money(kpis["renewal_exposure"]),
            "Annual cost tied to renewal risk records",
            icon="cost",
            status="warning" if kpis["renewal_exposure"] else "healthy",
        )
    with health_cols[1]:
        render_metric_card(
            "License Waste Exposure",
            _money(kpis["license_waste_exposure"]),
            "Estimated inactive SaaS license waste",
            icon="savings",
            status="warning" if kpis["license_waste_exposure"] else "healthy",
        )
    with health_cols[2]:
        render_health_card(
            "Average Health Score",
            f"{kpis['average_health']:,.1f}",
            "Composite score based on cost, dependencies, renewals, and inactive licenses",
            icon="health",
            status=_health_status(kpis["average_health"]),
        )

    render_section(
        "Portfolio Health",
        "Distribution of technology risk tiers across the CIO portfolio.",
    )
    if not risk_distribution.empty:
        fig = px.bar(
            risk_distribution,
            x="risk",
            y="count",
            title="Technology Risk Distribution",
            color="risk",
            color_discrete_map=RISK_COLORS,
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
    else:
        st.info("No technology risk distribution is currently available.")

    render_section(
        "Renewal & License Exposure",
        "Commercial exposure from renewal risk records and inactive SaaS utilization.",
    )
    exposure_cols = st.columns(2)
    with exposure_cols[0]:
        render_risk_card(
            "Renewal Exposure",
            _money(kpis["renewal_exposure"]),
            f"{len(renewal_exposure):,} renewal records in scope",
            description="Upcoming renewals can create cost, negotiation, and continuity risk.",
            icon="calendar",
            status="warning" if not renewal_exposure.empty else "healthy",
        )
    with exposure_cols[1]:
        render_risk_card(
            "License Waste Exposure",
            _money(kpis["license_waste_exposure"]),
            f"{len(license_waste):,} inactive license records in scope",
            description="Inactive licenses highlight savings and compliance cleanup opportunities.",
            icon="savings",
            status="warning" if not license_waste.empty else "healthy",
        )

    render_section(
        "Dependency Risk",
        "Relationship concentration that can amplify technology failure or change impact.",
    )
    dependency_cols = st.columns(3)
    with dependency_cols[0]:
        render_risk_card(
            "Tracked Dependencies",
            f"{kpis['dependency_edges']:,}",
            "Source-to-target technology relationships",
            icon="graph",
            status="info" if kpis["dependency_edges"] else "warning",
        )
    with dependency_cols[1]:
        render_risk_card(
            "High Risk Technologies",
            f"{kpis['high_risk_technologies']:,}",
            "Technologies in the high risk tier",
            icon="risk",
            status=_risk_status(kpis["high_risk_technologies"]),
        )
    with dependency_cols[2]:
        render_metric_card(
            "Vendors",
            f"{kpis['vendor_count']:,}",
            "Distinct technology vendors in scope",
            icon="enterprise",
            status="info",
        )

    render_section(
        "Critical Technology Matrix",
        "Executive view of the technologies most likely to need CIO attention.",
    )
    matrix_cols = st.columns(3)
    with matrix_cols[0]:
        render_risk_card(
            "Critical Tier",
            f"{kpis['critical_technologies']:,}",
            "Immediate remediation or decision attention",
            icon="alert",
            status=_risk_status(kpis["critical_technologies"]),
        )
    with matrix_cols[1]:
        render_risk_card(
            "High Tier",
            f"{kpis['high_risk_technologies']:,}",
            "Requires active ownership and mitigation tracking",
            icon="risk",
            status=_risk_status(kpis["high_risk_technologies"]),
        )
    with matrix_cols[2]:
        render_risk_card(
            "Medium Tier",
            f"{kpis['medium_risk_technologies']:,}",
            "Monitor for renewal, waste, and dependency movement",
            icon="governance",
            status="warning" if kpis["medium_risk_technologies"] else "healthy",
        )

    render_section(
        "Executive Technology Insight",
        "CIO narrative generated from the current technology health signals.",
    )
    render_insight_card(
        "Technology Health Narrative",
        description=(
            f"The enterprise technology estate contains {kpis['total_technologies']} tracked technologies "
            f"with an average health score of {kpis['average_health']:,.1f}. "
            f"{kpis['critical_technologies']} critical, {kpis['high_risk_technologies']} high risk, "
            f"and {kpis['medium_risk_technologies']} medium risk technologies require attention based on cost, "
            f"renewal exposure, inactive license exposure, and dependency concentration. "
            f"Renewal exposure totals {_money(kpis['renewal_exposure'])}, while license waste exposure "
            f"is estimated at {_money(kpis['license_waste_exposure'])}. "
            f"The dependency explorer is tracking {kpis['dependency_edges']} source-to-target relationships "
            f"for future graph-based technology health analysis."
        ),
        status=_health_status(kpis["average_health"]),
    )

    render_section(
        "Detailed Evidence / Drilldown",
        "Source tables for matrix, renewal, license, and dependency review.",
    )
    with st.expander("Detailed Evidence / Drilldown"):
        st.subheader("Technology Health Matrix")
        _show_health_matrix(health_matrix)

        st.subheader("Renewal Exposure")
        _show_dataframe(
            renewal_exposure,
            "No renewal exposure data is currently available.",
        )

        st.subheader("License Waste Exposure")
        _show_dataframe(
            license_waste,
            "No license waste exposure data is currently available.",
        )

        st.subheader("Dependency Explorer")
        _show_dataframe(
            dependency_edges,
            "No technology dependency relationships are currently available.",
        )


render_page(
    title="Technology Health",
    description="CIO view of enterprise technology health, renewal exposure, license waste, and dependency risk.",
    breadcrumbs=["Home", "CIO", "Technology Health"],
    content=render_technology_health_content,
    status=_health_status(kpis["average_health"]),
)
