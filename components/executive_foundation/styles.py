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
.nexora-kpi {{ min-height:290px; height:100%; box-sizing:border-box; display:flex; flex-direction:column; gap:.75rem; padding:1.25rem; background:var(--nexora-surface); border:1px solid var(--nexora-border); border-radius:12px; box-shadow:var(--nexora-shadow-card); }}
.nexora-kpi__top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:.75rem; }}
.nexora-kpi h3 {{ color:var(--nexora-text); font-size:1rem; line-height:1.375rem; margin:0; }}
.nexora-kpi__value {{ color:var(--nexora-text); font-size:2rem; line-height:2.5rem; font-weight:700; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }}
.nexora-kpi__unit {{ color:var(--nexora-text-muted); font-size:.8125rem; font-weight:600; margin-left:.4rem; }}
.nexora-kpi__movement {{ display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; min-height:1.75rem; }}
.nexora-delta,.nexora-trend {{ display:inline-flex; align-items:center; gap:.2rem; border-radius:8px; padding:.25rem .5rem; background:var(--nexora-surface-alt); color:var(--nexora-text); font-size:.8125rem; font-weight:600; }}
.nexora-delta small {{ color:var(--nexora-text-muted); font-weight:400; }}
.nexora-trend--up {{ color:var(--nexora-status-healthy); }}
.nexora-trend--down {{ color:var(--nexora-status-critical); }}
.nexora-trend--stable,.nexora-trend--unknown {{ color:var(--nexora-text-muted); }}
.nexora-kpi__meaning {{ color:var(--nexora-text-muted); font-size:.9375rem; line-height:1.5rem; margin:0; min-height:3rem; }}
.nexora-kpi__badges {{ display:flex; flex-wrap:wrap; margin-top:auto; }}
.nexora-kpi__metadata {{ display:flex; flex-wrap:wrap; gap:.25rem .75rem; padding-top:.65rem; border-top:1px solid var(--nexora-border); color:var(--nexora-text-muted); font-size:.75rem; }}
.nexora-threshold {{ color:var(--nexora-text-muted); font-size:.75rem; }}
.nexora-threshold__track {{ height:6px; border:1px solid var(--nexora-border); border-radius:999px; margin-top:.35rem; background:linear-gradient(90deg,var(--nexora-surface-alt) 0 33%,var(--nexora-border) 33% 66%,var(--nexora-surface-alt) 66% 100%); }}
.nexora-sparkline {{ color:var(--nexora-primary); display:flex; flex-direction:column; gap:.125rem; font-family:var(--nexora-mono); }}
.nexora-sparkline small {{ color:var(--nexora-text-muted); font-family:var(--nexora-font); }}
.nexora-evidence-summary,.nexora-evidence-card {{ background:var(--nexora-surface); border:1px solid var(--nexora-border); border-radius:12px; padding:1.25rem; }}
.nexora-evidence-summary {{ display:flex; flex-wrap:wrap; gap:.5rem; }}
.nexora-evidence-card h3,.nexora-evidence-timeline h3 {{ color:var(--nexora-text); font-size:1rem; margin:0 0 .75rem; }}
.nexora-evidence-grid {{ display:flex; flex-wrap:wrap; gap:.5rem; }}
.nexora-evidence-indicator {{ display:inline-flex; gap:.25rem; padding:.35rem .55rem; border:1px solid var(--nexora-border); border-radius:8px; color:var(--nexora-text); background:var(--nexora-surface-alt); font-size:.8125rem; }}
.nexora-citation {{ display:flex; flex-direction:column; gap:.35rem; margin-top:1rem; padding:.75rem; border-left:3px solid var(--nexora-evidence); background:var(--nexora-surface-alt); color:var(--nexora-text); font-style:normal; }}
.nexora-citation blockquote {{ margin:.25rem 0; color:var(--nexora-text-muted); }}
.nexora-citation code {{ overflow-wrap:anywhere; }}
.nexora-evidence-timeline {{ list-style:none; padding:0; margin:0; }}
.nexora-evidence-timeline li {{ display:grid; grid-template-columns:1rem 1fr; gap:.75rem; padding:0 0 1.25rem; }}
.nexora-evidence-timeline__marker {{ width:.625rem; height:.625rem; margin-top:.35rem; border-radius:999px; background:var(--nexora-evidence); }}
.nexora-evidence-timeline p {{ color:var(--nexora-text-muted); font-size:.8125rem; margin:.15rem 0; }}
.nexora-narrative {{ position:relative; background:var(--nexora-surface); border:1px solid var(--nexora-border); border-radius:12px; padding:1.25rem; overflow:hidden; }}
.nexora-materiality-ribbon {{ position:absolute; top:0; right:0; padding:.3rem .65rem; background:var(--nexora-surface-alt); color:var(--nexora-materiality); font-size:.75rem; font-weight:600; }}
.nexora-narrative__header {{ display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; padding-right:5rem; }}
.nexora-narrative h3 {{ color:var(--nexora-text); font-size:1.125rem; margin:0; }}
.nexora-narrative__text {{ color:var(--nexora-text); font-size:.9375rem; line-height:1.5rem; max-width:840px; }}
.nexora-narrative--short .nexora-narrative__text {{ max-width:60ch; }}
.nexora-narrative--medium .nexora-narrative__text {{ max-width:72ch; }}
.nexora-narrative--long .nexora-narrative__text {{ max-width:85ch; }}
.nexora-narrative__badges,.nexora-narrative__meta {{ display:flex; flex-wrap:wrap; gap:.4rem; }}
.nexora-narrative__meta {{ color:var(--nexora-text-muted); font-size:.8125rem; padding-top:.65rem; border-top:1px solid var(--nexora-border); }}
.nexora-unknown-statement,.nexora-assumptions {{ margin-top:.75rem; padding:.75rem; border-left:3px solid var(--nexora-status-unknown); background:var(--nexora-surface-alt); color:var(--nexora-text); }}
.nexora-assumptions h4 {{ margin:0 0 .35rem; }}
.nexora-assumptions ul {{ margin:.25rem 0; }}
.nexora-citation-footer {{ display:block; margin-top:.75rem; }}
.nexora-interaction {{ background:var(--nexora-surface); border:1px solid var(--nexora-border); border-radius:12px; padding:1rem; }}
.nexora-interaction__header {{ display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; }}
.nexora-interaction h3 {{ color:var(--nexora-text); font-size:1rem; margin:0; }}
.nexora-interaction p {{ color:var(--nexora-text-muted); font-size:.875rem; }}
.nexora-interaction__options,.nexora-interaction__context-row,.nexora-interaction__authority {{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.5rem; }}
.nexora-interaction__option,.nexora-interaction__context,.nexora-interaction__intent {{ padding:.35rem .55rem; border:1px solid var(--nexora-border); border-radius:8px; color:var(--nexora-text); background:var(--nexora-surface-alt); font-size:.8125rem; }}
.nexora-interaction__option[aria-current="true"] {{ border-color:var(--nexora-primary); }}
.nexora-interaction__option[aria-disabled="true"] {{ opacity:.6; }}
.nexora-skeleton {{ background:linear-gradient(90deg,var(--nexora-surface-alt) 25%,var(--nexora-border) 37%,var(--nexora-surface-alt) 63%); background-size:400% 100%; border-radius:6px; height:.875rem; margin:.55rem 0; animation:nexora-shimmer 1.4s ease infinite; }}
@keyframes nexora-shimmer {{ from {{ background-position:100% 0; }} to {{ background-position:0 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .nexora-skeleton {{ animation:none; }} }}
@media (max-width:1023px) {{ .nexora-executive-shell {{ padding-left:1rem; padding-right:1rem; }} }}
@media (max-width:767px) {{ .nexora-executive-shell {{ padding:.75rem; }} .nexora-section-heading {{ display:block; }} .nexora-page-heading h1 {{ font-size:1.5rem; line-height:2rem; }} .nexora-kpi {{ min-height:0; }} }}
</style>
"""


def inject_foundation_styles(mode: str = "light") -> None:
    st.markdown(foundation_css(mode), unsafe_allow_html=True)
