from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from connector_sdk import ConnectorRecord
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from data_fabric.source_facts import (
    AuthorityPolicy,
    CloudApiSourceFactAdapter,
    CmdbSourceFactAdapter,
    FactType,
    Freshness,
    LifecycleState,
    ReconciliationOutcome,
    RunStatus,
    SourceFactInput,
    SourceFactService,
    SourceInstance,
    SQLiteSourceFactRepository,
    TelemetrySourceFactAdapter,
    UniversalEvidenceSourceFactAdapter,
)

NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)
CTX = TenantContext("org-1", "tenant-1")


def instance(system="aws", source_type="cloud"):
    return SourceInstance(
        f"{system}-prod",
        "org-1",
        "tenant-1",
        source_type,
        system,
        "connector_sdk",
        "1.0",
        f"config:{system}",
        f"vault:{system}",
    )


def record(value="team-a", **changes):
    values = dict(
        source_record_id="CI-1001",
        fact_type=FactType.APPLICATION_OWNER,
        subject_reference="application:checkout",
        predicate="owned_by",
        value=value,
        observed_at=NOW,
        effective_from=NOW,
        source_schema_version="1",
        freshness=Freshness.FRESH,
        evidence_reference="source:CI-1001",
    )
    values.update(changes)
    return SourceFactInput(**values)


@pytest.fixture
def service(tmp_path):
    repository = SQLiteSourceFactRepository(tmp_path / "cmp-p4.db")
    result = SourceFactService(CTX, repository)
    result.register(instance())
    return result


def test_observation_identity_versioning_replay_and_restart(service):
    first = service.publish(
        instance(),
        (record(),),
        run_id="run-1",
        checkpoint_after="p1",
        schema={"owned_by": "string"},
    )
    replay = service.publish(
        instance(),
        (record(),),
        run_id="run-2",
        mode="replay",
        checkpoint_before="p1",
        checkpoint_after="p1",
        schema={"owned_by": "string"},
    )
    changed = service.publish(
        instance(),
        (record("team-b"),),
        run_id="run-3",
        checkpoint_before="p1",
        checkpoint_after="p2",
        schema={"owned_by": "string"},
    )
    assert first.facts[0].observation_key == changed.facts[0].observation_key
    assert [first.facts[0].fact_version, changed.facts[0].fact_version] == [1, 2]
    assert replay.unchanged == 1 and replay.facts == ()
    restarted = SourceFactService(CTX, SQLiteSourceFactRepository(service.repository.database))
    assert (
        restarted.repository.current_fact(
            "org-1", "tenant-1", first.facts[0].observation_key
        ).fact_version
        == 2
    )
    assert restarted.health(instance()).checkpoint == "p2"


def test_partial_failure_does_not_advance_checkpoint(service):
    service.publish(
        instance(), (record(),), run_id="ok", checkpoint_after="p1", schema={"owned_by": "string"}
    )
    partial = service.publish(
        instance(),
        (),
        run_id="partial",
        status=RunStatus.PARTIAL,
        checkpoint_before="p1",
        checkpoint_after="p2",
        schema={"owned_by": "string"},
        error="token=secret",
    )
    assert partial.checkpoint_after == "p1"
    assert service.health(instance()).checkpoint == "p1"
    assert service.health(instance()).partial_failure_count == 1


def test_schema_drift_additive_and_destructive_quarantine(service):
    service.publish(
        instance(),
        (record(),),
        run_id="base",
        schema={"owned_by": "string"},
        required_fields=("owned_by",),
    )
    additive = service.publish(
        instance(),
        (record(),),
        run_id="add",
        schema={"owned_by": "string", "region": "string"},
        required_fields=("owned_by",),
    )
    assert additive.schema_change.value == "compatible_additive"
    bad = service.publish(
        instance(),
        (record(),),
        run_id="bad",
        schema={"owner": "integer"},
        required_fields=("owned_by",),
        checkpoint_before="p1",
        checkpoint_after="p2",
    )
    assert bad.status is RunStatus.QUARANTINED and bad.facts == ()


def test_absence_is_not_deletion_and_explicit_tombstone_is_versioned(service):
    created = service.publish(instance(), (record(),), run_id="present", schema={}).facts[0]
    service.publish(instance(), (), run_id="absent", schema={})
    assert (
        service.repository.current_fact("org-1", "tenant-1", created.observation_key).lifecycle
        is LifecycleState.ACTIVE
    )
    tombstone = service.publish(
        instance(),
        (record(None, lifecycle=LifecycleState.SOURCE_TOMBSTONE),),
        run_id="delete",
        schema={},
    ).facts[0]
    assert tombstone.fact_version == 2
    assert tombstone.lifecycle is LifecycleState.SOURCE_TOMBSTONE


def test_fact_specific_tenant_policy_conflict_and_explanation(service):
    aws = service.publish(instance(), (record("team-a"),), run_id="aws", schema={}).facts[0]
    snow_instance = instance("servicenow", "cmdb")
    service.register(snow_instance)
    snow = service.publish(snow_instance, (record("team-b"),), run_id="snow", schema={}).facts[0]
    conflict = service.reconcile((aws, snow))
    assert conflict.outcome is ReconciliationOutcome.CANDIDATE_CONFLICT
    policy = AuthorityPolicy(
        "policy-1", "org-1", "tenant-1", FactType.APPLICATION_OWNER, 1, ("servicenow", "aws")
    )
    service.repository.append_policy(policy)
    resolved = service.reconcile((aws, snow), policy=policy)
    assert resolved.selected_fact_id == snow.source_fact_id
    explanation = service.explain(resolved, (aws, snow), policy)
    assert explanation["policy"] == {"id": "policy-1", "version": 1}
    assert {row["source_system"] for row in explanation["sources"]} == {"aws", "servicenow"}


def test_human_decision_requires_attribution_and_cross_tenant_fails(service):
    fact = service.publish(instance(), (record(),), run_id="run", schema={}).facts[0]
    with pytest.raises(ValueError, match="actor"):
        service.reconcile((fact,), selected_fact_id=fact.source_fact_id)
    decision = service.reconcile(
        (fact,),
        selected_fact_id=fact.source_fact_id,
        actor="alice",
        actor_role="client_admin",
        reason="verified",
    )
    assert decision.actor == "alice"
    foreign = replace(fact, tenant_id="tenant-2")
    with pytest.raises(DataFabricTenantBoundaryError):
        service.reconcile((fact, foreign))


def test_four_ingestion_classes_use_one_fact_contract():
    connector_record = ConnectorRecord(
        "r1", "resource", {"subject_id": "r1", "utilization": 20}, NOW
    )
    cloud = CloudApiSourceFactAdapter().adapt(
        (connector_record,), {"utilization": FactType.UTILIZATION}
    )
    cmdb = CmdbSourceFactAdapter().adapt(
        (connector_record,), {"utilization": FactType.APPLICATION_MEMBERSHIP}
    )
    telemetry = TelemetrySourceFactAdapter().adapt(
        (connector_record,), {"utilization": FactType.UTILIZATION}
    )
    file_rows = UniversalEvidenceSourceFactAdapter().adapt(
        ({"source_record_id": "r1", "subject_reference": "r1", "cost_center": "CC100"},),
        {"cost_center": FactType.COST_CENTER},
        file_id="finance.xlsx",
    )
    assert all(isinstance(rows[0], SourceFactInput) for rows in (cloud, cmdb, telemetry, file_rows))


def test_source_deactivation_is_scoped_and_history_remains(service):
    fact = service.publish(instance(), (record(),), run_id="run", schema={}).facts[0]
    assert service.repository.purge_source("org-1", "tenant-1", instance().source_instance_id) == 1
    assert service.repository.current_fact("org-1", "tenant-1", fact.observation_key) == fact
    assert service.repository.purge_source("org-1", "tenant-2", instance().source_instance_id) == 0
    with pytest.raises(ValueError, match="disabled"):
        service.publish(instance(), (record(),), run_id="after-disable", schema={})


def test_identical_source_keys_do_not_collide_across_tenant_persistence(tmp_path):
    database = tmp_path / "shared.db"
    first = SourceFactService(CTX, SQLiteSourceFactRepository(database))
    first.register(instance())
    left = first.publish(instance(), (record(),), run_id="same-run", schema={}).facts[0]
    other_context = TenantContext("org-1", "tenant-2")
    other_instance = replace(instance(), tenant_id="tenant-2")
    second = SourceFactService(other_context, SQLiteSourceFactRepository(database))
    second.register(other_instance)
    right = second.publish(other_instance, (record(),), run_id="same-run", schema={}).facts[0]
    assert left.source_fact_id != right.source_fact_id
    assert len(first.repository.list_current_facts("org-1", "tenant-1")) == 1
    assert len(second.repository.list_current_facts("org-1", "tenant-2")) == 1
