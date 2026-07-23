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
9. `0009_create_quality_assessments.sql`
10. `0010_create_ontology_concepts.sql`
11. `0011_create_ontology_relationships.sql`
12. `0012_create_semantic_mappings.sql`
13. `0013_create_idempotency_records.sql`
14. `0014_create_ontology_update_rpcs.sql`
15. `0015_create_semantic_mapping_update_rpc.sql`
16. `0016_create_idempotency_state_rpcs.sql`
17. `0017_create_atomic_entity_write_rpc.sql`
18. `0018_create_atomic_relationship_write_rpc.sql`
19. `0019_create_stewardship_persistence.sql`
20. `0020_create_stewardship_rpcs.sql`

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
- P3.15B atomic write RPCs use reviewed `SECURITY DEFINER`, safe `search_path`, schema-qualified references, revoked `PUBLIC` execute, and `service_role` execute grants
- atomic canonical write migrations are still manual deployment artifacts and are not wired to runtime startup
