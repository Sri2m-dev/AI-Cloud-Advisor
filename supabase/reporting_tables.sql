create table if not exists public.report_history (
    id uuid primary key,
    org_id text,
    tenant_id text,
    report_name text not null,
    requested_by text,
    delivery_channel text,
    status text,
    recipients jsonb not null default '[]'::jsonb,
    file_name text,
    notes text,
    created_at timestamptz not null default now()
);

create index if not exists idx_report_history_org_created
    on public.report_history (org_id, created_at desc);

create unique index if not exists idx_report_history_id
    on public.report_history (id);

create table if not exists public.report_distribution_lists (
    id uuid primary key,
    org_id text not null,
    tenant_id text,
    report_name text not null default 'executive_pdf',
    recipients jsonb not null default '[]'::jsonb,
    active boolean not null default true,
    updated_by text,
    updated_at timestamptz not null default now()
);

create unique index if not exists idx_report_distribution_org_report
    on public.report_distribution_lists (org_id, report_name);
