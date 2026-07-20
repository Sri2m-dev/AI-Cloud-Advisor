-- WP-005 stewardship persistence. Additive only; manual application.
create table if not exists data_fabric.stewardship_policies (
 policy_id uuid primary key default gen_random_uuid(), organization_id text not null, tenant_id text not null,
 policy_type text not null check (policy_type in ('authority','freshness')), domain text not null,
 policy_key text not null, configuration jsonb not null, active boolean not null default true,
 revision integer not null default 1 check (revision > 0), effective_from timestamptz not null,
 effective_to timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 created_by text not null, updated_by text not null, schema_version integer not null default 1,
 unique (organization_id,tenant_id,policy_type,domain,policy_key),
 check (effective_to is null or effective_to > effective_from));
create index if not exists stewardship_policies_scope_idx on data_fabric.stewardship_policies(organization_id,tenant_id,domain,active);
alter table data_fabric.stewardship_policies enable row level security;

create table if not exists data_fabric.stewardship_review_items (
 review_id uuid primary key default gen_random_uuid(), organization_id text not null, tenant_id text not null,
 review_key text not null, review_type text not null check (review_type in ('identity','quality')),
 domain text not null check (domain in ('technology','applications')), subject_type text not null, subject_id text not null,
 state text not null check (state in ('discovered','classified','under_review','steward_approved','canonical','superseded','archived','rejected')),
 assigned_role text, evidence_references jsonb not null default '[]', payload jsonb not null default '{}',
 payload_hash text not null, revision integer not null default 1 check (revision > 0), active boolean not null default true,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(), created_by text not null, updated_by text not null,
 schema_version integer not null default 1, unique(organization_id,tenant_id,review_key),
 unique(review_id,organization_id,tenant_id));
create index if not exists stewardship_reviews_queue_idx on data_fabric.stewardship_review_items(organization_id,tenant_id,state,domain,updated_at);
alter table data_fabric.stewardship_review_items enable row level security;

create table if not exists data_fabric.stewardship_audit_events (
 event_id uuid primary key default gen_random_uuid(), review_id uuid not null,
 organization_id text not null, tenant_id text not null, event_type text not null,
 from_state text, to_state text not null, actor text not null, rationale text,
 evidence_references jsonb not null default '[]', correlation_id text not null,
 idempotency_key text not null, payload_hash text not null, occurred_at timestamptz not null default now(), schema_version integer not null default 1,
 unique(organization_id,tenant_id,idempotency_key),
 foreign key(review_id,organization_id,tenant_id)
   references data_fabric.stewardship_review_items(review_id,organization_id,tenant_id));
create index if not exists stewardship_audit_review_idx on data_fabric.stewardship_audit_events(organization_id,tenant_id,review_id,occurred_at);
create or replace function data_fabric.prevent_stewardship_audit_mutation() returns trigger language plpgsql as $$ begin raise exception 'stewardship_audit_events is append-only'; end; $$;
do $$ begin
 if not exists(select 1 from pg_trigger where tgname='prevent_stewardship_audit_update') then create trigger prevent_stewardship_audit_update before update on data_fabric.stewardship_audit_events for each row execute function data_fabric.prevent_stewardship_audit_mutation(); end if;
 if not exists(select 1 from pg_trigger where tgname='prevent_stewardship_audit_delete') then create trigger prevent_stewardship_audit_delete before delete on data_fabric.stewardship_audit_events for each row execute function data_fabric.prevent_stewardship_audit_mutation(); end if;
end $$;
alter table data_fabric.stewardship_audit_events enable row level security;
comment on table data_fabric.stewardship_audit_events is 'WP-005 immutable tenant-scoped stewardship audit history.';

create or replace function data_fabric.enforce_stewardship_revision() returns trigger language plpgsql as $$
begin
 if new.revision <> old.revision + 1 then raise exception 'stewardship revision must increase by exactly one'; end if;
 if new.organization_id <> old.organization_id or new.tenant_id <> old.tenant_id then raise exception 'stewardship tenant scope is immutable'; end if;
 if tg_table_name = 'stewardship_policies' and
    (new.policy_id <> old.policy_id or new.policy_type <> old.policy_type or new.domain <> old.domain or new.policy_key <> old.policy_key or new.created_at <> old.created_at or new.created_by <> old.created_by)
 then raise exception 'stewardship policy identity is immutable'; end if;
 if tg_table_name = 'stewardship_review_items' and
    (new.review_id <> old.review_id or new.review_key <> old.review_key or new.review_type <> old.review_type or new.domain <> old.domain or new.subject_type <> old.subject_type or new.subject_id <> old.subject_id or new.created_at <> old.created_at or new.created_by <> old.created_by)
 then raise exception 'stewardship review identity is immutable'; end if;
 return new;
end $$;
do $$ begin
 if not exists(select 1 from pg_trigger where tgname='enforce_stewardship_policy_revision') then create trigger enforce_stewardship_policy_revision before update on data_fabric.stewardship_policies for each row execute function data_fabric.enforce_stewardship_revision(); end if;
 if not exists(select 1 from pg_trigger where tgname='enforce_stewardship_review_revision') then create trigger enforce_stewardship_review_revision before update on data_fabric.stewardship_review_items for each row execute function data_fabric.enforce_stewardship_revision(); end if;
end $$;

comment on table data_fabric.stewardship_policies is 'WP-005 tenant-scoped versioned authority and freshness policies. RLS enabled with no anonymous policy.';
comment on table data_fabric.stewardship_review_items is 'WP-005 tenant-scoped revision-controlled stewardship queue. RLS enabled with no anonymous policy.';
