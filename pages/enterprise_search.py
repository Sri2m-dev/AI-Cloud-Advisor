from __future__ import annotations

# ruff: noqa: E402
import os
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.sidebar_navigation import render_sidebar_navigation
from enterprise_intelligence import SearchRequest, enterprise_search_service
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]
configure_page(page_title="Enterprise Search | Nexora", page_icon="ES")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
authenticated = authenticated_tenant_context(st.session_state)
service = enterprise_search_service(authenticated.fabric_context, role=authenticated.role)

st.title("Enterprise Search")
st.caption("Governed cross-domain retrieval · read only")
query = st.text_input(
    "Search enterprise knowledge", placeholder="Account, application, owner, cost center…"
)
entity_types = sorted(
    {entity.entity_type.value for entity in service.intelligence.graph.search_graph("")}
)
shortcut = st.selectbox(
    "Governed shortcut",
    [
        "All",
        "Unknown Accounts",
        "Unowned Entities",
        "Needs Review",
        "Conflicted",
        "High Spend",
        "Quarantined Spend",
        "Critical Entities",
    ],
)
columns = st.columns(4)
selected_type = columns[0].selectbox("Entity Type", ["All", *entity_types])
classification = columns[1].selectbox(
    "Classification State", ["All", "UNCLASSIFIED", "NEEDS_REVIEW", "CONFLICTED", "APPROVED"]
)
owner = columns[2].selectbox("Owner State", ["All", "Unowned"])
financial = columns[3].checkbox("Financial context")
response = service.search(
    SearchRequest(
        authenticated.fabric_context,
        query,
        entity_types=() if selected_type == "All" else (selected_type,),
        filters={
            "classification_state": classification,
            "owner_state": "Unowned" if shortcut == "Unowned Entities" else owner,
            "shortcut": shortcut,
            "financial_state": shortcut
            if shortcut in {"High Spend", "Quarantined Spend"}
            else None,
        },
        include_financial=financial,
        include_relationships=True,
        include_evidence=authenticated.role in {"super_admin", "client_admin", "auditor"},
        authorization_scope=authenticated.role,
    )
)
st.metric("Governed matches", response.total_matches)
if response.partial:
    st.warning("Partial result: " + "; ".join(response.partial_reasons))
if not response.results:
    st.info("No tenant-scoped governed entities match the current search and filters.")
    st.stop()
rows = [
    {
        "Name": item.display_name,
        "Type": item.entity_type,
        "Canonical ID": item.canonical_id,
        "Source ID": item.source_id,
        "Why matched": item.match_reason,
        "Classification": item.classification_state,
        "Confidence": item.confidence,
        "Business context": item.business_context or "UNKNOWN",
        "Financial": dict(item.financial_summary) or "Not requested/available",
        "Relationships": item.relationship_summary.get("count", 0),
        "Freshness": item.freshness,
    }
    for item in response.results
]
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
selected = st.selectbox(
    "Open in Enterprise Intelligence", [item.canonical_id for item in response.results]
)
st.session_state["enterprise_intelligence_entity"] = selected
st.caption("Use Enterprise Intelligence for the governed detail and explanation contract.")
st.page_link("pages/enterprise_intelligence.py", label="Open governed detail")
