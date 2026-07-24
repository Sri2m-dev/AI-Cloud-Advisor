from datetime import datetime, timedelta, timezone

import pytest

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from governed_queries import (
    EvidenceReference,
    EvidenceState,
    GovernedQueryService,
    QueryControlError,
    QueryLimits,
)
from knowledge_projection import (
    CanonicalChange,
    ChangeKind,
    InMemoryCanonicalChangeLog,
    InMemoryProjectionStore,
    KnowledgeProjectionController,
)

NOW = datetime(2026, 7, 24, 3, tzinfo=timezone.utc)


def context(name="a"):
    return TenantContext(f"org-{name}", f"tenant-{name}")


def entity(ctx, subject, *, updated_at=NOW):
    return EnterpriseEntity(
        id=subject,
        canonical_id=f"canonical-{subject}",
        entity_type="application",
        name=subject,
        source_system="canonical",
        source_identifier=f"source-{subject}",
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        updated_at=updated_at,
        version=2,
    )


def relationship(ctx, subject, source, target):
    return EnterpriseRelationship(
        id=subject,
        relationship_type="depends_on",
        source_entity_id=source,
        target_entity_id=target,
        source_system="canonical",
        source_identifier=f"source-{subject}",
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        updated_at=NOW,
    )


def evidence(ctx, subject, name, *, observed_at=NOW, state=EvidenceState.AVAILABLE):
    return EvidenceReference(
        subject_id=subject,
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        evidence_id=name,
        observed_at=observed_at,
        state=state,
        source_system="canonical",
        lineage_ref=f"lineage-{name}",
        provenance_ref=f"provenance-{name}",
    )


def harness(edges=(("r1", "a", "b"), ("r2", "b", "c"))):
    ctx = context()
    source = InMemoryCanonicalChangeLog()
    projection = InMemoryProjectionStore()
    sequence = 0
    entity_ids = sorted({item for _, source_id, target_id in edges for item in (source_id, target_id)})
    for subject in entity_ids:
        sequence += 1
        source.append(
            ctx,
            CanonicalChange(
                sequence,
                ctx.organization_id,
                ctx.tenant_id,
                ChangeKind.ENTITY,
                "upsert",
                subject,
                entity(ctx, subject),
            ),
        )
    for rel_id, source_id, target_id in edges:
        sequence += 1
        source.append(
            ctx,
            CanonicalChange(
                sequence,
                ctx.organization_id,
                ctx.tenant_id,
                ChangeKind.RELATIONSHIP,
                "upsert",
                rel_id,
                relationship(ctx, rel_id, source_id, target_id),
            ),
        )
    KnowledgeProjectionController(source, projection).rebuild(ctx)
    return ctx, source, projection, GovernedQueryService(projection)


def test_dependency_paths_are_stable_and_reproducible():
    ctx, _, _, service = harness((("z", "a", "c"), ("a", "a", "b"), ("b", "b", "c")))
    first = service.dependency_query(ctx, "a", evaluated_at=NOW)
    second = service.dependency_query(ctx, "a", evaluated_at=NOW)

    assert first == second
    assert [path.relationship_ids for path in first.paths] == [
        ("a",),
        ("z",),
        ("a", "b"),
    ]


def test_impact_query_is_deterministic_and_identifies_derived_inference():
    ctx, _, _, service = harness()
    result = service.impact_query(ctx, "a", evaluated_at=NOW)

    assert result.entity_ids == ("a", "b", "c")
    assert result.relationship_ids == ("r1", "r2")
    assert result.inference.startswith("Impact set derived")


def test_evidence_query_returns_lineage_provenance_and_missing_disclosure():
    ctx, _, _, service = harness()
    result = service.evidence_query(
        ctx,
        ("a", "b"),
        evidence=(evidence(ctx, "a", "ev-a"),),
        evaluated_at=NOW,
    )

    assert result.evidence[0].lineage_ref == "lineage-ev-a"
    assert result.evidence[0].provenance_ref == "provenance-ev-a"
    assert result.evidence[1].state is EvidenceState.MISSING
    assert result.metadata.partial_reasons == ("missing_evidence",)


def test_cross_tenant_starting_entity_is_not_visible():
    ctx, _, _, service = harness()
    with pytest.raises(QueryControlError, match="checkpoint"):
        service.dependency_query(context("b"), "a")


def test_cross_tenant_evidence_is_rejected():
    ctx, _, _, service = harness()
    with pytest.raises(DataFabricTenantBoundaryError):
        service.evidence_query(
            ctx,
            ("a",),
            evidence=(evidence(context("b"), "a", "foreign"),),
            evaluated_at=NOW,
        )


def test_cross_tenant_projected_path_fails_closed():
    ctx, _, projection, service = harness()
    state = projection.snapshot(ctx)
    state["entity:foreign"] = entity(context("b"), "foreign")
    state["relationship:foreign-rel"] = relationship(
        context("b"), "foreign-rel", "a", "foreign"
    )
    projection._replace(
        ctx, state, projection.checkpoint(ctx), projection._controller_capability()
    )
    with pytest.raises(DataFabricTenantBoundaryError):
        service.dependency_query(ctx, "a")


def test_depth_limit_is_disclosed_as_partial_and_deterministic():
    ctx, _, _, service = harness()
    result = service.dependency_query(
        ctx, "a", limits=QueryLimits(max_depth=1), evaluated_at=NOW
    )

    assert [path.relationship_ids for path in result.paths] == [("r1",)]
    assert result.metadata.truncated
    assert result.metadata.truncation_reason == "depth_limit"
    assert result.metadata.partial


def test_result_limit_is_deterministic():
    ctx, _, _, service = harness(
        (("r3", "a", "d"), ("r1", "a", "b"), ("r2", "a", "c"))
    )
    result = service.dependency_query(
        ctx, "a", limits=QueryLimits(max_results=2), evaluated_at=NOW
    )
    assert [path.relationship_ids for path in result.paths] == [("r1",), ("r2",)]
    assert result.metadata.truncation_reason == "result_limit"


def test_fan_out_limit_sorts_before_truncating():
    ctx, _, _, service = harness(
        (("r3", "a", "d"), ("r1", "a", "b"), ("r2", "a", "c"))
    )
    result = service.dependency_query(
        ctx, "a", limits=QueryLimits(max_fan_out=2), evaluated_at=NOW
    )
    assert [path.relationship_ids for path in result.paths] == [("r1",), ("r2",)]
    assert "fan_out_limit" in result.metadata.partial_reasons


def test_work_budget_is_bounded_and_disclosed():
    ctx, _, _, service = harness()
    result = service.dependency_query(
        ctx, "a", limits=QueryLimits(work_budget=1), evaluated_at=NOW
    )
    assert result.metadata.work_consumed == 1
    assert result.metadata.truncation_reason == "work_budget"


@pytest.mark.parametrize(
    "limits",
    [
        QueryLimits(max_depth=11),
        QueryLimits(max_results=101),
        QueryLimits(max_fan_out=51),
        QueryLimits(work_budget=1001),
    ],
)
def test_requests_over_hard_limits_are_rejected(limits):
    ctx, _, _, service = harness()
    with pytest.raises(QueryControlError, match="governed limit"):
        service.dependency_query(ctx, "a", limits=limits)


def test_cycles_are_safe_and_do_not_repeat_entities_in_a_path():
    ctx, _, _, service = harness(
        (("r1", "a", "b"), ("r2", "b", "c"), ("r3", "c", "a"))
    )
    result = service.dependency_query(ctx, "a", evaluated_at=NOW)
    assert all(len(path.entity_ids) == len(set(path.entity_ids)) for path in result.paths)
    assert len(result.paths) == 2


def test_stale_evidence_is_not_presented_as_fresh():
    ctx, _, _, service = harness()
    result = service.evidence_query(
        ctx,
        ("a",),
        evidence=(evidence(ctx, "a", "old", observed_at=NOW - timedelta(days=2)),),
        evaluated_at=NOW,
    )
    assert result.evidence[0].state is EvidenceState.STALE
    assert result.metadata.partial_reasons == ("stale_evidence",)


def test_projection_checkpoint_version_and_temporal_metadata_are_disclosed():
    ctx, _, projection, service = harness()
    result = service.dependency_query(ctx, "a", evaluated_at=NOW)
    checkpoint = projection.checkpoint(ctx)

    assert result.metadata.checkpoint_sequence == checkpoint.sequence
    assert result.metadata.projection_state_hash == checkpoint.state_hash
    assert result.metadata.projection_time == NOW
    assert result.metadata.evaluated_at == NOW
    assert result.metadata.as_of is None
    assert result.entity_versions == {"a": 2, "b": 2, "c": 2}
    assert result.relationship_versions == {"r1": 1, "r2": 1}


def test_unsupported_historical_query_is_rejected_not_misrepresented_as_current():
    ctx, _, _, service = harness()
    with pytest.raises(QueryControlError, match="historical query is unsupported"):
        service.dependency_query(ctx, "a", as_of=NOW - timedelta(days=1))


def test_checkpoint_is_required():
    projection = InMemoryProjectionStore()
    with pytest.raises(QueryControlError, match="checkpoint"):
        GovernedQueryService(projection).dependency_query(context(), "a")


def test_query_boundary_has_no_canonical_write_back_interface():
    _, source, _, service = harness()
    before = source.changes_after(context(), 0)

    assert not hasattr(service, "register_entity")
    assert not hasattr(service, "append")
    assert source.changes_after(context(), 0) == before
