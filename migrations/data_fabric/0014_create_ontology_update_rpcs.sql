-- P3 Data Fabric migration 0014
-- Purpose: tenant-filtered optimistic concurrency RPCs for ontology records.
-- Safety: non-destructive create-or-replace functions; no credentials.
create or replace function data_fabric.data_fabric_update_ontology_concept(p_concept_id text,p_organization_id text,p_tenant_id text,p_expected_revision integer,p_concept jsonb)
returns setof data_fabric.ontology_concepts language sql security definer as $$
 update data_fabric.ontology_concepts set canonical_name=p_concept->>'canonical_name', normalized_canonical_name=p_concept->>'normalized_canonical_name', display_name=p_concept->>'display_name', description=p_concept->>'description', concept_type=p_concept->>'concept_type', parent_concept_id=p_concept->>'parent_concept_id', synonyms=coalesce(p_concept->'synonyms','[]'::jsonb), aliases=coalesce(p_concept->'aliases','[]'::jsonb), attributes=coalesce(p_concept->'attributes','{}'::jsonb), version=(p_concept->>'version')::integer, active=coalesce((p_concept->>'active')::boolean,true), revision=revision+1, updated_at=(p_concept->>'updated_at')::timestamptz, deactivated_at=nullif(p_concept->>'deactivated_at','')::timestamptz, deactivated_by=p_concept->>'deactivated_by', schema_version=coalesce((p_concept->>'schema_version')::integer,schema_version)
 where concept_id=p_concept_id and organization_id=p_organization_id and tenant_id=p_tenant_id and revision=p_expected_revision returning *;
$$;
create or replace function data_fabric.data_fabric_update_ontology_relationship(p_relationship_id uuid,p_organization_id text,p_tenant_id text,p_expected_revision integer,p_relationship jsonb)
returns setof data_fabric.ontology_relationships language sql security definer as $$
 update data_fabric.ontology_relationships set source_concept_id=p_relationship->>'source_concept_id', target_concept_id=p_relationship->>'target_concept_id', relationship_type=p_relationship->>'relationship_type', attributes=coalesce(p_relationship->'attributes','{}'::jsonb), active=coalesce((p_relationship->>'active')::boolean,true), revision=revision+1, updated_at=(p_relationship->>'updated_at')::timestamptz, deactivated_at=nullif(p_relationship->>'deactivated_at','')::timestamptz, schema_version=coalesce((p_relationship->>'schema_version')::integer,schema_version)
 where relationship_id=p_relationship_id and organization_id=p_organization_id and tenant_id=p_tenant_id and revision=p_expected_revision returning *;
$$;
