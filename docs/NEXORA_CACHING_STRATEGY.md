# Nexora Caching Strategy

Status: v1.0.0 foundation baseline
Scope: Repository caching, service payload caching, hybrid operational caching, and mutation safety.

## Principles

1. Cache analytical and read-only payloads.
2. Do not cache mutation paths.
3. Do not cache approval actions.
4. Keep operational queues live when freshness affects user decisions.
5. Prefer service-level payload caching over page-level rendering caches.
6. Keep cache TTLs conservative until production telemetry is available.

## Cache Layers

| Layer | Strategy |
| --- | --- |
| Repository Layer | Cache stable read queries where implemented |
| Enterprise Financial Model | Cache canonical reconciliation payloads |
| Platform Services | Cache shared context and evidence where read-only |
| Certification Services | Cache read-only dashboard payloads |
| Pages | Render from services; avoid page-owned business cache logic |
| Operational Actions | Live and uncached |

## Current TTL Baseline

| Component | TTL | Notes |
| --- | ---: | --- |
| Repository reads | 300s | Existing repository cache pattern |
| EnterpriseFinancialModel | 300s | Canonical financial model payload |
| BusinessContextService base context | 600s | Shared business context base payload |
| KnowledgeGraphCertificationService | 300s | Analytical graph certification payload |
| TechnologyDigitalTwinCertificationService | 300s | Analytical twin certification payload |
| TechnologyHealthCertificationService | 300s | Read-only technology health payload |
| ApplicationInventoryCertificationService | 300s | Read-only application portfolio payload |
| SaaSIntelligenceCertificationService | 300s | Read-only SaaS intelligence payload |
| RiskGovernanceCertificationService analytical payload | 120s | Shorter TTL due governance/approval proximity |
| Approval queue detail | Live | Explicitly uncached |
| Mutations and actions | Uncached | Required for correctness |

## Approved Pattern

Analytical dashboard data may be cached when all are true:

- The payload is read-only.
- The payload does not contain user-specific transient session state.
- The payload does not drive an approval action directly.
- The payload does not include mutation results requiring immediate visibility.

## Prohibited Pattern

Never cache:

- Approve, reject, escalate, save, delete, update, or submit handlers.
- Approval queue detail where users expect immediate action feedback.
- Session-specific authorization decisions.
- User-entered form state.

## Release Baseline

The v1.0.0 baseline uses a hybrid model:

```text
Analytical dashboard data -> cached
Operational queue/detail -> live
Mutation/action paths -> never cached
```

## Future Work

Production telemetry should validate:

- Cold start behavior
- Supabase response variance
- Multi-user concurrency
- Cache hit ratios
- Memory pressure under sustained use
