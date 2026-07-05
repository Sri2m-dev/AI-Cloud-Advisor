# ADR-004: Digital Twin

Status: Accepted
Date: 2026-07-05
Release: v1.0.0-enterprise-foundation

## Context

The platform needed more than dashboards; it needed entity-centered models that connect technology health, cost, risk, operations, infrastructure, dependencies, business services, and evidence.

## Decision

Establish Digital Twin as a core platform concept, with Technology Digital Twin as the first mature implementation and Enterprise/Business Architecture twin patterns emerging through the Business Architecture layer.

The Technology Digital Twin exposes:

- Estate-level summary
- Selected technology context
- Health intelligence
- Cost intelligence
- Risk intelligence
- Infrastructure evidence
- AI insights
- Dependency graph
- Technical evidence

## Options Considered

1. Keep technology as inventory rows only.
2. Build separate dashboards for health, cost, risk, and evidence.
3. Create entity-centered digital twins connected to the Knowledge Graph and financial model.

## Rationale

Digital twins provide a navigable operating model for enterprise technology. They make it possible to reason from business impact down to technology, cost, risk, and operations.

## Consequences

- Digital Twin services own twin assembly logic.
- Pages should not recreate twin graph or evidence logic.
- Twin confidence, evidence, and mapping coverage should remain visible to executives.

## Future Considerations

- Add business process and cloud resource twins.
- Add predictive twin simulation.
- Add AI-guided what-if and impact analysis.
