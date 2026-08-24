from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
import plotly.express as px
import streamlit as st

from components.executive_foundation import (
    ComponentState,
    InteractionKind,
    InteractionOption,
    InteractionView,
    KpiKind,
    KpiView,
    NarrativeKind,
    NarrativeView,
    executive_columns,
    render_executive_shell,
    render_interaction,
    render_kpi_card,
    render_narrative,
    render_page_header,
    render_section_header,
)

if TYPE_CHECKING:
    from services.executive_workspace_composition_service import WorkspaceSnapshot


@dataclass(frozen=True)
class SurfaceLink:
    label: str
    page: str
    purpose: str


@dataclass(frozen=True)
class WorkspaceDefinition:
    key: str
    title: str
    question: str
    roles: tuple[str, ...]
    surfaces: tuple[SurfaceLink, ...]


WORKSPACES = {
    "command": WorkspaceDefinition(
        "command",
        "Executive Command Center",
        "What changed, why does it matter, and what requires attention?",
        ("super_admin", "client_admin", "executive", "cio", "finance", "operations", "auditor"),
        (
            SurfaceLink(
                "Enterprise Intelligence",
                "pages/enterprise_intelligence.py",
                "Governed enterprise context",
            ),
            SurfaceLink(
                "Enterprise Search", "pages/enterprise_search.py", "Canonical answer and evidence"
            ),
            SurfaceLink(
                "Decision Intelligence",
                "pages/decision_intelligence.py",
                "Authoritative decision queue",
            ),
            SurfaceLink(
                "Scenario Intelligence",
                "pages/scenario_intelligence.py",
                "Explicit alternatives and assumptions",
            ),
            SurfaceLink(
                "Enterprise AI",
                "pages/enterprise_ai_copilot.py",
                "Ask, explain, compare, brief, and simulate",
            ),
        ),
    ),
    "ceo": WorkspaceDefinition(
        "ceo",
        "Today's Executive Brief",
        "What changed, why does it matter, and what requires leadership action?",
        ("super_admin", "executive"),
        (
            SurfaceLink(
                "Leadership Dashboard",
                "pages/leadership_dashboard.py",
                "Strategic summary and enterprise KPIs",
            ),
            SurfaceLink(
                "Business Services", "pages/business_services.py", "Outcome and service health"
            ),
            SurfaceLink("Risk & Governance", "pages/risk_governance.py", "Top governed risks"),
            SurfaceLink(
                "Approvals", "pages/approval_center.py", "Human decisions requiring authority"
            ),
            SurfaceLink("Reports", "pages/reports.py", "Board snapshot and governed reports"),
        ),
    ),
    "cio": WorkspaceDefinition(
        "cio",
        "CIO Workspace",
        "Is the technology estate resilient, governed, affordable, and aligned?",
        ("super_admin", "cio"),
        (
            SurfaceLink(
                "Technology Health", "pages/technology_health.py", "Certified technology health"
            ),
            SurfaceLink(
                "Cloud Estate", "pages/cloud_account_registry.py", "Canonical cloud accounts"
            ),
            SurfaceLink(
                "Application Estate", "pages/application_inventory.py", "Application portfolio"
            ),
            SurfaceLink(
                "Architecture", "pages/technology_knowledge_graph.py", "Governed architecture graph"
            ),
            SurfaceLink(
                "Impact Analysis", "pages/impact_analysis.py", "Dependencies and blast radius"
            ),
            SurfaceLink("Cloud Strategy", "pages/cloud_strategy.py", "Modernization context"),
        ),
    ),
    "cfo": WorkspaceDefinition(
        "cfo",
        "CFO Workspace",
        "Are we financially controlled, on plan, and realizing approved value?",
        ("super_admin", "finance", "executive"),
        (
            SurfaceLink(
                "Enterprise Spend", "pages/enterprise_spend.py", "Reconciled enterprise spend"
            ),
            SurfaceLink("Forecast", "pages/financial_forecasting.py", "Certified forecast outputs"),
            SurfaceLink(
                "Cost Intelligence", "pages/cost_intelligence.py", "Budget and variance drivers"
            ),
            SurfaceLink("Vendor Spend", "pages/technology_spend.py", "Vendor exposure"),
            SurfaceLink(
                "Chargeback / Showback", "pages/tbm_chargeback.py", "Allocation and accountability"
            ),
            SurfaceLink(
                "Savings Governance",
                "pages/savings_governance.py",
                "Potential-to-realized value states",
            ),
        ),
    ),
    "architect": WorkspaceDefinition(
        "architect",
        "Enterprise Architect Workspace",
        "Where is the operating model fragile, redundant, or misaligned?",
        ("super_admin", "client_admin", "cio"),
        (
            SurfaceLink(
                "Business Services", "pages/business_services.py", "Capability and service context"
            ),
            SurfaceLink(
                "Knowledge Graph", "pages/enterprise_graph.py", "Canonical enterprise relationships"
            ),
            SurfaceLink(
                "Dependencies", "pages/dependency_analysis.py", "Governed dependency paths"
            ),
            SurfaceLink("Impact Analysis", "pages/impact_analysis.py", "Change impact"),
            SurfaceLink(
                "Enterprise Registry",
                "pages/enterprise_registry.py",
                "Canonical entities and ownership",
            ),
            SurfaceLink("Governance", "pages/governance_authorization.py", "Policy and authority"),
        ),
    ),
    "operations": WorkspaceDefinition(
        "operations",
        "Operations Command Center",
        "What is changing now, what can disrupt service, and who owns the response?",
        ("super_admin", "client_admin", "technical", "operations"),
        (
            SurfaceLink(
                "Operations Workspace", "pages/operations_workspace.py", "Operational posture"
            ),
            SurfaceLink("Incident Overview", "pages/incident_timeline.py", "Incident chronology"),
            SurfaceLink(
                "Observability", "pages/enterprise_observability.py", "Availability and telemetry"
            ),
            SurfaceLink(
                "Capacity", "pages/capacity_planning.py", "Certified capacity intelligence"
            ),
            SurfaceLink("Automation", "pages/automation_center.py", "Governed automation pathways"),
            SurfaceLink("Execution", "pages/execution_center.py", "Authorized execution only"),
        ),
    ),
    "finops": WorkspaceDefinition(
        "finops",
        "FinOps Workspace",
        "What drove cost, who owns it, and where is verified value?",
        ("super_admin", "finance", "cio"),
        (
            SurfaceLink("Savings", "pages/savings_governance.py", "Governed value pipeline"),
            SurfaceLink(
                "Coverage", "pages/enterprise_spend.py", "Allocation and reconciliation coverage"
            ),
            SurfaceLink("Waste", "pages/optimization_center.py", "Certified optimization findings"),
            SurfaceLink(
                "Recommendations",
                "pages/decision_intelligence.py",
                "Preserved recommendation order",
            ),
            SurfaceLink("Forecast", "pages/financial_forecasting.py", "Versioned forecast"),
            SurfaceLink(
                "Commitments", "pages/cost_intelligence.py", "RI/SP and commitment context"
            ),
        ),
    ),
    "board": WorkspaceDefinition(
        "board",
        "Board Intelligence",
        "What governed story is ready for Board review and sign-off?",
        ("super_admin", "executive", "auditor"),
        (
            SurfaceLink("Board Pack", "pages/reports.py", "Versioned report artifact"),
            SurfaceLink(
                "Executive Brief", "pages/leadership_dashboard.py", "Checkpointed executive summary"
            ),
            SurfaceLink("Quarterly Evidence", "pages/audit_timeline.py", "Immutable chronology"),
            SurfaceLink(
                "Review & Sign-off", "pages/approval_center.py", "Human review and approval"
            ),
        ),
    ),
}


def _chart_layout(figure, title: str, y_title: str = ""):
    figure.update_layout(
        title={"text": title, "font": {"size": 18}},
        margin={"l": 24, "r": 16, "t": 54, "b": 24},
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
        yaxis_title=y_title,
        xaxis_title="",
    )
    return figure


def _render_decision_analytics(snapshot: WorkspaceSnapshot) -> None:
    analytics = snapshot.analytics or {}
    required = {
        "budget_vs_actual",
        "vendor_concentration",
        "business_service_health",
        "technology_portfolio",
        "savings_waterfall",
        "recommendation_pipeline",
    }
    if not required.issubset(analytics):
        return

    render_section_header(
        "Executive visual intelligence",
        "Each visual answers a named decision question using supplied demonstration evidence.",
    )
    left, right = st.columns(2)

    budget = pd.DataFrame(analytics["budget_vs_actual"])
    with left:
        st.caption("Are technology costs on plan?")
        figure = px.bar(
            budget,
            x="quarter",
            y=["budget", "actual"],
            barmode="group",
            color_discrete_sequence=["#94A3B8", "#2563EB"],
        )
        st.plotly_chart(
            _chart_layout(figure, "Budget vs actual", "Quarterly spend ($)"),
            use_container_width=True,
        )
        latest = budget.iloc[-1]
        variance = latest["actual"] - latest["budget"]
        st.markdown(
            f"**What this means:** {latest['quarter']} is "
            f"${abs(variance) / 1_000_000:.1f}M "
            f"{'above' if variance > 0 else 'below'} plan."
        )

    vendors = pd.DataFrame(analytics["vendor_concentration"])
    with right:
        st.caption("Where is commercial concentration highest?")
        figure = px.bar(
            vendors.sort_values("annual_spend"),
            x="annual_spend",
            y="vendor",
            orientation="h",
            color="share",
            color_continuous_scale=["#BFDBFE", "#1D4ED8"],
        )
        st.plotly_chart(
            _chart_layout(figure, "Vendor concentration", "Annual spend ($)"),
            use_container_width=True,
        )
        leading_vendor = vendors.sort_values("share", ascending=False).iloc[0]
        st.markdown(
            f"**What this means:** {leading_vendor['vendor']} represents "
            f"{leading_vendor['share']:.0f}% of measured vendor spend."
        )

    services = pd.DataFrame(analytics["business_service_health"])
    with left:
        st.caption("Which business services need intervention?")
        figure = px.bar(
            services.sort_values("health"),
            x="health",
            y="service",
            orientation="h",
            color="risk",
            color_discrete_map={
                "Critical": "#B91C1C",
                "High": "#EA580C",
                "Moderate": "#D97706",
                "Controlled": "#15803D",
            },
        )
        st.plotly_chart(
            _chart_layout(figure, "Business service health", "Health score"),
            use_container_width=True,
        )
        weakest_service = services.sort_values("health").iloc[0]
        st.markdown(
            f"**What this means:** {weakest_service['service']} has the lowest "
            f"health score ({weakest_service['health']:.0f}) and requires review."
        )

    portfolio = pd.DataFrame(analytics["technology_portfolio"])
    with right:
        st.caption("How should the technology estate change?")
        figure = px.treemap(
            portfolio,
            path=["category"],
            values="count",
            color="category",
            color_discrete_map={
                "Strategic": "#15803D",
                "Tolerate": "#64748B",
                "Modernize": "#2563EB",
                "Retire": "#B91C1C",
            },
        )
        st.plotly_chart(
            _chart_layout(figure, "Technology portfolio disposition"),
            use_container_width=True,
        )
        change_total = portfolio.loc[
            portfolio["category"].isin(["Modernize", "Retire"]), "count"
        ].sum()
        st.markdown(
            f"**What this means:** {int(change_total):,} technologies are marked "
            "for modernization or retirement."
        )

    savings = pd.DataFrame(analytics["savings_waterfall"])
    with left:
        st.caption("How much opportunity has become verified value?")
        figure = px.funnel(
            savings,
            x="value",
            y="stage",
            color_discrete_sequence=["#0F766E"],
        )
        st.plotly_chart(
            _chart_layout(figure, "Value realization funnel", "Value ($)"),
            use_container_width=True,
        )
        funnel = dict(zip(savings["stage"], savings["value"], strict=True))
        st.markdown(
            f"**What this means:** ${funnel.get('Evidence qualified', 0) / 1_000_000:.1f}M "
            "is evidence-qualified; opportunity is not presented as realized value."
        )

    pipeline = pd.DataFrame(analytics["recommendation_pipeline"])
    with right:
        st.caption("Where are recommendations waiting for action?")
        figure = px.funnel(
            pipeline,
            x="count",
            y="status",
            color_discrete_sequence=["#7C3AED"],
        )
        st.plotly_chart(
            _chart_layout(figure, "Recommendation pipeline", "Recommendations"),
            use_container_width=True,
        )
        waiting = pipeline.loc[
            ~pipeline["status"].str.lower().isin(["implemented", "closed"]), "count"
        ].sum()
        st.markdown(
            f"**What this means:** {int(waiting):,} recommendations remain before "
            "verified completion."
        )

    with st.expander("Accessible visual intelligence data"):
        for name in sorted(required):
            st.markdown(f"**{name.replace('_', ' ').title()}**")
            st.dataframe(
                pd.DataFrame(analytics[name]), hide_index=True, use_container_width=True
            )


def _render_demo_executive_ai(snapshot: WorkspaceSnapshot) -> None:
    """Render evidence-backed executive answers from the isolated demonstration snapshot."""
    questions = (
        "Where can we reduce costs this quarter?",
        "Why is technology spend above plan?",
        "Which decisions need leadership attention?",
        "What should I take to the next board meeting?",
    )
    render_section_header(
        "Ask Nexora",
        "Ask an executive question and receive an answer grounded in the current evidence.",
    )
    question = st.selectbox("Executive question", questions, key="ceo_demo_question")
    analytics = snapshot.analytics or {}

    if question == questions[0]:
        funnel = {item["stage"]: item["value"] for item in analytics["savings_waterfall"]}
        answer = (
            f"Nexora identifies ${funnel['Identified'] / 1_000_000:.1f}M of annual opportunity; "
            f"${funnel['Evidence qualified'] / 1_000_000:.1f}M is evidence-qualified and "
            f"${funnel['Verified realized'] / 1_000_000:.1f}M is already verified as realized. "
            "The immediate leadership decision is the $4.2M collaboration and analytics SaaS "
            "consolidation, sequenced against renewal and migration controls."
        )
    elif question == questions[1]:
        latest = analytics["budget_vs_actual"][-1]
        variance = latest["actual"] - latest["budget"]
        answer = (
            f"{latest['quarter']} technology spend is ${variance / 1_000_000:.1f}M above plan. "
            "The evidence points to vendor concentration, overlapping SaaS contracts, and the "
            "checkout modernization requirement. These drivers should be governed separately "
            "from realized savings."
        )
    elif question == questions[2]:
        answer = (
            "Three decisions require attention: approve the phased Global Digital Checkout "
            "modernization, govern the $4.2M SaaS consolidation, and mitigate payment-provider "
            "concentration. The risk decision retains UNKNOWN financial impact until Finance "
            "certifies the evidence."
        )
    else:
        answer = (
            "Take the checkout modernization decision, the qualified-to-realized value funnel, "
            "and the payment-provider concentration exposure. The board message is: protect "
            "digital revenue, release governed savings, and preserve accountable evidence for "
            "each decision."
        )

    with st.container(border=True):
        st.caption("EVIDENCE-BACKED EXECUTIVE ANSWER · SYNTHETIC DEMONSTRATION")
        st.markdown(answer)
        st.caption(
            f"Confidence {snapshot.story.confidence} · Evidence {snapshot.story.evidence} · "
            "Human approval remains required"
        )


def render_workspace(
    key: str,
    *,
    role: str,
    tenant_id: str,
    allowed_page_paths: frozenset[str],
    snapshot: WorkspaceSnapshot,
) -> None:
    definition = WORKSPACES[key]
    if role not in definition.roles:
        st.error("This workspace is not available for the current role.")
        st.stop()
    with render_executive_shell():
        render_page_header(
            definition.title,
            definition.question,
            breadcrumbs=("Executive Intelligence",),
            persona=(
                None
                if key == "ceo" and snapshot.synthetic
                else role.replace("_", " ").title()
            ),
            scope=(
                "Synthetic demonstration"
                if key == "ceo" and snapshot.synthetic
                else f"Tenant {tenant_id}"
            ),
            period=(
                None
                if key == "ceo" and snapshot.synthetic
                else "Current governed checkpoint"
            ),
        )
        if snapshot.synthetic:
            st.warning(
                "SYNTHETIC DEMONSTRATION DATA — this isolated tenant does not contain "
                "customer or production records."
            )
        if key == "cfo" and snapshot.synthetic:
            st.markdown(
                """
                <section class="nexora-executive-hero">
                  <p class="nexora-eyebrow">FINANCIAL POSITION</p>
                  <h2>Separate qualified opportunity from value already realized.</h2>
                </section>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(snapshot.story.today)
            st.info(f"Recommended finance action — {snapshot.story.recommendation}")
        if key == "ceo" and snapshot.synthetic and snapshot.journeys:
            lead = snapshot.journeys[0]
            savings = {
                item["stage"]: item["value"]
                for item in (snapshot.analytics or {}).get("savings_waterfall", [])
            }
            metric_values = {metric.title: metric.value for metric in snapshot.metrics}
            st.markdown(
                """
                <section class="nexora-executive-hero">
                  <p class="nexora-eyebrow">TODAY'S EXECUTIVE BRIEF</p>
                  <h2>Your technology estate is governed. Three decisions require
                  leadership attention.</h2>
                </section>
                """,
                unsafe_allow_html=True,
            )
            estate = st.columns(4)
            estate[0].metric(
                "Technology investment",
                metric_values.get("Technology investment", "UNKNOWN"),
                "Current estate",
            )
            estate[1].metric(
                "Qualified opportunity",
                f"${savings.get('Evidence qualified', 0) / 1_000_000:.1f}M",
                "Evidence qualified",
            )
            estate[2].metric(
                "Verified savings",
                f"${savings.get('Verified realized', 0) / 1_000_000:.1f}M",
                "Realized and verified",
            )
            estate[3].metric(
                "Decisions waiting", str(len(snapshot.decisions)), "Leadership action"
            )
            st.markdown("### Today's most important decision")
            with st.container(border=True):
                st.caption("GLOBAL DIGITAL CHECKOUT · REQUIRES EXECUTIVE REVIEW")
                st.markdown("## Protect peak-season digital revenue")
                st.markdown(lead["impact"])
                outcome, investment = st.columns([1.7, 1])
                outcome.metric("Business outcome", "Avoid peak-season disruption")
                investment.metric("Proposed investment", "$8.2M")
                st.markdown(f"**Recommended executive action:** {lead['recommendation']}")
                st.info(f"Accountable next step — {lead['next_step']}")
                with st.expander("Confidence, evidence, and delay consequence"):
                    details = st.columns(2)
                    details[0].metric("Scenario confidence", "88%")
                    details[1].metric("Evidence coverage", "94%")
                    st.write(f"**If leadership delays:** {lead['impact']}")
            _render_demo_executive_ai(snapshot)
            primary_actions = st.columns(2)
            with primary_actions[0]:
                st.page_link(
                    "pages/analyze_environment.py",
                    label="Analyze Environment",
                    help="Upload governed cost data or connect an authorized cloud account.",
                    use_container_width=True,
                )
            with primary_actions[1]:
                st.page_link(
                    "pages/decision_intelligence.py",
                    label="Review Executive Decisions",
                    use_container_width=True,
                )
        filter_view = InteractionView(
            "Executive filters",
            InteractionKind.FILTER,
            "Presentation intent only; canonical surfaces apply authorized filtering.",
            (
                InteractionOption("Current checkpoint", "current", selected=True),
                InteractionOption("Compare", "compare"),
            ),
            (("Tenant", tenant_id), ("Persona", role)),
            primary_intent="preserve_executive_context",
        )
        if key == "ceo" and snapshot.synthetic:
            with st.expander("Advanced context and checkpoint controls"):
                render_interaction(filter_view)
        else:
            render_section_header(
                "Shared executive context",
                "Filters preserve tenant, scope, persona, and checkpoint.",
            )
            render_interaction(filter_view)
        if not (key == "ceo" and snapshot.synthetic):
            render_section_header(
                "Certified posture",
                "P5 displays only upstream-certified values and policies.",
            )
            cols = executive_columns(len(snapshot.metrics))
        else:
            cols = ()
        kinds = {
            "executive": KpiKind.EXECUTIVE,
            "financial": KpiKind.FINANCIAL,
            "health": KpiKind.HEALTH,
            "risk": KpiKind.RISK,
            "trend": KpiKind.TREND,
            "decision": KpiKind.DECISION,
        }
        # The CEO synthetic brief intentionally replaces the generic posture cards.
        # In that presentation ``cols`` is empty while the snapshot remains intact.
        for column, metric in zip(cols, snapshot.metrics):
            with column:
                render_kpi_card(
                    KpiView(
                        metric.title,
                        metric.value,
                        metric.meaning,
                        metric.source,
                        "Current checkpoint",
                        "Current" if metric.available else "UNKNOWN",
                        kind=kinds.get(metric.kind, KpiKind.EXECUTIVE),
                        confidence=snapshot.story.confidence if metric.available else None,
                        evidence=snapshot.story.evidence if metric.available else None,
                        state=None if metric.available else ComponentState.UNKNOWN,
                        state_reason=(
                            None
                            if metric.available
                            else "No certified value was supplied to this composition surface."
                        ),
                    )
                )
        if key == "cfo" and snapshot.synthetic:
            _render_demo_executive_ai(snapshot)
        if key == "ceo" and snapshot.synthetic and snapshot.journeys:
            render_section_header(
                "Three decisions requiring action",
                "Prioritized by business impact, evidence coverage, and accountable authority.",
            )
            decisions_by_id = {item["id"]: item for item in snapshot.decisions}
            for journey in snapshot.journeys:
                decision = decisions_by_id.get(journey["decision_id"], {})
                impact = decision.get("financial_impact")
                with st.container(border=True):
                    st.caption(journey["decision_id"])
                    st.markdown(f"### {journey['title']} · {decision.get('business_service', '')}")
                    st.markdown(journey["impact"])
                    columns = st.columns(3)
                    columns[0].metric(
                        "Financial impact",
                        f"${impact / 1_000_000:.1f}M" if impact else "UNKNOWN",
                    )
                    columns[1].metric("Confidence", f"{decision.get('confidence', 0)}%")
                    columns[2].metric(
                        "Evidence coverage", f"{decision.get('evidence_coverage', 0)}%"
                    )
                    st.markdown(f"**Recommended decision:** {journey['recommendation']}")
                    links = st.columns(3)
                    with links[0]:
                        st.page_link(
                            "pages/decision_intelligence.py", label="Review decision"
                        )
                    with links[1]:
                        st.page_link(
                            "pages/twin_explorer.py",
                            label="Trace in Digital Twin",
                            help=(
                                "Trace business, application, technology, cost, risk, "
                                "and decision context."
                            ),
                        )
                    with links[2]:
                        st.page_link("pages/approval_center.py", label="Open approval path")
        render_section_header(
            "Executive decision story",
            "A governed sequence from change and risk to recommendation and accountable action.",
        )
        story_steps = (
            ("Yesterday", snapshot.story.yesterday, NarrativeKind.STRATEGIC),
            ("Today", snapshot.story.today, NarrativeKind.EXECUTIVE),
            ("Risk", snapshot.story.risk, NarrativeKind.RISK),
            ("Recommendation", snapshot.story.recommendation, NarrativeKind.RECOMMENDATION),
            ("Business outcome", snapshot.story.outcome, NarrativeKind.INSIGHT),
            ("Action", snapshot.story.action, NarrativeKind.DECISION),
        )
        story_context = (
            st.expander("Show full narrative and decision evidence")
            if key in {"ceo", "cfo"} and snapshot.synthetic
            else nullcontext()
        )
        with story_context:
            for title, text, kind in story_steps:
                render_narrative(
                    NarrativeView(
                        title,
                        text,
                        kind,
                        "Current governed checkpoint",
                        "Human decision authority",
                        "Synthetic" if snapshot.synthetic else "Certified composition",
                        snapshot.story.confidence,
                        snapshot.story.evidence,
                        materiality="Decision context",
                        ai_assisted=False,
                    )
                )
        if snapshot.trend:
            render_section_header(
                "Decision trend",
                "Accessible visual context for the current governed story.",
            )
            trend_frame = pd.DataFrame(snapshot.trend).set_index("period")
            st.line_chart(trend_frame, use_container_width=True)
            with st.expander("Decision trend data"):
                st.dataframe(trend_frame, use_container_width=True)
        _render_decision_analytics(snapshot)
        if snapshot.journeys and not (key == "ceo" and snapshot.synthetic):
            render_section_header(
                "Three decisions, one enterprise story",
                "Follow the evidence from signal to accountable executive action.",
            )
            for journey in snapshot.journeys:
                with st.expander(f"{journey['title']} · {journey['decision_id']}"):
                    st.markdown(f"**What changed:** {journey['change']}")
                    st.markdown(f"**Why it matters:** {journey['impact']}")
                    st.markdown(f"**Recommended decision:** {journey['recommendation']}")
                    st.markdown(f"**Evidence:** {journey['evidence']}")
                    st.markdown(f"**Accountable next step:** {journey['next_step']}")
        if snapshot.decisions:
            render_section_header(
                "Decisions requiring action",
                "Synthetic decision records retain status, evidence coverage, and confidence.",
            )
            st.dataframe(
                pd.DataFrame(snapshot.decisions), hide_index=True, use_container_width=True
            )
        render_section_header(
            "Canonical intelligence surfaces",
            "Open existing P4.3 capabilities without duplicating their logic.",
        )
        visible_surfaces = tuple(
            surface for surface in definition.surfaces if surface.page in allowed_page_paths
        )
        for surface in visible_surfaces:
            st.page_link(
                surface.page,
                label=surface.label,
                help=surface.purpose,
                icon=":material/arrow_forward:",
            )
        if len(visible_surfaces) < len(definition.surfaces):
            st.caption("Some surfaces are hidden by the current role entitlement.")
