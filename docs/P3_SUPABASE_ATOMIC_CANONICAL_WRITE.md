# P3 Supabase Atomic Canonical Write

## Purpose

P3.15B adds reviewed Supabase PostgreSQL RPC boundaries for canonical entity and relationship writes that must commit current state, append-only supporting records, and idempotency completion together.

Supabase REST calls are not treated as a multi-statement transaction boundary. Python invokes exactly one RPC per bundle through `SupabaseAtomicWriteExecutor`.

Runtime wiring remains disabled. No connector, dashboard, scheduler, service, or Knowledge Graph path consumes this boundary yet.

## RPC Boundaries

- `data_fabric.data_fabric_atomic_entity_write(p_request jsonb)`
- `data_fabric.data_fabric_atomic_relationship_write(p_request jsonb)`

Each RPC runs inside the PostgreSQL function transaction. Unhandled validation, constraint, revision, history, quality, lineage, provenance, or idempotency errors roll back all statements in the function.

## Entity Sequence

1. Validate organization and tenant.
2. Validate required request fields and operation.
3. Lock or create the tenant-scoped idempotency record.
4. Return completed replay for the same key and payload hash.
5. Reject the same key with a different payload hash.
6. Return deterministic `in_progress` for an active duplicate request.
7. Create, update, deactivate, or no-change the entity.
8. Enforce expected revision for update and deactivate.
9. Append an entity version when supplied and the operation is not `no_change`.
10. Append lineage events in request order.
11. Append provenance records in request order.
12. Append optional quality assessment.
13. Build deterministic result JSON.
14. Mark idempotency completed last.

## Relationship Sequence

The relationship RPC mirrors the entity sequence. It validates source and target entity IDs in the same organization and tenant before writing the relationship bundle.

Relationship-version history is deferred. The current persistence contracts include entity version snapshots, but they do not define a compatible relationship-version or temporal history record for this bundle. P3.15B does not create a competing model.

## Operations

- `create`: insert current state and reject duplicates through tenant-scoped database uniqueness.
- `update`: require `expected_revision`, tenant-filter the row, compare revision atomically, and increment once.
- `deactivate`: require `expected_revision`, soft deactivate, preserve history, and increment once.
- `no_change`: do not mutate current state or create version/history by default. Explicit lineage, provenance, or quality inputs may still be appended and documented in the deterministic result.

## Idempotency

Durable idempotency identity remains:

```text
organization_id + tenant_id + idempotency_key
```

Behavior:

- Same tenant, same key, same payload hash, completed: return stored result with `replayed=true`.
- Same tenant, same key, different payload hash: raise `P3_IDEMPOTENCY_CONFLICT`.
- Same tenant, same key, same hash, in_progress: return deterministic `in_progress`.
- Failed or expired records follow the existing retry policy by moving back to `in_progress` for the same hash.

Completion is written only after current-state and append-only writes succeed. A failed transaction cannot leave a completed idempotency record.

## Append-Only Records

Entity versions, lineage events, provenance records, and quality assessments remain append-only. Existing mutation-prevention triggers and repository update rejection remain in force.

Subject references in supplied lineage, provenance, and quality records must match the bundle subject and tenant context.

## Security Model

Both RPCs use `SECURITY DEFINER` for server-side service-role execution. The functions:

- set `search_path = data_fabric, pg_temp`
- schema-qualify table and function references
- revoke `PUBLIC` execute access
- grant execute only to `service_role`
- explicitly compare caller-supplied organization and tenant values on every lookup and write

RLS remains enabled on the underlying tables. Service-role execution is server-side only; repositories and executors still carry explicit tenant context.

## Error Mapping

The Python executor maps stable PostgreSQL error codes and failure payloads to Data Fabric errors:

| Code family | Python error |
| --- | --- |
| `P3_REVISION_CONFLICT` | `DataFabricConflictError` |
| `P3_TENANT_BOUNDARY` | `DataFabricTenantBoundaryError` |
| `P3_IDEMPOTENCY_CONFLICT` | `DataFabricIdempotencyError` |
| `P3_VALIDATION_ERROR` | `DataFabricValidationError` |
| other RPC or transaction failures | `DataFabricTransactionError` |

Error messages are redacted and do not include service-role values, credentials, or complete payloads.

## Python Executor

`SupabaseAtomicWriteExecutor` exposes:

- `execute_entity_write(request)`
- `execute_relationship_write(request)`

Request and result models are frozen. The executor serializes deterministically, invokes exactly one RPC, maps the response into `AtomicWriteResult`, and never calls individual repositories to simulate atomicity.

## Unit Of Work Limitation

`SupabaseDataFabricUnitOfWork` remains a state marker for isolated repository operations. It does not provide general multi-call REST transactions. The atomic executor is the only supported multi-record canonical-write path.

## Integration Testing

`tests/data_fabric/test_supabase_atomic_write_integration.py` is skipped by default. It requires explicit safe-test environment variables and refuses production-looking URLs. Migrations must be applied manually to a disposable Supabase test project.

## Operational Limitations

- No automatic migration execution.
- No bulk ingestion.
- No cross-tenant transaction.
- No ontology or semantic mutation inside canonical-write bundles.
- No runtime product path consumes this boundary until the P3 persistence certification checkpoint is complete.
