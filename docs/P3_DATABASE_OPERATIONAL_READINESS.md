# P3 Database Operational Readiness

## Purpose

Define operational readiness expectations for the future Supabase PostgreSQL Data Fabric adapter before implementation begins.

## Connection Management

The adapter must use the approved Nexora secrets and client patterns. Connection pooling strategy must be defined before load-bearing runtime integration.

## Observability

The adapter should expose operation-level observability for:

- repository operation name
- tenant scope without leaking sensitive ids in logs
- latency
- retries
- timeout failures
- conflict failures
- tenant-boundary failures
- transaction outcome

## Backup And Recovery

Data Fabric stores include current state and immutable history. Backup strategy must preserve both, with recovery objectives documented before production writes are enabled.

## Timeout Policy

Timeouts should be explicit by operation type:

- point lookup
- search/list
- transaction commit
- append-only write
- migration execution

## Retry Policy

Retry only transient failures. Do not silently retry validation, conflict, tenant-boundary, idempotency, or immutable-state errors.

## Security And Secrets

No new secrets are added in P3.12. Future adapter implementation must document required secrets, local development setup, CI secrets, and production secret rotation expectations.

## Deployment Readiness

Before runtime integration:

- migrations reviewed and applied in non-production
- compliance suite passes against real adapter
- RLS/tenant policy verified
- rollback tested
- observability enabled
- backup/recovery expectation documented

## Current Status

Operational readiness is defined, but implementation remains deferred.
