from __future__ import annotations

# ruff: noqa: E402, I001

import os
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.sidebar_navigation import render_sidebar_navigation
from enterprise_scenario import ScenarioRequest, ScenarioService, ScenarioType
from services.enterprise_registry_composition import enterprise_registry_service
from services.enterprise_spend_composition import authenticated_tenant_context
from services.relationship_intelligence_composition import relationship_intelligence_service
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "executive", "cio", "finance", "operations", "auditor"]
configure_page(page_title="Scenario Intelligence | Nexora", page_icon="SI")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
authenticated = authenticated_tenant_context(st.session_state)
context = authenticated.fabric_context
registry = enterprise_registry_service(context, role=authenticated.role)
relationships = relationship_intelligence_service(context, role=authenticated.role)
service = ScenarioService(
    context, role=authenticated.role, registry=registry, relationships=relationships
)

st.title("Scenario Intelligence")
st.error("SIMULATION — NOT AUTHORIZATION")
st.caption("Governed what-if analysis over immutable enterprise baselines. No action is executed.")
entities = registry.list_entities()
if not entities:
    st.info("No canonical entities are available for this tenant.")
    st.stop()

left, right = st.columns(2)
scenario_type = left.selectbox("Scenario type", [item.value for item in ScenarioType])
subject_id = right.selectbox("Subject", [item.canonical_id for item in entities])
horizon = left.selectbox("Horizon", ["NOW", "30_DAYS", "90_DAYS", "12_MONTHS"])
depth = right.slider("Governed relationship depth", 0, 5, 3)
percentage = st.number_input("Cost percentage", min_value=0.0, max_value=1000.0, value=20.0)
assumption_text = st.text_area("Visible assumptions", "No unlisted assumptions")

if st.button("Run Simulation", type="primary"):
    request = ScenarioRequest(
        context,
        scenario_type,
        subject_id,
        temporal_context=horizon,
        depth=depth,
        financial_parameters={"percentage": percentage},
        assumptions={"user_visible": assumption_text},
    )
    result = service.simulate(request)
    st.session_state.setdefault("scenario_results", []).append(result)

results = st.session_state.get("scenario_results", [])[-3:]
if results:
    result = results[-1]
    tabs = st.tabs(
        [
            "Baseline",
            "Simulated State",
            "Business Impact",
            "Financial Impact",
            "Risk",
            "Dependencies",
            "Governance",
            "Policy Preview",
            "Unknowns",
            "Evidence",
        ]
    )
    payloads = [
        result.baseline_state,
        result.simulated_state,
        result.business_impact,
        result.financial_impact,
        result.risk_impact,
        result.relationship_paths,
        result.governance_impact,
        result.policy_preview or {"state": "NOT_REQUESTED"},
        result.unknowns,
        result.evidence,
    ]
    for tab, payload in zip(tabs, payloads):
        with tab:
            st.json(payload)
    if len(results) > 1:
        st.subheader("Compare Scenarios")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Scenario": row.scenario_id,
                        "Cost": row.financial_impact.get("simulated_spend"),
                        "Risk": row.risk_impact.get("state"),
                        "Impact": len(row.impacted_entities),
                        "Confidence": row.confidence,
                        "Unknowns": len(row.unknowns),
                    }
                    for row in results
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
