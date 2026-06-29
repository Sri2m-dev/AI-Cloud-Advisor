from __future__ import annotations

from typing import Any

import streamlit as st

from services.enterprise_intelligence_service import EnterpriseIntelligenceService


def render_intelligence_workspace(current: str) -> None:
    pages = EnterpriseIntelligenceService.get_workspace_pages()
    st.caption("Enterprise Intelligence")
    columns = st.columns(len(pages))
    for index, page in enumerate(pages):
        active = page["Label"] == current
        label = page["Label"] if not active else f"{page['Label']} •"
        if columns[index].button(label, key=f"ei_nav_{page['Label']}", use_container_width=True, disabled=active):
            st.switch_page(page["Path"])


def render_common_asset_search(
    organization_id: str | None,
    key_prefix: str,
    default: str = "AWS",
    allowed_types: set[str] | None = None,
) -> tuple[str, str]:
    assets = EnterpriseIntelligenceService.get_assets(organization_id)
    if allowed_types:
        assets = [row for row in assets if row["type"] in allowed_types]
    if not assets:
        return default, "Unknown"
    labels = [row["label"] for row in assets]
    default_index = next(
        (index for index, row in enumerate(assets) if row["name"] == default),
        0,
    )
    selected_label = st.selectbox("Asset", labels, index=default_index, key=f"{key_prefix}_asset")
    selected = assets[labels.index(selected_label)]
    st.session_state["enterprise_intelligence_asset"] = selected["name"]
    return selected["name"], selected["type"]


def render_demo_scenarios(key_prefix: str) -> dict[str, Any] | None:
    scenarios = EnterpriseIntelligenceService.get_demo_scenarios()
    labels = [row["Name"] for row in scenarios]
    selected = st.selectbox("Demo Scenario", ["Custom", *labels], key=f"{key_prefix}_demo")
    if selected == "Custom":
        return None
    return scenarios[labels.index(selected)]


def render_empty_state(title: str, message: str, next_step: str | None = None) -> None:
    st.info(f"{title}\n\n{message}" + (f"\n\nNext step: {next_step}" if next_step else ""))


def render_explanation_panel(explanation: dict[str, Any]) -> None:
    st.subheader("AI Explanation")
    st.write(explanation.get("Why") or explanation.get("Recommendation") or "No explanation is available.")
    c1, c2 = st.columns(2)
    with c1:
        st.write("Evidence")
        st.write(explanation.get("Evidence") or [])
        st.write("Policies Applied")
        st.write(explanation.get("Policies Applied") or [])
    with c2:
        st.write("Alternatives")
        st.write(explanation.get("Alternatives") or [])
        st.write("Expected Outcome")
        st.write(explanation.get("Expected Outcome") or "-")
