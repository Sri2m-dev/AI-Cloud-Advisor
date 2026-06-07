"""Enterprise UI theme primitives for Streamlit dashboards."""

from __future__ import annotations

import streamlit as st


def configure_page(
    page_title: str,
    page_icon: str | None = None,
    *,
    layout: str = "wide",
    initial_sidebar_state: str = "collapsed",
) -> None:
    """Configure a Streamlit page and load the enterprise dashboard theme."""
    kwargs = {
        "page_title": page_title,
        "layout": layout,
        "initial_sidebar_state": initial_sidebar_state,
    }

    if page_icon:
        kwargs["page_icon"] = page_icon

    st.set_page_config(**kwargs)
    apply_enterprise_styles()


def apply_enterprise_styles() -> None:
    """
    Inject enterprise dashboard styling only once per Streamlit session.
    """

    if st.session_state.get("_enterprise_styles_loaded"):
        return

    st.session_state["_enterprise_styles_loaded"] = True

    st.markdown(
        """
        <style>
        :root {
            --enterprise-bg: #f7f9fc;
            --enterprise-surface: #ffffff;
            --enterprise-border: #d9e1ec;
            --enterprise-border-soft: #e8edf4;
            --enterprise-text: #111827;
            --enterprise-muted: #607087;
            --enterprise-primary: #1d4ed8;
            --enterprise-primary-dark: #1e3a8a;
            --enterprise-success: #047857;
            --enterprise-warning: #b45309;
            --enterprise-danger: #b91c1c;
            --enterprise-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
        }

        html, body, [class*="css"] {
            font-family: Inter, "Segoe UI", Arial, sans-serif;
            color: var(--enterprise-text);
        }

        .stApp {
            background: var(--enterprise-bg);
        }

        .block-container {
            max-width: 1480px;
            padding: 1.15rem 1.4rem 2rem;
        }

        section[data-testid="stSidebar"] {
            width: 15.5rem !important;
            min-width: 15.5rem !important;
            background: #f8fafc;
            border-right: 1px solid var(--enterprise-border);
        }

        section[data-testid="stSidebar"] > div {
            width: 15.5rem !important;
            padding: 0.9rem 0.65rem;
        }

        [data-testid="stSidebarCollapsedControl"] {
            left: 0.5rem;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.65rem;
        }

        div[data-testid="column"] {
            min-width: 0;
        }

        div[data-testid="stMetric"] {
            background: var(--enterprise-surface);
            border: 1px solid var(--enterprise-border);
            border-radius: 8px;
            padding: 0.75rem 0.85rem;
            box-shadow: var(--enterprise-shadow);
        }

        div[data-testid="stMetric"] label {
            color: var(--enterprise-muted);
            font-size: 0.78rem;
            font-weight: 650;
        }

        div[data-testid="stMetricValue"] {
            color: var(--enterprise-text);
            font-size: 1.35rem;
            font-weight: 750;
        }

        .enterprise-page-header {
            padding: 0 0 0.85rem;
            border-bottom: 1px solid var(--enterprise-border);
            margin: 0 0 0.9rem;
        }

        .enterprise-page-header h1 {
            margin: 0;
            color: var(--enterprise-text);
            font-size: clamp(1.55rem, 2.2vw, 2.05rem);
            line-height: 1.15;
            font-weight: 760;
            letter-spacing: 0;
        }

        .enterprise-page-header p {
            margin: 0.25rem 0 0;
            color: var(--enterprise-muted);
            font-size: 0.92rem;
            line-height: 1.45;
        }

        .enterprise-section {
            margin: 1rem 0 0.45rem;
        }

        .enterprise-section h2 {
            margin: 0;
            color: var(--enterprise-text);
            font-size: 1.02rem;
            line-height: 1.3;
            font-weight: 720;
            letter-spacing: 0;
        }

        .enterprise-section p {
            margin: 0.15rem 0 0;
            color: var(--enterprise-muted);
            font-size: 0.84rem;
        }

        .enterprise-panel {
            background: var(--enterprise-surface);
            border: 1px solid var(--enterprise-border);
            border-radius: 8px;
            padding: 0.85rem;
            box-shadow: var(--enterprise-shadow);
            margin-bottom: 0.75rem;
        }

        .enterprise-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
            gap: 0.65rem;
            margin: 0.2rem 0 0.8rem;
        }

        .enterprise-kpi-card {
            min-width: 0;
            min-height: 92px;
            background: var(--enterprise-surface);
            border: 1px solid var(--enterprise-border);
            border-radius: 8px;
            padding: 0.75rem 0.85rem;
            box-shadow: var(--enterprise-shadow);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
        }

        .enterprise-kpi-label {
            color: var(--enterprise-muted);
            font-size: 0.76rem;
            line-height: 1.25;
            font-weight: 700;
            text-transform: uppercase;
        }

        .enterprise-kpi-value {
            color: var(--enterprise-text);
            font-size: clamp(1.25rem, 2.2vw, 1.75rem);
            line-height: 1.08;
            font-weight: 780;
            overflow-wrap: anywhere;
        }

        .enterprise-kpi-delta {
            color: var(--enterprise-success);
            font-size: 0.78rem;
            line-height: 1.25;
            margin-top: 0.3rem;
        }

        .enterprise-chart {
            background: var(--enterprise-surface);
            border: 1px solid var(--enterprise-border);
            border-radius: 8px;
            padding: 0.5rem 0.55rem 0.2rem;
            box-shadow: var(--enterprise-shadow);
            margin-bottom: 0.75rem;
        }

        .enterprise-scroll-table {
            max-height: var(--enterprise-table-height, 360px);
            overflow-y: auto;
            border: 1px solid var(--enterprise-border);
            border-radius: 8px;
            background: var(--enterprise-surface);
        }

        .enterprise-scroll-table [data-testid="stDataFrame"] {
            border: 0;
        }

        [data-testid="stDataFrame"] {
            border-radius: 8px;
            border: 1px solid var(--enterprise-border);
            overflow: hidden;
            box-shadow: var(--enterprise-shadow);
        }

        [data-testid="stDataFrame"] div[role="grid"] {
            font-size: 0.82rem;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 6px;
            min-height: 2.15rem;
            padding: 0.35rem 0.75rem;
            font-size: 0.84rem;
            font-weight: 650;
        }

        div[data-baseweb="select"] > div,
        div[data-testid="stTextInput"] input {
            min-height: 2.15rem;
            border-radius: 6px;
        }

        @media (max-width: 760px) {
            .block-container {
                padding: 0.85rem 0.75rem 1.5rem;
            }

            .enterprise-kpi-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )