"""Enterprise UI theme primitives for Streamlit dashboards."""

from __future__ import annotations

import html

import streamlit as st


def configure_page(
    page_title: str,
    page_icon: str | None = None,
    *,
    layout: str = "wide",
    initial_sidebar_state: str = "expanded",
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
            --enterprise-accent: #7c3aed;
            --enterprise-primary-dark: #1e3a8a;
            --enterprise-success: #047857;
            --enterprise-warning: #b45309;
            --enterprise-danger: #b91c1c;
            --enterprise-shadow: 0 12px 35px rgba(15, 23, 42, 0.07);
        }

        html, body, [class*="css"] {
            font-family: Inter, "Segoe UI", Arial, sans-serif;
            color: var(--enterprise-text);
        }

        .stApp {
            background:
                radial-gradient(circle at 82% 0%, rgba(37, 99, 235, 0.08), transparent 28rem),
                var(--enterprise-bg);
        }

        .block-container {
            max-width: 1680px;
            padding: 0.85rem 2rem 3rem;
        }

        .nexora-product-bar {
            position: sticky;
            top: 0;
            z-index: 50;
            display: flex;
            align-items: center;
            justify-content: space-between;
            min-height: 58px;
            margin: -0.85rem -2rem 0.7rem;
            padding: 0 2rem;
            background: color-mix(in srgb, var(--enterprise-surface) 90%, transparent);
            border-bottom: 1px solid var(--enterprise-border-soft);
            backdrop-filter: blur(18px);
        }

        .nexora-product-brand { display: flex; align-items: center; gap: 0.75rem; }
        .nexora-product-mark {
            display: grid; place-items: center; width: 32px; height: 32px;
            border-radius: 9px; color: white; font-weight: 850;
            background: linear-gradient(135deg, var(--enterprise-primary), var(--enterprise-accent));
            box-shadow: 0 8px 20px rgba(29, 78, 216, 0.24);
        }
        .nexora-product-name { font-weight: 820; letter-spacing: -0.02em; }
        .nexora-product-context { color: var(--enterprise-muted); font-size: 0.78rem; }

        .nexora-welcome-hero {
            max-width: none;
            padding: clamp(2rem, 4vw, 4.5rem);
            margin: 0 0 1.5rem;
            border: 1px solid var(--enterprise-border-soft);
            border-radius: 24px;
            background:
                linear-gradient(120deg, color-mix(in srgb, var(--enterprise-surface) 95%, var(--enterprise-primary) 5%), var(--enterprise-surface));
            box-shadow: var(--enterprise-shadow);
        }

        .nexora-welcome-hero h1 {
            max-width: 820px;
            margin: 0.25rem 0 0.75rem;
            font-size: clamp(2.5rem, 5vw, 4.8rem);
            line-height: 0.98;
            letter-spacing: -0.055em;
            font-weight: 790;
        }

        .nexora-welcome-hero > p:last-child {
            max-width: 760px;
            color: var(--enterprise-muted);
            font-size: clamp(1rem, 1.5vw, 1.25rem);
            line-height: 1.55;
        }

        .nexora-executive-hero {
            max-width: 1040px;
            padding: 1.1rem 0 1.35rem;
        }

        .nexora-executive-hero h2 {
            max-width: 920px;
            margin: 0.25rem 0 0;
            font-size: clamp(2rem, 3.8vw, 3.8rem);
            line-height: 1.04;
            letter-spacing: -0.045em;
            font-weight: 790;
        }

        .nexora-eyebrow {
            margin: 0;
            color: var(--enterprise-primary);
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.12em;
        }

        .nexora-process {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.5rem;
            margin: 1rem 0;
        }

        .nexora-process-step {
            padding: 0.8rem;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid var(--enterprise-border-soft);
            border-top: 3px solid var(--enterprise-border);
            border-radius: 10px;
            color: var(--enterprise-muted);
            font-size: 0.8rem;
            font-weight: 700;
        }

        .nexora-process-step.ready {
            border-color: var(--enterprise-success);
            color: var(--enterprise-text);
        }

        @media (max-width: 900px) {
            .nexora-process { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }

        section[data-testid="stSidebar"] {
            width: 15.5rem !important;
            min-width: 15.5rem !important;
            background: color-mix(in srgb, var(--enterprise-surface) 94%, var(--enterprise-primary) 6%);
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
            border: 1px solid var(--enterprise-border-soft);
            border-radius: 16px;
            padding: 1rem 1.05rem;
            box-shadow: var(--enterprise-shadow);
            transition: transform 160ms ease, box-shadow 160ms ease;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px;
            border-color: var(--enterprise-border-soft);
            background: var(--enterprise-surface);
            box-shadow: 0 12px 32px rgba(15, 23, 42, 0.055);
        }

        [data-testid="stChatMessage"] {
            border: 1px solid var(--enterprise-border-soft);
            border-radius: 14px;
            background: var(--enterprise-surface);
            padding: 0.75rem 1rem;
        }

        [data-testid="stFileUploaderDropzone"] {
            min-height: 180px;
            border: 1.5px dashed color-mix(in srgb, var(--enterprise-primary) 55%, var(--enterprise-border));
            border-radius: 18px;
            background: color-mix(in srgb, var(--enterprise-surface) 94%, var(--enterprise-primary) 6%);
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .nexora-analysis-hero {
            padding-bottom: 1.35rem;
            margin-bottom: 1rem;
        }
        .nexora-start-icon {
            display: grid;
            place-items: center;
            width: 46px;
            height: 46px;
            margin-bottom: .7rem;
            border-radius: 14px;
            color: white;
            font-size: 1.35rem;
            font-weight: 850;
            box-shadow: 0 10px 24px rgba(15, 23, 42, .12);
        }
        .nexora-start-icon.technology {
            background: linear-gradient(135deg, #2563eb, #0ea5e9);
        }
        .nexora-start-icon.finance {
            background: linear-gradient(135deg, #059669, #10b981);
        }
        .nexora-start-icon.ai {
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
        }

        .nexora-twin-path {
            display: flex;
            align-items: stretch;
            gap: 0.65rem;
            overflow-x: auto;
            padding: 0.75rem 0 1.25rem;
        }

        .nexora-twin-node {
            min-width: 175px;
            padding: 1rem;
            border: 1px solid var(--enterprise-border-soft);
            border-radius: 16px;
            background: linear-gradient(145deg, var(--enterprise-surface), color-mix(in srgb, var(--enterprise-surface) 92%, var(--enterprise-primary) 8%));
            box-shadow: var(--enterprise-shadow);
        }
        .nexora-twin-node span { display: block; color: var(--enterprise-primary); font-size: 0.68rem; font-weight: 800; letter-spacing: 0.09em; }
        .nexora-twin-node strong { display: block; margin-top: 0.45rem; line-height: 1.25; }
        .nexora-twin-arrow { display: grid; place-items: center; color: var(--enterprise-primary); font-size: 1.35rem; }

        .nexora-os-hero {
            display: grid;
            grid-template-columns: minmax(0, 1.8fr) minmax(230px, 0.55fr);
            gap: 2rem;
            align-items: center;
            margin: 0 0 1rem;
            padding: clamp(1.6rem, 3vw, 3rem);
            color: #f8fafc;
            border-radius: 24px;
            background:
                radial-gradient(circle at 92% 14%, rgba(96, 165, 250, 0.35), transparent 19rem),
                linear-gradient(125deg, #081632 0%, #122a5e 58%, #312e81 100%);
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.22);
        }
        .nexora-os-hero .nexora-eyebrow { color: #93c5fd; }
        .nexora-os-hero h1 { margin: 0.35rem 0 0.8rem; font-size: clamp(2.4rem, 4.6vw, 4.6rem); line-height: 0.98; letter-spacing: -0.055em; }
        .nexora-os-summary { max-width: 900px; margin: 0; color: #dbeafe; font-size: clamp(1rem, 1.5vw, 1.25rem); line-height: 1.6; }
        .nexora-os-score { padding: 1.4rem; border: 1px solid rgba(255,255,255,.2); border-radius: 18px; background: rgba(255,255,255,.09); backdrop-filter: blur(12px); }
        .nexora-os-score span, .nexora-os-score small { display: block; color: #bfdbfe; }
        .nexora-os-score strong { display: block; margin: .35rem 0; font-size: clamp(2.4rem, 5vw, 4.4rem); line-height: 1; }

        .nexora-posture-strip {
            display: grid;
            grid-template-columns: repeat(5, minmax(140px, 1fr));
            gap: .75rem;
            margin: 0 0 1.35rem;
        }
        .nexora-domain-card {
            position: relative;
            overflow: hidden;
            min-height: 126px;
            padding: 1rem;
            border: 1px solid var(--enterprise-border-soft);
            border-top: 4px solid var(--domain-accent);
            border-radius: 16px;
            background: linear-gradient(145deg, var(--enterprise-surface), color-mix(in srgb, var(--enterprise-surface) 92%, var(--domain-accent) 8%));
            box-shadow: var(--enterprise-shadow);
        }
        .nexora-domain-card > span { position: absolute; right: .8rem; top: .6rem; color: var(--domain-accent); font-size: 1.3rem; font-weight: 900; }
        .nexora-domain-card small, .nexora-domain-card em { display: block; color: var(--enterprise-muted); font-style: normal; }
        .nexora-domain-card small { max-width: calc(100% - 1.6rem); font-weight: 750; }
        .nexora-domain-card strong { display: block; margin: .55rem 0 .2rem; color: var(--enterprise-text); font-size: clamp(1.45rem, 2.3vw, 2rem); line-height: 1; }
        .nexora-domain-card em { font-size: .72rem; }
        .nexora-domain-card.technology { --domain-accent: #2563eb; }
        .nexora-domain-card.finance { --domain-accent: #059669; }
        .nexora-domain-card.risk { --domain-accent: #dc2626; }
        .nexora-domain-card.business { --domain-accent: #7c3aed; }
        .nexora-domain-card.ai { --domain-accent: #4f46e5; }

        @media (max-width: 880px) {
            .nexora-os-hero { grid-template-columns: 1fr; }
            .nexora-posture-strip { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
        }
        @media (max-width: 520px) {
            .nexora-posture-strip { grid-template-columns: 1fr; }
        }

        div[data-testid="stMetric"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.08);
        }

        div[data-testid="stMetric"] label {
            color: var(--enterprise-muted);
            font-size: 0.78rem;
            font-weight: 650;
        }

        div[data-testid="stMetricValue"] {
            color: var(--enterprise-text);
            font-size: clamp(1.35rem, 2.4vw, 2rem);
            font-weight: 750;
        }

        .stButton > button, [data-testid="stPageLink"] a {
            border-radius: 12px;
            min-height: 2.75rem;
            font-weight: 700;
            transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
        }

        .stButton > button:hover, [data-testid="stPageLink"] a:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(29, 78, 216, 0.12);
        }

        .stButton > button:focus-visible, [data-testid="stPageLink"] a:focus-visible {
            outline: 3px solid rgba(37, 99, 235, 0.35);
            outline-offset: 2px;
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --enterprise-bg: #0b1220;
                --enterprise-surface: #111827;
                --enterprise-border: #334155;
                --enterprise-border-soft: #253247;
                --enterprise-text: #f8fafc;
                --enterprise-muted: #a8b4c6;
                --enterprise-primary: #60a5fa;
                --enterprise-primary-dark: #93c5fd;
                --enterprise-success: #34d399;
                --enterprise-warning: #fbbf24;
                --enterprise-danger: #f87171;
                --enterprise-shadow: 0 1px 2px rgba(0, 0, 0, 0.28);
            }

            .stApp, section[data-testid="stSidebar"] {
                background: var(--enterprise-bg);
                color: var(--enterprise-text);
            }

            .nexora-process-step {
                background: rgba(17, 24, 39, 0.82);
            }
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
                padding: 0.5rem 0.75rem 1.5rem;
            }

            .nexora-product-bar { margin: -0.5rem -0.75rem 0.7rem; padding: 0 0.75rem; }
            .nexora-product-context { display: none; }

            .enterprise-kpi-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    organization = html.escape(
        str(st.session_state.get("organization_name") or "Enterprise workspace")
    )
    role = html.escape(
        str(st.session_state.get("role") or "Secure session").replace("_", " ").title()
    )
    st.markdown(
        f"""
        <header class="nexora-product-bar" aria-label="Nexora product header">
          <div class="nexora-product-brand">
            <span class="nexora-product-mark" aria-hidden="true">N</span>
            <span><span class="nexora-product-name">Nexora</span><br>
            <span class="nexora-product-context">Enterprise Decision Intelligence</span></span>
          </div>
          <div class="nexora-product-context">{organization} · {role}</div>
        </header>
        """,
        unsafe_allow_html=True,
    )
