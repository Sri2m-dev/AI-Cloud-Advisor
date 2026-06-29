from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.ai_copilot_service import AICopilotService


st.set_page_config(page_title="AI Copilot", layout="wide")


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

    st.title("Enterprise AI Copilot")
    st.caption("Ask questions across the Enterprise Digital Twin, FinOps, governance, connectors, recommendations, and decisions.")

    dashboard = AICopilotService.get_dashboard(session_id)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Questions Asked", f"{dashboard['questions_asked']:,}")
    k2.metric("Avg Response", f"{dashboard['average_response_time_ms']:,.0f} ms")
    k3.metric("Insights Generated", f"{dashboard['insights_generated']:,}")
    k4.metric("Recommendations Ref", f"{dashboard['recommendations_referenced']:,}")
    k5.metric("Decisions Ref", f"{dashboard['decisions_referenced']:,}")

    st.divider()
    st.subheader("Suggested Prompts")
    prompt_cols = st.columns(4)
    selected_prompt = None
    for index, prompt in enumerate(AICopilotService.SUGGESTED_PROMPTS):
        if prompt_cols[index % 4].button(prompt, key=f"prompt_{index}", use_container_width=True):
            selected_prompt = prompt

    if st.button("Clear Conversation"):
        AICopilotService.clear_history(session_id)
        st.rerun()

    st.divider()
    chat_col, context_col = st.columns([0.62, 0.38])

    with chat_col:
        st.subheader("Chat")
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
                st.caption(f"Intent: {response['intent']} | Response time: {response['response_time_ms']:,.0f} ms")
            st.rerun()

    with context_col:
        st.subheader("Context Panel")
        history = AICopilotService.get_history(session_id)
        latest = history[-1] if history else None
        if latest:
            _show_context_panel(latest.get("context") or {})

            st.subheader("Source Traceability")
            sources = [{"Source": source, "Used": True} for source in latest.get("source_traceability", [])]
            st.dataframe(pd.DataFrame(sources), use_container_width=True, hide_index=True)

            st.subheader("Follow-up Questions")
            for followup in latest.get("followup_questions", []):
                st.write(followup)
        else:
            st.info("Ask a question to see the Digital Twin context and source traceability.")


if __name__ == "__main__":
    main()
