# P3 Runtime Integration Readiness Checklist

Status values: `PASS`, `PASS WITH CONDITIONS`, `BLOCKED`, `DEFERRED`.

| Area | Status | Certification Notes |
| --- | --- | --- |
| Contract stability | PASS WITH CONDITIONS | Repository and persistence models are stable for certification; runtime mapping still needs feature-flag design. |
| Repository coverage | PASS | Entity, relationship, version, lineage, provenance, quality, ontology, semantic mapping, and idempotency contracts exist. |
| Persistence adapter coverage | PASS | Supabase adapters exist for all required repository contracts plus atomic write executor. |
| Migrations | PASS WITH CONDITIONS | Migrations `0001`-`0018` are additive and reviewed; staging rehearsal remains mandatory. |
| RLS | PASS WITH CONDITIONS | RLS is enabled on Data Fabric tables; real Supabase policy/role certification remains mandatory. |
| Tenant isolation | PASS WITH CONDITIONS | Adapter queries and RPCs apply tenant predicates; live RLS verification remains mandatory. |
| Optimistic concurrency | PASS | Entity, relationship, ontology, semantic, and atomic bundle updates use expected revision predicates. |
| Idempotency | PASS | Idempotency state machine and atomic completion-last semantics are implemented. |
| Atomic writes | PASS WITH CONDITIONS | Entity and relationship bundles use one PostgreSQL RPC transaction; live rollback/replay validation remains mandatory. |
| Rollback | PASS WITH CONDITIONS | PostgreSQL exceptions roll back bundle writes by design; staging failure scenarios must prove it. |
| Error model | PASS WITH CONDITIONS | Errors map to Data Fabric families and redact sensitive data; live PostgreSQL error normalization remains to be exercised. |
| Serialization | PASS | Frozen request/result models and deterministic adapter serialization are covered by unit tests. |
| Integration tests | PASS WITH CONDITIONS | Tests are gated and skip by default; full live scenario coverage requires disposable Supabase credentials. |
| Staging rehearsal | BLOCKED | Not yet run. Required before runtime wiring. |
| Performance baseline | BLOCKED | No atomic bundle load baseline yet. Required before runtime wiring. |
| Operational observability | DEFERRED | No runtime metrics/alerts are wired. Required before production enablement. |
| Backup/recovery | BLOCKED | Restore rehearsal for Data Fabric migrations has not been completed. |
| Connector compatibility | DEFERRED | No connector ingestion path is mapped to Data Fabric. |
| Orchestration-to-adapter mapping | DEFERRED | No orchestration runtime path is wired to Supabase adapters. |
| Feature flag strategy | BLOCKED | Required before any runtime integration branch. |
| Rollback switch | BLOCKED | Required before any runtime integration branch. |
| Production enablement | BLOCKED | Requires staging, RLS, performance, backup/recovery, observability, and feature-flag approvals. |

## Decision

The P3 persistence foundation is certified for continued review and staging rehearsal. Runtime integration is **BLOCKED** until all mandatory pre-runtime conditions in `docs/P3_PERSISTENCE_CERTIFICATION_REPORT.md` are met.

## Next Allowed Work

- Staging Supabase migration rehearsal.
- Safe live integration validation in a disposable Supabase project.
- Feature-flagged orchestration integration design, still disabled by default.

## Explicitly Not Allowed Yet

- Connector ingestion wiring.
- Dashboard or service wiring.
- Scheduler execution.
- Knowledge Graph writes.
- Automatic migration execution.
- Production database execution.
