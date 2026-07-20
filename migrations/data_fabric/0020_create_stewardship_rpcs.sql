-- WP-005 atomic stewardship RPCs. Manual application only.
create or replace function data_fabric.stewardship_create_review(p_request jsonb) returns jsonb
language plpgsql security definer set search_path=data_fabric,pg_temp as $$
declare v_org text:=p_request#>>'{tenant_context,organization_id}'; v_tenant text:=p_request#>>'{tenant_context,tenant_id}';
 v_actor text:=p_request#>>'{authorization,subject_id}'; v_key text:=p_request->>'idempotency_key'; v_hash text:=p_request->>'payload_hash';
 v_corr text:=p_request->>'correlation_id'; v_item jsonb:=p_request->'review_item'; v_id uuid; v_existing data_fabric.stewardship_audit_events%rowtype;
begin
 if v_org is null or v_tenant is null or v_actor is null or v_key is null or v_hash is null or v_corr is null then raise exception 'WP005_VALIDATION: scoped authorization, idempotency, hash, and correlation are required'; end if;
 if p_request#>>'{authorization,state}' <> 'authorized' or not coalesce(p_request#>'{authorization,permissions}','[]') ? 'stewardship.review.create' then raise exception 'WP005_AUTHORIZATION: create permission required'; end if;
 if v_item->>'organization_id' <> v_org or v_item->>'tenant_id' <> v_tenant then raise exception 'WP005_TENANT_BOUNDARY: review crosses tenant scope'; end if;
 select * into v_existing from data_fabric.stewardship_audit_events where organization_id=v_org and tenant_id=v_tenant and idempotency_key=v_key;
 if found then
  if v_existing.payload_hash<>v_hash then raise exception 'WP005_IDEMPOTENCY_CONFLICT: key reused with different payload'; end if;
  return jsonb_build_object('review_id',v_existing.review_id,'state',v_existing.to_state,'revision',1,'replayed',true);
 end if;
 insert into data_fabric.stewardship_review_items(review_id,organization_id,tenant_id,review_key,review_type,domain,subject_type,subject_id,state,assigned_role,evidence_references,payload,payload_hash,created_by,updated_by)
 values(coalesce((v_item->>'review_id')::uuid,gen_random_uuid()),v_org,v_tenant,v_item->>'review_key',v_item->>'review_type',v_item->>'domain',v_item->>'subject_type',v_item->>'subject_id','discovered',v_item->>'assigned_role',coalesce(v_item->'evidence_references','[]'),coalesce(v_item->'payload','{}'),v_hash,v_actor,v_actor)
 returning review_id into v_id;
 insert into data_fabric.stewardship_audit_events(review_id,organization_id,tenant_id,event_type,to_state,actor,rationale,evidence_references,correlation_id,idempotency_key,payload_hash)
 values(v_id,v_org,v_tenant,'review_created','discovered',v_actor,p_request->>'rationale',coalesce(v_item->'evidence_references','[]'),v_corr,v_key,v_hash);
 return jsonb_build_object('review_id',v_id,'state','discovered','revision',1,'replayed',false);
end $$;

create or replace function data_fabric.stewardship_transition_review(p_request jsonb) returns jsonb
language plpgsql security definer set search_path=data_fabric,pg_temp as $$
declare v_org text:=p_request#>>'{tenant_context,organization_id}'; v_tenant text:=p_request#>>'{tenant_context,tenant_id}';
 v_actor text:=p_request#>>'{authorization,subject_id}'; v_key text:=p_request->>'idempotency_key'; v_hash text:=p_request->>'payload_hash'; v_corr text:=p_request->>'correlation_id';
 v_id uuid:=(p_request->>'review_id')::uuid; v_expected integer:=(p_request->>'expected_revision')::integer; v_target text:=p_request->>'target_state';
 v_current data_fabric.stewardship_review_items%rowtype; v_existing data_fabric.stewardship_audit_events%rowtype; v_from text;
begin
 if v_org is null or v_tenant is null or v_actor is null or v_key is null or v_hash is null or v_corr is null or v_id is null or v_expected is null or v_target is null then raise exception 'WP005_VALIDATION: transition fields are required'; end if;
 if p_request#>>'{authorization,state}' <> 'authorized' or not coalesce(p_request#>'{authorization,permissions}','[]') ? 'stewardship.review.transition' then raise exception 'WP005_AUTHORIZATION: transition permission required'; end if;
 select * into v_existing from data_fabric.stewardship_audit_events where organization_id=v_org and tenant_id=v_tenant and idempotency_key=v_key;
 if found then
  if v_existing.payload_hash<>v_hash then raise exception 'WP005_IDEMPOTENCY_CONFLICT: key reused with different payload'; end if;
  select * into v_current from data_fabric.stewardship_review_items where review_id=v_existing.review_id and organization_id=v_org and tenant_id=v_tenant;
  return jsonb_build_object('review_id',v_current.review_id,'state',v_current.state,'revision',v_current.revision,'replayed',true);
 end if;
 select * into v_current from data_fabric.stewardship_review_items where review_id=v_id and organization_id=v_org and tenant_id=v_tenant for update;
 if not found then raise exception 'WP005_NOT_FOUND: scoped review not found'; end if;
 if v_current.revision<>v_expected then raise exception 'WP005_REVISION_CONFLICT: stale revision'; end if;
 if not case v_current.state when 'discovered' then v_target in ('classified','rejected') when 'classified' then v_target in ('under_review','rejected') when 'under_review' then v_target in ('steward_approved','rejected') when 'steward_approved' then v_target in ('canonical','rejected') when 'canonical' then v_target='superseded' when 'superseded' then v_target='archived' else false end then raise exception 'WP005_INVALID_TRANSITION: lifecycle edge rejected'; end if;
 v_from:=v_current.state;
 update data_fabric.stewardship_review_items set state=v_target,revision=revision+1,updated_at=now(),updated_by=v_actor,active=(v_target not in ('archived','rejected')) where review_id=v_id and organization_id=v_org and tenant_id=v_tenant returning * into v_current;
 insert into data_fabric.stewardship_audit_events(review_id,organization_id,tenant_id,event_type,from_state,to_state,actor,rationale,evidence_references,correlation_id,idempotency_key,payload_hash)
 values(v_id,v_org,v_tenant,'state_transition',v_from,v_target,v_actor,p_request->>'rationale',coalesce(p_request->'evidence_references','[]'),v_corr,v_key,v_hash);
 return jsonb_build_object('review_id',v_id,'state',v_current.state,'revision',v_current.revision,'replayed',false);
end $$;

revoke all on function data_fabric.stewardship_create_review(jsonb) from public;
revoke all on function data_fabric.stewardship_transition_review(jsonb) from public;
grant execute on function data_fabric.stewardship_create_review(jsonb) to service_role;
grant execute on function data_fabric.stewardship_transition_review(jsonb) to service_role;
