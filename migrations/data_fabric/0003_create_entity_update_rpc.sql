-- P3 Data Fabric migration 0003
-- Purpose: atomic entity update with optimistic revision check.
-- Safety: non-destructive create-or-replace function; no credentials.

create or replace function data_fabric.data_fabric_update_enterprise_entity(
    p_entity_id text,
    p_organization_id text,
    p_tenant_id text,
    p_expected_revision integer,
    p_entity jsonb
)
returns setof data_fabric.enterprise_entities
language sql
security definer
as $$
    update data_fabric.enterprise_entities
    set
        canonical_id = p_entity->>'canonical_id',
        entity_type = p_entity->>'entity_type',
        name = p_entity->>'name',
        source_system = p_entity->>'source_system',
        source_identifier = p_entity->>'source_identifier',
        version = (p_entity->>'version')::integer,
        confidence_score = nullif(p_entity->>'confidence_score', '')::numeric,
        quality_score = nullif(p_entity->>'quality_score', '')::numeric,
        tags = coalesce(p_entity->'tags', '[]'::jsonb),
        metadata = coalesce(p_entity->'metadata', '{}'::jsonb),
        active = coalesce((p_entity->>'active')::boolean, true),
        revision = revision + 1,
        updated_at = (p_entity->>'updated_at')::timestamptz,
        deactivated_at = nullif(p_entity->>'deactivated_at', '')::timestamptz,
        deactivated_by = p_entity->>'deactivated_by',
        updated_by = p_entity->>'updated_by',
        schema_version = coalesce((p_entity->>'schema_version')::integer, schema_version)
    where id = p_entity_id
      and organization_id = p_organization_id
      and tenant_id = p_tenant_id
      and revision = p_expected_revision
    returning *;
$$;

comment on function data_fabric.data_fabric_update_enterprise_entity(text, text, text, integer, jsonb) is 'Atomic P3 entity update with tenant filter and optimistic revision check.';
