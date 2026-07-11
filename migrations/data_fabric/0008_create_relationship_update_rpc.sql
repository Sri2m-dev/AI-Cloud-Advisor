-- P3 Data Fabric migration 0008
-- Purpose: atomic relationship update with optimistic revision check.
-- Safety: non-destructive create-or-replace function; no credentials.

create or replace function data_fabric.data_fabric_update_enterprise_relationship(
    p_relationship_id uuid,
    p_organization_id text,
    p_tenant_id text,
    p_expected_revision integer,
    p_relationship jsonb
)
returns setof data_fabric.enterprise_relationships
language sql
security definer
set search_path = data_fabric, pg_temp
as $$
    update data_fabric.enterprise_relationships
    set
        source_entity_id = (p_relationship->>'source_entity_id')::uuid,
        target_entity_id = (p_relationship->>'target_entity_id')::uuid,
        relationship_type = p_relationship->>'relationship_type',
        source_system = p_relationship->>'source_system',
        source_identifier = p_relationship->>'source_identifier',
        confidence_score = nullif(p_relationship->>'confidence_score', '')::numeric,
        quality_score = nullif(p_relationship->>'quality_score', '')::numeric,
        metadata = coalesce(p_relationship->'metadata', '{}'::jsonb),
        active = coalesce((p_relationship->>'active')::boolean, true),
        revision = revision + 1,
        version = coalesce((p_relationship->>'version')::integer, version),
        updated_at = (p_relationship->>'updated_at')::timestamptz,
        deactivated_at = nullif(p_relationship->>'deactivated_at', '')::timestamptz,
        deactivated_by = p_relationship->>'deactivated_by',
        updated_by = p_relationship->>'updated_by',
        schema_version = coalesce((p_relationship->>'schema_version')::integer, schema_version)
    where id = p_relationship_id
      and organization_id = p_organization_id
      and tenant_id = p_tenant_id
      and revision = p_expected_revision
    returning *;
$$;

comment on function data_fabric.data_fabric_update_enterprise_relationship(uuid, text, text, integer, jsonb) is 'Atomic P3 relationship update with tenant filter and optimistic revision check.';

revoke all on function data_fabric.data_fabric_update_enterprise_relationship(uuid, text, text, integer, jsonb) from public;
grant execute on function data_fabric.data_fabric_update_enterprise_relationship(uuid, text, text, integer, jsonb) to service_role;
