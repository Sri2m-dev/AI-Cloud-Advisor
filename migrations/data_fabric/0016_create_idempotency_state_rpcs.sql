-- P3 Data Fabric migration 0016
-- Purpose: atomic tenant-scoped idempotency reservation and state transitions.
-- Safety: non-destructive create-or-replace functions; no credentials.
create or replace function data_fabric.data_fabric_reserve_idempotency_key(p_organization_id text,p_tenant_id text,p_idempotency_key text,p_payload_hash text,p_correlation_id text default null,p_expires_at timestamptz default null)
returns setof data_fabric.idempotency_records language plpgsql security definer set search_path = data_fabric, pg_temp as $$
declare existing data_fabric.idempotency_records%rowtype;
begin
 select * into existing from data_fabric.idempotency_records where organization_id=p_organization_id and tenant_id=p_tenant_id and idempotency_key=p_idempotency_key for update;
 if not found then
  return query insert into data_fabric.idempotency_records(organization_id,tenant_id,idempotency_key,payload_hash,status,reserved_at,correlation_id,expires_at) values(p_organization_id,p_tenant_id,p_idempotency_key,p_payload_hash,'in_progress',now(),p_correlation_id,p_expires_at) returning *;
  return;
 end if;
 if existing.payload_hash <> p_payload_hash then return; end if;
 if existing.status in ('completed','in_progress') then return query select * from data_fabric.idempotency_records where record_id=existing.record_id; return; end if;
 update data_fabric.idempotency_records set status='in_progress', failure_reason=null, failed_at=null, revision=revision+1 where record_id=existing.record_id returning * into existing;
 return query select * from data_fabric.idempotency_records where record_id=existing.record_id;
end; $$;
create or replace function data_fabric.data_fabric_complete_idempotency_key(p_organization_id text,p_tenant_id text,p_idempotency_key text,p_result_payload jsonb)
returns setof data_fabric.idempotency_records language sql security definer set search_path = data_fabric, pg_temp as $$
 update data_fabric.idempotency_records set status='completed', result_payload=p_result_payload, completed_at=now(), revision=revision+1 where organization_id=p_organization_id and tenant_id=p_tenant_id and idempotency_key=p_idempotency_key and status='in_progress' returning *;
$$;
create or replace function data_fabric.data_fabric_fail_idempotency_key(p_organization_id text,p_tenant_id text,p_idempotency_key text,p_failure_reason text)
returns setof data_fabric.idempotency_records language sql security definer set search_path = data_fabric, pg_temp as $$
 update data_fabric.idempotency_records set status='failed', failure_reason=p_failure_reason, failed_at=now(), revision=revision+1 where organization_id=p_organization_id and tenant_id=p_tenant_id and idempotency_key=p_idempotency_key and status='in_progress' returning *;
$$;
create or replace function data_fabric.data_fabric_expire_idempotency_key(p_organization_id text,p_tenant_id text,p_idempotency_key text)
returns setof data_fabric.idempotency_records language sql security definer set search_path = data_fabric, pg_temp as $$
 update data_fabric.idempotency_records set status='expired', expires_at=coalesce(expires_at,now()), revision=revision+1 where organization_id=p_organization_id and tenant_id=p_tenant_id and idempotency_key=p_idempotency_key and status in ('in_progress','failed') returning *;
$$;
revoke all on function data_fabric.data_fabric_reserve_idempotency_key(text, text, text, text, text, timestamptz) from public;
grant execute on function data_fabric.data_fabric_reserve_idempotency_key(text, text, text, text, text, timestamptz) to service_role;
revoke all on function data_fabric.data_fabric_complete_idempotency_key(text, text, text, jsonb) from public;
grant execute on function data_fabric.data_fabric_complete_idempotency_key(text, text, text, jsonb) to service_role;
revoke all on function data_fabric.data_fabric_fail_idempotency_key(text, text, text, text) from public;
grant execute on function data_fabric.data_fabric_fail_idempotency_key(text, text, text, text) to service_role;
revoke all on function data_fabric.data_fabric_expire_idempotency_key(text, text, text) from public;
grant execute on function data_fabric.data_fabric_expire_idempotency_key(text, text, text) to service_role;
