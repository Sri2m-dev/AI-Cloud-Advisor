# ruff: noqa: E501
from __future__ import annotations

import streamlit as st

from components.design_system import get_theme


def foundation_css(mode: str = "light") -> str:
    """Return the frozen P5.1.1 semantic/component CSS."""
    tokens = get_theme(mode).token_map()
    variables = ";\n".join(f"{name}: {value}" for name, value in tokens.items())
    return f"""
<style>
:root {{
{variables};
--nexora-status-healthy: #16794a;
--nexora-status-info: #1769aa;
--nexora-status-watch: #9a5b00;
--nexora-status-warning: #a54800;
--nexora-status-critical: #b42318;
--nexora-status-blocked: #8f1d1d;
--nexora-status-unknown: #526176;
--nexora-status-partial: #71601b;
--nexora-status-stale: #5e6674;
--nexora-status-conflicted: #6941c6;
--nexora-status-unsupported: #526176;
--nexora-authority: #315a85;
--nexora-confidence: #365f91;
--nexora-materiality: #765315;
--nexora-evidence: #22675a;
}}
.nexora-executive-shell {{
  max-width: 1440px; margin: 0 auto;
  padding: var(--nexora-space-4) var(--nexora-space-6) var(--nexora-space-8);
}}
.nexora-page-heading {{ border-bottom: 1px solid var(--nexora-border); padding-bottom: 1rem; }}
.nexora-breadcrumbs {{ color: var(--nexora-text-muted); font-size: .8125rem; margin-bottom: .5rem; }}
.nexora-page-heading h1 {{ color: var(--nexora-text); font-size: 1.875rem; line-height: 2.375rem; margin: 0; }}
.nexora-page-heading p {{ color: var(--nexora-text-muted); font-size: .9375rem; line-height: 1.5rem; margin: .25rem 0 0; max-width: 840px; }}
.nexora-page-meta {{ display:flex; flex-wrap:wrap; gap:.5rem 1rem; margin-top:.75rem; color:var(--nexora-text-muted); font-size:.8125rem; }}
.nexora-section-heading {{ display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; margin:2rem 0 1rem; }}
.nexora-section-heading h2 {{ color:var(--nexora-text); font-size:1.5rem; line-height:2rem; margin:0; }}
.nexora-section-heading p {{ color:var(--nexora-text-muted); margin:.125rem 0 0; max-width:840px; }}
.nexora-badge {{ display:inline-flex; align-items:center; gap:.375rem; min-height:28px; padding:.2rem .625rem; border:1px solid currentColor; border-radius:999px; background:var(--nexora-surface); font-size:.8125rem; line-height:1rem; font-weight:600; margin:0 .375rem .375rem 0; }}
.nexora-badge__icon {{ font-weight:800; }}
.nexora-state {{ border:1px solid var(--nexora-border); border-left:4px solid var(--nexora-state-color); border-radius:12px; background:var(--nexora-surface); padding:1.25rem; min-height:112px; }}
.nexora-state h3 {{ color:var(--nexora-text); font-size:1rem; line-height:1.375rem; margin:0 0 .25rem; }}
.nexora-state p {{ color:var(--nexora-text-muted); font-size:.9375rem; line-height:1.5rem; margin:0; }}
.nexora-state__meta {{ display:block; color:var(--nexora-text-muted); font-size:.8125rem; margin-top:.5rem; }}
.nexora-skeleton {{ background:linear-gradient(90deg,var(--nexora-surface-alt) 25%,var(--nexora-border) 37%,var(--nexora-surface-alt) 63%); background-size:400% 100%; border-radius:6px; height:.875rem; margin:.55rem 0; animation:nexora-shimmer 1.4s ease infinite; }}
@keyframes nexora-shimmer {{ from {{ background-position:100% 0; }} to {{ background-position:0 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .nexora-skeleton {{ animation:none; }} }}
@media (max-width:1023px) {{ .nexora-executive-shell {{ padding-left:1rem; padding-right:1rem; }} }}
@media (max-width:767px) {{ .nexora-executive-shell {{ padding:.75rem; }} .nexora-section-heading {{ display:block; }} .nexora-page-heading h1 {{ font-size:1.5rem; line-height:2rem; }} }}
</style>
"""


def inject_foundation_styles(mode: str = "light") -> None:
    st.markdown(foundation_css(mode), unsafe_allow_html=True)
