create table if not exists public.business_capability_registry (
    id uuid primary key default gen_random_uuid(),
    organization_id text not null,
    capability_code text not null,
    capability_name text not null,
    capability_description text,
    business_domain text,
    business_unit text,
    executive_owner text,
    department text,
    criticality text,
    maturity integer not null default 3,
    status text not null default 'Active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists idx_business_capability_registry_org_name
    on public.business_capability_registry (organization_id, capability_name);

create unique index if not exists idx_business_capability_registry_org_code
    on public.business_capability_registry (organization_id, capability_code);

create index if not exists idx_business_capability_registry_unit
    on public.business_capability_registry (organization_id, business_unit);

create index if not exists idx_business_capability_registry_owner
    on public.business_capability_registry (organization_id, executive_owner);
