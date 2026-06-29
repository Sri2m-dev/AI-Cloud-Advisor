create table if not exists public.relationship_graph (
    id uuid primary key default gen_random_uuid(),
    source_type text not null,
    source_name text not null,
    relationship_type text not null,
    target_type text not null,
    target_name text not null,
    organization_id text,
    source_system text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table if exists public.relationship_graph
    add column if not exists organization_id text,
    add column if not exists source_system text;

drop index if exists public.idx_relationship_graph_unique_edge;

create unique index if not exists idx_relationship_graph_org_unique_edge
    on public.relationship_graph (
        organization_id,
        source_type,
        source_name,
        relationship_type,
        target_type,
        target_name
    );

create index if not exists idx_relationship_graph_source
    on public.relationship_graph (source_type, source_name);

create index if not exists idx_relationship_graph_target
    on public.relationship_graph (target_type, target_name);

insert into public.relationship_graph (
    source_type,
    source_name,
    relationship_type,
    target_type,
    target_name,
    metadata
)
values
    ('Business Unit', 'Retail', 'OWNS', 'Business Service', 'Revenue Services', '{}'::jsonb),
    ('Business Service', 'Revenue Services', 'USES', 'Application', 'Checkout', '{}'::jsonb),
    ('Application', 'Checkout', 'HOSTED_ON', 'Cloud', 'AWS', '{"cost_domain":"Cloud"}'::jsonb),
    ('Application', 'Checkout', 'USES_SAAS', 'SaaS', 'GitHub', '{"cost_domain":"SaaS"}'::jsonb),
    ('Application', 'Checkout', 'USES_SAAS', 'SaaS', 'Datadog', '{"cost_domain":"License"}'::jsonb),
    ('Application', 'Checkout', 'USES_AI', 'AI', 'ChatGPT Enterprise', '{"cost_domain":"AI"}'::jsonb),
    ('Application', 'Checkout', 'USES_AI', 'AI', 'GitHub Copilot', '{"cost_domain":"AI"}'::jsonb)
on conflict do nothing;
