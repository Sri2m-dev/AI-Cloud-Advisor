# P3 Database Test Strategy

## Purpose

Define how a future Supabase PostgreSQL adapter will be tested without adding database code in P3.12.

## Test Layers

| Layer | Purpose |
| --- | --- |
| Unit tests | Mapper and error translation behavior without network/database. |
| Compliance tests | Reuse P3.11 repository compliance suites against the adapter. |
| Integration tests | Validate real Supabase/Postgres behavior in isolated test database. |
| Migration tests | Apply and rollback migrations in disposable database. |
| Tenant isolation tests | Prove RLS and repository tenant filters both prevent cross-tenant access. |
| Transaction tests | Prove atomic commit, rollback, idempotency completion, and no partial writes. |

## Local Test Strategy

Use either local Supabase or a PostgreSQL-compatible container. Local tests must not depend on production credentials.

## CI Test Strategy

CI should run unit and compliance tests by default. Database-backed tests should run in a controlled job with disposable credentials and isolated schema/database.

## Fixtures

Fixtures must create tenant-scoped data for at least two tenants and validate no cross-tenant aggregation or mutation occurs.

## Compliance Suite Requirements

The future adapter must pass:

- repository compliance suite
- mutable repository compliance suite
- append-only repository compliance suite
- temporal repository compliance suite
- tenant isolation compliance suite
- transaction compliance suite

## Non-Goals In P3.12

No containers, fixtures, database clients, migrations, or adapter test code are added in this phase.
