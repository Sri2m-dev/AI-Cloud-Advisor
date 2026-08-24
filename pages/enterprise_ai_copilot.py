from __future__ import annotations

# ruff: noqa: E402
import os
import sys
from dataclasses import asdict

import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.sidebar_navigation import render_sidebar_navigation
from enterprise_copilot import CopilotRequest, enterprise_ai_copilot
from services.demo_tenant_service import demo_mode_enabled, is_demo_tenant, load_demo_tenant
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.currency import format_currency_amount
from shared.evidence_context import resolve_active_evidence_context
from shared.prospect_answers import prospect_evidence_answer
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]
configure_page(page_title="Enterprise AI Copilot | Nexora", page_icon="AI")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
evidence_context = resolve_active_evidence_context(st.session_state)
if evidence_context.is_prospect:
    analysis = evidence_context.prospect_analysis
    prospect_history_key = f"prospect_copilot:{getattr(analysis, 'audit_id', 'analysis')}"
    prospect_history = st.session_state.setdefault(prospect_history_key, [])
    st.title("Ask Nexora")
    st.caption("TEMPORARY PROSPECT ANALYSIS · PROSPECT EVIDENCE ONLY")
    st.markdown("### Current prospect evidence")
    if getattr(analysis, "currency_resolution_required", True):
        st.warning("Currency could not be determined from the uploaded evidence.")
    else:
        metrics = st.columns(4)
        metrics[0].metric(
            "Observed spend",
            format_currency_amount(analysis.total_spend, analysis.currency),
        )
        metrics[1].metric("Evidence rows", f"{analysis.row_count:,}")
        metrics[2].metric("Evidence coverage", f"{analysis.evidence_coverage:.1f}%")
        metrics[3].metric(
            "Qualified opportunity",
            format_currency_amount(
                analysis.opportunity_evidence_qualified, analysis.currency
            ),
        )
    for item in prospect_history[-10:]:
        with st.chat_message(item["role"]):
            st.write(item["content"])
    question = st.chat_input("Ask about the current uploaded prospect evidence")
    if question:
        answer = prospect_evidence_answer(question, analysis)
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write(answer)
        prospect_history.extend(
            ({"role": "user", "content": question}, {"role": "assistant", "content": answer})
        )
        del prospect_history[:-10]
    st.stop()
authenticated = authenticated_tenant_context(st.session_state)
copilot = enterprise_ai_copilot(authenticated.fabric_context, role=authenticated.role)
session_id = (
    f"{authenticated.fabric_context.tenant_id}:{st.session_state.get('user_id', 'session')}"
)
history_key = f"enterprise_copilot:{session_id}"
history = st.session_state.setdefault(history_key, [])


def _demo_executive_answer(question: str, organization_id: str) -> str | None:
    """Answer supported demo questions from the same governed presentation dataset."""
    if not (demo_mode_enabled() and is_demo_tenant(organization_id)):
        return None
    normalized = " ".join(question.lower().split())
    if not any(term in normalized for term in ("saving", "opportunity", "value")):
        return None
    demo = load_demo_tenant(organization_id)
    metrics = demo.get("metrics", {})
    decisions = demo.get("decisions", [])
    known_impacts = [
        item for item in decisions if item.get("financial_impact") is not None
    ]
    largest = max(known_impacts, key=lambda item: item["financial_impact"], default=None)
    largest_text = (
        f" The largest decision-linked amount is {largest['title']} "
        f"(${largest['financial_impact'] / 1_000_000:.1f}M)."
        if largest
        else ""
    )
    return (
        "Based on the current governed demonstration evidence, "
        f"${metrics.get('identified_savings', 0) / 1_000_000:.1f}M is qualified "
        "opportunity and must not be treated as booked savings. "
        f"${metrics.get('verified_realized_savings', 0) / 1_000_000:.1f}M has been "
        f"verified as realized value.{largest_text} "
        f"{len(decisions)} leadership decisions currently require action."
    )

st.title("Enterprise AI Copilot")
st.markdown(
    """
    <section class="nexora-executive-hero">
      <p class="nexora-eyebrow">ASK NEXORA</p>
      <h2>Turn governed evidence into an executive answer.</h2>
    </section>
    """,
    unsafe_allow_html=True,
)
st.caption("Read-only · governed tenant evidence · unsupported conclusions remain UNKNOWN")

organization_id = str(st.session_state.get("organization_id") or "")
if not history and demo_mode_enabled() and is_demo_tenant(organization_id):
    demo = load_demo_tenant(organization_id)
    metrics = demo.get("metrics", {})
    st.markdown("### Current executive summary")
    with st.container(border=True):
        st.write(
            f"Certified demonstration evidence connects "
            f"${metrics.get('annual_technology_spend', 0) / 1_000_000:.0f}M of technology "
            f"investment to {metrics.get('business_services', 0):,} business services. "
            f"{metrics.get('pending_decisions', 0)} leadership decisions require attention; "
            f"${metrics.get('identified_savings', 0) / 1_000_000:.1f}M is qualified opportunity, "
            f"not realized value."
        )
        st.caption("Synthetic demonstration data · isolated from production records")

st.markdown("### Try an executive question")
prompts = st.columns(4)
prompt_labels = (
    "What requires my attention today?",
    "Where is value at risk?",
    "Which business service needs intervention?",
    "What evidence supports the top decision?",
)
for index, label in enumerate(prompt_labels):
    prompts[index].caption(f"• {label}")
for item in history[-10:]:
    with st.chat_message(item["role"]):
        st.write(item["content"])

question = st.chat_input("Ask about governed enterprise entities, cost, ownership, or dependencies")
if question:
    with st.chat_message("user"):
        st.write(question)
    demo_answer = _demo_executive_answer(question, organization_id)
    response = copilot.ask(
        CopilotRequest(
            authenticated.fabric_context,
            question,
            authenticated.role,
            session_id,
        )
    )
    with st.chat_message("assistant"):
        answer = demo_answer or str(response.answer or "").strip()
        empty_answer = answer.lower() in {"", "unknown", "unknown remains unknown.", "[]", "{}"}
        if empty_answer:
            st.write(
                "I cannot certify an answer from the currently available tenant evidence. "
                "Connect or upload the missing source, then ask again; Nexora will not guess."
            )
        else:
            st.write(answer)
        if response.blocked and not demo_answer:
            st.error("Policy blocked this request.")
        elif response.unsupported and not demo_answer:
            st.warning(
                "This question is not currently supported by certified evidence. "
                "No conclusion has been inferred."
            )
        with st.expander("Show Evidence"):
            tabs = st.tabs(["Citations", "Evidence", "Context", "Confidence"])
            with tabs[0]:
                st.json([asdict(item) for item in response.citations])
            with tabs[1]:
                st.json(
                    asdict(response.grounded_context.evidence)
                    if response.grounded_context
                    else {}
                )
            with tabs[2]:
                st.json(asdict(response.grounded_context) if response.grounded_context else {})
            with tabs[3]:
                st.json(
                    {
                        "enterprise_confidence": response.enterprise_confidence,
                        "model_confidence": response.model_confidence,
                        "freshness": [item.freshness for item in response.citations],
                    }
                )
    history.extend(
        ({"role": "user", "content": question}, {"role": "assistant", "content": answer})
    )
    del history[:-10]
