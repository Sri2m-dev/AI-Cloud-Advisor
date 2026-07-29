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
from services.executive_dashboard_certification_service import (
    ExecutiveDashboardCertificationService,
)
from shared.auth import require_role
from shared.session import init_session
from auth.authenticated_tenant import AuthenticatedTenantError
from services.enterprise_spend_composition import (
    authenticated_tenant_context,
    enterprise_spend_service,
)


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

try:
    tenant_context = authenticated_tenant_context(st.session_state)
    certification = ExecutiveDashboardCertificationService.get_dashboard(
        tenant_context,
        enterprise_spend_service(),
    )
except AuthenticatedTenantError as exc:
    st.error(f"Financial data unavailable: {exc}")
    st.stop()

role = st.session_state.get("role", "Unknown")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Executive Dashboard"],
)
legacy_metrics = certification["legacy_metrics"]
reconciliation_cards = certification["reconciliation_cards"]
financial_model = certification["financial_model"]
reconciliation = certification["reconciliation"]
evidence = certification["evidence"]
format_compact_currency = ExecutiveDashboardCertificationService.format_compact_currency

cloud_cost = legacy_metrics["cloud_cost"]
saas_cost = legacy_metrics["saas_cost"]
msp_cost = legacy_metrics["msp_cost"]
license_cost = legacy_metrics["license_cost"]
total_spend = legacy_metrics["total_spend"]
potential_savings = legacy_metrics["potential_savings"]
savings_realized = legacy_metrics["savings_realized"]
governance_score = legacy_metrics["governance_score"]
critical_risks = legacy_metrics["critical_risks"]
pending_approvals = legacy_metrics["pending_approvals"]
budget_health = legacy_metrics["budget_health"]
optimization_health = legacy_metrics["optimization_health"]
risk_posture = legacy_metrics["risk_posture"]
opportunities_found = legacy_metrics["opportunities_found"]


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
    posture = certification["financial_posture"]
    if posture.quarantined_spend:
        st.warning(
            f"Cloud spend of {posture.quarantined_spend:,.2f} {posture.currency} "
            "has been ingested and reconciled. The spend remains unclassified "
            f"because {posture.unknown_account_count} cloud accounts require "
            "tenant ownership approval."
        )

    render_section(
        "Executive Summary",
        "Board-level summary of enterprise technology posture, financial reconciliation, and recommended attention.",
        divider=False,
    )

    render_insight_card(
        "Executive Summary",
        "Enterprise Business Health",
        description=certification["executive_summary"],
        icon="executive",
        status="warning" if reconciliation.get("status") == "Variance Detected" else "info",
    )

    render_section(
        "Data Reconciliation Status",
        "Canonical financial model status for executive reporting and allocation confidence.",
        divider=True,
    )

    reconciliation_cols = st.columns(4)
    with reconciliation_cols[0]:
        render_insight_card(
            "Reconciliation Status",
            reconciliation.get("status", "Unknown"),
            subtitle="Enterprise Financial Model",
            icon="governance",
            status="warning" if reconciliation.get("status") == "Variance Detected" else "healthy",
        )
    with reconciliation_cols[1]:
        render_health_card(
            "Allocation Coverage",
            reconciliation_cards["allocation_coverage_display"],
            subtitle="Mapped to allocation model",
            status="healthy" if reconciliation_cards["allocation_coverage"] >= 90 else "warning",
        )
    with reconciliation_cols[2]:
        render_kpi_card(
            "Allocated Spend",
            format_compact_currency(financial_model.get("allocated_spend")),
            subtitle="Canonical model spend",
            icon="cost",
            status="healthy",
        )
    with reconciliation_cols[3]:
        render_kpi_card(
            "Unallocated Spend",
            format_compact_currency(financial_model.get("unallocated_spend")),
            subtitle="Requires mapping review",
            icon="risk",
            status="warning" if reconciliation_cards["unallocated_spend"] else "healthy",
        )

    render_section(
        "Executive KPI Summary",
        "Enterprise spend, optimization value, governance health, executive actions, and active risk.",
        divider=True,
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
        "Business Health Index",
        "Leadership view of governance, budget, optimization, and risk posture.",
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
        "Leadership Interpretation",
        "Enterprise Business Health",
        description=narrative,
        icon="executive",
        status="info",
    )

    render_section(
        "Evidence",
        "Source data, coverage, financial reconciliation, AI interpretation, and raw evidence supporting this dashboard.",
        divider=True,
    )

    evidence_tabs = st.tabs([
        "Source Data",
        "Data Coverage",
        "Financial Reconciliation",
        "AI Interpretation",
        "Raw Evidence",
    ])

    with evidence_tabs[0]:
        st.dataframe(
            pd.DataFrame(evidence["source_data"]),
            use_container_width=True,
            hide_index=True,
        )

    with evidence_tabs[1]:
        st.dataframe(
            pd.DataFrame(evidence["data_coverage"]),
            use_container_width=True,
            hide_index=True,
        )

    with evidence_tabs[2]:
        st.dataframe(
            pd.DataFrame(evidence["financial_reconciliation"]),
            use_container_width=True,
            hide_index=True,
        )

    with evidence_tabs[3]:
        st.write(evidence["ai_interpretation"])

    with evidence_tabs[4]:
        raw_financial = evidence["raw_evidence"].get("Financial Model", [])
        raw_variance = evidence["raw_evidence"].get("Variance Layers", [])
        st.caption("Financial Model")
        st.dataframe(
            pd.DataFrame(raw_financial),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Variance Layers")
        if raw_variance:
            st.dataframe(
                pd.DataFrame(raw_variance),
                use_container_width=True,
                hide_index=True,
            )
        else:
            render_empty_state(
                "No variance layers detected",
                "The Enterprise Financial Model did not report layer-level variance for this run.",
            )


render_page(
    title="Enterprise Business Health",
    description="Executive overview of enterprise spend, risk, governance, and optimization opportunities.",
    breadcrumbs=["Executive Overview", "Executive", "Executive Dashboard"],
    content=render_dashboard_content,
)
