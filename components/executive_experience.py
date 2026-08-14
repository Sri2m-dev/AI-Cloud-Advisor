from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
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
        "CEO Workspace",
        "Are enterprise outcomes at risk, and which decisions require leadership attention?",
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
            persona=role.replace("_", " ").title(),
            scope=f"Tenant {tenant_id}",
            period="Current governed checkpoint",
        )
        if snapshot.synthetic:
            st.warning(
                "SYNTHETIC DEMONSTRATION DATA — this isolated tenant does not contain "
                "customer or production records."
            )
        render_section_header(
            "Shared executive context", "Filters preserve tenant, scope, persona, and checkpoint."
        )
        render_interaction(
            InteractionView(
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
        )
        render_section_header(
            "Certified posture", "P5 displays only upstream-certified values and policies."
        )
        cols = executive_columns(len(snapshot.metrics))
        kinds = {
            "executive": KpiKind.EXECUTIVE,
            "financial": KpiKind.FINANCIAL,
            "health": KpiKind.HEALTH,
            "risk": KpiKind.RISK,
            "trend": KpiKind.TREND,
            "decision": KpiKind.DECISION,
        }
        for column, metric in zip(cols, snapshot.metrics, strict=True):
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
