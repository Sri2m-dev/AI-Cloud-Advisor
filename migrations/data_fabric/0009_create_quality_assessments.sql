-- P3 Data Fabric migration 0009
-- Purpose: create append-only quality assessment history table.
-- Safety: non-destructive create-if-absent migration; no credentials.
create table if not exists data_fabric.quality_assessments (
    assessment_id uuid primary key,
    subject_type text not null,
    subject_id uuid not null,
    organization_id text not null,
    tenant_id text not null,
    overall_score numeric not null,
    trust_score numeric,
    decision text,
    dimensions jsonb not null,
    issues jsonb not null default '[]'::jsonb,
    blocking_issues jsonb not null default '[]'::jsonb,
    evaluator_version text,
    assessed_at timestamptz not null,
    metadata jsonb not null default '{}'::jsonb,
    payload_hash text,
    schema_version integer not null default 1,
    constraint quality_assessments_subject_type check (subject_type in ('entity','relationship')),
    constraint quality_assessments_overall_score_range check (overall_score >= 0 and overall_score <= 100),
    constraint quality_assessments_trust_score_range check (trust_score is null or (trust_score >= 0 and trust_score <= 100))
);
create index if not exists quality_assessments_subject_idx on data_fabric.quality_assessments (organization_id, tenant_id, subject_type, subject_id);
create index if not exists quality_assessments_assessed_at_idx on data_fabric.quality_assessments (organization_id, tenant_id, assessed_at);
create index if not exists quality_assessments_overall_score_idx on data_fabric.quality_assessments (overall_score);
create index if not exists quality_assessments_decision_idx on data_fabric.quality_assessments (decision);
create or replace function data_fabric.prevent_quality_assessments_mutation() returns trigger language plpgsql as $$ begin raise exception 'quality_assessments is append-only'; end; $$;
do $$ begin
 if not exists (select 1 from pg_trigger where tgname='prevent_quality_assessments_update') then create trigger prevent_quality_assessments_update before update on data_fabric.quality_assessments for each row execute function data_fabric.prevent_quality_assessments_mutation(); end if;
 if not exists (select 1 from pg_trigger where tgname='prevent_quality_assessments_delete') then create trigger prevent_quality_assessments_delete before delete on data_fabric.quality_assessments for each row execute function data_fabric.prevent_quality_assessments_mutation(); end if;
end $$;
alter table data_fabric.quality_assessments enable row level security;
comment on table data_fabric.quality_assessments is 'P3 append-only quality assessment table. RLS is enabled with no anonymous policy.';
