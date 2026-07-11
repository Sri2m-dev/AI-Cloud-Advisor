# Data Fabric Migrations

P3 migration files are reviewed SQL artifacts. They are not executed automatically by application startup, dashboards, connectors, schedulers, or Knowledge Graph code.

## Order

1. `0001_create_data_fabric_schema.sql`
2. `0002_create_enterprise_entities.sql`
3. `0003_create_entity_update_rpc.sql`
4. `0004_create_enterprise_relationships.sql`
5. `0005_create_entity_versions.sql`
6. `0006_create_lineage_events.sql`
7. `0007_create_provenance_records.sql`
8. `0008_create_relationship_update_rpc.sql`

## Manual Application

Apply migrations only from an approved deployment or test-environment migration process. Use test-only Supabase projects for integration validation. Never run these migrations from app startup or client-facing runtime paths.

## Prerequisites

- Supabase PostgreSQL project approved for Data Fabric testing or deployment.
- Server-side service-role credentials stored in secure server secret storage.
- No browser, dashboard, connector, or client-side access to service-role credentials.

## Rollback Guidance

These migrations are additive and non-destructive. Rollback should be handled by disabling the adapter path, restoring from database backup where required, or applying a reviewed forward migration. Do not cascade-delete append-only history.

## Safety Rules

- no destructive SQL
- no hardcoded credentials
- no production URLs
- no automatic runtime execution
- RLS enabled with no anonymous access policies in these foundation migrations
- repositories still apply organization and tenant filters explicitly
