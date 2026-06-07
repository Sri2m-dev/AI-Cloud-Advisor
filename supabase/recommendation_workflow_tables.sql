alter table if exists public.recommendations
    add column if not exists owner text,
    add column if not exists approved_at timestamptz,
    add column if not exists assigned_at timestamptz,
    add column if not exists snoozed_at timestamptz,
    add column if not exists snooze_until timestamptz;

create index if not exists idx_recommendations_org_status
    on public.recommendations (org_id, status);

create index if not exists idx_recommendations_org_owner
    on public.recommendations (org_id, owner);

create index if not exists idx_recommendations_snooze_until
    on public.recommendations (snooze_until);
