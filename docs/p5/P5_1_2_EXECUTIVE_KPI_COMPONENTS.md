# P5.1.2 Executive KPI Component Library

Status: **IMPLEMENTED LOCALLY — PUBLICATION NOT YET AUTHORIZED**

Executive UI version: **2.2.0**

## Delivered

- immutable KPI, delta, trend, threshold, and sparkline-placeholder contracts;
- Executive, Financial, Health, Risk, Trend, and Decision KPI variants;
- upstream-supplied confidence, coverage, evidence, materiality, authority, source,
  period, freshness, delta, direction, and threshold presentation;
- shared P5.1.1 component states, Showcase fixtures, and focused contract tests;
- independent Executive UI semantic version metadata.

## Boundary statement

The library formats and renders supplied strings and enums only. It does not
calculate values, currency, deltas, direction, confidence, coverage, severity,
materiality, thresholds, scores, financial states, decision states, or evidence.
It imports no repository, SQL, service, provider, AI, or workflow layer.

Sparklines are labelled presentation placeholders and receive no series. Threshold
visualization displays an approved upstream label/position and never evaluates a
boundary. Health without an approved composite model uses a supported dimension
state or the existing `UNSUPPORTED` presentation state.

## Certification

```powershell
python -m pytest tests/executive_foundation -q -p no:cacheprovider
python -m ruff check components/executive_foundation pages/component_showcase.py tests/executive_foundation
python -m compileall -q components/executive_foundation pages/component_showcase.py
git diff --check
```

Hosted CI follows publication. Visual/browser certification remains part of the
consolidated P5 release gate unless a working browser bridge is available earlier.

## Exclusions

No evidence drawer/timeline/card, narrative/recommendation/finding/scenario card,
search, AI panel, filters, tables, charts, command bar, service composition, merge,
tag, or release is included. P5.1.3 has not started.
