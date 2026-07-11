-- P3 Data Fabric migration 0015
-- Purpose: tenant-filtered optimistic concurrency RPC for semantic mappings.
-- Safety: non-destructive create-or-replace function; no credentials.
create or replace function data_fabric.data_fabric_update_semantic_mapping(p_mapping_id uuid,p_organization_id text,p_tenant_id text,p_expected_revision integer,p_mapping jsonb)
returns setof data_fabric.semantic_mappings language sql security definer set search_path = data_fabric, pg_temp as $$
 update data_fabric.semantic_mappings set source_system=p_mapping->>'source_system', source_term=p_mapping->>'source_term', source_type=p_mapping->>'source_type', source_identifier=p_mapping->>'source_identifier', provider=p_mapping->>'provider', entity_type=p_mapping->>'entity_type', concept_id=p_mapping->>'concept_id', confidence_score=(p_mapping->>'confidence_score')::numeric, mapping_strategy=p_mapping->>'mapping_strategy', explanation=coalesce(p_mapping->'explanation','{}'::jsonb), attributes=coalesce(p_mapping->'attributes','{}'::jsonb), active=coalesce((p_mapping->>'active')::boolean,true), revision=revision+1, updated_at=(p_mapping->>'updated_at')::timestamptz, deactivated_at=nullif(p_mapping->>'deactivated_at','')::timestamptz, schema_version=coalesce((p_mapping->>'schema_version')::integer,schema_version)
 where mapping_id=p_mapping_id and organization_id=p_organization_id and tenant_id=p_tenant_id and revision=p_expected_revision returning *;
$$;
revoke all on function data_fabric.data_fabric_update_semantic_mapping(uuid, text, text, integer, jsonb) from public;
grant execute on function data_fabric.data_fabric_update_semantic_mapping(uuid, text, text, integer, jsonb) to service_role;
