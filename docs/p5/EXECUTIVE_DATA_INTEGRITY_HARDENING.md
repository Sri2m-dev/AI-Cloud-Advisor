# Executive Data Integrity Hardening

## Scope

This bounded follow-up addresses two defects identified during manual screenshot review:

- Enterprise Spend presented synthetic fallback values when certified sources were absent.
- Risk & Governance exposed a raw backend configuration exception to executive users.

It does not add new data sources, calculations, intelligence engines, or product scope.

## Integrity rules

- Missing certified data is `UNKNOWN`, never zero and never a fabricated demonstration value.
- A real zero may be shown only when an available certified source reports zero.
- Source availability is tracked independently for spend, budget, forecast,
  recommendations, cost trend, and risk.
- Partial truth is preserved. For example, certified recommendation savings remain visible
  even when the spend mart is unavailable.
- Executive narratives follow the same availability rules as cards and charts.

## Graceful degradation

Risk & Governance now converts unavailable cost-intelligence and financial-model backends
into a bounded unavailable state. The page explains that Risk Intelligence is unavailable
and identifies configuration of a certified governance source as the next step. Backend
configuration details are not exposed in the executive experience.

## Verification

- Python compilation: pass
- Full regression suite: 1,020 passed, 2 skipped
- Targeted tests protect UNKNOWN semantics and partial recommendation truth.

Visual review remains part of the consolidated manual P5 release gate.
