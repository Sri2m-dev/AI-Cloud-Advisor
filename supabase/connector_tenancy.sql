alter table if exists public.connector_registry
    add column if not exists organization_id text,
    add column if not exists configured_by text;

alter table if exists public.connector_sync_history
    add column if not exists organization_id text;

alter table if exists public.discovered_assets
    add column if not exists organization_id text;

alter table if exists public.technology_inventory
    add column if not exists organization_id text;

alter table if exists public.relationship_graph
    add column if not exists organization_id text;

alter table if exists public.technology_relationships
    add column if not exists organization_id text;

update public.connector_registry
set organization_id = 'bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c'
where organization_id is null;

update public.connector_sync_history
set organization_id = 'bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c'
where organization_id is null;

update public.discovered_assets
set organization_id = 'bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c'
where organization_id is null;

update public.technology_inventory
set organization_id = 'bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c'
where organization_id is null;

update public.relationship_graph
set organization_id = 'bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c'
where organization_id is null;

update public.technology_relationships
set organization_id = 'bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c'
where organization_id is null;

drop index if exists public.idx_connector_registry_name;

create unique index if not exists idx_connector_registry_org_connector
    on public.connector_registry (organization_id, connector_name);

create index if not exists idx_connector_sync_history_org_connector
    on public.connector_sync_history (organization_id, connector_name);

create index if not exists idx_discovered_assets_org_connector
    on public.discovered_assets (organization_id, connector_name);

create index if not exists idx_technology_inventory_organization
    on public.technology_inventory (organization_id);

create index if not exists idx_relationship_graph_organization
    on public.relationship_graph (organization_id);

create index if not exists idx_technology_relationships_organization
    on public.technology_relationships (organization_id);
