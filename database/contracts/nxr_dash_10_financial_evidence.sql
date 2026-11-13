-- NXR-DASH-10 standalone implementation candidate; NOT a production migration.
-- No manifest registration, role provisioning, SECURITY DEFINER or runtime grants.
-- D1-D8 remain pending. Installation only into an explicitly authorized isolated database.
begin;
create schema financial_evidence;
create table financial_evidence.source_attestation (

    organization_id uuid not null,
    tenant_id uuid not null,
    import_id uuid not null, attestation_id uuid not null,
    retained_evidence_ref text not null check (length(retained_evidence_ref)>0),
    retained_evidence_sha256 text not null check (retained_evidence_sha256 ~ '^[0-9a-f]{64}$'),
    source_file_sha256 text not null check (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    payer_account_id text not null, currency_code text not null check (currency_code ~ '^[A-Z]{3}$'),
    parser_contract text not null, attester_id text not null,
    billing_period_start date not null, billing_period_end date not null,
    source_row_count bigint not null check (source_row_count>0),
    source_cost_total numeric(24,10) not null,
    attested_at timestamptz not null,
    attestation_status text not null check (attestation_status in ('verified','revoked')),
    primary key (organization_id,tenant_id,attestation_id),
    unique (organization_id,tenant_id,import_id),
    unique (organization_id,tenant_id,import_id,attestation_id),
    foreign key (organization_id,tenant_id,import_id) references
        public.cloud_cost_import(organization_id,tenant_id,import_id) on delete restrict,
    check (billing_period_start<=billing_period_end),
    foreign key (organization_id,tenant_id) references
        public.cloud_cost_tenant_scope(organization_id,tenant_id) on delete restrict,
    check (organization_id=tenant_id)
);
alter table financial_evidence.source_attestation enable row level security;
alter table financial_evidence.source_attestation force row level security;
create table financial_evidence.operation_authorization_grant (

    organization_id uuid not null,
    tenant_id uuid not null,
    grant_id uuid not null, actor_auth_uid uuid not null references auth.users(id) on delete restrict,
    permission text not null check (permission in ('read','refresh')),
    request_fingerprint text not null check (request_fingerprint ~ '^[0-9a-f]{64}$'),
    issued_at timestamptz not null, expires_at timestamptz not null,
    revoked_at timestamptz, issuer_id text not null,
    primary key (organization_id,tenant_id,grant_id),
    unique (organization_id,tenant_id,grant_id,actor_auth_uid),
    check (expires_at>issued_at), check (revoked_at is null or revoked_at>=issued_at),
    foreign key (organization_id,tenant_id) references
        public.cloud_cost_tenant_scope(organization_id,tenant_id) on delete restrict,
    check (organization_id=tenant_id)
);
alter table financial_evidence.operation_authorization_grant enable row level security;
alter table financial_evidence.operation_authorization_grant force row level security;
create table financial_evidence.projection_generation (
    creation_transaction xid8 not null default pg_current_xact_id(),

    organization_id uuid not null,
    tenant_id uuid not null,
    generation_id uuid not null, request_id uuid not null, trigger_import_id uuid not null,
    authorization_grant_id uuid not null,
    actor_auth_uid uuid not null references auth.users(id) on delete restrict,
    previous_generation_id uuid,
    currency text not null check (currency ~ '^[A-Z]{3}$'),
    period_start date not null, period_end date not null, spanning_periods boolean not null,
    requested_import_ids uuid[] not null,
    request_fingerprint text not null check (request_fingerprint ~ '^[0-9a-f]{64}$'),
    input_digest text not null check (input_digest ~ '^[0-9a-f]{64}$'),
    input_snapshot_id text not null, published_at timestamptz not null,
    status text not null check (status='published'),
    posture jsonb not null, total numeric(24,10) not null,
    primary key (organization_id,tenant_id,generation_id),
    unique (organization_id,tenant_id,request_id),
    unique (organization_id,tenant_id,currency,period_start,period_end,spanning_periods,generation_id),
    foreign key (organization_id,tenant_id,trigger_import_id) references
        public.cloud_cost_import(organization_id,tenant_id,import_id) on delete restrict,
    foreign key (organization_id,tenant_id,previous_generation_id) references
        financial_evidence.projection_generation(organization_id,tenant_id,generation_id) on delete restrict,
    foreign key (organization_id,tenant_id,authorization_grant_id,actor_auth_uid) references
        financial_evidence.operation_authorization_grant(organization_id,tenant_id,grant_id,actor_auth_uid) on delete restrict,
    check (previous_generation_id is null or previous_generation_id<>generation_id),
    check (period_start<=period_end),
    check (trigger_import_id=any(requested_import_ids)),
    check (cardinality(requested_import_ids)>0 and array_position(requested_import_ids,null) is null),
    check (jsonb_typeof(posture)='object'),
    foreign key (organization_id,tenant_id) references
        public.cloud_cost_tenant_scope(organization_id,tenant_id) on delete restrict,
    check (organization_id=tenant_id)
);
alter table financial_evidence.projection_generation enable row level security;
alter table financial_evidence.projection_generation force row level security;
create table financial_evidence.published_generation_pointer (

    organization_id uuid not null,
    tenant_id uuid not null,
    currency text not null check (currency ~ '^[A-Z]{3}$'),
    period_start date not null, period_end date not null, spanning_periods boolean not null,
    generation_id uuid not null,
    primary key (organization_id,tenant_id,currency,period_start,period_end,spanning_periods),
    foreign key (organization_id,tenant_id,currency,period_start,period_end,spanning_periods,generation_id)
        references financial_evidence.projection_generation
        (organization_id,tenant_id,currency,period_start,period_end,spanning_periods,generation_id) on delete restrict,
    check (period_start<=period_end),
    foreign key (organization_id,tenant_id) references
        public.cloud_cost_tenant_scope(organization_id,tenant_id) on delete restrict,
    check (organization_id=tenant_id)
);
alter table financial_evidence.published_generation_pointer enable row level security;
alter table financial_evidence.published_generation_pointer force row level security;
create table financial_evidence.published_import_membership (

    organization_id uuid not null,
    tenant_id uuid not null,
    generation_id uuid not null, import_id uuid not null, attestation_id uuid not null,
    import_snapshot jsonb not null, reconciliation_snapshot jsonb not null,
    published_contribution jsonb not null,
    primary key (organization_id,tenant_id,generation_id,import_id),
    foreign key (organization_id,tenant_id,generation_id) references
        financial_evidence.projection_generation(organization_id,tenant_id,generation_id) on delete restrict,
    foreign key (organization_id,tenant_id,import_id) references
        public.cloud_cost_import(organization_id,tenant_id,import_id) on delete restrict,
    foreign key (organization_id,tenant_id,import_id,attestation_id) references
        financial_evidence.source_attestation(organization_id,tenant_id,import_id,attestation_id) on delete restrict,
    check (jsonb_typeof(import_snapshot)='object' and jsonb_typeof(reconciliation_snapshot)='object' and jsonb_typeof(published_contribution)='object'),
    foreign key (organization_id,tenant_id) references
        public.cloud_cost_tenant_scope(organization_id,tenant_id) on delete restrict,
    check (organization_id=tenant_id)
);
alter table financial_evidence.published_import_membership enable row level security;
alter table financial_evidence.published_import_membership force row level security;
create table financial_evidence.published_fact_membership (

    organization_id uuid not null,
    tenant_id uuid not null,
    generation_id uuid not null, import_id uuid not null, cloud_cost_fact_id uuid not null,
    fact_snapshot jsonb not null, included_in_resolved boolean not null check (included_in_resolved),
    primary key (organization_id,tenant_id,generation_id,cloud_cost_fact_id),
    foreign key (organization_id,tenant_id,generation_id,import_id) references
        financial_evidence.published_import_membership(organization_id,tenant_id,generation_id,import_id) on delete restrict,
    foreign key (organization_id,tenant_id,cloud_cost_fact_id) references
        public.cloud_cost_fact(organization_id,tenant_id,cloud_cost_fact_id) on delete restrict,
    check (jsonb_typeof(fact_snapshot)='object'),
    foreign key (organization_id,tenant_id) references
        public.cloud_cost_tenant_scope(organization_id,tenant_id) on delete restrict,
    check (organization_id=tenant_id)
);
alter table financial_evidence.published_fact_membership enable row level security;
alter table financial_evidence.published_fact_membership force row level security;
create index published_fact_by_import on financial_evidence.published_fact_membership
    (organization_id,tenant_id,generation_id,import_id);

-- This is deliberately unconditional: no caller, service role, claim or setting activates it.
-- An approved issuer/session integration must replace it under separate authorization.
create function financial_evidence.require_approved_authority()
returns void language plpgsql security invoker set search_path=pg_catalog as $$
begin
 raise insufficient_privilege using message='BLOCKED_D1_D3_D4_D7: trusted issuer/session/privileges not approved';
end $$;

create function financial_evidence.scope_lock(o uuid,t uuid) returns void
language sql volatile security invoker set search_path=pg_catalog as $$
 select pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(o::text||':'||t::text,0))
$$;

create function financial_evidence.authorize(o uuid,t uuid,g uuid,op text,fp text)
returns uuid language plpgsql security invoker set search_path=pg_catalog as $$
declare actor uuid;
begin
 perform financial_evidence.require_approved_authority();
 if o is null or t is distinct from o then raise insufficient_privilege; end if;
 select a.actor_auth_uid into actor from financial_evidence.operation_authorization_grant a
 join public.users u on u.auth_user_id=a.actor_auth_uid and u.org_id=o
 where a.organization_id=o and a.tenant_id=t and a.grant_id=g and a.permission=op
 and a.request_fingerprint=fp and a.issued_at<=clock_timestamp()
 and a.expires_at>clock_timestamp() and a.revoked_at is null;
 if actor is null then raise insufficient_privilege using message='SCOPED_GRANT_DENIED'; end if;
 return actor;
end $$;

-- Deterministic versioned JSONB encoding candidate, not an approved cross-runtime encoding.
create function financial_evidence.digest(j jsonb) returns text
language sql immutable security invoker set search_path=pg_catalog as $$
 select encode(sha256(convert_to('nxr-jsonb-v1:'||j::text,'UTF8')),'hex')
$$;
create function financial_evidence.fingerprint(o uuid,t uuid,ids uuid[],c text,s date,e date,
 span boolean,op text,trigger_id uuid default null,request_id uuid default null,prev uuid default null)
returns text language sql immutable security invoker set search_path=pg_catalog as $$
 select financial_evidence.digest(jsonb_build_array(o,t,
   (select jsonb_agg(x order by x) from unnest(ids) x),c,s,e,span,op,trigger_id,request_id,prev))
$$;
create function financial_evidence.validate_request(o uuid,t uuid,ids uuid[],c text,s date,e date,span boolean)
returns void language plpgsql security invoker set search_path=pg_catalog as $$
begin
 if o is null or t is distinct from o or ids is null or cardinality(ids)=0
 or array_ndims(ids)<>1 or array_position(ids,null) is not null
 or (select count(distinct x) from unnest(ids) x)<>cardinality(ids)
 or c is null or c !~ '^[A-Z]{3}$' or s is null or e is null or s>e or span is null then
 raise invalid_parameter_value using message='INVALID_FINANCIAL_QUERY'; end if;
end $$;

create function financial_evidence.capture(o uuid,t uuid,s date,e date) returns jsonb
language sql stable security invoker set search_path=pg_catalog as $$
 with universe as (
 select * from public.cloud_cost_import i where i.organization_id=o and i.tenant_id=t
 and i.billing_period_end>=s and i.billing_period_start<=e
 )
 select jsonb_build_object(
 'imports',(select coalesce(jsonb_agg(to_jsonb(i) order by import_id),'[]') from universe i),
 'facts',(select coalesce(jsonb_agg(to_jsonb(f) order by cloud_cost_fact_id),'[]')
 from public.cloud_cost_fact f where f.organization_id=o and f.tenant_id=t
 and f.import_id in (select import_id from universe)),
 'reconciliations',(select coalesce(jsonb_agg(to_jsonb(r) order by import_id),'[]')
 from public.cloud_cost_reconciliation r where r.organization_id=o and r.tenant_id=t
 and r.import_id in (select import_id from universe)),
 'sources',(select coalesce(jsonb_agg(to_jsonb(a) order by import_id),'[]')
 from financial_evidence.source_attestation a where a.organization_id=o and a.tenant_id=t
 and a.import_id in (select import_id from universe)),
 'mappings',(select coalesce(jsonb_agg(to_jsonb(m) order by cloud_account_mapping_id),'[]')
 from public.cloud_account_mapping m where m.organization_id=o and m.tenant_id=t))
$$;

-- All inputs originate in the same database snapshot. No source amount is derived from facts.
create function financial_evidence.certify(j jsonb,ids uuid[],c text,s date,e date,span boolean)
returns numeric language plpgsql security invoker set search_path=pg_catalog as $$
declare i jsonb; a jsonb; r jsonb; f jsonb; n bigint; amount numeric; total numeric:=0;
begin
 if (select array_agg(x::uuid order by x::uuid) from jsonb_array_elements_text(to_jsonb(ids)) x)
 is distinct from (select array_agg((x->>'import_id')::uuid order by (x->>'import_id')::uuid)
 from jsonb_array_elements(j->'imports') x) then
 raise check_violation using message='IMPORT_MEMBERSHIP_MISMATCH'; end if;
 for i in select * from jsonb_array_elements(j->'imports') loop
 select x into a from jsonb_array_elements(j->'sources') x where x->>'import_id'=i->>'import_id';
 select x into r from jsonb_array_elements(j->'reconciliations') x where x->>'import_id'=i->>'import_id';
 if a is null or r is null or a->>'attestation_status'<>'verified'
 or i->>'status'<>'completed' or i->>'supersedes_import_id' is not null
 or i->>'completed_at' is null or r->>'reconciled_at' is null
 or r->>'status'<>'reconciled' or r->>'variance_amount' is null
 or (r->>'variance_amount')::numeric<>0 then
 raise check_violation using message='UNVERIFIED_IMPORT'; end if;
 if i->>'currency_code' is distinct from c or a->>'currency_code' is distinct from c
 or r->>'currency_code' is distinct from c
 or (i->>'billing_period_start')::date<s or (i->>'billing_period_end')::date>e
 or (not span and ((i->>'billing_period_start')::date<>s or (i->>'billing_period_end')::date<>e))
 or exists(select 1 from jsonb_array_elements(jsonb_build_array(a,r)) x
 where x->>'payer_account_id' is distinct from i->>'payer_account_id'
 or x->>'billing_period_start' is distinct from i->>'billing_period_start'
 or x->>'billing_period_end' is distinct from i->>'billing_period_end')
 or a->>'source_file_sha256' is distinct from i->>'source_file_sha256' then
 raise check_violation using message='SOURCE_IDENTITY_MISMATCH'; end if;
 n:=(a->>'source_row_count')::bigint; amount:=(a->>'source_cost_total')::numeric;
 if n is null or n<=0 or amount is null
 or exists(select 1 from jsonb_array_elements(jsonb_build_array(i,r)) x
 where x->>'duplicate_row_count' is null or (x->>'duplicate_row_count')::bigint<>0
 or x->>'rejected_row_count' is null or (x->>'rejected_row_count')::bigint<>0
 or (x->>'source_row_count')::bigint is distinct from n
 or (x->>'source_cost_total')::numeric is distinct from amount
 or (x->>'normalized_cost_total')::numeric is distinct from amount)
 or (i->>'accepted_row_count')::bigint is distinct from n
 or (r->>'normalized_row_count')::bigint is distinct from n
 or (select count(*) from jsonb_array_elements(j->'facts') x where x->>'import_id'=i->>'import_id')<>n
 or (select sum((x->>'unblended_cost')::numeric) from jsonb_array_elements(j->'facts') x
 where x->>'import_id'=i->>'import_id') is distinct from amount then
 raise check_violation using message='SOURCE_CANONICAL_RECONCILIATION_MISMATCH'; end if;
 for f in select x from jsonb_array_elements(j->'facts') x where x->>'import_id'=i->>'import_id' loop
 if f->>'fact_status'<>'active' or f->>'supersedes_fact_id' is not null or f->>'unblended_cost' is null
 or f->>'currency_code' is distinct from c
 or f->>'payer_account_id' is distinct from i->>'payer_account_id'
 or f->>'billing_period_start' is distinct from i->>'billing_period_start'
 or f->>'billing_period_end' is distinct from i->>'billing_period_end'
 or not exists(select 1 from jsonb_array_elements(j->'mappings') m
 where m->>'account_id'=f->>'member_account_id' and m->>'payer_account_id'=f->>'payer_account_id'
 and m->>'status'='active' and m->>'account_kind'='member'
 and (m->>'effective_from')::date<=(f->>'billing_period_start')::date
 and ((m->>'effective_to') is null or (m->>'effective_to')::date>=(f->>'billing_period_end')::date))
 or not exists(select 1 from jsonb_array_elements(j->'mappings') m
 where m->>'account_id'=f->>'payer_account_id' and m->>'payer_account_id'=f->>'payer_account_id'
 and m->>'status'='active' and m->>'account_kind'='payer'
 and (m->>'effective_from')::date<=(f->>'billing_period_start')::date
 and ((m->>'effective_to') is null or (m->>'effective_to')::date>=(f->>'billing_period_end')::date)) then
 raise check_violation using message='UNCERTIFIED_FACT_OR_ACCOUNT'; end if;
 end loop;
 total:=total+amount;
 end loop;
 if (select count(*) from jsonb_array_elements(j->'facts'))<>
 (select count(distinct x->>'source_row_key') from jsonb_array_elements(j->'facts') x) then
 raise check_violation using message='DUPLICATE_FACT'; end if;
 return total::numeric(24,10);
end $$;

create function financial_evidence.make_posture(o uuid,c text,j jsonb,stamp timestamptz,total numeric)
returns jsonb language sql stable security invoker set search_path=pg_catalog as $$
 select jsonb_build_object('organization_id',o,'currency',c,
 'period_start',(select min(x->>'billing_period_start') from jsonb_array_elements(j->'imports') x),
 'period_end',(select max(x->>'billing_period_end') from jsonb_array_elements(j->'imports') x),
 'generated_at',stamp,'import_count',jsonb_array_length(j->'imports'),
 'latest_import_id',(select x->>'import_id' from jsonb_array_elements(j->'imports') x
 order by (x->>'created_at')::timestamptz desc,(x->>'import_id')::uuid desc limit 1),
 'latest_import_status','completed','source_rows',jsonb_array_length(j->'facts'),
 'persisted_facts',jsonb_array_length(j->'facts'),'total_ingested_spend',total::text,
 'cloud_spend',total::text,'resolved_spend',total::text,'quarantined_spend','0',
 'allocated_spend','0','unallocated_resolved_spend',total::text,'reconciled_spend',total::text,
 'unreconciled_spend','0','reconciliation_variance','0','allocation_coverage_percentage','0',
 'resolved_account_count',(select count(distinct (x->>'payer_account_id',x->>'member_account_id'))
 from jsonb_array_elements(j->'facts') x),'unknown_account_count',0,'foreign_account_count',0,
 'ambiguous_account_count',0,'reconciliation_status','reconciled','warnings','[]'::jsonb,
 'contract_version','pvt-003c1-v1')
$$;

create function financial_evidence.receipt(g financial_evidence.projection_generation)
returns jsonb language sql stable security invoker set search_path=pg_catalog as $$
 select jsonb_build_object('organization_id',g.organization_id,'tenant_id',g.tenant_id,
 'generation_id',g.generation_id,'request_id',g.request_id,'trigger_import_id',g.trigger_import_id,
 'previous_generation_id',g.previous_generation_id,'import_ids',g.requested_import_ids,
 'published_at',g.published_at,'currency',g.currency,'period_start',g.period_start,'period_end',g.period_end,
 'spanning_periods',g.spanning_periods,'input_digest',g.input_digest,'replayed',false,
 'is_current',exists(select 1 from financial_evidence.published_generation_pointer p
 where p.organization_id=g.organization_id and p.tenant_id=g.tenant_id
 and p.generation_id=g.generation_id and p.currency=g.currency
 and p.period_start=g.period_start and p.period_end=g.period_end and p.spanning_periods=g.spanning_periods))
$$;

create function public.refresh_tenant_cloud_financial_projections_v2(
 organization_id uuid,tenant_id uuid,import_ids uuid[],currency text,period_start date,period_end date,
 spanning_periods boolean,trigger_import_id uuid,request_id uuid,authorization_grant_id uuid,
 expected_previous_generation_id uuid) returns jsonb
language plpgsql security invoker set search_path=pg_catalog as $$
declare actor uuid; fp text; old uuid; gid uuid:=gen_random_uuid(); j jsonb; total numeric;
 stamp timestamptz; posture jsonb; i jsonb; f jsonb; a jsonb; r jsonb; saved financial_evidence.projection_generation;
begin
 perform financial_evidence.validate_request($1,$2,$3,$4,$5,$6,$7);
 fp:=financial_evidence.fingerprint($1,$2,$3,$4,$5,$6,$7,'refresh',$8,$9,$11);
 actor:=financial_evidence.authorize($1,$2,$10,'refresh',fp);
 if current_setting('transaction_isolation')<>'serializable' then
 raise invalid_transaction_state using message='SERIALIZABLE_REQUIRED'; end if;
 if $8 is null or $9 is null or not ($8=any($3)) then raise invalid_parameter_value; end if;
 perform financial_evidence.scope_lock($1,$2);
 select * into saved from financial_evidence.projection_generation g
 where g.organization_id=$1 and g.tenant_id=$2 and g.request_id=$9;
 if found then
 if saved.request_fingerprint<>fp or saved.actor_auth_uid<>actor then raise insufficient_privilege; end if;
 return financial_evidence.receipt(saved)||jsonb_build_object('replayed',true);
 end if;
 select p.generation_id into old from financial_evidence.published_generation_pointer p
 where p.organization_id=$1 and p.tenant_id=$2 and p.currency=$4 and p.period_start=$5
 and p.period_end=$6 and p.spanning_periods=$7 for update;
 if old is distinct from $11 then raise serialization_failure using message='STALE_PREVIOUS_GENERATION'; end if;
 j:=financial_evidence.capture($1,$2,$5,$6);
 total:=financial_evidence.certify(j,$3,$4,$5,$6,$7);
 stamp:=clock_timestamp();
 posture:=financial_evidence.make_posture($1,$4,j,stamp,total);
 if posture->>'latest_import_id'<>$8::text then raise check_violation using message='TRIGGER_NOT_LATEST'; end if;
 insert into financial_evidence.projection_generation
 (organization_id,tenant_id,generation_id,request_id,trigger_import_id,authorization_grant_id,actor_auth_uid,
 previous_generation_id,currency,period_start,period_end,spanning_periods,requested_import_ids,
 request_fingerprint,input_digest,input_snapshot_id,published_at,status,posture,total)
 values ($1,$2,gid,$9,$8,$10,actor,old,$4,$5,$6,$7,$3,fp,financial_evidence.digest(j),
 pg_current_snapshot()::text,stamp,'published',posture,total) returning * into saved;
 for i in select * from jsonb_array_elements(j->'imports') loop
 select x into a from jsonb_array_elements(j->'sources') x where x->>'import_id'=i->>'import_id';
 select x into r from jsonb_array_elements(j->'reconciliations') x where x->>'import_id'=i->>'import_id';
 insert into financial_evidence.published_import_membership
 (organization_id,tenant_id,generation_id,import_id,attestation_id,import_snapshot,reconciliation_snapshot,published_contribution)
 values ($1,$2,gid,(i->>'import_id')::uuid,(a->>'attestation_id')::uuid,i,r,
 i||jsonb_build_object('generation_id',gid,'attestation_id',a->>'attestation_id',
 'persisted_facts',(a->>'source_row_count')::bigint,'source_cost_total',a->>'source_cost_total',
 'total_unblended_spend',a->>'source_cost_total','variance_amount',r->>'variance_amount',
 'reconciled_at',r->>'reconciled_at','reconciliation_status',r->>'status'));
 end loop;
 for f in select * from jsonb_array_elements(j->'facts') loop
 insert into financial_evidence.published_fact_membership
 (organization_id,tenant_id,generation_id,import_id,cloud_cost_fact_id,fact_snapshot,included_in_resolved)
 values($1,$2,gid,(f->>'import_id')::uuid,(f->>'cloud_cost_fact_id')::uuid,f,true);
 end loop;
 -- No error is swallowed: all inserts and pointer update roll back together.
 insert into financial_evidence.published_generation_pointer
 (organization_id,tenant_id,currency,period_start,period_end,spanning_periods,generation_id)
 values($1,$2,$4,$5,$6,$7,gid)
 on conflict on constraint published_generation_pointer_pkey
 do update set generation_id=excluded.generation_id;
 return financial_evidence.receipt(saved);
end $$;

-- Decimal wire values: numbers representing money become strings, counts remain integer JSON.
create function financial_evidence.wire(j jsonb) returns jsonb
language plpgsql immutable security invoker set search_path=pg_catalog as $$
declare result jsonb; k text; v jsonb;
begin
 if jsonb_typeof(j)='array' then
 select coalesce(jsonb_agg(financial_evidence.wire(x)),'[]') into result from jsonb_array_elements(j) x;
 return result;
 elsif jsonb_typeof(j)='object' then
 result:='{}';
 for k,v in select * from jsonb_each(j) loop
 if jsonb_typeof(v)='number' and (k like '%cost%' or k like '%spend%' or k in
 ('total','variance_amount','reconciliation_variance','allocation_coverage_percentage')) then
 result:=result||jsonb_build_object(k,v::text);
 else result:=result||jsonb_build_object(k,financial_evidence.wire(v)); end if;
 end loop; return result;
 end if; return j;
end $$;

create function public.read_aws_financial_contribution_evidence_v1(
 organization_id uuid,tenant_id uuid,import_ids uuid[],currency text,period_start date,period_end date,
 spanning_periods boolean,authorization_grant_id uuid) returns jsonb
language plpgsql security invoker set search_path=pg_catalog as $$
declare actor uuid; j jsonb; g financial_evidence.projection_generation; pub jsonb;
 reasons jsonb:='[]'; state text:='COMPLETE'; checked numeric; actual_ids uuid[];
begin
 perform financial_evidence.validate_request($1,$2,$3,$4,$5,$6,$7);
 actor:=financial_evidence.authorize($1,$2,$8,'read',
 financial_evidence.fingerprint($1,$2,$3,$4,$5,$6,$7,'read'));
 if current_setting('transaction_isolation') not in ('repeatable read','serializable') then
 raise invalid_transaction_state using message='CONSISTENT_SNAPSHOT_REQUIRED'; end if;
 j:=financial_evidence.capture($1,$2,$5,$6);
 begin checked:=financial_evidence.certify(j,$3,$4,$5,$6,$7);
 exception when check_violation then
 state:='INCOMPLETE'; reasons:=reasons||jsonb_build_array(SQLERRM); end;
 select g0.* into g from financial_evidence.published_generation_pointer p
 join financial_evidence.projection_generation g0 on g0.organization_id=p.organization_id
 and g0.tenant_id=p.tenant_id and g0.generation_id=p.generation_id
 where p.organization_id=$1 and p.tenant_id=$2 and p.currency=$4
 and p.period_start=$5 and p.period_end=$6 and p.spanning_periods=$7;
 if not found then state:='UNAVAILABLE'; reasons:=reasons||'"NO_PUBLICATION"'::jsonb;
 else
 if g.input_digest<>financial_evidence.digest(j) then
 state:='INCOMPLETE'; reasons:=reasons||'"STALE_GENERATION"'::jsonb; end if;
 pub:=financial_evidence.receipt(g)||jsonb_build_object('revision',g.generation_id,
 'requested_import_ids',g.requested_import_ids,'input_snapshot_id',g.input_snapshot_id,
 'total',g.total::text,'posture',g.posture,
 'published_imports',(select coalesce(jsonb_agg(m.published_contribution order by m.import_id),'[]')
 from financial_evidence.published_import_membership m where m.organization_id=$1
 and m.tenant_id=$2 and m.generation_id=g.generation_id),
 'published_facts',(select coalesce(jsonb_agg(m.fact_snapshot||jsonb_build_object('generation_id',g.generation_id,
 'included_in_resolved',m.included_in_resolved) order by m.cloud_cost_fact_id),'[]')
 from financial_evidence.published_fact_membership m where m.organization_id=$1 and m.tenant_id=$2 and m.generation_id=g.generation_id),
 'included_fact_ids',(select coalesce(jsonb_agg(m.cloud_cost_fact_id order by m.cloud_cost_fact_id),'[]')
 from financial_evidence.published_fact_membership m where m.organization_id=$1 and m.tenant_id=$2 and m.generation_id=g.generation_id));
 end if;
 select array_agg((x->>'import_id')::uuid) into actual_ids from jsonb_array_elements(j->'imports') x;
 return financial_evidence.wire(jsonb_build_object('contract_version','nxr-dash-08-v1',
 'organization_id',$1,'tenant_id',$2,'requested_import_ids',$3,
 'query',jsonb_build_object('currency',$4,'period_start',$5,'period_end',$6,'spans_multiple_periods',$7),
 'snapshot_id',pg_current_snapshot()::text,'observed_at',clock_timestamp(),
 'completeness',state,'reasons',reasons,
 'missing_import_ids',(select coalesce(jsonb_agg(x),'[]') from unnest($3) x where not (x=any(coalesce(actual_ids,'{}')))),
 'unexpected_import_ids',(select coalesce(jsonb_agg(x),'[]') from unnest(actual_ids) x where not (x=any($3))),
 'sources',j->'sources','canonical',jsonb_build_object('imports',j->'imports','facts',j->'facts',
 'reconciliations',j->'reconciliations'),'publication',pub,
 'authorization',jsonb_build_object('grant_id',$8,'actor_auth_uid',actor,'permission','read')));
end $$;

-- Immutable history and transaction-local append guard, not an xmin authorization check.
create function financial_evidence.guard_history() returns trigger
language plpgsql security invoker set search_path=pg_catalog as $$
declare g financial_evidence.projection_generation;
begin
 if TG_OP<>'INSERT' then raise check_violation using message='IMMUTABLE_PUBLISHED_HISTORY'; end if;
 if TG_TABLE_NAME='projection_generation' then
 NEW.creation_transaction:=pg_current_xact_id(); return NEW;
 end if;
 select * into g from financial_evidence.projection_generation p where
 p.organization_id=NEW.organization_id and p.tenant_id=NEW.tenant_id and p.generation_id=NEW.generation_id;
 if g.creation_transaction is distinct from pg_current_xact_id() then
 raise check_violation using message='GENERATION_ALREADY_COMMITTED'; end if;
 if TG_TABLE_NAME='published_fact_membership' then
 if NEW.fact_snapshot->>'import_id' is distinct from NEW.import_id::text
 or NEW.fact_snapshot->>'cloud_cost_fact_id' is distinct from NEW.cloud_cost_fact_id::text
 or NEW.fact_snapshot->>'organization_id' is distinct from NEW.organization_id::text
 or NEW.fact_snapshot->>'tenant_id' is distinct from NEW.tenant_id::text
 or not exists(select 1 from public.cloud_cost_fact f where f.organization_id=NEW.organization_id
 and f.tenant_id=NEW.tenant_id and f.import_id=NEW.import_id and f.cloud_cost_fact_id=NEW.cloud_cost_fact_id
 and to_jsonb(f)=NEW.fact_snapshot) then raise check_violation using message='FACT_SNAPSHOT_MISMATCH'; end if;
 else
 if NEW.import_snapshot->>'import_id' is distinct from NEW.import_id::text
 or NEW.import_snapshot->>'organization_id' is distinct from NEW.organization_id::text
 or NEW.import_snapshot->>'tenant_id' is distinct from NEW.tenant_id::text then
 raise check_violation using message='IMPORT_SNAPSHOT_MISMATCH'; end if;
 end if;
 return NEW;
end $$;
create trigger immutable_generation before insert or update or delete on financial_evidence.projection_generation
 for each row execute function financial_evidence.guard_history();
create trigger immutable_imports before insert or update or delete on financial_evidence.published_import_membership
 for each row execute function financial_evidence.guard_history();
create trigger immutable_facts before insert or update or delete on financial_evidence.published_fact_membership
 for each row execute function financial_evidence.guard_history();

create function financial_evidence.validate_commit() returns trigger
language plpgsql security invoker set search_path=pg_catalog as $$
declare ids uuid[]; n bigint; amount numeric; inputs jsonb;
begin
 select array_agg(import_id order by import_id) into ids from financial_evidence.published_import_membership
 where organization_id=NEW.organization_id and tenant_id=NEW.tenant_id and generation_id=NEW.generation_id;
 select count(*),sum((fact_snapshot->>'unblended_cost')::numeric) into n,amount
 from financial_evidence.published_fact_membership where organization_id=NEW.organization_id
 and tenant_id=NEW.tenant_id and generation_id=NEW.generation_id;
 if ids is distinct from (select array_agg(x order by x) from unnest(NEW.requested_import_ids) x)
 or n is distinct from (NEW.posture->>'persisted_facts')::bigint or amount is distinct from NEW.total then
 raise check_violation using message='INCOMPLETE_GENERATION_AT_COMMIT'; end if;
 inputs:=financial_evidence.capture(NEW.organization_id,NEW.tenant_id,NEW.period_start,NEW.period_end);
 if financial_evidence.digest(inputs)<>NEW.input_digest
 or financial_evidence.certify(inputs,NEW.requested_import_ids,NEW.currency,NEW.period_start,NEW.period_end,NEW.spanning_periods)<>NEW.total
 or financial_evidence.make_posture(NEW.organization_id,NEW.currency,inputs,NEW.published_at,NEW.total)<>NEW.posture
 or exists(
   (select (x->>'cloud_cost_fact_id')::uuid from jsonb_array_elements(inputs->'facts') x
    except select cloud_cost_fact_id from financial_evidence.published_fact_membership
    where organization_id=NEW.organization_id and tenant_id=NEW.tenant_id and generation_id=NEW.generation_id)
   union all
   (select cloud_cost_fact_id from financial_evidence.published_fact_membership
    where organization_id=NEW.organization_id and tenant_id=NEW.tenant_id and generation_id=NEW.generation_id
    except select (x->>'cloud_cost_fact_id')::uuid from jsonb_array_elements(inputs->'facts') x)) then
 raise check_violation using message='GENERATION_EVIDENCE_MISMATCH_AT_COMMIT'; end if;
 return NEW;
end $$;
create constraint trigger complete_generation after insert on financial_evidence.projection_generation
 deferrable initially deferred for each row execute function financial_evidence.validate_commit();

-- Proposed all-writer mutation protocol. No existing production writer has been activated here.
create function financial_evidence.lock_mutation() returns trigger
language plpgsql security invoker set search_path=pg_catalog as $$
begin
 if TG_OP='UPDATE' and (OLD.organization_id,OLD.tenant_id) is distinct from
 (NEW.organization_id,NEW.tenant_id) then raise insufficient_privilege; end if;
 if TG_OP='DELETE' then perform financial_evidence.scope_lock(OLD.organization_id,OLD.tenant_id); return OLD; end if;
 perform financial_evidence.scope_lock(NEW.organization_id,NEW.tenant_id); return NEW;
end $$;
do $$ declare tab text; begin
 foreach tab in array array['cloud_cost_import','cloud_cost_fact','cloud_cost_reconciliation','cloud_account_mapping'] loop
 execute format('create trigger financial_scope_mutation before insert or update or delete on public.%I for each row execute function financial_evidence.lock_mutation()',tab);
 end loop;
end $$;
create trigger source_scope_mutation before insert or update or delete on financial_evidence.source_attestation
 for each row execute function financial_evidence.lock_mutation();
create trigger grant_scope_mutation before insert or update or delete on financial_evidence.operation_authorization_grant
 for each row execute function financial_evidence.lock_mutation();

create function financial_evidence.guard_authority_history() returns trigger
language plpgsql security invoker set search_path=pg_catalog as $$
begin
 if TG_OP='DELETE' then raise check_violation using message='RETAIN_AUTHORITY_HISTORY'; end if;
 if TG_TABLE_NAME='source_attestation' then
 if (to_jsonb(NEW)-'attestation_status')<>(to_jsonb(OLD)-'attestation_status')
 or OLD.attestation_status<>'verified' or NEW.attestation_status<>'revoked' then
 raise check_violation using message='IMMUTABLE_ATTESTATION'; end if;
 else
 if (to_jsonb(NEW)-'revoked_at')<>(to_jsonb(OLD)-'revoked_at')
 or OLD.revoked_at is not null or NEW.revoked_at is null then
 raise check_violation using message='IMMUTABLE_GRANT'; end if;
 end if;
 return NEW;
end $$;
create trigger retain_attestation before update or delete on financial_evidence.source_attestation
 for each row execute function financial_evidence.guard_authority_history();
create trigger retain_grant before update or delete on financial_evidence.operation_authorization_grant
 for each row execute function financial_evidence.guard_authority_history();

revoke all on schema financial_evidence from public,anon,authenticated,service_role;
revoke all on all tables in schema financial_evidence from public,anon,authenticated,service_role;
revoke all on all functions in schema financial_evidence from public,anon,authenticated,service_role;
revoke all on function public.read_aws_financial_contribution_evidence_v1(uuid,uuid,uuid[],text,date,date,boolean,uuid)
 from public,anon,authenticated,service_role;
revoke all on function public.refresh_tenant_cloud_financial_projections_v2(uuid,uuid,uuid[],text,date,date,boolean,uuid,uuid,uuid,uuid)
 from public,anon,authenticated,service_role;
commit;
