from __future__ import annotations

import streamlit as st

from components.executive_foundation import (
    EXECUTIVE_UI_VERSION,
    CitationView,
    ComponentState,
    DeltaView,
    EvidenceDrawerView,
    EvidenceEventView,
    EvidenceItemView,
    EvidenceSummaryView,
    KpiKind,
    KpiView,
    SparklinePlaceholder,
    ThresholdView,
    TrendDirection,
    TrendView,
    executive_columns,
    render_authority_badge,
    render_citation,
    render_component_state,
    render_confidence_badge,
    render_evidence_badge,
    render_evidence_card,
    render_evidence_drawer,
    render_evidence_summary,
    render_evidence_timeline,
    render_executive_shell,
    render_kpi_card,
    render_materiality_badge,
    render_page_header,
    render_section_header,
    render_source_badge,
    render_status_badge,
)
from shared.styles import configure_page

configure_page("Nexora Component Showcase", page_icon=":material/widgets:", layout="wide")

if not st.session_state.get("authenticated"):
    st.switch_page("pages/login.py")
    st.stop()

if st.session_state.get("role") != "super_admin":
    st.error("Component Showcase is restricted to authorized developer tools users.")
    st.stop()

with render_executive_shell():
    render_page_header(
        "Component Showcase",
        "Isolated Executive UI components for design, accessibility, and regression review.",
        breadcrumbs=("Developer Tools",),
        persona="Developer",
        scope="Presentation fixtures only",
        period="Not applicable",
    )

    evidence_citation = CitationView(
        "AWS CUR line item", "evidence://EV-204", "AWS", "Authorized fixture excerpt."
    )
    evidence_item = EvidenceItemView(
        "Reconciled spend fact",
        "AWS",
        "13 Aug 2026 15:00 UTC",
        "v3",
        "High",
        "Fresh",
        "Internal",
        "Governed fact",
        evidence_citation,
    )
    evidence_summary = EvidenceSummaryView(
        "8 sources",
        "92%",
        "Updated 2 hours ago",
        "High",
        "Governed fact",
        unknowns="2 fields",
        conflicts="None disclosed",
    )
    evidence_events = (
        EvidenceEventView(
            "Source observed",
            "13 Aug 14:55 UTC",
            "13 Aug 15:00 UTC",
            "AWS",
            "Governed fact",
            "EV-204",
        ),
        EvidenceEventView(
            "Reconciliation completed",
            "13 Aug 15:02 UTC",
            "13 Aug 15:03 UTC",
            "Financial Data Fabric",
            "Verified",
            "EV-205",
        ),
    )
    render_section_header(
        "Evidence component library",
        "Entitlement-safe evidence presentation with explicit uncertainty.",
        eyebrow=f"Executive UI v{EXECUTIVE_UI_VERSION}",
    )
    evidence_columns = executive_columns(2)
    with evidence_columns[0]:
        render_evidence_summary(evidence_summary)
        render_evidence_card(evidence_item)
        render_citation(evidence_citation)
    with evidence_columns[1]:
        render_evidence_timeline(evidence_events)
        for source in ("AWS", "Azure", "GitHub", "CMDB", "ServiceNow", "Manual"):
            render_source_badge(source)
    with st.expander("Evidence Drawer certification fixture", expanded=False):
        render_evidence_drawer(
            EvidenceDrawerView(
                "Enterprise spend",
                evidence_summary,
                (evidence_item,),
                ("AWS CUR → Financial Data Fabric → Executive view",),
                ("Reporting period supplied upstream",),
                ("Two allocation fields unknown",),
            )
        )

    render_section_header(
        "Evidence certification matrix",
        "Every evidence component supports the complete required state contract.",
    )
    certification_states = (
        ("Fresh", None),
        ("Loading", ComponentState.LOADING),
        ("Empty", ComponentState.EMPTY),
        ("Partial", ComponentState.PARTIAL),
        ("Stale", ComponentState.STALE),
        ("Unknown", ComponentState.UNKNOWN),
        ("Conflicted", ComponentState.CONFLICTED),
        ("Unauthorized", ComponentState.UNAUTHORIZED),
        ("Unsupported", ComponentState.UNSUPPORTED),
        ("Error", ComponentState.ERROR),
    )
    evidence_components = (
        "Drawer",
        "Summary",
        "Card",
        "Timeline",
        "Citation",
        "Source badge",
        "Freshness",
        "Coverage",
        "Unknown",
        "Conflict",
        "Authority",
        "Version",
    )
    for component_name in evidence_components:
        st.caption(component_name)
        columns = executive_columns(4)
        for index, (label, state) in enumerate(certification_states):
            with columns[index % 4]:
                if state is None:
                    render_status_badge(label, tone="healthy")
                else:
                    render_component_state(
                        state,
                        title=f"{component_name} · {label}",
                        description="Certification fixture; no product data.",
                    )

    render_section_header(
        "Executive KPI library",
        "All values and semantic states are supplied presentation metadata.",
        eyebrow=f"Executive UI v{EXECUTIVE_UI_VERSION}",
    )
    kpi_fixtures = (
        KpiView(
            "Enterprise services",
            "128",
            "Governed services in the current scope.",
            "Enterprise Registry",
            "Current checkpoint",
            "Observed 8 min ago",
            kind=KpiKind.EXECUTIVE,
            status="Healthy",
            delta=DeltaView("+6", "prior checkpoint", "positive"),
            trend=TrendView("Growing", TrendDirection.UP, "30 days"),
            confidence="High",
            coverage="96%",
            evidence="24 sources",
            materiality="Not assessed",
            sparkline=SparklinePlaceholder(),
        ),
        KpiView(
            "Current spend",
            "$4.82M",
            "Authoritative reconciled spend supplied upstream.",
            "Financial Data Fabric",
            "August 2026 MTD",
            "Reconciled 12 min ago",
            kind=KpiKind.FINANCIAL,
            unit="USD",
            delta=DeltaView("+$120K", "July MTD", "warning"),
            trend=TrendView("Increasing", TrendDirection.UP, "month to date"),
            confidence="Supplied: high",
            evidence="Reconciled",
            metadata=(("Value state", "Current spend"),),
        ),
        KpiView(
            "Technology health",
            "Supported dimensions",
            "No composite health model is approved.",
            "Governed Query",
            "Current checkpoint",
            "Observed 18 min ago",
            kind=KpiKind.HEALTH,
            status="Partial",
            coverage="74%",
            evidence="18 sources",
            threshold=ThresholdView("No approved composite threshold"),
        ),
        KpiView(
            "Material risk",
            "Critical",
            "Severity and materiality remain distinct upstream states.",
            "Decision Intelligence",
            "Current checkpoint",
            "Observed 5 min ago",
            kind=KpiKind.RISK,
            status="Critical",
            materiality="Material",
            trend=TrendView("Worsening", TrendDirection.UP, "7 days"),
            evidence="Governed",
        ),
        KpiView(
            "Service trend",
            "12%",
            "Upstream trend for the selected business service.",
            "Governed Query",
            "Last 30 days",
            "Observed 10 min ago",
            kind=KpiKind.TREND,
            trend=TrendView("Up 12%", TrendDirection.UP, "30 days"),
            evidence="Complete",
            sparkline=SparklinePlaceholder("Placeholder only"),
        ),
        KpiView(
            "Decision waiting",
            "Renewal approval",
            "Actual governed decision awaiting an authorized actor.",
            "WP-011 Decision",
            "Due 20 Aug 2026",
            "Observed 3 min ago",
            kind=KpiKind.DECISION,
            status="Watch",
            authority="Decision",
            evidence="Package EV-204",
            metadata=(("Owner", "CIO"),),
        ),
    )
    for start in range(0, len(kpi_fixtures), 3):
        kpi_columns = executive_columns(3)
        for column, fixture in zip(kpi_columns, kpi_fixtures[start : start + 3], strict=False):
            with column:
                render_kpi_card(fixture)

    render_section_header(
        "KPI state coverage", "The shared foundation state frame remains authoritative."
    )
    kpi_state_columns = executive_columns(4)
    state_fixtures = (
        ComponentState.LOADING,
        ComponentState.PARTIAL,
        ComponentState.UNKNOWN,
        ComponentState.UNAUTHORIZED,
    )
    for column, state in zip(kpi_state_columns, state_fixtures, strict=True):
        with column:
            render_kpi_card(
                KpiView(
                    "Executive KPI",
                    "Not displayed",
                    "State fixture.",
                    "Presentation fixture",
                    "Current scope",
                    "Not applicable",
                    state=state,
                )
            )

    render_section_header(
        "Badges", "Semantic labels supplement color and preserve authority boundaries."
    )
    badge_columns = executive_columns(4)
    with badge_columns[0]:
        st.caption("Status")
        for label in (
            "Healthy",
            "Informational",
            "Watch",
            "Warning",
            "Critical",
            "Blocked",
            "Unknown",
            "Partial",
            "Stale",
            "Conflicted",
            "Unsupported",
        ):
            render_status_badge(label)
    with badge_columns[1]:
        st.caption("Authority")
        for label in (
            "Insight",
            "Finding",
            "Recommendation proposal",
            "Simulation",
            "Decision",
            "Policy preview",
            "Authorized",
            "Executing",
            "Verified outcome",
        ):
            render_authority_badge(label)
    with badge_columns[2]:
        st.caption("Confidence and materiality")
        render_confidence_badge(
            "Confidence", value="Not assessed", description="Confidence: no approved band"
        )
        render_confidence_badge(
            "Coverage", value="72%", description="Coverage: 72 percent of governed inputs"
        )
        render_materiality_badge("Not assessed", description="Materiality model is not approved")
    with badge_columns[3]:
        st.caption("Evidence")
        render_evidence_badge("Governed", value="12 sources")
        render_evidence_badge("Partial", value="3 unknowns")
        render_evidence_badge("Stale", value="Observed 48h ago")

    render_section_header(
        "Standard component states", "Each state preserves meaning without inventing facts."
    )
    states = list(ComponentState)
    for start in range(0, len(states), 2):
        columns = executive_columns(2)
        for column, state in zip(columns, states[start : start + 2], strict=False):
            with column:
                metadata = (
                    "Reference NX-FOUNDATION-001"
                    if state is ComponentState.ERROR
                    else "Scope: Enterprise"
                )
                render_component_state(state, metadata=metadata)

    render_section_header(
        "Responsive layout", "The same semantic order wraps from four columns to one."
    )
    for index, column in enumerate(executive_columns(4), start=1):
        with column:
            st.markdown(
                '<section class="nexora-state" '
                'style="--nexora-state-color:var(--nexora-primary)">'
                f"<h3>Grid region {index}</h3>"
                "<p>Presentation-only fixture.</p></section>",
                unsafe_allow_html=True,
            )

    st.caption(
        f"Executive UI v{EXECUTIVE_UI_VERSION} • No business logic • "
        "No service or repository access • WCAG 2.2 AA target"
    )
