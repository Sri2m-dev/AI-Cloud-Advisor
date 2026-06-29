create table if not exists public.aws_connector_config (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid,
    connector_name text not null default 'AWS',
    role_arn text,
    external_id text,
    region text default 'us-east-1',
    enabled boolean default true,
    sync_frequency text default 'DAILY',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create unique index if not exists idx_aws_connector_config_org
on public.aws_connector_config (
    organization_id,
    connector_name
);

notify pgrst, 'reload schema';