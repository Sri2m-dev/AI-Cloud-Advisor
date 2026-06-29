from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.copilot_service import CopilotService


st.set_page_config(page_title="Technology Copilot", layout="wide")


def _money(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _format_storyboard(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    money_metrics = {"Technology Spend", "Savings Opportunity"}
    formatted["Value"] = formatted.apply(
        lambda row: _money(row["Value"]) if row["Metric"] in money_metrics else row["Value"],
        axis=1,
    )
    return formatted


def _insight_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)

    st.title("Technology Copilot")
    st.caption("Executive answers from the knowledge graph, cost, SaaS, AI governance, and risk layers")

    st.subheader("Ask Anything")
    question = st.text_input(
        "Question",
        value="What breaks if GitHub goes down?",
        placeholder="Ask about cost, risk, ownership, renewals, applications, or dependencies",
    )
    response = CopilotService.ask_anything(question)
    st.info(response["answer"])
    route_cols = st.columns([0.7, 1.3])
    route_cols[0].metric("Query Route", response["route"])
    route_cols[1].write("Evidence")
    route_cols[1].code("\n".join(str(item) for item in response["evidence"]) or "No evidence returned.", language="text")

    st.divider()
    st.subheader("Executive Storyboard")
    storyboard_df = _format_storyboard(CopilotService.storyboard_dataframe())
    _show_dataframe(storyboard_df, "No executive storyboard is available.")

    st.divider()
    cio_tab, cfo_tab = st.tabs(["CIO Insights", "CFO Insights"])

    with cio_tab:
        insights = CopilotService.get_cio_insights()
        for title, rows in insights.items():
            st.markdown(f"#### {title}")
            _show_dataframe(_insight_table(rows), f"No {title.lower()} are available.")

    with cfo_tab:
        cfo = CopilotService.get_cfo_insights()
        cfo_cols = st.columns(4)
        cfo_cols[0].metric("Potential Savings", _money(cfo["Potential Savings"]))
        cfo_cols[1].metric("Unused SaaS", _money(cfo["Unused SaaS"]))
        cfo_cols[2].metric("Unused AI Licenses", _money(cfo["Unused AI Licenses"]))
        cfo_cols[3].metric("Cloud Waste", _money(cfo["Cloud Waste"]))
        st.markdown("#### Overspending")
        st.code("\n".join(f"- {item}" for item in cfo["Overspending"]), language="text")
        st.markdown("#### Contracts Renewing")
        _show_dataframe(pd.DataFrame(cfo["Renewals This Quarter"]), "No renewal risks are available.")
        st.markdown("#### Applications Without Owner")
        st.code("\n".join(cfo["Applications Without Owner"]) or "No unmapped owner gaps found.", language="text")

    st.divider()
    left, right = st.columns([0.95, 1.05])
    with left:
        st.subheader("Relationship Explorer")
        node_name = st.selectbox(
            "Node",
            ["AWS", "GitHub", "Datadog", "ChatGPT Enterprise", "GitHub Copilot", "Microsoft 365"],
            index=0,
        )
        relationship = CopilotService.get_relationship_explorer(node_name)
        relationship_df = pd.DataFrame(
            [{"Attribute": key, "Value": _money(value) if key == "Annual Cost" else value} for key, value in relationship.items()]
        )
        _show_dataframe(relationship_df, "No relationship details are available.")

    with right:
        st.subheader("Recommendation Engine v2")
        _show_dataframe(
            CopilotService.recommendations_dataframe(),
            "No graph-generated recommendations are available.",
        )


if __name__ == "__main__":
    main()
