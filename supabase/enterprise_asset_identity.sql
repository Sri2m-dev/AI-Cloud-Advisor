create table if not exists public.enterprise_asset_identity (
    asset_uid text primary key,
    organization_id text not null,
    provider text not null,
    connector_name text not null,
    source_asset_id text not null,
    asset_name text,
    asset_type text,
    normalized_asset_type text,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    status text default 'ACTIVE'
);

create unique index if not exists idx_enterprise_asset_identity_source
    on public.enterprise_asset_identity (
        organization_id,
        provider,
        connector_name,
        source_asset_id
    );

create index if not exists idx_enterprise_asset_identity_org
    on public.enterprise_asset_identity (organization_id);

create index if not exists idx_enterprise_asset_identity_provider_type
    on public.enterprise_asset_identity (organization_id, provider, normalized_asset_type);

create index if not exists idx_enterprise_asset_identity_asset_uid
    on public.enterprise_asset_identity (asset_uid);
