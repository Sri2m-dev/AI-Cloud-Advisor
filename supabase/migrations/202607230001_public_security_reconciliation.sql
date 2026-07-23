-- Nexora public-schema security reconciliation.
-- Mirrors the manually verified AI-Cloud-Advisor-Dev posture.
-- This migration is repository evidence only until separately approved for deployment.
-- It intentionally does not alter CRUD grants or column types.

begin;

-- Structural privileges are never required by browser/authenticated application
-- consumers. Preserve existing SELECT/INSERT/UPDATE/DELETE grants unchanged.
revoke truncate, references, trigger
on all tables in schema public
from anon, authenticated;

-- Prevent future application tables created by the normal postgres migration
-- owner from restoring structural privileges through historical GRANT ALL
-- defaults. supabase_admin is Supabase-managed and cannot be altered by the
-- supported linked migration role.
alter default privileges for role postgres in schema public
    revoke truncate, references, trigger on tables from anon, authenticated;

-- DEV has RLS enabled across public application tables. Views are excluded
-- because PostgreSQL row security applies to tables and partitioned tables.
do $$
declare
    relation record;
begin
    for relation in
        select n.nspname as schema_name, c.relname as relation_name
        from pg_catalog.pg_class c
        join pg_catalog.pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relkind in ('r', 'p')
    loop
        execute format(
            'alter table %I.%I enable row level security',
            relation.schema_name,
            relation.relation_name
        );
    end loop;
end
$$;

-- Remove only repository-evidenced legacy policies plus the prior generic
-- recommendation policy. Do not remove unknown CRUD policies silently.
drop policy if exists "Allow read for now" on public.clients;
drop policy if exists "Allow all read" on public.organizations;
drop policy if exists "Allow insert for all" on public.recommendations;
drop policy if exists "Allow insert recommendations" on public.recommendations;
drop policy if exists "Allow read recommendations" on public.recommendations;
drop policy if exists "Users can see only their org data" on public.recommendations;
drop policy if exists tenant_isolation_recommendations on public.recommendations;

-- Recreate the confirmed DEV policies idempotently.
drop policy if exists clients_select_own_org on public.clients;
create policy clients_select_own_org
on public.clients
for select
to authenticated
using (
    org_id = (
        select u.org_id
        from public.users u
        where lower(u.email) = lower(auth.jwt() ->> 'email')
        limit 1
    )
);

drop policy if exists organizations_select_own on public.organizations;
create policy organizations_select_own
on public.organizations
for select
to authenticated
using (
    id = (
        select u.org_id
        from public.users u
        where lower(u.email) = lower(auth.jwt() ->> 'email')
        limit 1
    )
);

drop policy if exists recommendations_select_own_org on public.recommendations;
create policy recommendations_select_own_org
on public.recommendations
for select
to authenticated
using (
    org_id = (
        select u.org_id
        from public.users u
        where lower(u.email) = lower(auth.jwt() ->> 'email')
        limit 1
    )
);

drop policy if exists recommendations_insert_own_org on public.recommendations;
create policy recommendations_insert_own_org
on public.recommendations
for insert
to authenticated
with check (
    org_id = (
        select u.org_id
        from public.users u
        where lower(u.email) = lower(auth.jwt() ->> 'email')
        limit 1
    )
);

drop policy if exists report_history_select_own_org on public.report_history;
create policy report_history_select_own_org
on public.report_history
for select
to authenticated
using (
    org_id is not null
    and tenant_id is not null
    and org_id = (
        select u.org_id::text
        from public.users u
        where lower(u.email) = lower(auth.jwt() ->> 'email')
        limit 1
    )
    and tenant_id = (
        select u.org_id::text
        from public.users u
        where lower(u.email) = lower(auth.jwt() ->> 'email')
        limit 1
    )
);

drop policy if exists report_history_insert_own_org on public.report_history;
create policy report_history_insert_own_org
on public.report_history
for insert
to authenticated
with check (
    org_id is not null
    and tenant_id is not null
    and org_id = (
        select u.org_id::text
        from public.users u
        where lower(u.email) = lower(auth.jwt() ->> 'email')
        limit 1
    )
    and tenant_id = (
        select u.org_id::text
        from public.users u
        where lower(u.email) = lower(auth.jwt() ->> 'email')
        limit 1
    )
);

drop policy if exists users_select_self on public.users;
create policy users_select_self
on public.users
for select
to authenticated
using (lower(email) = lower(auth.jwt() ->> 'email'));

-- Fail closed if a repository-known sensitive table still has a policy
-- explicitly available to anon/public or an always-true predicate. Unknown
-- restrictive authenticated policies are preserved for review.
do $$
declare
    unsafe_policy record;
begin
    for unsafe_policy in
        select schemaname, tablename, policyname
        from pg_catalog.pg_policies
        where schemaname = 'public'
          and tablename in (
              'clients',
              'organizations',
              'recommendations',
              'report_history',
              'users'
          )
          and (
              roles && array['public', 'anon']::name[]
              or coalesce(qual, '') ~ '^\s*\(?true\)?\s*$'
              or coalesce(with_check, '') ~ '^\s*\(?true\)?\s*$'
          )
    loop
        raise exception
            'Unsafe tenant policy remains: %.% policy %',
            unsafe_policy.schemaname,
            unsafe_policy.tablename,
            unsafe_policy.policyname;
    end loop;
end
$$;

commit;
