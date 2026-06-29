create table if not exists public.entity_identity_matches (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    source_entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    target_entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    entity_type text not null,
    confidence_score integer not null default 0,
    status text not null default 'Pending',
    signals jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, source_entity_id, target_entity_id)
);

create index if not exists idx_entity_identity_matches_status
    on public.entity_identity_matches (organization_id, status, confidence_score desc);

create table if not exists public.identity_resolution_decisions (
    id uuid primary key default gen_random_uuid(),
    candidate_id uuid not null references public.entity_identity_matches(id) on delete cascade,
    status text not null,
    source_entity_id uuid,
    target_entity_id uuid,
    decided_by uuid,
    decided_at timestamptz not null default now(),
    notes text not null default ''
);

create index if not exists idx_identity_resolution_decisions_candidate
    on public.identity_resolution_decisions (candidate_id, decided_at desc);

create table if not exists public.identity_resolution_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid,
    candidate_id uuid references public.entity_identity_matches(id) on delete set null,
    source_entity_id uuid,
    target_entity_id uuid,
    status text not null,
    confidence_score integer,
    signals jsonb not null default '[]'::jsonb,
    notes text not null default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_identity_resolution_history_entity
    on public.identity_resolution_history (source_entity_id, target_entity_id, created_at desc);

create table if not exists public.enterprise_source_identities (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    entity_type text not null,
    source_system text not null,
    external_id text not null,
    external_name text not null default '',
    normalized_identity text not null,
    attributes jsonb not null default '{}'::jsonb,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    unique (organization_id, source_system, external_id)
);

create index if not exists idx_enterprise_source_identities_entity
    on public.enterprise_source_identities (entity_id);

create index if not exists idx_enterprise_source_identities_normalized
    on public.enterprise_source_identities (organization_id, entity_type, normalized_identity);
