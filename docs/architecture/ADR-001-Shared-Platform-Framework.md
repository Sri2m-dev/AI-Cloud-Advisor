# ADR-001: Shared Platform Framework

Status: Accepted
Date: 2026-07-05
Release: v1.0.0-enterprise-foundation

## Context

Nexora originally contained page-specific implementations for executive summaries, evidence, reconciliation, business context, AI narratives, and Streamlit rendering helpers. This created repeated code, inconsistent presentation, and a higher risk of regressions as more workspaces were added.

## Decision

Introduce a Shared Platform Framework under `components/shared/` and `services/platform/`.

The framework owns reusable presentation and platform support for:

- Executive summaries
- Data reconciliation panels
- Business architecture context
- Evidence panels
- AI narratives
- Portfolio summaries
- Certification banners
- Streamlit compatibility helpers

## Options Considered

1. Continue page-specific rendering patterns.
2. Build a large design-system rewrite.
3. Introduce a focused shared framework and migrate pages incrementally.

## Rationale

The incremental framework approach preserved certified page behavior while reducing duplication. It allowed each page to migrate without redesigning KPIs, charts, domain services, or business logic.

## Consequences

- Certified pages now share consistent executive and evidence patterns.
- Future pages should consume shared renderers by default.
- Page-specific rendering should be limited to domain-specific content.
- The framework becomes part of the platform contract and should be changed carefully.

## Future Considerations

- Add visual regression testing for shared components.
- Expand accessibility and responsive layout checks.
- Continue migrating remaining legacy patterns into shared services when low risk.
