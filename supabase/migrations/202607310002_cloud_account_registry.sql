begin;
create table if not exists public.cloud_account_registry (
 id uuid primary key default gen_random_uuid(), organization_id uuid not null, tenant_id uuid not null,
 provider text not null check (provider in ('aws','azure','gcp')), account_id text not null,
 account_name text not null default '', alias text, environment text, business_unit text, department text,
 application text, business_service text, owner text, technical_owner text, finance_owner text,
 cost_center text, project text, budget numeric not null default 0, monthly_budget numeric not null default 0,
 currency text not null default 'USD', status text not null default 'pending_mapping', landing_zone text,
 tags_coverage numeric not null default 0 check (tags_coverage between 0 and 100), governance_score integer not null default 0,
 health_score integer not null default 0, last_synchronization timestamptz, metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(organization_id,tenant_id,provider,account_id), check (organization_id=tenant_id)
);
create table if not exists public.cloud_account_registry_audit (
 id uuid primary key default gen_random_uuid(), registry_id uuid not null references public.cloud_account_registry(id),
 organization_id uuid not null, tenant_id uuid not null, actor_id text not null, actor_email text not null,
 action text not null, old_value jsonb not null default '{}'::jsonb, new_value jsonb not null default '{}'::jsonb,
 reason text not null, created_at timestamptz not null default now(), check (organization_id=tenant_id)
);
create index if not exists cloud_account_registry_tenant_idx on public.cloud_account_registry(organization_id,tenant_id,status,provider);
create index if not exists cloud_account_registry_audit_idx on public.cloud_account_registry_audit(organization_id,tenant_id,registry_id,created_at desc);
alter table public.cloud_account_registry enable row level security;
alter table public.cloud_account_registry_audit enable row level security;
create policy cloud_account_registry_tenant_access on public.cloud_account_registry for all to authenticated
 using (public.pvt003c1_can_read_organization(organization_id) and organization_id=tenant_id)
 with check (public.pvt003c1_can_read_organization(organization_id) and organization_id=tenant_id);
create policy cloud_account_registry_audit_tenant_access on public.cloud_account_registry_audit for select to authenticated
 using (public.pvt003c1_can_read_organization(organization_id) and organization_id=tenant_id);
create policy cloud_account_registry_audit_insert on public.cloud_account_registry_audit for insert to authenticated
 with check (public.pvt003c1_can_read_organization(organization_id) and organization_id=tenant_id);
revoke delete on public.cloud_account_registry from authenticated;
revoke update, delete on public.cloud_account_registry_audit from authenticated;
grant select,insert,update on public.cloud_account_registry to authenticated,service_role;
grant select,insert on public.cloud_account_registry_audit to authenticated,service_role;
commit;
