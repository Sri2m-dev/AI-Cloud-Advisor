# PUE-ACT-009 Production Persistence & Lifecycle

## Persistence gap matrix

| State | Before ACT-009 | ACT-009 boundary |
| --- | --- | --- |
| Profiling/discovery objects | derived/process-local | recomputable; durable source metadata references |
| Semantic decisions and history | process-local | durable lifecycle envelope |
| Normalization metadata/fingerprints | process-local | durable lifecycle envelope |
| Capability/authorization references | process-local | durable lifecycle envelope; current state is revalidated |
| Plans and execution references | process-local | durable lifecycle envelope; stale results remain historical |
| ACT-006 entities/relationships | canonical existing | existing Data Fabric repositories remain authoritative |
| ACT-007 proposals/decisions/bindings | process-local | durable lifecycle envelope |
| ACT-008 answer references | process/session-local | durable fingerprint/reference envelope, never authoritative text |
| Audit/tombstones | mixed local stores | append-only lifecycle audit and minimal purge tombstones |
| Raw uploaded bytes | encrypted prospect storage | unchanged; never copied into lifecycle JSON |

## Repository and schema

`SQLiteLifecycleRepository` is the database-independent service boundary for
ACT-009 metadata. It uses the versioned migration
`migrations/universal_evidence/0001_create_lifecycle_state.sql`, enables SQLite
foreign keys, requires organization and tenant on every operation, and includes
prospect and analysis in the key. Payloads are JSON metadata only; raw evidence
bytes and encryption material are rejected.

The repository uses scoped composite primary keys, idempotent upserts, version
increments, fingerprints, explicit lifecycle states, append-only audit events,
and scoped purge tombstones. Existing canonical entity/relationship persistence
and the prospect Fernet storage boundary are not duplicated or redesigned.

## Service reconstruction

`DurableRuntimeComposition` is the explicit ACT-009 composition root. It
constructs durable activation, mapping-decision, normalization-run metadata,
analytical-plan, aggregation-result, lineage, reconciliation-binding, and
answer-reference adapters from the database. The existing
`ConfirmationService` can be reconstructed over
`DurableMappingDecisionRepository` and retains effective decisions plus
immutable history after the original service and repository objects are
discarded. ACT-007 bindings and ACT-008 answer references reload through their
scoped adapters. Missing database configuration raises an error; production
code is not silently replaced with an ephemeral authority.

## Restart and lifecycle contract

Records survive repository disposal and reconstruction. Currentness remains a
domain-service decision: persisted fingerprints and references must be compared
with current evidence, governance, normalization, capability, authorization,
materialization, reconciliation, and graph state before an answer is reused.
Persisted answer text is never treated as authority.

`ACTIVE`, `EXPIRED`, `PURGE_PENDING`, and `PURGED` are supported. Purging a
prospect/analysis removes its payloads, retains minimal non-sensitive tombstones,
and emits immutable audit events. Other scopes and canonical entities outside the
pilot lifecycle store are untouched. `app_main.py` invokes the normal startup
initializer, which runs the replay-safe migration before composition. A corrupt
or inaccessible configured database fails closed, and production refuses to
start the governed runtime without `NEXORA_UNIVERSAL_EVIDENCE_DB`.

## Deployment authority decision

SQLite is the certified durable authority for Universal Evidence under the
current single-node application deployment architecture. Existing enterprise
canonical entities and relationships remain in their established Data Fabric
repositories. A speculative parallel Supabase implementation would create two
authorities, so ACT-009 deliberately does not add one.

## Process-local authority audit

| Object | Classification | Reason |
| --- | --- | --- |
| Discovery/profile objects | DERIVED | Deterministically rebuilt from admitted evidence |
| Normalized row objects | DERIVED | Recomputed and checked against durable run fingerprint metadata |
| Capability assessments/authorizations | DERIVED | Re-evaluated from current governed normalized evidence |
| Pilot telemetry/audit sink facade | CACHE | Operational observations; lifecycle audit remains durable |
| Enterprise registry test fixtures | TEST_ONLY | Production canonical authority remains existing Data Fabric stores |
| In-memory repositories in unit fixtures | TEST_ONLY | Explicit dependency injection; absent from durable composition |
| Streamlit widget/session state | CACHE | Presentation state is never governance authority |

No required activation, semantic governance, plan/result history,
materialization lineage, reconciliation binding, or answer-reference authority
in the durable composition depends exclusively on process memory.

## Encryption and demo boundary

Raw prospect evidence remains under `services.prospect_data_intake_service` and
its approved `NEXORA_PROSPECT_DATA_KEY`/local development key behavior. ACT-009
does not persist raw bytes or keys and does not weaken missing-key fail-closed
behavior. Demo and production data are separate scopes; no demo records are
written by this repository unless explicitly supplied by a caller.

## Deliberate limitations

Normalized row payloads and capability assessment objects intentionally remain
derived and are recomputed after restart. Historical plans and results are
durable but never become current without domain revalidation. Raw evidence
retention scheduling and multi-node database selection remain deployment work;
they do not weaken the certified single-node restart contract.
