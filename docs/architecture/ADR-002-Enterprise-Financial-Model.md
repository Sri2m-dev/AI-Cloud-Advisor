# ADR-002: Enterprise Financial Model

Status: Accepted
Date: 2026-07-05
Release: v1.0.0-enterprise-foundation

## Context

Multiple dashboards calculated spend, allocation, and variance independently. This created inconsistent numbers across business units, capabilities, services, applications, and technology views.

## Decision

Introduce `EnterpriseFinancialModel` as the canonical financial reconciliation layer.

The model owns:

- Allocation summaries
- Reconciliation status
- Allocation coverage
- Unallocated spend
- Variance visibility
- Business-to-technology financial lineage

## Options Considered

1. Keep page-level financial calculations.
2. Move calculations into each domain service.
3. Centralize allocation and reconciliation in a canonical financial model.

## Rationale

Financial inconsistency erodes executive trust. A single model makes variance explicit instead of hiding it and gives every certified page the same reconciliation vocabulary.

## Consequences

- Pages must not duplicate canonical financial reconciliation logic.
- Certified pages should expose reconciliation status when financial data is shown.
- Domain-specific spend may still exist, but labels must distinguish it from enterprise allocation metrics.

## Future Considerations

- Extend reconciliation to Finance and Operations workspaces.
- Add source-level lineage and audit evidence.
- Add automated variance alerts once production telemetry is available.
