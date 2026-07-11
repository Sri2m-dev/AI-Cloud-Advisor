# P3.15A Supabase Governance, Semantic And Idempotency Adapter

## Purpose

P3.15A extends the Data Fabric Supabase adapter with governance, semantic, and idempotency persistence only. Runtime wiring remains disabled.

Implemented tables:

- `quality_assessments`
- `ontology_concepts`
- `ontology_relationships`
- `semantic_mappings`
- `idempotency_records`

## Repository Classification

`quality_assessments` is append-only history. Repository update is unsupported and database triggers prevent UPDATE and DELETE.

`ontology_concepts`, `ontology_relationships`, and `semantic_mappings` are mutable current-state stores with tenant-filtered optimistic-concurrency RPCs.

`idempotency_records` is mutable only through explicit atomic state-transition RPCs. Direct update/deactivate is unsupported.

## Idempotency State Machine

Supported states are `in_progress`, `completed`, `failed`, and `expired`. Reservation behavior is atomic:

- absent key creates `in_progress`
- same key and same hash returns existing `in_progress` or `completed` state
- same key with a different hash conflicts
- failed or expired records may be explicitly reserved again as `in_progress`
- no scheduler-based expiry is introduced

## RLS And Tenant Isolation

All new tables enable RLS with no anonymous policy. Repositories still apply explicit `organization_id` and `tenant_id` filters on every read/write path.

## Transaction Boundary

P3.15A does not implement the canonical write bundle RPC. That remains deferred to P3.15B after these repositories are merged and stable.

## Testing Strategy

Unit tests use fake Supabase clients. Integration tests are environment-gated and skip unless explicit safe test credentials are configured.

## Decision

P3.15A is **GO WITH CONDITIONS** for review as a repository expansion. It is not approval to wire these repositories into product runtime paths.
