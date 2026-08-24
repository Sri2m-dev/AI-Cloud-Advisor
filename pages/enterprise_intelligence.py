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
from enterprise_intelligence import QueryType, enterprise_intelligence_service
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]
QUERIES = {
    "Overview": QueryType.ENTERPRISE_CONTEXT,
    "Explain": QueryType.EXPLAIN,
    "Dependencies": QueryType.DEPENDENCIES,
    "Business Impact": QueryType.BUSINESS_IMPACT,
    "Financial Impact": QueryType.FINANCIAL_IMPACT,
    "Ownership": QueryType.OWNERSHIP,
    "Risk": QueryType.RISK,
    "Health": QueryType.HEALTH,
    "Governance": QueryType.GOVERNANCE,
}

configure_page(page_title="Enterprise Intelligence | Nexora", page_icon="EI")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
authenticated = authenticated_tenant_context(st.session_state)
service = enterprise_intelligence_service(authenticated.fabric_context, role=authenticated.role)

st.title("Enterprise Intelligence")
st.caption("Governed, deterministic, read-only enterprise context")
search = st.text_input("Entity Search")
matches = service.graph.search_graph(search, limit=100)
if not matches:
    st.info("No tenant-scoped canonical entities match the current search.")
    st.stop()

labels = {f"{entity.display_name} · {entity.entity_type.value}": entity for entity in matches}
selected_label = st.selectbox("Entity", labels)
query_label = st.selectbox("Query", list(QUERIES))
response = service.run_named_query(QUERIES[query_label], labels[selected_label].canonical_id)

st.subheader("Answer Summary")
st.write(response.narrative)
if response.partial:
    st.warning("Partial result: " + "; ".join(response.partial_reasons))
cols = st.columns(3)
cols[0].metric(
    "Confidence", f"{response.confidence:.0%}" if response.confidence is not None else "UNKNOWN"
)
cols[1].metric("Freshness", response.freshness)
cols[2].metric("Relationship Paths", len(response.paths))

tabs = st.tabs(
    ["Facts", "Derived Findings", "Context", "Relationship Paths", "Evidence", "Governance"]
)
with tabs[0]:
    st.json([asdict(item) for item in response.facts])
with tabs[1]:
    st.json([asdict(item) for item in response.derived_findings] or {"status": "MISSING"})
with tabs[2]:
    st.json(asdict(response.context) if response.context else {"status": "UNSUPPORTED"})
with tabs[3]:
    st.json([str(item) for item in response.paths] or {"status": "No governed paths"})
with tabs[4]:
    st.json(list(response.evidence) or {"status": "Unavailable for this persona or entity"})
with tabs[5]:
    st.json(
        {
            "lineage": str(response.lineage),
            "provenance": str(response.provenance),
            "versions": response.checkpoint_references,
        }
    )
