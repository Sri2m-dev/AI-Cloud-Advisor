create table if not exists public.alert_configs (
    id uuid primary key,
    org_id text not null,
    tenant_id text,
    spend_spike_pct numeric not null default 25,
    idle_vm_min_savings numeric not null default 100,
    savings_opportunity_threshold numeric not null default 500,
    governance_score_drop_threshold numeric not null default 10,
    governance_score_floor numeric not null default 70,
    cooldown_minutes integer not null default 180,
    channels jsonb not null default '{}'::jsonb,
    updated_by text,
    updated_at timestamptz not null default now()
);

create unique index if not exists idx_alert_configs_org on public.alert_configs (org_id);

create table if not exists public.alert_history (
    id uuid primary key,
    org_id text not null,
    tenant_id text,
    alert_type text not null,
    severity text,
    message text not null,
    channels jsonb not null default '[]'::jsonb,
    status text,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_alert_history_org_created on public.alert_history (org_id, created_at desc);
