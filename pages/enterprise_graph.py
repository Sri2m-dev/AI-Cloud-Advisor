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
from services.knowledge_graph_composition import enterprise_knowledge_graph_service
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]

configure_page(page_title="Enterprise Knowledge Graph | Nexora", page_icon="KG")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
authenticated = authenticated_tenant_context(st.session_state)
service = enterprise_knowledge_graph_service(authenticated.fabric_context, role=authenticated.role)

st.title("Enterprise Knowledge Graph")
st.caption("Canonical knowledge projection · no duplicate entity or relationship storage")

query = st.text_input("Search enterprise knowledge")
entity_types = ["All", *sorted({entity.entity_type.value for entity in service.search_graph("")})]
selected_type = st.selectbox("Entity type", entity_types)
matches = service.search_graph(query, entity_type=None if selected_type == "All" else selected_type)
if not matches:
    st.info("No tenant-scoped canonical knowledge matches the current search.")
    st.stop()

selected = st.selectbox(
    "Canonical entity",
    [entity.canonical_id for entity in matches],
    format_func=lambda value: next(
        entity.display_name for entity in matches if entity.canonical_id == value
    ),
)
depth = st.slider("Expansion depth", min_value=1, max_value=10, value=3)
answer = service.explain_entity(selected)
paths = service.relationships.traverse(selected, max_hops=depth)

for column, (label, value) in zip(
    st.columns(5),
    [
        ("Canonical Entities", len(service.search_graph(""))),
        ("Connected Entities", len(paths)),
        ("Relationship Paths", len(answer.paths)),
        ("Classifications", len(answer.subject.classifications)),
        ("Financial Impact", f"${answer.financial_impact:,.2f}"),
    ],
    strict=True,
):
    column.metric(label, value)

st.subheader("Enterprise explanation")
st.info(answer.narrative)

tabs = st.tabs(
    [
        "Graph",
        "Identity",
        "Business Impact",
        "Financial",
        "Classification",
        "Risk",
        "Evidence",
    ]
)
rows = [
    {
        "Hops": path.hops,
        "Path": " → ".join(entity.display_name for entity in path.entities),
        "Relationship": path.relationships[-1].relationship_type.value,
        "Entity": path.entities[-1].display_name,
        "Entity Type": path.entities[-1].entity_type.value,
        "Confidence": path.relationships[-1].confidence_score,
        "Evidence": "; ".join(path.relationships[-1].evidence),
        "Lineage": path.relationships[-1].lineage_reference or "UNKNOWN",
    }
    for path in paths
]
with tabs[0]:
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info("No evidence-backed canonical graph paths are available for this entity.")
with tabs[1]:
    st.json(
        {
            "canonical_id": answer.subject.entity.canonical_id,
            "canonical_name": answer.subject.entity.canonical_name,
            "entity_type": answer.subject.entity.entity_type.value,
            "source": answer.subject.entity.source_system,
            "source_identifier": answer.subject.entity.source_identifier,
            "lifecycle": answer.subject.entity.lifecycle_status,
            "version": answer.subject.entity.version,
        }
    )
with tabs[2]:
    impact = service.find_business_impact(selected, depth)
    st.json(
        [
            {
                "canonical_id": entity.canonical_id,
                "name": entity.display_name,
                "type": entity.entity_type.value,
            }
            for entity in impact
        ]
    )
with tabs[3]:
    st.json(dict(answer.subject.financial_context) or {"status": "UNKNOWN"})
with tabs[4]:
    st.json(list(answer.subject.classifications) or [{"status": "UNKNOWN"}])
with tabs[5]:
    st.json(
        {
            "risk_reference": answer.subject.entity.risk_reference or "UNKNOWN",
            "health_reference": answer.subject.entity.health_reference or "UNKNOWN",
        }
    )
with tabs[6]:
    st.json(
        [
            {
                "source": evidence.source,
                "confidence": evidence.confidence,
                "evidence": evidence.evidence,
                "lineage": evidence.lineage,
                "classification_status": evidence.classification_status,
            }
            for evidence in (answer.subject.evidence, *answer.evidence)
        ]
    )

st.subheader("Deterministic path query")
target = st.selectbox(
    "Target entity",
    [entity.canonical_id for entity in service.search_graph("")],
    format_func=lambda value: next(
        entity.display_name for entity in service.search_graph("") if entity.canonical_id == value
    ),
)
path = service.find_path(selected, target)
if path:
    st.code(" → ".join(entity.display_name for entity in path.entities), language="text")
else:
    st.info("No evidence-backed path exists between the selected canonical entities.")
