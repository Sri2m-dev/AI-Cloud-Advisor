-- Transactional workflow persistence for recommendation lifecycle.
-- Run this in Supabase SQL editor after recommendation_workflow_tables.sql.

create extension if not exists pgcrypto;

alter table if exists public.recommendations
    add column if not exists workflow_version integer not null default 0,
    add column if not exists last_transition_at timestamptz,
    add column if not exists last_transition_by text,
    add column if not exists last_transition_key text;

create table if not exists public.recommendation_transition_log (
    id uuid primary key default gen_random_uuid(),
    recommendation_id text not null,
    org_id text,
    from_status text,
    to_status text not null,
    actor text,
    idempotency_key text not null,
    metadata jsonb not null default '{}'::jsonb,
    expected_version integer,
    resulting_version integer,
    created_at timestamptz not null default now()
);

create unique index if not exists idx_rec_transition_log_idempotency
    on public.recommendation_transition_log (idempotency_key);

create index if not exists idx_rec_transition_log_rec_created
    on public.recommendation_transition_log (recommendation_id, created_at desc);

create or replace function public.recommendation_transition_txn(
    p_recommendation_id text,
    p_to_status text,
    p_actor text default null,
    p_idempotency_key text default null,
    p_expected_version integer default null,
    p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_rec public.recommendations%rowtype;
    v_existing public.recommendation_transition_log%rowtype;
    v_from_status text;
    v_to_status text;
    v_idempotency_key text;
    v_next_version integer;
    v_owner text;
    v_snooze_until timestamptz;
begin
    if p_recommendation_id is null or btrim(p_recommendation_id) = '' then
        return jsonb_build_object('ok', false, 'error', 'INVALID_RECOMMENDATION_ID');
    end if;

    v_to_status := lower(coalesce(p_to_status, ''));
    if v_to_status = '' then
        return jsonb_build_object('ok', false, 'error', 'INVALID_TARGET_STATUS');
    end if;

    v_idempotency_key := nullif(btrim(coalesce(p_idempotency_key, '')), '');
    if v_idempotency_key is null then
        v_idempotency_key := encode(
            digest(
                concat_ws('|', p_recommendation_id, v_to_status, coalesce(p_actor, ''), coalesce(p_metadata::text, '')),
                'sha256'
            ),
            'hex'
        );
    end if;

    select *
      into v_existing
      from public.recommendation_transition_log
     where idempotency_key = v_idempotency_key
     limit 1;

    if found then
        return jsonb_build_object(
            'ok', true,
            'idempotent', true,
            'recommendation_id', v_existing.recommendation_id,
            'status', v_existing.to_status,
            'version', coalesce(v_existing.resulting_version, 0)
        );
    end if;

    select *
      into v_rec
      from public.recommendations
     where id = p_recommendation_id
     for update;

    if not found then
        return jsonb_build_object('ok', false, 'error', 'NOT_FOUND', 'recommendation_id', p_recommendation_id);
    end if;

    v_from_status := lower(coalesce(v_rec.status, 'new'));

    if p_expected_version is not null and coalesce(v_rec.workflow_version, 0) <> p_expected_version then
        return jsonb_build_object(
            'ok', false,
            'error', 'VERSION_MISMATCH',
            'current_version', coalesce(v_rec.workflow_version, 0)
        );
    end if;

    if v_from_status <> v_to_status then
        if not (
            (v_from_status = 'new'      and v_to_status in ('approved', 'accepted', 'snoozed', 'dismissed', 'done', 'completed')) or
            (v_from_status = 'pending'  and v_to_status in ('approved', 'accepted', 'snoozed', 'dismissed', 'done', 'completed')) or
            (v_from_status = 'approved' and v_to_status in ('done', 'completed', 'snoozed', 'dismissed')) or
            (v_from_status = 'accepted' and v_to_status in ('done', 'completed', 'snoozed', 'dismissed')) or
            (v_from_status = 'snoozed'  and v_to_status in ('new', 'pending', 'approved', 'accepted', 'dismissed', 'done', 'completed')) or
            (v_from_status = 'dismissed' and v_to_status in ('new', 'pending')) or
            (v_from_status in ('done', 'completed') and v_to_status in ('done', 'completed'))
        ) then
            return jsonb_build_object(
                'ok', false,
                'error', 'INVALID_TRANSITION',
                'from_status', v_from_status,
                'to_status', v_to_status
            );
        end if;
    end if;

    v_owner := nullif(coalesce(p_metadata->>'owner', p_actor), '');
    v_snooze_until := nullif(p_metadata->>'snooze_until', '')::timestamptz;
    v_next_version := coalesce(v_rec.workflow_version, 0) + 1;

    update public.recommendations
       set status = v_to_status,
           workflow_version = v_next_version,
           last_transition_at = now(),
           last_transition_by = p_actor,
           last_transition_key = v_idempotency_key,
           owner = coalesce(v_owner, owner),
           approved_at = case when v_to_status in ('approved', 'accepted') then now() else approved_at end,
           snoozed_at = case when v_to_status = 'snoozed' then now() else snoozed_at end,
           snooze_until = case when v_to_status = 'snoozed' then coalesce(v_snooze_until, snooze_until) else snooze_until end,
           completed_at = case when v_to_status in ('done', 'completed') then now() else completed_at end,
           updated_at = now()
     where id = p_recommendation_id;

    insert into public.recommendation_transition_log (
        recommendation_id,
        org_id,
        from_status,
        to_status,
        actor,
        idempotency_key,
        metadata,
        expected_version,
        resulting_version,
        created_at
    ) values (
        p_recommendation_id,
        coalesce(v_rec.org_id::text, null),
        v_from_status,
        v_to_status,
        p_actor,
        v_idempotency_key,
        coalesce(p_metadata, '{}'::jsonb),
        p_expected_version,
        v_next_version,
        now()
    );

    return jsonb_build_object(
        'ok', true,
        'idempotent', false,
        'recommendation_id', p_recommendation_id,
        'status', v_to_status,
        'version', v_next_version
    );
exception
    when unique_violation then
        return jsonb_build_object('ok', true, 'idempotent', true, 'recommendation_id', p_recommendation_id);
    when others then
        return jsonb_build_object('ok', false, 'error', sqlstate, 'message', sqlerrm);
end;
$$;
