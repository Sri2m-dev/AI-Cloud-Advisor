from __future__ import annotations

from typing import Any

import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.ai_copilot_service import AICopilotService
from shared.styles import configure_page

configure_page(page_title="Ask Nexora", page_icon="N")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("AI Copilot is available to Super Admins, Client Admins, CIOs, and Executives.")
        st.stop()


def _show_context_panel(context: dict[str, Any]) -> None:
    tabs = st.tabs(["Capabilities", "Applications", "Assets", "Cost", "Recommendations", "Decisions", "Connectors"])
    with tabs[0]:
        st.write(context.get("capabilities") or [])
    with tabs[1]:
        st.write(context.get("applications") or [])
    with tabs[2]:
        st.write(context.get("assets") or [])
    with tabs[3]:
        st.json(context.get("cost") or {})
    with tabs[4]:
        st.write(context.get("recommendations") or [])
    with tabs[5]:
        st.write(context.get("decisions") or [])
    with tabs[6]:
        st.write(context.get("connectors") or [])


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    session_id = f"{organization_id}:{user.get('email') or st.session_state.get('email') or 'default'}"

    st.markdown(
        """
        <section class="nexora-welcome-hero">
          <p class="nexora-eyebrow">ASK NEXORA</p>
          <h1>Turn evidence into an executive answer.</h1>
          <p>Ask about spend, risk, business impact, recommendations, or decisions.
          Nexora answers from governed tenant evidence and identifies missing sources
          instead of inventing a conclusion.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.caption("START WITH AN EXECUTIVE QUESTION")
    prompt_cols = st.columns(4)
    selected_prompt = None
    for index, prompt in enumerate(AICopilotService.SUGGESTED_PROMPTS):
        if prompt_cols[index % 4].button(prompt, key=f"prompt_{index}", use_container_width=True):
            selected_prompt = prompt

    st.subheader("Conversation")
    with st.container(border=True):
        for row in AICopilotService.get_history(session_id):
            with st.chat_message("user"):
                st.write(row["question"])
            with st.chat_message("assistant"):
                st.write(row["answer"])
                if row.get("citations"):
                    st.caption("Citations: " + ", ".join(str(item) for item in row["citations"]))

        question = selected_prompt or st.chat_input("Ask Nexora about cost, governance, connectors, recommendations, or decisions")
        if question:
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                response = AICopilotService.ask(question, organization_id, session_id)
                st.write(response["answer"])
                if response.get("citations"):
                    st.caption("Citations: " + ", ".join(str(item) for item in response["citations"]))
            st.rerun()

    history = AICopilotService.get_history(session_id)
    latest = history[-1] if history else None
    if latest:
        st.subheader("Recommended follow-up")
        for followup in latest.get("followup_questions", []):
            st.write(f"→ {followup}")
        with st.expander("Advanced evidence and source traceability"):
            _show_context_panel(latest.get("context") or {})
            st.markdown("**Sources used**")
            for source in latest.get("source_traceability", []):
                st.write(f"• {source}")
            st.caption("Governed tenant scope")
    if st.button("Clear conversation"):
        AICopilotService.clear_history(session_id)
        st.rerun()


if __name__ == "__main__":
    main()
