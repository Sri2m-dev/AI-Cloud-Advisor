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
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]
configure_page(page_title="Enterprise AI Copilot | Nexora", page_icon="AI")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
authenticated = authenticated_tenant_context(st.session_state)
copilot = enterprise_ai_copilot(authenticated.fabric_context, role=authenticated.role)
session_id = (
    f"{authenticated.fabric_context.tenant_id}:{st.session_state.get('user_id', 'session')}"
)
history_key = f"enterprise_copilot:{session_id}"
history = st.session_state.setdefault(history_key, [])

st.title("Enterprise AI Copilot")
st.caption("Governed explanation over Enterprise Intelligence · read only")
st.info(f"Persona: {authenticated.role} · Provider: Mock · Policy: copilot-policy-v1")
for item in history[-10:]:
    with st.chat_message(item["role"]):
        st.write(item["content"])

question = st.chat_input("Ask about governed enterprise entities, cost, ownership, or dependencies")
if question:
    with st.chat_message("user"):
        st.write(question)
    response = copilot.ask(
        CopilotRequest(
            authenticated.fabric_context,
            question,
            authenticated.role,
            session_id,
        )
    )
    with st.chat_message("assistant"):
        st.write(response.answer)
        if response.blocked:
            st.error("Policy blocked this request.")
        elif response.unsupported:
            st.warning("The intent is unsupported; only governed retrieved context is shown.")
        tabs = st.tabs(["Citations", "Evidence", "Context", "Confidence"])
        with tabs[0]:
            st.json([asdict(item) for item in response.citations])
        with tabs[1]:
            st.json(asdict(response.grounded_context.evidence) if response.grounded_context else {})
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
        ({"role": "user", "content": question}, {"role": "assistant", "content": response.answer})
    )
    del history[:-10]
