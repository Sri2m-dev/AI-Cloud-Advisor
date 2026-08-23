from __future__ import annotations

import html

import streamlit as st

from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.demo_tenant_service import demo_mode_enabled, load_demo_tenant
from shared.currency import format_currency_amount
from shared.evidence_context import clear_prospect_context
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

configure_page(page_title="Nexora | Executive Operating System", page_icon="N")
init_session()
require_role(["executive", "finance", "sales_engineer", "client_admin", "super_admin"])
role = normalize_role(st.session_state.get("role"))
render_sidebar_navigation(role)

organization_id = str(st.session_state.get("organization_id") or "")
display_name = str(st.session_state.get("display_name") or "").strip()
if not display_name:
    display_name = str(st.session_state.get("email") or "Executive").split("@", 1)[0]
display_name = html.escape(display_name.replace(".", " ").replace("_", " ").title())
is_demo = demo_mode_enabled() and (
    organization_id.startswith("demo-") or organization_id.startswith("de000000-")
)

prospect_result = st.session_state.get("prospect_analysis")
prospect_name = str(
    st.session_state.get("prospect_name") or "Uploaded Environment"
).strip()

if prospect_result and not getattr(prospect_result, "currency_resolution_required", True):
    currency = str(prospect_result.currency)
    money = lambda value: format_currency_amount(value, currency)
    total_spend = float(getattr(prospect_result, "total_spend", 0) or 0)
    cloud_spend = float(getattr(prospect_result, "cloud_spend", 0) or 0)
    saas_spend = float(getattr(prospect_result, "saas_spend", 0) or 0)
    other_spend = float(getattr(prospect_result, "other_spend", 0) or 0)
    unclassified_spend = float(
        getattr(prospect_result, "unclassified_spend", 0) or 0
    )
    evidence_coverage = float(
        getattr(prospect_result, "evidence_coverage", 0) or 0
    )
    confidence = float(getattr(prospect_result, "confidence", 0) or 0)
    qualified_opportunity = float(
        getattr(prospect_result, "opportunity_evidence_qualified", 0) or 0
    )
    identified_opportunity = float(
        getattr(prospect_result, "opportunity_identified", 0) or 0
    )
    row_count = int(getattr(prospect_result, "row_count", 0) or 0)

    st.markdown(
        f"""
        <section class="nexora-os-hero">
          <div>
            <p class="nexora-eyebrow">TEMPORARY PROSPECT ANALYSIS</p>
            <h1>{html.escape(prospect_name)}</h1>
            <p class="nexora-os-summary">
              Nexora analysed <strong>{row_count:,} governed evidence rows</strong>
              representing <strong>{money(total_spend)}</strong> of normalized spend.
              Evidence coverage is <strong>{evidence_coverage:.1f}%</strong>.
            </p>
          </div>
          <div class="nexora-os-score">
            <span>Evidence coverage</span>
            <strong>{evidence_coverage:.0f}%</strong>
            <small>Temporary governed analysis</small>
          </div>
        </section>

        <section class="nexora-posture-strip" aria-label="Uploaded evidence posture">
          <article class="nexora-domain-card technology">
            <span aria-hidden="true">&#9672;</span>
            <small>Total normalized spend</small>
            <strong>{money(total_spend)}</strong>
            <em>Uploaded evidence</em>
          </article>
          <article class="nexora-domain-card finance">
            <span aria-hidden="true">&#36;</span>
            <small>Qualified opportunity</small>
            <strong>{money(qualified_opportunity)}</strong>
            <em>Evidence qualified</em>
          </article>
          <article class="nexora-domain-card risk">
            <span aria-hidden="true">&#9888;</span>
            <small>Unclassified spend</small>
            <strong>{money(unclassified_spend)}</strong>
            <em>Requires classification</em>
          </article>
          <article class="nexora-domain-card business">
            <span aria-hidden="true">&#9638;</span>
            <small>Evidence rows</small>
            <strong>{row_count:,}</strong>
            <em>Normalized records</em>
          </article>
          <article class="nexora-domain-card ai">
            <span aria-hidden="true">&#10022;</span>
            <small>Confidence</small>
            <strong>{confidence:.0f}%</strong>
            <em>Evidence-derived</em>
          </article>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.warning(
        "PROSPECT DEMONSTRATION DATA · Temporary Analysis · "
        "Not Certified Production Data"
    )

    quick = st.columns(4)
    with quick[0]:
        st.page_link(
            "pages/analyze_environment.py",
            label="Review Analysis",
            use_container_width=True,
        )
    with quick[1]:
        st.page_link(
            "pages/enterprise_ai_copilot.py",
            label="Ask Nexora",
            use_container_width=True,
        )
    with quick[2]:
        st.page_link(
            "pages/reports.py",
            label="Prepare Board Pack",
            use_container_width=True,
        )
    with quick[3]:
        if st.button(
            "Return to Demo Enterprise",
            use_container_width=True,
            key="return_to_demo_enterprise",
        ):
            clear_prospect_context(st.session_state)
            st.rerun()

    st.markdown("### Spend composition")
    spend = st.columns(4)
    spend[0].metric("Total spend", money(total_spend))
    spend[1].metric("Cloud spend", money(cloud_spend))
    spend[2].metric("SaaS spend", money(saas_spend))
    spend[3].metric("Other spend", money(other_spend))

    st.markdown("### Evidence and opportunity")
    evidence = st.columns(4)
    evidence[0].metric("Evidence coverage", f"{evidence_coverage:.1f}%")
    evidence[1].metric("Confidence", f"{confidence:.1f}%")
    evidence[2].metric(
        "Identified opportunity",
        money(identified_opportunity),
    )
    evidence[3].metric(
        "Qualified opportunity",
        money(qualified_opportunity),
    )

    with st.container(border=True):
        st.markdown("### Executive interpretation")
        st.write(
            f"Nexora has validated and normalized {row_count:,} uploaded evidence rows "
            f"for {prospect_name}. The current evidence represents "
            f"{money(total_spend)} of normalized spend."
        )

        if qualified_opportunity > 0:
            st.write(
                f"{money(qualified_opportunity)} is currently "
                "evidence-qualified as an opportunity."
            )
        elif identified_opportunity > 0:
            st.write(
                f"{money(identified_opportunity)} of opportunity was identified, "
                "but it has not yet met the evidence qualification threshold."
            )
        else:
            st.write(
                "No savings opportunity is currently evidenced by the uploaded dataset. "
                "Nexora will not invent an opportunity where the source evidence does not support one."
            )

        if unclassified_spend > 0:
            st.write(
                f"{money(unclassified_spend)} remains unclassified and should "
                "be enriched before stronger business conclusions are made."
            )

elif prospect_result:
    st.warning("Currency could not be determined from the uploaded evidence.")
    if getattr(prospect_result, "currency_source", "") == "MIXED_EVIDENCE":
        st.error(
            "Multiple currencies were detected: "
            + ", ".join(getattr(prospect_result, "detected_currencies", ()))
            + ". Monetary totals are not available without separated evidence."
        )
    st.page_link(
        "pages/analyze_environment.py",
        label="Resolve currency in Analyze Environment",
        use_container_width=True,
    )

elif is_demo:
    demo = load_demo_tenant(organization_id)
    metrics = demo.get("metrics", {})
    story = demo.get("story", {})
    decisions = demo.get("decisions", [])
    journeys = {item["decision_id"]: item for item in demo.get("journeys", [])}

    st.markdown(
        f"""
        <section class="nexora-os-hero">
          <div>
            <p class="nexora-eyebrow">TODAY'S ENTERPRISE POSTURE</p>
            <h1>Good morning, {display_name}.</h1>
            <p class="nexora-os-summary">We analysed <strong>{metrics.get('applications', 0):,} applications</strong>
            across <strong>{metrics.get('business_services', 0):,} business services</strong>.
            The governed evidence identifies <strong>${metrics.get('identified_savings', 0) / 1_000_000:.1f}M
            of qualified opportunity</strong>, <strong>{metrics.get('critical_risks', 0)} critical risks</strong>,
            and <strong>{len(decisions)} decisions requiring leadership attention</strong>.</p>
          </div>
          <div class="nexora-os-score"><span>Technology posture</span><strong>{metrics.get('technology_health', 'UNKNOWN')}%</strong><small>Governed health signal</small></div>
        </section>
        <section class="nexora-posture-strip" aria-label="Today's enterprise posture">
          <article class="nexora-domain-card technology"><span aria-hidden="true">&#9672;</span><small>Technology health</small><strong>{metrics.get('technology_health', 'UNKNOWN')}%</strong><em>Governed posture</em></article>
          <article class="nexora-domain-card finance"><span aria-hidden="true">&#36;</span><small>Qualified opportunity</small><strong>${metrics.get('identified_savings', 0) / 1_000_000:.1f}M</strong><em>Not realized value</em></article>
          <article class="nexora-domain-card risk"><span aria-hidden="true">&#9888;</span><small>Critical risks</small><strong>{metrics.get('critical_risks', 'UNKNOWN')}</strong><em>Require attention</em></article>
          <article class="nexora-domain-card business"><span aria-hidden="true">&#9638;</span><small>Business services</small><strong>{metrics.get('business_services', 0):,}</strong><em>Connected outcomes</em></article>
          <article class="nexora-domain-card ai"><span aria-hidden="true">&#10022;</span><small>Leadership decisions</small><strong>{len(decisions)}</strong><em>Action required</em></article>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.warning("SYNTHETIC DEMONSTRATION DATA · isolated from customer and production records.")

    quick = st.columns(4)
    with quick[0]:
        st.page_link("pages/ceo_workspace.py", label="Open Executive Brief", use_container_width=True)
    with quick[1]:
        st.page_link("pages/decision_intelligence.py", label="Review Decisions", use_container_width=True)
    with quick[2]:
        st.page_link("pages/analyze_environment.py", label="Analyze Environment", use_container_width=True)
    with quick[3]:
        st.page_link("pages/reports.py", label="Prepare Board Pack", use_container_width=True)

    st.markdown("### Investment and value")
    posture = st.columns(4)
    posture[0].metric("Technology investment", f"${metrics.get('annual_technology_spend', 0) / 1_000_000:.0f}M", "Governed estate")
    posture[1].metric("Qualified opportunity", f"${metrics.get('identified_savings', 0) / 1_000_000:.1f}M", "Not realized value")
    posture[2].metric("Verified realized", f"${metrics.get('verified_realized_savings', 0) / 1_000_000:.1f}M", "Outcome evidenced")
    posture[3].metric("Critical risks", metrics.get("critical_risks", "UNKNOWN"), "Leadership attention")

    left, right = st.columns([1.55, 1])
    with left:
        st.markdown("### Three decisions requiring leadership attention")
        for decision in decisions:
            journey = journeys.get(decision["id"], {})
            impact = decision.get("financial_impact")
            with st.container(border=True):
                st.caption(f"{decision['id']} · {decision['status'].replace('_', ' ').title()}")
                st.markdown(f"#### {decision['title']}")
                st.write(journey.get("impact") or "Business impact remains UNKNOWN.")
                facts = st.columns(3)
                facts[0].metric("Impact", f"${impact / 1_000_000:.1f}M" if impact is not None else "UNKNOWN")
                facts[1].metric("Confidence", f"{decision['confidence']}%")
                facts[2].metric("Evidence", f"{decision['evidence_coverage']}%")
                st.markdown(f"**Recommended action:** {journey.get('recommendation', 'UNKNOWN')}")
                actions = st.columns(2)
                actions[0].page_link("pages/decision_intelligence.py", label="View Impact", use_container_width=True)
                actions[1].page_link("pages/approval_center.py", label="Review Approval", use_container_width=True)
    with right:
        st.markdown("### Executive AI summary")
        with st.container(border=True):
            st.markdown(f"**What happened**  \n{story.get('today', 'UNKNOWN')}")
            st.markdown(f"**Why it matters**  \n{story.get('risk', 'UNKNOWN')}")
            st.markdown(
                f"**Recommended next move**  \n{story.get('recommendation', 'UNKNOWN')}"
            )
            st.page_link("pages/ai_copilot.py", label="Ask Nexora", use_container_width=True)

        st.markdown("### Enterprise Digital Twin")
        lead_path = (next(iter(journeys.values()), {}).get("twin_path") or [])
        with st.container(border=True):
            for item in lead_path:
                st.markdown(f"**{item['layer']}**  \n{item['entity']}")
            st.page_link("pages/twin_explorer.py", label="Trace Dependencies", use_container_width=True)

        st.markdown("### Business health")
        with st.container(border=True):
            st.metric("Business services", f"{metrics.get('business_services', 0):,}")
            st.write("The checkout and payments services carry the most material evidenced attention.")
            st.page_link("pages/business_services.py", label="Open Business Services", use_container_width=True)

else:
    st.markdown(
        f"""
        <section class="nexora-os-hero">
          <div><p class="nexora-eyebrow">ENTERPRISE DECISION INTELLIGENCE</p>
          <h1>Good morning, {display_name}.</h1>
          <p class="nexora-os-summary">Connect certified evidence or begin a secure temporary analysis.
          Nexora will explain what is known, what requires action, and what remains UNKNOWN.</p></div>
          <div class="nexora-os-score"><span>Enterprise posture</span><strong>UNKNOWN</strong><small>Awaiting certified evidence</small></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.info("No certified tenant summary is available yet. Nexora does not substitute sample values.")
    choices = st.columns(3)
    with choices[0]:
        with st.container(border=True):
            st.markdown("### Analyze your environment")
            st.write("Connect an existing certified source or review supported upload paths.")
            st.page_link("pages/analyze_environment.py", label="Start Analysis", use_container_width=True)
    with choices[1]:
        with st.container(border=True):
            st.markdown("### Upload governed evidence")
            st.write("Encrypted temporary analysis with consent, audit, and automatic expiry.")
            if role in {"sales_engineer", "finance"}:
                st.page_link("pages/prospect_data_intake.py", label="Upload Evidence", use_container_width=True)
            else:
                st.caption("Requires a Sales Engineer or Finance Operator.")
    with choices[2]:
        with st.container(border=True):
            st.markdown("### Explore Demo Enterprise")
            st.write("Use the existing isolated synthetic dataset; production RBAC remains unchanged.")
            st.caption("Demo access depends on the configured demonstration tenant.")

st.caption("Certified evidence only · tenant isolated · unsupported conclusions remain UNKNOWN")
