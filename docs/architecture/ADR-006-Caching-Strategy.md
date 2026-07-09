# ADR-006: Caching Strategy

Status: Accepted
Date: 2026-07-05
Release: v1.0.0-enterprise-foundation

## Context

Nexora pulls together multiple analytical domains: financial reconciliation, business context, knowledge graph, digital twin, technology health, SaaS intelligence, application inventory, and governance. Repeated payload assembly can create unnecessary latency, but operational actions must remain fresh.

## Decision

Use conservative service-level payload caching for read-only analytical data and keep operational queues and mutations live.

Approved pattern:

```text
Analytical dashboard data -> cached
Operational queue/detail -> live
Mutation/action paths -> never cached
```

## Options Considered

1. No caching beyond repositories.
2. Page-level UI caching.
3. Service-level payload caching with explicit mutation exclusions.

## Rationale

Service-level caching improves performance while preserving clean separation of concerns. Avoiding mutation and approval-action caching protects correctness.

## Current Baseline

| Component | TTL |
| --- | ---: |
| Repository reads | 300s |
| EnterpriseFinancialModel | 300s |
| BusinessContextService base context | 600s |
| KnowledgeGraphCertificationService | 300s |
| TechnologyDigitalTwinCertificationService | 300s |
| TechnologyHealthCertificationService | 300s |
| ApplicationInventoryCertificationService | 300s |
| SaaSIntelligenceCertificationService | 300s |
| RiskGovernanceCertificationService analytical payload | 120s |
| Approval queue detail | Live |
| Mutations/actions | Uncached |

## Consequences

- Analytical dashboards have stable warm-route response times.
- Approval queues remain live and action-safe.
- Cache policy is documented and auditable.

## Future Considerations

- Add production cache hit-rate telemetry.
- Revisit TTLs under multi-user load.
- Add explicit cache invalidation hooks for future workflow engines.
