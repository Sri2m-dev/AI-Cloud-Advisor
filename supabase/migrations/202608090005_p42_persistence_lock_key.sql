begin;

create or replace function public.p42_save_inferred_classification(
 requested_organization_id uuid, requested_result jsonb
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public as $$
declare current_row public.classification_result%rowtype;
 result_row public.classification_result%rowtype;
 next_version integer; evidence_id text; approved_protected boolean := false;
begin
 if not public.pvt003c1_can_read_organization(requested_organization_id) then
  raise insufficient_privilege using message='organization membership required';
 end if;
 if requested_result->>'organization_id' <> requested_organization_id::text
  or requested_result->>'tenant_id' <> requested_organization_id::text then
  raise insufficient_privilege using message='classification tenant scope mismatch';
 end if;
 if requested_result->>'inference_status' not in ('NEEDS_REVIEW','RESOLVED_INFERRED')
  or requested_result->>'approval_status' not in ('UNAPPROVED','NEEDS_APPROVAL') then
  raise insufficient_privilege using message='inference service has no approval authority';
 end if;
 perform pg_advisory_xact_lock(hashtextextended(
  requested_organization_id::text||':'||(requested_result->>'entity_type')||':'||
  (requested_result->>'entity_id')||':'||(requested_result->>'field_name'),0));
 select * into current_row from public.classification_result
 where organization_id=requested_organization_id and tenant_id=requested_organization_id
  and entity_type=requested_result->>'entity_type' and entity_id=requested_result->>'entity_id'
  and field_name=requested_result->>'field_name' and valid_to is null
 order by version desc limit 1 for update;
 if found and current_row.evidence_set_hash=requested_result->>'evidence_set_hash'
  and current_row.policy_version=(requested_result->>'policy_version')::integer then
  return to_jsonb(current_row);
 end if;
 select exists(select 1 from public.classification_result
  where organization_id=requested_organization_id and tenant_id=requested_organization_id
   and entity_type=requested_result->>'entity_type' and entity_id=requested_result->>'entity_id'
   and field_name=requested_result->>'field_name' and valid_to is null
   and approval_status in ('APPROVED','AUTO_APPROVED')) into approved_protected;
 next_version := coalesce(current_row.version,0)+1;
 insert into public.classification_result(
  id,organization_id,tenant_id,entity_type,entity_id,field_name,inferred_value,
  confidence_score,inference_method,inference_status,policy_version,engine_version,
  evidence_set_hash,source_timestamp,valid_from,approval_status,version,
  candidate_values,conflict,review_reason
 ) values (
  (requested_result->>'id')::uuid,requested_organization_id,requested_organization_id,
  requested_result->>'entity_type',requested_result->>'entity_id',requested_result->>'field_name',
  requested_result->>'inferred_value',(requested_result->>'confidence_score')::numeric,
  requested_result->>'inference_method',case when approved_protected then 'NEEDS_REVIEW'
   else requested_result->>'inference_status' end,
  (requested_result->>'policy_version')::integer,requested_result->>'engine_version',
  requested_result->>'evidence_set_hash',(requested_result->>'source_timestamp')::timestamptz,
  (requested_result->>'valid_from')::timestamptz,requested_result->>'approval_status',
  next_version,coalesce(requested_result->'candidate_values','{}'::jsonb),
  coalesce((requested_result->>'conflict')::boolean,false),case when approved_protected
   then 'new evidence conflicts with protected approved value'
   else requested_result->>'review_reason' end
 ) returning * into result_row;
 if current_row.id is not null and not approved_protected then
  update public.classification_result set valid_to=result_row.valid_from,superseded_by=result_row.id,
   inference_status='SUPERSEDED' where id=current_row.id;
 end if;
 for evidence_id in select jsonb_array_elements_text(
  coalesce(requested_result->'evidence_ids','[]'::jsonb)
 ) loop
  insert into public.classification_evidence_link(
   classification_result_id,organization_id,tenant_id,evidence_id,evidence_hash
  ) values(result_row.id,requested_organization_id,requested_organization_id,evidence_id,evidence_id)
  on conflict do nothing;
 end loop;
 return to_jsonb(result_row);
end $$;

commit;
