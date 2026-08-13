from __future__ import annotations

import streamlit as st

from components.executive_foundation import (
    ComponentState,
    executive_columns,
    render_authority_badge,
    render_component_state,
    render_confidence_badge,
    render_evidence_badge,
    render_executive_shell,
    render_materiality_badge,
    render_page_header,
    render_section_header,
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
        "Isolated P5.1.1 foundation states for design, accessibility, and regression review.",
        breadcrumbs=("Developer Tools",),
        persona="Developer",
        scope="Presentation fixtures only",
        period="Not applicable",
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

    st.caption("P5.1.1 • No business logic • No service or repository access • WCAG 2.2 AA target")
