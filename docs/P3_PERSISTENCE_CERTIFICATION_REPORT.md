# P3 Persistence Certification Report

## Executive Summary

P3 persistence is certified as **PASS WITH CONDITIONS** for a controlled Supabase-backed Data Fabric foundation. The platform now has repository contracts, Supabase adapters, reviewed migrations through `0018`, tenant-scoped optimistic concurrency, append-only history enforcement, durable idempotency, and one-RPC atomic canonical write boundaries for entities and relationships.

Runtime integration remains **DEFERRED**. No connector, service, dashboard, scheduler, or Knowledge Graph path may consume the Data Fabric until the mandatory pre-runtime conditions below are met.

## Reviewed Baseline

- `origin/main` after P3.15B merge: `b228e818 merge: add P3 atomic canonical write RPC boundary`
- Packages reviewed: `data_fabric/persistence/`, `data_fabric/adapters/supabase/`
- Migrations reviewed: `migrations/data_fabric/0001` through `0018`
- Documentation reviewed: P3 persistence architecture, storage model, transaction/idempotency model, implementation plan, migration strategy, test strategy, operational readiness, Supabase adapter docs, ADR-016, and ADR-017.

## Package And Adapter Map

| Contract | Supabase adapter | Status |
| --- | --- | --- |
| EntityRepository | SupabaseEntityRepository | PASS |
| RelationshipRepository | SupabaseRelationshipRepository | PASS |
| VersionRepository | SupabaseVersionRepository | PASS |
| LineageRepository | SupabaseLineageRepository | PASS |
| ProvenanceRepository | SupabaseProvenanceRepository | PASS |
| QualityAssessmentRepository | SupabaseQualityAssessmentRepository | PASS |
| OntologyRepository | SupabaseOntologyRepository | PASS |
| SemanticMappingRepository | SupabaseSemanticMappingRepository | PASS |
| IdempotencyRepository | SupabaseIdempotencyRepository | PASS |
| Atomic canonical write boundary | SupabaseAtomicWriteExecutor | PASS WITH CONDITIONS |

## Repository Coverage Matrix

| Repository | Contract | Adapter | Unit tests | Compliance | Integration | RLS | Tenant filters | Mutation model | Optimistic concurrency | Append-only | Atomic bundle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Entity | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Mutable current state | RPC revision check | N/A | Entity bundle |
| Relationship | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Mutable current state | RPC revision check | N/A | Relationship bundle |
| Version | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Append only | N/A | Trigger + API reject | Entity bundle |
| Lineage | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Append only | N/A | Trigger + API reject | Entity + relationship bundles |
| Provenance | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Append only | N/A | Trigger + API reject | Entity + relationship bundles |
| Quality | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Append only | N/A | Trigger + API reject | Entity + relationship bundles |
| Ontology | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Mutable current state | RPC revision check | N/A | Not in bundle |
| Semantic mapping | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Mutable current state | RPC revision check | N/A | Not in bundle |
| Idempotency | PASS | PASS | PASS | PASS | GATED | PASS | PASS | Controlled state machine | Transition RPCs | N/A | Entity + relationship bundles |

## Table Classification Matrix

| Table | Classification | Enforcement |
| --- | --- | --- |
| enterprise_entities | MUTABLE CURRENT STATE | Tenant uniqueness, RLS, update RPC |
| enterprise_relationships | MUTABLE CURRENT STATE | Active uniqueness, RLS, update RPC |
| entity_versions | APPEND ONLY | Unique entity/version, mutation-prevention triggers |
| lineage_events | APPEND ONLY | Subject requirement, mutation-prevention triggers |
| provenance_records | APPEND ONLY | Subject requirement, mutation-prevention triggers |
| quality_assessments | APPEND ONLY | Score constraints, mutation-prevention triggers |
| ontology_concepts | MUTABLE CURRENT STATE | Tenant uniqueness, RLS, update RPC |
| ontology_relationships | MUTABLE CURRENT STATE | Active uniqueness, RLS, update RPC |
| semantic_mappings | MUTABLE CURRENT STATE | Active uniqueness, RLS, update RPC |
| idempotency_records | STATE MACHINE | Tenant key uniqueness, transition RPCs |

## Migration Certification

Migrations `0001` through `0018` are ordered, additive, schema-scoped to `data_fabric`, and manually applied artifacts. All Data Fabric tables enable RLS. Append-only tables have mutation-prevention triggers. No migration contains destructive SQL, production URLs, or automatic runtime execution.

Confirmed certification correction: existing `SECURITY DEFINER` RPC migrations lacked a consistent safe `search_path` and execute revocation/grant posture. The checkpoint corrects `0003`, `0008`, `0014`, `0015`, and `0016` with `set search_path = data_fabric, pg_temp`, `revoke ... from public`, and `grant execute ... to service_role`.

Rollback remains operational and forward-only: disable the adapter path, restore a test database backup, or apply a reviewed forward migration. Do not cascade-delete append-only history.

## Tenant-Isolation Certification

Repository APIs require `TenantContext` or explicit organization/tenant values. Supabase repository reads apply both `organization_id` and `tenant_id`; update and transition RPCs include tenant predicates. Atomic RPCs validate bundle records, subjects, endpoints, and idempotency keys inside the same tenant scope.

Live Supabase RLS policy certification remains mandatory before runtime use because these foundation migrations enable RLS but do not define production tenant policies.

## Optimistic-Concurrency Certification

Certified RPCs:

- entity update
- relationship update
- ontology concept update
- ontology relationship update
- semantic mapping update
- atomic entity update/deactivate
- atomic relationship update/deactivate

Each requires expected revision where appropriate, includes tenant predicates, compares revision atomically, and increments revision once on success.

## Idempotency Certification

Idempotency identity is `organization_id + tenant_id + idempotency_key`. Same key plus same hash can replay or return in-progress deterministically. Same key plus different hash conflicts. Failed or expired records retry according to documented policy. Atomic bundle completion occurs last inside the database transaction, so rollback cannot leave a false completed record.

## Atomicity Certification

P3.15B entity and relationship canonical writes use one Supabase RPC as one PostgreSQL transaction. Current-state writes, optional entity versions, lineage, provenance, quality, and idempotency completion participate in that transaction. Python does not issue sequential repository calls to simulate atomicity.

## Serialization Certification

Persistence models freeze payloads and metadata. Adapter helpers normalize mapping, tuple, list, set, datetime, and nested values into JSON-compatible structures. Atomic write requests serialize deterministically before RPC invocation. UUID and enum values are carried as strings at the adapter boundary.

## Time-Semantics Certification

Database time columns use `timestamptz`. Foundation models normalize datetimes to UTC. Current-state tables enforce `updated_at >= created_at`; version records carry `recorded_at`, `effective_from`, and `effective_to`; quality uses `assessed_at`; lineage uses `occurred_at`; provenance uses `captured_at`.

## Score-Semantics Certification

Current-state `confidence_score` and `quality_score` use 0-100 database constraints. Quality `overall_score` and `trust_score` use 0-100 constraints. Semantic mapping confidence uses 0-100. Adapters convert ratio-style domain scores where existing repository behavior requires it.

## Error-Model Certification

Supabase adapter errors normalize to Data Fabric families:

- validation defects -> `DataFabricValidationError`
- stale revision and conflict -> `DataFabricConflictError`
- tenant boundary -> `DataFabricTenantBoundaryError`
- immutable mutation -> `DataFabricImmutableStateError` or adapter operation error
- idempotency rejection -> `DataFabricIdempotencyError`
- RPC/transaction failure -> `DataFabricTransactionError`

P3.15B atomic executor redacts service-role values, credentials, and full payloads from error messages.

## Security Certification

PASS WITH CONDITIONS:

- No hardcoded secrets found in migration artifacts.
- Supabase config repr redacts service-role keys.
- Service-role use is documented as server-side only.
- RLS is enabled on Data Fabric tables.
- No anonymous policies are introduced.
- `SECURITY DEFINER` RPCs now have safe `search_path`.
- Privileged RPCs revoke public execute and grant only `service_role`.
- Runtime/product packages do not import Supabase Data Fabric adapters.

Condition: live Supabase role/RLS policy validation is mandatory before runtime wiring.

## Integration-Test Readiness

Supabase integration tests are gated by explicit environment flags and credentials, skip by default, and avoid automatic migration execution. Atomic integration tests include a production-looking URL safeguard and unique test scope generation. Full row-count and rollback scenario execution requires a disposable Supabase project with migrations applied manually.

## Runtime-Readiness Review

| Question | Answer |
| --- | --- |
| Can the Data Fabric accept a canonical entity write atomically? | Yes, by reviewed RPC, pending live test. |
| Can it accept a canonical relationship write atomically? | Yes, by reviewed RPC, pending live test. |
| Can current state and immutable history remain consistent? | Yes by design; live rollback validation remains mandatory. |
| Is idempotent replay guaranteed by the DB boundary? | Yes by tenant-scoped idempotency rows and RPC locking. |
| Are tenant boundaries enforced by adapter and SQL design? | Yes by explicit predicates; live RLS certification remains mandatory. |
| Can orchestration now use one atomic persistence boundary? | Architecturally yes, but runtime wiring remains deferred. |
| Which orchestration contracts remain unmapped? | Product ingestion, scheduler, connector, service, dashboard, and Knowledge Graph paths remain unmapped. |
| Is production integration testing mandatory? | No direct production test; staging/test Supabase validation is mandatory. |
| Is staging migration rehearsal mandatory? | Yes. |
| Is RLS certification against real Supabase mandatory? | Yes. |
| Is performance/load validation mandatory? | Yes before runtime wiring. |

## Confirmed Defects

1. Earlier privileged RPC migrations did not consistently set safe `search_path` or restrict execute permissions.

## Corrections Made

1. Added safe `search_path`, `PUBLIC` execute revocation, and `service_role` execute grants to `0003`, `0008`, `0014`, `0015`, and `0016`.
2. Added certification tests to prevent regression of migration order, RLS, append-only triggers, privileged RPC security posture, tenant scoping, atomic executor presence, runtime non-wiring, and SQL safety.

## Deferred Items

- Live Supabase integration run in a disposable test project.
- Staging migration rehearsal.
- Production RLS policy design and verification.
- Performance/load baseline.
- Operational dashboards, alerting, backup and recovery rehearsal.
- Orchestration-to-adapter mapping behind a feature flag.

## Runtime-Readiness Decision

**BLOCKED FOR PRODUCT RUNTIME, PASS WITH CONDITIONS FOR PERSISTENCE FOUNDATION.**

The persistence foundation is ready for a controlled certification review and staging rehearsal. It is not yet approved for product runtime consumption.

## Mandatory Pre-Runtime Conditions

1. Disposable Supabase integration run covering repositories and atomic RPC rollback/replay scenarios.
2. Staging migration rehearsal with backup/restore proof.
3. Real Supabase RLS and role certification.
4. Performance and load baseline for atomic bundles.
5. Feature flag and rollback switch design.
6. Explicit orchestration-to-adapter mapping.
7. Operational observability and alerting plan.

## Recommended Next Phase

Proceed to a staging Supabase rehearsal and controlled orchestration-to-Data-Fabric integration design behind a disabled-by-default feature flag. Do not wire product paths until mandatory pre-runtime conditions pass.
