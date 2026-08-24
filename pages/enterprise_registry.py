from __future__ import annotations

# ruff: noqa: E402
import os
import sys
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum

import pandas as pd
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.sidebar_navigation import render_sidebar_navigation
from services.enterprise_registry_composition import enterprise_registry_service
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]


def _serializable(value):
    if value is None:
        return {}
    if is_dataclass(value):
        return {item.name: _serializable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_serializable(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


configure_page(page_title="Enterprise Registry | Nexora", page_icon="ER")
init_session()
require_role(ROLES)

role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
authenticated = authenticated_tenant_context(st.session_state)
service = enterprise_registry_service(authenticated.fabric_context, role=authenticated.role)
entities = service.list_entities()

st.title("Enterprise Registry")
st.caption(
    "Canonical identity index across governed enterprise sources"
    f" · Repository: {service.source_mode}"
)

type_counts = {}
for entity in entities:
    type_counts[entity.entity_type.value] = type_counts.get(entity.entity_type.value, 0) + 1

unclassified = sum(entity.classification_status == "UNCLASSIFIED" for entity in entities)
unowned = sum(not entity.ownership_reference for entity in entities)
conflicted = sum(entity.classification_status == "CONFLICTED" for entity in entities)

metrics = [
    ("Enterprise Entities", len(entities)),
    (
        "Business Entities",
        sum(
            key
            in {
                "organization",
                "business_unit",
                "department",
                "portfolio",
                "business_capability",
                "business_service",
                "business_process",
            }
            for entity in entities
            for key in [entity.entity_type.value]
        ),
    ),
    ("Applications", type_counts.get("application", 0)),
    ("Technologies", type_counts.get("technology", 0)),
    ("Cloud Accounts", type_counts.get("cloud_account", 0)),
    ("SaaS Products", type_counts.get("saas_product", 0)),
    ("Vendors", type_counts.get("vendor", 0)),
    ("Unclassified", unclassified),
    ("Unowned", unowned),
    ("Conflicted", conflicted),
]
for column, (label, value) in zip(st.columns(5), metrics[:5], strict=True):
    column.metric(label, value)
for column, (label, value) in zip(st.columns(5), metrics[5:], strict=True):
    column.metric(label, value)

st.divider()
search_col, type_col = st.columns([2, 1])
query = search_col.text_input("Search enterprise identities")
type_options = ["All"] + sorted(type_counts)
selected_type = type_col.selectbox("Entity type", type_options)
filtered = service.search_entities(
    query,
    entity_type=None if selected_type == "All" else selected_type,
)

rows = []
for entity in filtered:
    relationships = service.get_relationships(entity.canonical_id)
    financial = service.get_financial_context(entity.canonical_id)
    rows.append(
        {
            "Entity": entity.display_name,
            "Type": entity.entity_type.value,
            "Business Context": entity.business_context_reference or "UNKNOWN",
            "Owner": entity.ownership_reference or "UNKNOWN",
            "Source": f"{entity.source_system}:{entity.source_identifier}",
            "Classification": entity.classification_status,
            "Confidence": f"{entity.confidence_score:.0%}",
            "Relationships": len(relationships),
            "Financial Context": "Available" if financial else "UNKNOWN",
            "Lifecycle": entity.lifecycle_status,
            "Canonical ID": entity.canonical_id,
        }
    )

if not rows:
    st.info("No tenant-scoped enterprise entities match the current filter.")
    st.stop()

st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
selected = st.selectbox("Entity detail", [row["Canonical ID"] for row in rows])
detail = service.get_detail(selected)
entity = detail.entity

tabs = st.tabs(
    [
        "Overview",
        "Business Context",
        "Relationships",
        "Classification",
        "Financial Context",
        "Health & Risk",
        "Lineage",
        "Provenance",
        "Versions",
    ]
)
with tabs[0]:
    st.json(
        {
            "canonical_id": entity.canonical_id,
            "type": entity.entity_type.value,
            "canonical_name": entity.canonical_name,
            "display_name": entity.display_name,
            "source_system": entity.source_system,
            "source_entity_id": entity.source_identifier,
            "lifecycle": entity.lifecycle_status,
        }
    )
with tabs[1]:
    st.json(
        {
            "reference": entity.business_context_reference or "UNKNOWN",
            "owner": entity.ownership_reference or "UNKNOWN",
        }
    )
with tabs[2]:
    st.json(_serializable(detail.relationships))
with tabs[3]:
    st.json(_serializable(detail.classifications))
with tabs[4]:
    st.json(_serializable(detail.financial_context) or {"status": "UNKNOWN"})
with tabs[5]:
    st.json(
        {
            "health_reference": entity.health_reference or "UNKNOWN",
            "risk_reference": entity.risk_reference or "UNKNOWN",
        }
    )
with tabs[6]:
    st.json(_serializable(detail.lineage))
with tabs[7]:
    st.json(_serializable(detail.provenance))
with tabs[8]:
    st.json(_serializable(detail.versions))
