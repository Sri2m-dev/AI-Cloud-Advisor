# P3 Transaction And Idempotency Model

## Purpose

Define transaction and idempotency semantics for future Data Fabric persistence adapters.

## Transaction Boundary

The orchestration unit of work is the only valid boundary for writes spanning current state, history, quality, lineage, provenance, and idempotency.

A durable transaction must include:

- current-state entity and relationship writes
- version snapshot writes when required
- temporal history writes when required
- lineage event writes
- provenance record writes
- quality assessment writes
- transaction audit writes
- idempotency completion after successful commit

## Atomicity Rules

- No partial committed write plan on failure.
- Rollback must leave current state unchanged.
- Idempotency completion must not occur before commit.
- Transaction failure must be explainable in audit state.
- Staged writes from different units of work must remain isolated.
- Tenant context cannot change inside a transaction.

## Idempotency Key

Durable idempotency identity is:

```text
organization_id + tenant_id + idempotency_key
```

The idempotency record stores:

- payload hash
- state: `in_progress`, `completed`, `failed`, `expired`
- request id
- correlation id
- started timestamp
- completed timestamp
- result reference
- failure reason

## Replay Rules

| Condition | Result |
| --- | --- |
| Same tenant, same key, same payload hash, completed | Return previous result. |
| Same tenant, same key, different payload hash | Raise conflict. |
| Same key in another tenant | Isolated record; no collision. |
| Failed attempt, same payload hash | Retry according to policy. |
| In-progress attempt | Return conflict or retry-after decision; no silent overwrite. |
| Expired record | Retry only if retention policy permits. |

## Optimistic Concurrency

Current-state updates require expected row version. A mismatch raises `DataFabricConflictError` or a package-specific subtype.

Immutable records do not use optimistic concurrency for mutation because they are append-only.

## Rollback Strategy

Rollback must record an audit event that includes:

- transaction id
- tenant context
- request id
- staged operation counts
- failure reason
- rollback timestamp

Rollback must not write entity, relationship, snapshot, lineage, provenance, or quality rows except transaction audit if the durable store supports independent audit writes.

## Batch Transactions

Batch mode can use either one transaction per record or an outer batch transaction depending on implementation phase. The initial persistence implementation should prefer one transaction per record to preserve continue-on-error semantics.

Fail-fast batch mode stops after the first failed record. Continue-on-error mode preserves deterministic per-record results.
