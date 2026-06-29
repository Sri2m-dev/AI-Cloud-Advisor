from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.digital_twin_service import DigitalTwinService


st.set_page_config(page_title="Enterprise Digital Twin", layout="wide")


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if amount >= 1_000:
        value_k = amount / 1_000
        return f"${value_k:,.0f}K" if value_k.is_integer() else f"${value_k:,.1f}K"
    return f"${amount:,.0f}"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    formatted = df.copy()
    for column in columns:
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(_money)
    return formatted


def _format_overview(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    formatted["Value"] = formatted.apply(
        lambda row: _money(row["Value"]) if row["KPI"] == "Savings" else row["Value"],
        axis=1,
    )
    return formatted


def _map_figure() -> go.Figure:
    relationships = DigitalTwinService.get_relationships()
    if relationships:
        labels = pd.unique(
            pd.DataFrame(
                [
                    {"source": row["source"], "target": row["target"]}
                    for row in relationships
                ]
            )[["source", "target"]].values.ravel("K")
        ).tolist()
    else:
        labels = []
    if not labels:
        labels = [
            "Retail",
            "Revenue Services",
            "Checkout",
            "AWS",
            "Datadog",
            "GitHub",
            "ChatGPT Enterprise",
            "GitHub Copilot",
        ]
    index = {label: idx for idx, label in enumerate(labels)}
    links = [(row["source"], row["target"]) for row in relationships if row["source"] in index and row["target"] in index]
    return go.Figure(
        data=[
            go.Sankey(
                node={"label": labels, "pad": 18, "thickness": 16},
                link={
                    "source": [index[source] for source, _ in links],
                    "target": [index[target] for _, target in links],
                    "value": [1] * len(links),
                },
            )
        ],
        layout={"height": 360, "margin": {"l": 10, "r": 10, "t": 10, "b": 10}},
    )


def _tree_text(tree: dict[str, Any], indent: int = 0) -> str:
    lines = ["  " * indent + str(tree["Entity"])]
    for child in tree.get("Children", []):
        lines.append(_tree_text(child, indent + 1))
    return "\n".join(lines)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)

    st.title("Enterprise Digital Twin")
    st.caption("Business, application, technology, cost, risk, and savings propagation model")

    overview = DigitalTwinService.get_enterprise_overview()

    st.subheader("KPI Row")
    keys = ["Business Units", "Business Services", "Applications", "Technologies", "Risks", "Savings"]
    cols = st.columns(len(keys))
    for idx, key in enumerate(keys):
        value = _money(overview[key]) if key == "Savings" else f"{overview[key]:,}"
        cols[idx].metric(key, value)
    _show_dataframe(_format_overview(DigitalTwinService.overview_dataframe()), "No enterprise overview is available.")

    st.divider()
    st.subheader("Enterprise Digital Twin Map")
    st.plotly_chart(_map_figure(), use_container_width=True)
    _show_dataframe(DigitalTwinService.map_dataframe(), "No digital twin map is available.")
    st.code(_tree_text(DigitalTwinService.get_full_dependency_tree("Retail")), language="text")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Impact Simulation")
        impact_entity = st.selectbox("Failure entity", ["AWS", "GitHub", "Datadog", "ChatGPT Enterprise"], index=0)
        simulation = DigitalTwinService.simulate_failure(impact_entity)
        sim_df = pd.DataFrame(
            [
                {"Metric": "Affected Applications", "Value": ", ".join(simulation["Impacted Applications"])},
                {"Metric": "Affected Services", "Value": ", ".join(simulation["Impacted Services"])},
                {"Metric": "Affected Business Units", "Value": ", ".join(simulation["Impacted Business Units"])},
                {"Metric": "Affected Costs", "Value": _money(simulation["Annual Exposure"])},
                {"Metric": "Affected Risks", "Value": simulation["Risk"]},
            ]
        )
        _show_dataframe(sim_df, "No impact simulation is available.")

    with right:
        st.subheader("Cost Propagation")
        cost_entity = st.selectbox("Cost entity", ["Checkout", "AWS"], index=0)
        cost = DigitalTwinService.calculate_cost_propagation(cost_entity)
        cost_df = pd.DataFrame([{"Cost Domain": key, "Annual Cost": value} for key, value in cost.items()])
        _show_dataframe(_format_money_columns(cost_df, ["Annual Cost"]), "No cost propagation is available.")

    st.divider()
    risk_col, savings_col = st.columns(2)
    with risk_col:
        st.subheader("Risk Propagation")
        risk_entity = st.selectbox("Risk entity", ["AWS", "GitHub", "Datadog", "ChatGPT Enterprise"], index=0)
        risk = DigitalTwinService.calculate_risk_propagation(risk_entity)
        risk_df = pd.DataFrame([{"Metric": key, "Value": ", ".join(value) if isinstance(value, list) else value} for key, value in risk.items()])
        _show_dataframe(risk_df, "No risk propagation is available.")

    with savings_col:
        st.subheader("Savings Propagation")
        savings_entity = st.selectbox("Savings entity", ["Cloud Optimization", "AWS Optimization"], index=0)
        savings = DigitalTwinService.calculate_savings_propagation(savings_entity)
        savings_df = pd.DataFrame([{"Metric": key, "Value": _money(value) if key == "Direct Savings" else value} for key, value in savings.items()])
        _show_dataframe(savings_df, "No savings propagation is available.")

    st.divider()
    st.subheader("Scenario Simulator")
    scenario = st.selectbox(
        "Scenario",
        [
            "AWS Cost +20%",
            "GitHub Contract Removed",
            "ChatGPT Enterprise Expansion",
        ],
        index=0,
    )
    scenario_result = DigitalTwinService.simulate_scenario(scenario)
    scenario_df = pd.DataFrame(
        [
            {
                "Metric": key,
                "Value": _money(value) if key in {"Budget Impact", "Additional Spend", "Additional Savings"} else value,
            }
            for key, value in scenario_result.items()
        ]
    )
    _show_dataframe(scenario_df, "No scenario output is available.")

    st.divider()
    search_col, owner_col = st.columns(2)
    with search_col:
        st.subheader("Digital Twin Search")
        search_entity = st.selectbox(
            "Search",
            ["AWS", "GitHub", "Checkout", "CloudOps", "Microsoft 365", "ChatGPT Enterprise"],
            index=0,
        )
        search = DigitalTwinService.search_entity(search_entity)
        search_df = pd.DataFrame(
            [
                {
                    "Metric": key,
                    "Value": _money(value) if key in {"Cost Exposure", "Savings"} else ", ".join(value) if isinstance(value, list) else value,
                }
                for key, value in search.items()
            ]
        )
        _show_dataframe(search_df, "No search result is available.")

    with owner_col:
        st.subheader("Ownership Explorer")
        owner_entity = st.selectbox("Ownership entity", ["GitHub", "AWS", "ChatGPT Enterprise", "Datadog"], index=0)
        owner = DigitalTwinService.get_owner(owner_entity)
        owner_df = pd.DataFrame(
            [
                {"Metric": key, "Value": _money(value) if key == "Annual Cost" else value}
                for key, value in owner.items()
            ]
        )
        _show_dataframe(owner_df, "No ownership data is available.")

    st.divider()
    st.subheader("Executive Narrative")
    st.info(DigitalTwinService.get_executive_narrative())


if __name__ == "__main__":
    main()
