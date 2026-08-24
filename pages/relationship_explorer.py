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
from services.enterprise_spend_composition import authenticated_tenant_context
from services.relationship_intelligence_composition import relationship_intelligence_service
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]

configure_page(page_title="Relationship Explorer | Nexora", page_icon="RX")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
authenticated = authenticated_tenant_context(st.session_state)
service = relationship_intelligence_service(authenticated.fabric_context, role=authenticated.role)

st.title("Relationship Explorer")
st.caption("Evidence-governed traversal of canonical P3 enterprise relationships")

query = st.text_input("Search canonical enterprise entity")
matches = service.search(query)
if not matches:
    st.info("No tenant-scoped canonical entities match the current search.")
    st.stop()

selected_id = st.selectbox(
    "Enterprise entity",
    [entity.canonical_id for entity in matches],
    format_func=lambda value: next(
        entity.display_name for entity in matches if entity.canonical_id == value
    ),
)
direction = st.selectbox("Direction", ["both", "outbound", "inbound"])
max_hops = st.slider("Traversal depth", min_value=1, max_value=10, value=3)
view = st.radio("View", ["Dependency", "Impact", "Ownership"], horizontal=True)

direct = service.get_relationships(selected_id, direction=direction)
paths = service.traverse(selected_id, max_hops=max_hops, direction=direction)
impact = service.get_impact(selected_id, max_hops=max_hops)

for column, (label, value) in zip(
    st.columns(4),
    [
        ("Direct Relationships", len(direct)),
        ("Traversed Entities", len(paths)),
        ("Maximum Hops", max((path.hops for path in paths), default=0)),
        ("Evidence-backed", sum(bool(row.evidence) for row in direct)),
    ],
    strict=True,
):
    column.metric(label, value)

st.subheader("Executive impact summary")
st.write(impact.narrative)

rows = []
for path in paths:
    endpoint = path.entities[-1]
    edge = path.relationships[-1]
    rows.append(
        {
            "Hops": path.hops,
            "Entity": endpoint.display_name,
            "Entity Type": endpoint.entity_type.value,
            "Relationship": edge.relationship_type.value,
            "Source": edge.source_system,
            "Confidence": f"{edge.confidence_score:.0%}",
            "Evidence": "; ".join(edge.evidence),
            "Last Validation": edge.last_validation,
            "Lineage": edge.lineage_reference or "UNKNOWN",
            "Canonical ID": endpoint.canonical_id,
        }
    )

if not rows:
    st.info(
        "No governed relationships are available for this entity. "
        "Missing relationships are not inferred or fabricated."
    )
else:
    if view == "Ownership":
        owners = {entity.canonical_id for entity in service.get_owners(selected_id)}
        rows = [row for row in rows if row["Canonical ID"] in owners]
    elif view == "Dependency":
        dependency_ids = {
            path.entities[-1].canonical_id
            for path in service.get_dependencies(selected_id, max_hops)
        }
        rows = [row for row in rows if row["Canonical ID"] in dependency_ids]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

with st.expander("Direct relationship evidence", expanded=True):
    for relationship in direct:
        st.json(
            {
                "relationship_id": relationship.id,
                "type": relationship.relationship_type.value,
                "source_entity_id": relationship.source_entity_id,
                "target_entity_id": relationship.target_entity_id,
                "source": relationship.source_system,
                "confidence": relationship.confidence_score,
                "evidence": relationship.evidence,
                "discovered_at": relationship.discovery_timestamp,
                "last_validation": relationship.last_validation,
                "lineage": relationship.lineage_reference,
                "provenance": relationship.provenance_reference,
                "version": relationship.version,
            }
        )
