-- P3 Data Fabric migration 0017
-- Purpose: atomic canonical entity write bundle RPC.
-- Safety: non-destructive create-or-replace function; no credentials; no runtime execution.

create or replace function data_fabric.data_fabric_atomic_entity_write(p_request jsonb)
returns jsonb
language plpgsql
security definer
set search_path = data_fabric, pg_temp
as $$
declare
    v_org text := p_request #>> '{tenant_context,organization_id}';
    v_tenant text := p_request #>> '{tenant_context,tenant_id}';
    v_operation text := p_request ->> 'operation';
    v_expected_revision integer := nullif(p_request ->> 'expected_revision','')::integer;
    v_key text := p_request ->> 'idempotency_key';
    v_hash text := p_request ->> 'payload_hash';
    v_correlation_id text := p_request ->> 'correlation_id';
    v_actor text := p_request ->> 'actor';
    v_entity jsonb := p_request -> 'entity_record';
    v_entity_payload jsonb := coalesce(v_entity -> 'payload', '{}'::jsonb);
    v_entity_id text := v_entity ->> 'record_id';
    v_entity_uuid uuid;
    v_current data_fabric.enterprise_entities%rowtype;
    v_idempotency data_fabric.idempotency_records%rowtype;
    v_version jsonb;
    v_lineage jsonb;
    v_provenance jsonb;
    v_quality jsonb;
    v_lineage_ids text[] := array[]::text[];
    v_provenance_ids text[] := array[]::text[];
    v_quality_id text;
    v_version_created boolean := false;
    v_result jsonb;
    v_resulting_revision integer;
    v_resulting_version integer;
begin
    if v_org is null or v_tenant is null or v_key is null or v_hash is null or v_entity_id is null then
        raise exception 'P3_VALIDATION_ERROR: organization_id, tenant_id, idempotency_key, payload_hash, and entity record are required';
    end if;
    if v_operation not in ('create','update','deactivate','no_change') then
        raise exception 'P3_VALIDATION_ERROR: unsupported entity atomic write operation';
    end if;
    if v_operation in ('update','deactivate') and v_expected_revision is null then
        raise exception 'P3_REVISION_CONFLICT: expected_revision is required';
    end if;
    if v_entity ->> 'organization_id' <> v_org or v_entity ->> 'tenant_id' <> v_tenant then
        raise exception 'P3_TENANT_BOUNDARY: entity record crosses tenant boundary';
    end if;

    select * into v_idempotency
    from data_fabric.idempotency_records
    where organization_id = v_org and tenant_id = v_tenant and idempotency_key = v_key
    for update;

    if found then
        if v_idempotency.payload_hash <> v_hash then
            raise exception 'P3_IDEMPOTENCY_CONFLICT: same key was used with a different payload hash';
        end if;
        if v_idempotency.status = 'completed' then
            return v_idempotency.result_payload || jsonb_build_object('status','replayed','replayed',true);
        end if;
        if v_idempotency.status = 'in_progress' then
            return jsonb_build_object('status','in_progress','subject_type','entity','subject_id',v_entity_id,'operation',v_operation,'idempotency_status','in_progress','replayed',false,'correlation_id',v_correlation_id);
        end if;
        update data_fabric.idempotency_records
        set status = 'in_progress', failure_reason = null, failed_at = null, revision = revision + 1
        where record_id = v_idempotency.record_id
        returning * into v_idempotency;
    else
        insert into data_fabric.idempotency_records(organization_id, tenant_id, idempotency_key, payload_hash, status, reserved_at, correlation_id)
        values(v_org, v_tenant, v_key, v_hash, 'in_progress', now(), v_correlation_id)
        returning * into v_idempotency;
    end if;

    if v_operation = 'create' then
        insert into data_fabric.enterprise_entities(
            id, canonical_id, entity_type, name, source_system, source_identifier, organization_id, tenant_id,
            version, confidence_score, quality_score, tags, metadata, active, revision, created_at, updated_at,
            deactivated_at, deactivated_by, created_by, updated_by, schema_version
        )
        values(
            v_entity_id,
            v_entity_payload ->> 'canonical_id',
            v_entity_payload ->> 'entity_type',
            v_entity_payload ->> 'name',
            coalesce(v_entity_payload ->> 'source_system', v_entity #>> '{metadata,source_system}'),
            coalesce(v_entity_payload ->> 'source_identifier', v_entity #>> '{metadata,source_identifier}'),
            v_org,
            v_tenant,
            coalesce((v_entity_payload ->> 'version')::integer, 1),
            nullif(v_entity_payload ->> 'confidence_score','')::numeric,
            nullif(v_entity_payload ->> 'quality_score','')::numeric,
            coalesce(v_entity_payload -> 'tags', '[]'::jsonb),
            coalesce(v_entity_payload -> 'metadata', '{}'::jsonb),
            true,
            coalesce((v_entity ->> 'revision')::integer, 1),
            coalesce(nullif(v_entity ->> 'created_at','')::timestamptz, now()),
            coalesce(nullif(v_entity ->> 'updated_at','')::timestamptz, now()),
            null,
            null,
            v_entity ->> 'created_by',
            coalesce(v_entity ->> 'updated_by', v_actor),
            coalesce((v_entity ->> 'schema_version')::integer, 1)
        )
        returning * into v_current;
    elsif v_operation = 'update' then
        update data_fabric.enterprise_entities
        set canonical_id = v_entity_payload ->> 'canonical_id',
            entity_type = v_entity_payload ->> 'entity_type',
            name = v_entity_payload ->> 'name',
            source_system = coalesce(v_entity_payload ->> 'source_system', source_system),
            source_identifier = coalesce(v_entity_payload ->> 'source_identifier', source_identifier),
            version = coalesce((v_entity_payload ->> 'version')::integer, version),
            confidence_score = nullif(v_entity_payload ->> 'confidence_score','')::numeric,
            quality_score = nullif(v_entity_payload ->> 'quality_score','')::numeric,
            tags = coalesce(v_entity_payload -> 'tags', tags),
            metadata = coalesce(v_entity_payload -> 'metadata', metadata),
            active = coalesce((v_entity ->> 'active')::boolean, active),
            revision = revision + 1,
            updated_at = coalesce(nullif(v_entity ->> 'updated_at','')::timestamptz, now()),
            updated_by = coalesce(v_entity ->> 'updated_by', v_actor),
            schema_version = coalesce((v_entity ->> 'schema_version')::integer, schema_version)
        where id = v_entity_id and organization_id = v_org and tenant_id = v_tenant and revision = v_expected_revision
        returning * into v_current;
        if not found then
            raise exception 'P3_REVISION_CONFLICT: stale revision or entity not found';
        end if;
    elsif v_operation = 'deactivate' then
        update data_fabric.enterprise_entities
        set active = false,
            revision = revision + 1,
            updated_at = now(),
            updated_by = coalesce(v_entity ->> 'updated_by', v_actor),
            deactivated_at = coalesce(nullif(v_entity ->> 'deactivated_at','')::timestamptz, now()),
            deactivated_by = coalesce(v_entity ->> 'deactivated_by', v_actor)
        where id = v_entity_id and organization_id = v_org and tenant_id = v_tenant and revision = v_expected_revision
        returning * into v_current;
        if not found then
            raise exception 'P3_REVISION_CONFLICT: stale revision or entity not found';
        end if;
    else
        select * into v_current
        from data_fabric.enterprise_entities
        where id = v_entity_id and organization_id = v_org and tenant_id = v_tenant;
        if not found then
            raise exception 'P3_VALIDATION_ERROR: no_change requires an existing entity';
        end if;
    end if;

    v_resulting_revision := v_current.revision;
    v_resulting_version := v_current.version;
    v_entity_uuid := v_entity_id::uuid;

    v_version := p_request -> 'entity_version';
    if v_version is not null and v_operation <> 'no_change' then
        if v_version ->> 'organization_id' <> v_org or v_version ->> 'tenant_id' <> v_tenant then
            raise exception 'P3_TENANT_BOUNDARY: entity version crosses tenant boundary';
        end if;
        if coalesce(v_version #>> '{payload,entity_id}', v_version #>> '{metadata,entity_id}') <> v_entity_id then
            raise exception 'P3_TENANT_BOUNDARY: entity version subject does not match bundle entity';
        end if;
        if exists (
            select 1 from data_fabric.entity_versions
            where organization_id = v_org and tenant_id = v_tenant and entity_id = v_entity_uuid
            and version >= (v_version #>> '{payload,version}')::integer
        ) then
            raise exception 'P3_DUPLICATE_VERSION: entity version must increase monotonically';
        end if;
        insert into data_fabric.entity_versions(
            snapshot_id, entity_id, canonical_id, organization_id, tenant_id, version, source_system, source_identifier,
            recorded_at, effective_from, effective_to, payload, payload_hash, lineage_references, provenance_references, schema_version
        )
        values(
            (v_version ->> 'record_id')::uuid,
            v_entity_uuid,
            coalesce(v_version #>> '{payload,canonical_id}', v_current.canonical_id),
            v_org,
            v_tenant,
            (v_version #>> '{payload,version}')::integer,
            coalesce(v_version #>> '{payload,source_system}', v_current.source_system),
            coalesce(v_version #>> '{payload,source_identifier}', v_current.source_identifier),
            coalesce(nullif(v_version ->> 'created_at','')::timestamptz, now()),
            nullif(v_version #>> '{payload,effective_from}','')::timestamptz,
            nullif(v_version #>> '{payload,effective_to}','')::timestamptz,
            coalesce(v_version #> '{payload,payload}', v_version -> 'payload', '{}'::jsonb),
            v_version ->> 'payload_hash',
            coalesce(v_version #> '{payload,lineage_references}', '[]'::jsonb),
            coalesce(v_version #> '{payload,provenance_references}', '[]'::jsonb),
            coalesce((v_version ->> 'schema_version')::integer, 1)
        );
        v_version_created := true;
        v_resulting_version := (v_version #>> '{payload,version}')::integer;
    end if;

    for v_lineage in select value from jsonb_array_elements(coalesce(p_request -> 'lineage_events', '[]'::jsonb)) with ordinality order by ordinality loop
        if v_lineage ->> 'organization_id' <> v_org or v_lineage ->> 'tenant_id' <> v_tenant then
            raise exception 'P3_TENANT_BOUNDARY: lineage event crosses tenant boundary';
        end if;
        if coalesce(v_lineage #>> '{payload,entity_id}', v_entity_id) <> v_entity_id then
            raise exception 'P3_TENANT_BOUNDARY: lineage subject does not match bundle entity';
        end if;
        insert into data_fabric.lineage_events(event_id, entity_id, relationship_id, organization_id, tenant_id, event_type, source_system, source_identifier, occurred_at, correlation_id, payload, metadata, schema_version)
        values((v_lineage ->> 'record_id')::uuid, v_entity_uuid, null, v_org, v_tenant, v_lineage #>> '{payload,event_type}', v_lineage #>> '{payload,source_system}', v_lineage #>> '{payload,source_identifier}', coalesce(nullif(v_lineage #>> '{payload,occurred_at}','')::timestamptz, nullif(v_lineage ->> 'created_at','')::timestamptz, now()), coalesce(v_lineage #>> '{payload,correlation_id}', v_correlation_id), coalesce(v_lineage -> 'payload','{}'::jsonb), coalesce(v_lineage -> 'metadata','{}'::jsonb), coalesce((v_lineage ->> 'schema_version')::integer,1));
        v_lineage_ids := array_append(v_lineage_ids, v_lineage ->> 'record_id');
    end loop;

    for v_provenance in select value from jsonb_array_elements(coalesce(p_request -> 'provenance_records', '[]'::jsonb)) with ordinality order by ordinality loop
        if v_provenance ->> 'organization_id' <> v_org or v_provenance ->> 'tenant_id' <> v_tenant then
            raise exception 'P3_TENANT_BOUNDARY: provenance record crosses tenant boundary';
        end if;
        if coalesce(v_provenance #>> '{payload,entity_id}', v_entity_id) <> v_entity_id then
            raise exception 'P3_TENANT_BOUNDARY: provenance subject does not match bundle entity';
        end if;
        insert into data_fabric.provenance_records(provenance_id, entity_id, relationship_id, organization_id, tenant_id, source_system, source_identifier, captured_at, payload_hash, evidence, metadata, schema_version)
        values((v_provenance ->> 'record_id')::uuid, v_entity_uuid, null, v_org, v_tenant, v_provenance #>> '{payload,source_system}', v_provenance #>> '{payload,source_identifier}', coalesce(nullif(v_provenance #>> '{payload,captured_at}','')::timestamptz, nullif(v_provenance ->> 'created_at','')::timestamptz, now()), v_provenance ->> 'payload_hash', coalesce(v_provenance #> '{payload,evidence}', '{}'::jsonb), coalesce(v_provenance -> 'metadata','{}'::jsonb), coalesce((v_provenance ->> 'schema_version')::integer,1));
        v_provenance_ids := array_append(v_provenance_ids, v_provenance ->> 'record_id');
    end loop;

    v_quality := p_request -> 'quality_assessment';
    if v_quality is not null then
        if v_quality ->> 'organization_id' <> v_org or v_quality ->> 'tenant_id' <> v_tenant then
            raise exception 'P3_TENANT_BOUNDARY: quality assessment crosses tenant boundary';
        end if;
        if coalesce(v_quality #>> '{payload,subject_type}', v_quality #>> '{metadata,subject_type}') <> 'entity' or coalesce(v_quality #>> '{payload,subject_id}', v_quality #>> '{metadata,subject_id}') <> v_entity_id then
            raise exception 'P3_TENANT_BOUNDARY: quality subject does not match bundle entity';
        end if;
        insert into data_fabric.quality_assessments(assessment_id, subject_type, subject_id, organization_id, tenant_id, overall_score, trust_score, decision, dimensions, issues, blocking_issues, evaluator_version, assessed_at, metadata, payload_hash, schema_version)
        values((v_quality ->> 'record_id')::uuid, 'entity', v_entity_uuid, v_org, v_tenant, (v_quality #>> '{payload,overall_score}')::numeric, nullif(v_quality #>> '{payload,trust_score}','')::numeric, v_quality #>> '{payload,decision}', coalesce(v_quality #> '{payload,dimensions}', '{}'::jsonb), coalesce(v_quality #> '{payload,issues}', '[]'::jsonb), coalesce(v_quality #> '{payload,blocking_issues}', '[]'::jsonb), v_quality #>> '{payload,evaluator_version}', coalesce(nullif(v_quality #>> '{payload,assessed_at}','')::timestamptz, nullif(v_quality ->> 'created_at','')::timestamptz, now()), coalesce(v_quality -> 'metadata','{}'::jsonb), v_quality ->> 'payload_hash', coalesce((v_quality ->> 'schema_version')::integer,1));
        v_quality_id := v_quality ->> 'record_id';
    end if;

    v_result := jsonb_build_object(
        'status', case when v_operation = 'no_change' then 'no_change' else 'committed' end,
        'subject_type','entity',
        'subject_id',v_entity_id,
        'operation',v_operation,
        'resulting_revision',v_resulting_revision,
        'resulting_version',v_resulting_version,
        'version_created',v_version_created,
        'lineage_ids',to_jsonb(v_lineage_ids),
        'provenance_ids',to_jsonb(v_provenance_ids),
        'quality_assessment_id',v_quality_id,
        'idempotency_status','completed',
        'replayed',false,
        'correlation_id',v_correlation_id,
        'records','[]'::jsonb
    );

    update data_fabric.idempotency_records
    set status = 'completed', result_payload = v_result, completed_at = now(), revision = revision + 1
    where record_id = v_idempotency.record_id and status = 'in_progress'
    returning * into v_idempotency;
    if not found then
        raise exception 'P3_IDEMPOTENCY_CONFLICT: idempotency completion was not in progress';
    end if;

    return v_result;
end;
$$;

comment on function data_fabric.data_fabric_atomic_entity_write(jsonb) is 'P3 atomic entity canonical write bundle. SECURITY DEFINER is used for server-side service-role execution; table references are schema-qualified and PUBLIC execute is revoked.';

revoke all on function data_fabric.data_fabric_atomic_entity_write(jsonb) from public;
grant execute on function data_fabric.data_fabric_atomic_entity_write(jsonb) to service_role;
