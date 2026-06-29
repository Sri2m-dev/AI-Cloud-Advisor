import pandas as pd
import plotly.express as px
import streamlit as st

from components.cards import (
    render_approval_card,
    render_health_card,
    render_insight_card,
    render_kpi_card,
    render_risk_card,
)
from components.layout import render_empty_state, render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.supabase_client import supabase
from shared.auth import require_role
from shared.session import init_session


def fetch_rows(table_name, limit=None):
    try:
        query = supabase.table(table_name).select("*")
        if limit:
            query = query.limit(limit)
        response = query.execute()
        return response.data or []
    except Exception:
        return []


def fetch_one(table_name):
    rows = fetch_rows(table_name, limit=1)
    return rows[0] if rows else {}


def spend_value(row, new_key, old_key):
    return float(row.get(new_key, row.get(old_key, 0)) or 0)


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value, fallback=0):
    try:
        return int(float(value if value is not None else fallback))
    except (TypeError, ValueError):
        return fallback


def format_compact_currency(value):
    value = safe_float(value)
    if abs(value) >= 1000:
        return f"${value / 1000:,.1f}K".replace(".0K", "K")
    return f"${value:,.0f}"


st.set_page_config(
    page_title="Enterprise Business Health",
    layout="wide",
)

init_session()

require_role([
    "executive",
    "technical",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Executive Dashboard"],
)

summary = fetch_one("mart_executive_summary")
spend_breakdown = fetch_one("mart_enterprise_spend_v2")
recommendations = fetch_rows("recommendations")

cloud_cost = spend_value(spend_breakdown, "cloud_spend", "cloud_cost")
saas_cost = spend_value(spend_breakdown, "saas_spend", "saas_cost")
msp_cost = spend_value(spend_breakdown, "msp_spend", "msp_cost")
license_cost = spend_value(spend_breakdown, "license_spend", "license_cost")

total_spend = safe_float(summary.get("total_spend"))
if not total_spend:
    total_spend = cloud_cost + saas_cost + msp_cost + license_cost

potential_savings = safe_float(
    summary.get("optimization_savings")
    or summary.get("optimization")
    or summary.get("potential_savings")
)

savings_realized = safe_float(
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

governance_score = safe_int(summary.get("governance_score"), 0)
critical_risks = safe_int(summary.get("critical_risks"), safe_int(summary.get("anomaly_count"), 0))
pending_approvals = safe_int(summary.get("pending_approvals"), 0)
budget_health = safe_int(summary.get("budget_adherence"), 85)
optimization_health = safe_int(summary.get("optimization_adoption"), 85)
risk_posture = safe_int(summary.get("risk_posture"), max(0, 100 - critical_risks * 5))

opportunities_found = safe_int(
    summary.get("optimization_count")
    or summary.get("recommendation_count")
    or summary.get("opportunities_found"),
    len(recommendations),
)


def inject_executive_dashboard_styles():
    st.markdown(
        """
        <style>
        [data-testid="stVerticalBlockBorderWrapper"] {
            min-height: 164px;
        }
        [data-testid="stMetric"] {
            min-height: 140px;
        }
        [data-testid="stDataFrame"] {
            border-radius: 8px;
            overflow: hidden;
        }
        .js-plotly-plot {
            border: 1px solid var(--nexora-border);
            border-radius: 8px;
            overflow: hidden;
            background: var(--nexora-surface);
        }
        @media (max-width: 900px) {
            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard_content():
    inject_executive_dashboard_styles()

    render_section(
        "Executive KPI Summary",
        "Enterprise spend, optimization value, governance health, executive actions, and active risk.",
        divider=False,
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        render_kpi_card(
            "Enterprise Spend",
            format_compact_currency(total_spend),
            subtitle="Cloud + SaaS + MSP + Licenses",
            icon="cost",
            status="healthy" if budget_health >= 80 else "warning",
        )
    with col2:
        render_kpi_card(
            "Optimization Potential",
            format_compact_currency(potential_savings),
            subtitle="Identified optimization value",
            icon="cost",
            status="warning" if potential_savings else "healthy",
        )
    with col3:
        render_health_card(
            "Governance Health",
            f"{governance_score}%",
            subtitle="Policy and ownership health",
            status="healthy" if governance_score >= 75 else "warning",
        )
    with col4:
        render_approval_card(
            "Executive Actions",
            pending_approvals,
            subtitle="Awaiting executive decision",
            status="watch" if pending_approvals else "healthy",
        )
    with col5:
        render_risk_card(
            "Critical Risks",
            critical_risks,
            subtitle="Active risks requiring review",
            status="critical" if critical_risks else "healthy",
        )

    render_section(
        "Executive Attention Required",
        "Prioritized signals that may require executive review.",
        divider=True,
    )

    attention_cols = st.columns(5)
    with attention_cols[0]:
        render_health_card(
            "Spend Threshold",
            "On Track" if budget_health >= 80 else "Review",
            subtitle="Spend within approved threshold" if budget_health >= 80 else "Spend requires budget threshold review",
            status="healthy" if budget_health >= 80 else "warning",
        )
    with attention_cols[1]:
        render_insight_card(
            "Optimization",
            format_compact_currency(potential_savings) if potential_savings else "Clear",
            subtitle="Optimization opportunity identified" if potential_savings else "No material opportunity identified",
            status="warning" if potential_savings else "healthy",
            icon="cost",
        )
    with attention_cols[2]:
        render_approval_card(
            "Approvals",
            pending_approvals,
            subtitle="No approvals awaiting action" if pending_approvals == 0 else "Approvals awaiting executive action",
            status="healthy" if pending_approvals == 0 else "watch",
        )
    with attention_cols[3]:
        render_risk_card(
            "Critical Review",
            critical_risks,
            subtitle="No critical risks require review" if critical_risks == 0 else "Critical risks require review",
            status="healthy" if critical_risks == 0 else "critical",
        )
    with attention_cols[4]:
        render_health_card(
            "Governance",
            f"{governance_score}%",
            subtitle="Governance health remains stable" if governance_score >= 75 else "Governance health requires review",
            status="healthy" if governance_score >= 75 else "warning",
        )

    render_section(
        "Enterprise Investment Allocation",
        "Current allocation across cloud, SaaS, managed services, and licenses.",
        divider=True,
    )

    allocation_df = pd.DataFrame([
        {"Category": "Cloud", "Spend": cloud_cost},
        {"Category": "SaaS", "Spend": saas_cost},
        {"Category": "MSP", "Spend": msp_cost},
        {"Category": "Licenses", "Spend": license_cost},
    ])

    allocation_display_df = allocation_df.copy()
    allocation_display_df["Spend"] = allocation_display_df["Spend"].apply(format_compact_currency)

    alloc_left, alloc_right = st.columns([1, 2])

    with alloc_left:
        st.dataframe(
            allocation_display_df,
            use_container_width=True,
            hide_index=True,
        )

    with alloc_right:
        if allocation_df["Spend"].sum() > 0:
            fig = px.pie(
                allocation_df,
                names="Category",
                values="Spend",
                title="Enterprise Spend Allocation",
                hole=0.4,
                color_discrete_sequence=["#2563EB", "#16A34A", "#F59E0B", "#7C3AED"],
            )
            fig.update_layout(
                margin=dict(l=16, r=16, t=48, b=16),
                legend_title_text="Category",
                font=dict(size=13),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            render_empty_state(
                "No spend allocation available",
                "Cloud, SaaS, managed services, and license spend will appear once source data is loaded.",
            )

    render_section(
        "Governance & Risk",
        "Executive risk posture, pending decisions, and governance score.",
        divider=True,
    )

    risk_cols = st.columns(3)
    with risk_cols[0]:
        render_risk_card(
            "Critical Risks",
            f"{critical_risks:,}",
            subtitle="Open critical risks",
            status="critical" if critical_risks else "healthy",
        )
    with risk_cols[1]:
        render_approval_card(
            "Pending Actions",
            f"{pending_approvals:,}",
            subtitle="Executive approvals and decisions",
            status="watch" if pending_approvals else "healthy",
        )
    with risk_cols[2]:
        render_health_card(
            "Governance Health",
            f"{governance_score}%",
            subtitle="Policy and ownership",
            status="healthy" if governance_score >= 75 else "warning",
        )

    render_section(
        "Savings / Optimization",
        "Optimization opportunity, realized savings, and adoption health.",
        divider=True,
    )

    optimization_cols = st.columns(4)
    with optimization_cols[0]:
        render_insight_card(
            "Opportunities Found",
            f"{opportunities_found:,}",
            subtitle="Identified opportunities",
            icon="ai",
            status="info",
        )
    with optimization_cols[1]:
        render_kpi_card(
            "Potential Savings",
            format_compact_currency(potential_savings),
            subtitle="Optimization value",
            icon="cost",
            status="warning" if potential_savings else "healthy",
        )
    with optimization_cols[2]:
        render_kpi_card(
            "Savings Realized",
            format_compact_currency(savings_realized),
            subtitle="Implemented savings",
            icon="cost",
            status="healthy",
        )
    with optimization_cols[3]:
        render_health_card(
            "Optimization Health",
            f"{optimization_health}%",
            subtitle="Savings program",
            status="healthy" if optimization_health >= 80 else "warning",
        )

    render_section(
        "Executive Narrative",
        "Business health index and leadership summary.",
        divider=True,
    )

    health_cols = st.columns(4)

    with health_cols[0]:
        render_health_card("Governance", f"{governance_score}%", subtitle="Policy and ownership", status="healthy" if governance_score >= 75 else "warning")
    with health_cols[1]:
        render_health_card("Budget Health", f"{budget_health}%", subtitle="Spend control", status="healthy" if budget_health >= 80 else "warning")
    with health_cols[2]:
        render_health_card("Optimization", f"{optimization_health}%", subtitle="Savings program", status="healthy" if optimization_health >= 80 else "warning")
    with health_cols[3]:
        render_health_card("Risk Posture", f"{risk_posture}%", subtitle="Operational exposure", status="healthy" if risk_posture >= 80 else "warning")

    narrative = (
        f"Enterprise technology spend is {format_compact_currency(total_spend)} with "
        f"{format_compact_currency(potential_savings)} in identified optimization potential. "
        f"Governance health is {governance_score}% and {critical_risks} critical risks are currently flagged."
    )
    render_insight_card(
        "Executive Summary",
        "Enterprise Business Health",
        description=narrative,
        icon="executive",
        status="info",
    )


render_page(
    title="Enterprise Business Health",
    description="Executive overview of enterprise spend, risk, governance, and optimization opportunities.",
    breadcrumbs=["Executive Overview", "Executive", "Executive Dashboard"],
    content=render_dashboard_content,
)
