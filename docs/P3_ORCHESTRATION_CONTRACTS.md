# P3 Orchestration Contracts

## Purpose

P3.10B defines orchestration contracts for the Enterprise Data Fabric without adding persistence, dashboard wiring, connector runtime changes, schedulers, migrations, Supabase adapters, or Knowledge Graph integration.

The orchestration layer coordinates existing P3 responsibilities. It does not replace registry, identity, semantic, quality, lineage, provenance, or versioning packages.

## Architecture

The orchestration layer introduces two supporting packages:

| Package | Responsibility |
| --- | --- |
| `data_fabric.foundation` | Shared exception hierarchy, deterministic serialization, timezone validation, and tenant context. |
| `data_fabric.orchestration` | Request/result contracts, pipeline interfaces, quality/version/lineage policies, idempotency, unit-of-work, batch coordinator, and in-memory references. |

## Pipeline Sequence

The canonicalization pipeline exposes these explicit stages:

1. validate tenant context
2. validate source record
3. check idempotency
4. perform semantic mapping
5. perform identity resolution
6. construct or update canonical entity plan
7. evaluate data quality
8. apply quality gate
9. determine version creation
10. prepare lineage/provenance emission
11. prepare relationship writes
12. execute within unit-of-work boundary
13. record idempotency completion
14. return explainable result

Stage methods prepare plans and decisions first. They do not directly mutate registries or persistence stores.

## Responsibility Matrix

| Component | Responsibility |
| --- | --- |
| `IngestionCoordinator` | Coordinates single-record and batch workflows. |
| `CanonicalizationPipeline` | Produces write plans, decisions, lineage plans, and transaction results. |
| `SemanticMapper` | Maps source terms to semantic concepts. |
| `IdentityResolver` | Resolves canonical identity candidates. |
| `Registry` | Owns current canonical state outside this phase. |
| `QualityGatePolicy` | Decides allow, warning, quarantine, or reject outcomes. |
| `LineageEmissionPolicy` | Determines explainability events and provenance records. |
| `VersionCreationPolicy` | Determines initial, changed, skipped, forced, or rejected version behavior. |
| `UnitOfWork` | Protects atomic staging, commit, rollback, and tenant boundaries. |
| `IdempotencyStore` | Protects repeat processing within tenant scope. |

## Aggregate And Transaction Boundaries

The orchestration aggregate is a tenant-scoped ingestion request. Entity and relationship writes are represented as plans, then staged through a unit of work. The in-memory unit of work demonstrates atomic commit and rollback semantics but intentionally does not persist data.

Transaction rules:

- no partial committed write plan on failure
- idempotency completion happens only after successful commit
- rollback retains explainable failure information
- tenant context cannot change inside a transaction
- staged items remain isolated between units of work

## Idempotency Semantics

Idempotency state is keyed by organization, tenant, and idempotency key.

- same tenant, same key, same payload hash returns the previous successful result
- same key with a different payload hash raises an explicit conflict
- failed attempts may be retried
- in-progress, completed, failed, and expired states are represented
- no silent overwriting is allowed

## Quality Gate Lifecycle

`DefaultQualityGatePolicy` is deterministic and explainable:

| Condition | Outcome |
| --- | --- |
| Blocking quality issue | `reject` |
| Score below hard threshold | `quarantine` |
| Score below warning threshold | `allow_with_warning` |
| Otherwise | `allow` |

Reject and quarantine results do not commit write plans.

## Lineage Emission Lifecycle

`DefaultLineageEmissionPolicy` plans source, normalization, semantic mapping, identity resolution, canonicalization, quality assessment, version, relationship, rejection, and quarantine explainability decisions. The current lineage event contract supports source, normalization, canonicalization, and relationship event records; additional lifecycle decisions are represented as booleans on `LineageEmissionPlan` until persistence/event schemas are defined.

## Version Creation Lifecycle

`DefaultVersionCreationPolicy` uses deterministic payload hashing to decide:

- `create_initial_version`
- `create_changed_version`
- `skip_unchanged`
- `force_version`
- `reject_out_of_order`

This phase produces decisions only. It does not write version snapshots to a store.

## Batch Behavior

Batch processing is tenant-isolated and deterministic:

- input order is preserved in output records
- mixed tenant contexts are rejected
- fail-fast mode stops after the first failure
- continue-on-error mode preserves per-record results
- totals report processed successes and failures
- no hidden partial success is implied

## Tenant Isolation

`TenantContext` requires `organization_id` and `tenant_id`. Boundary checks reject records or transactions whose tenant context differs from the orchestration request.

## Failure And Rollback Behavior

Unit-of-work rollback clears staged operations and returns an explainable failure result. Failed idempotency attempts remain retryable according to the in-memory policy. Completed idempotency records replay only after successful commit.

## Extension Model

Persistence adapters can later implement the same interfaces. Service integration can later provide concrete registry, semantic, identity, quality, lineage, provenance, and version stores behind the orchestration contracts.

## Limitations

- No database or Supabase persistence is included.
- No migrations are included.
- No dashboard, connector runtime, scheduler, or Knowledge Graph wiring is included.
- Relationship write planning is represented but not yet derived from source payloads beyond the model contract.
- Version decisions are produced, but immutable snapshot storage remains deferred.

## Persistence Status

Persistence and runtime integration remain deferred. P3.10B resolves several orchestration blockers, but persistence architecture still needs repository boundaries, schema design, concurrency policy, and migration strategy.
