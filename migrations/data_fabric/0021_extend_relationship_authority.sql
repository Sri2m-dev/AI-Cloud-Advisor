-- CMP-P3 additive relationship governance and temporal authority.
alter table data_fabric.enterprise_relationships
    add column if not exists evidence jsonb not null default '[]'::jsonb,
    add column if not exists lineage jsonb not null default '{}'::jsonb,
    add column if not exists provenance jsonb not null default '{}'::jsonb,
    add column if not exists decision_state text not null default 'confirmed',
    add column if not exists effective_from timestamptz,
    add column if not exists effective_to timestamptz,
    add column if not exists actor text,
    add column if not exists actor_role text,
    add column if not exists decision_reason text,
    add column if not exists superseded_by uuid;

alter table data_fabric.enterprise_relationships
    add constraint enterprise_relationships_decision_state_check
    check (decision_state in ('candidate','under_review','confirmed','rejected','revision_required','superseded','inactive')),
    add constraint enterprise_relationships_effective_interval_check
    check (effective_to is null or effective_from is null or effective_to > effective_from);

create index if not exists enterprise_relationships_authority_time_idx
    on data_fabric.enterprise_relationships
    (organization_id, tenant_id, decision_state, effective_from, effective_to);
