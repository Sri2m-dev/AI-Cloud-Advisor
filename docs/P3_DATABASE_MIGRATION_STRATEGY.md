# P3 Database Migration Strategy

## Purpose

Define the migration strategy for the future Supabase PostgreSQL adapter without creating migration files in P3.12.

## Migration Tooling

Use Supabase/Postgres migration tooling aligned with the existing repository `supabase/` structure. The exact command and file naming convention must be confirmed in the implementation phase before migration files are created.

## Schema Namespace Strategy

Preferred namespace: a dedicated Data Fabric schema or clearly prefixed public tables, depending on Supabase policy compatibility. The design preference is a dedicated `data_fabric` schema when supported by RLS, grants, and operational tooling.

## Migration Phases

1. Control tables: idempotency and transaction audit.
2. Current-state entity and relationship tables.
3. Immutable version and temporal history tables.
4. Lineage and provenance tables.
5. Quality assessment tables.
6. Semantic ontology and mapping tables.
7. Indexes, constraints, and RLS policies.
8. Seed/fixture data only where approved.

## Rollback Policy

Every migration must include a rollback plan. Rollback must preserve immutable audit/history records unless the migration failed before production traffic used them.

## Tenant Policy

Every tenant-scoped table must include `organization_id` and `tenant_id`. RLS or equivalent Postgres policy must prevent cross-tenant reads and writes. Application-level tenant checks are required but not sufficient.

## Concurrency Policy

Mutable current-state tables require a revision column. Updates must compare expected revision and advance revision on success.

## JSONB Policy

Use JSONB for deterministic payloads and flexible metadata. Store all fields needed for filtering, joins, uniqueness, and ordering as normalized columns.

## Migration Readiness Gate

No migration file should be created until ADR-017 and this strategy are reviewed and merged.
