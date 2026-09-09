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
from services.demo_ask_nexora_service import DemoAskNexoraService
from services.demo_tenant_service import load_demo_tenant
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.currency import format_currency_amount
from shared.evidence_context import resolve_active_evidence_context
from shared.prospect_answers import prospect_evidence_answer
from shared.session import init_session
from shared.styles import configure_page
from universal_evidence.pilot.governed_intelligence import GovernedAskNexoraService
from universal_evidence.pilot.runtime import ACTIVATION_RESOLVER, get_measurement_pilot_service
from universal_evidence.pilot.semantic_control import authenticated_confirmation_actor
from universal_evidence.product_closure import answer_document_question
from universal_evidence.production_workflow import evidence_counts

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]
configure_page(page_title="Enterprise AI Copilot | Nexora", page_icon="AI")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
evidence_context = resolve_active_evidence_context(st.session_state)
st.caption(f"ACTIVE WORKSPACE · {evidence_context.label}")
if evidence_context.is_prospect:
    analysis = evidence_context.prospect_analysis
    admission = evidence_context.evidence_admission
    scope_id = getattr(admission, "fingerprint", None) or getattr(analysis, "audit_id", "analysis")
    prospect_history_key = f"prospect_copilot:{scope_id}"
    prospect_history = st.session_state.setdefault(prospect_history_key, [])
    st.title("Ask Nexora")
    st.caption("CURRENT SCOPE · PROSPECT · GOVERNED EVIDENCE ONLY")
    st.markdown("### Current prospect evidence")
    if admission is not None:
        records, fields = evidence_counts(admission)
        metrics = st.columns(3)
        metrics[0].metric("Evidence", admission.original_filename)
        metrics[1].metric("Detail records", f"{records:,}")
        metrics[2].metric("Fields discovered", f"{fields:,}")
    closure = st.session_state.get("document_closure_result")
    if closure is not None:
        document_metrics = st.columns(4)
        document_metrics[0].metric("Documents", len(closure.documents))
        document_metrics[1].metric("Business invoices", closure.business_document_count)
        document_metrics[2].metric("Purchased licenses", closure.purchased_licenses)
        document_metrics[3].metric("Unassigned licenses", closure.unassigned_licenses)
    if analysis is None or getattr(analysis, "currency_resolution_required", True):
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
            format_currency_amount(analysis.opportunity_evidence_qualified, analysis.currency),
        )
    for item in prospect_history[-10:]:
        with st.chat_message(item["role"]):
            st.write(item["content"])
    question = st.chat_input("Ask about the current uploaded prospect evidence")
    if question:
        governed = None
        closure_answer = None
        closure_provenance = ()
        if closure is not None:
            closure_answer, closure_provenance = answer_document_question(question, closure)
        elif admission is not None:
            try:
                actor = authenticated_confirmation_actor(st.session_state)
                governed = GovernedAskNexoraService(
                    measurement_service=get_measurement_pilot_service(),
                    activation_resolver=ACTIVATION_RESOLVER,
                ).ask(
                    question,
                    scope=admission.scope,
                    actor_id=actor.actor_id,
                    admission=admission,
                    actor=actor,
                )
            except PermissionError:
                governed = None
        answer = (
            closure_answer
            if closure_answer is not None
            else governed.answer
            if governed is not None
            else prospect_evidence_answer(question, analysis)
            if analysis is not None
            else "Nexora does not currently have enough governed evidence to answer that."
        )
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write(answer)
            if governed is not None and governed.provenance:
                with st.expander("Evidence"):
                    st.caption(f"{len(governed.provenance)} governed provenance reference(s)")
                    st.json(list(governed.provenance))
            elif closure_provenance:
                with st.expander("Evidence"):
                    st.caption(f"{len(closure_provenance)} source reference(s)")
                    st.json(list(closure_provenance))
        prospect_history.extend(
            ({"role": "user", "content": question}, {"role": "assistant", "content": answer})
        )
        del prospect_history[:-10]
    st.stop()
organization_id = str(st.session_state.get("organization_id") or "")
authenticated = None
copilot = None
if evidence_context.is_demo:
    session_id = f"demo:{organization_id}:{st.session_state.get('user_id', 'session')}"
else:
    authenticated = authenticated_tenant_context(st.session_state)
    copilot = enterprise_ai_copilot(
        authenticated.fabric_context,
        role=authenticated.role,
        financial_context=authenticated,
    )
    session_id = (
        f"{authenticated.fabric_context.tenant_id}:" f"{st.session_state.get('user_id', 'session')}"
    )
history_key = f"enterprise_copilot:{session_id}"
history = st.session_state.setdefault(history_key, [])


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

if not history and evidence_context.is_demo:
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
    demo_result = None
    response = None
    if evidence_context.is_demo:
        demo_result = DemoAskNexoraService().ask(
            question, organization_id=evidence_context.organization_id or ""
        )
    else:
        assert authenticated is not None and copilot is not None
        response = copilot.ask(
            CopilotRequest(
                authenticated.fabric_context,
                question,
                authenticated.role,
                session_id,
            )
        )
    with st.chat_message("assistant"):
        answer = (
            demo_result.answer if demo_result is not None else str(response.answer or "").strip()
        )
        empty_answer = answer.lower() in {"", "unknown", "unknown remains unknown.", "[]", "{}"}
        if empty_answer:
            st.write(
                "I cannot certify an answer from the currently available tenant evidence. "
                "Connect or upload the missing source, then ask again; Nexora will not guess."
            )
        else:
            st.write(answer)
        if demo_result is not None and not demo_result.supported:
            st.warning(
                "This question is not currently supported by certified demonstration "
                "evidence. No conclusion has been inferred."
            )
        elif response is not None and response.blocked:
            st.error("Policy blocked this request.")
        elif response is not None and response.unsupported:
            st.warning(
                "This question is not currently supported by certified evidence. "
                "No conclusion has been inferred."
            )
        with st.expander("Show Evidence"):
            tabs = st.tabs(["Citations", "Evidence", "Context", "Confidence"])
            with tabs[0]:
                st.json(
                    list(demo_result.provenance)
                    if demo_result is not None
                    else [asdict(item) for item in response.citations]
                )
            with tabs[1]:
                st.json(
                    {"facts": list(demo_result.facts)}
                    if demo_result is not None
                    else asdict(response.grounded_context.evidence)
                    if response.grounded_context
                    else {}
                )
            with tabs[2]:
                st.json(
                    {
                        "workspace": "DEMO",
                        "classification": "SYNTHETIC_DEMONSTRATION_DATA",
                        "unknowns": list(demo_result.unknowns),
                    }
                    if demo_result is not None
                    else asdict(response.grounded_context)
                    if response.grounded_context
                    else {}
                )
            with tabs[3]:
                st.json(
                    {"evidence_kind": "synthetic_demo", "model_confidence": None}
                    if demo_result is not None
                    else {
                        "enterprise_confidence": response.enterprise_confidence,
                        "model_confidence": response.model_confidence,
                        "freshness": [item.freshness for item in response.citations],
                    }
                )
    history.extend(
        ({"role": "user", "content": question}, {"role": "assistant", "content": answer})
    )
    del history[:-10]
