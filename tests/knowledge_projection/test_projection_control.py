from dataclasses import replace

import pytest

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from knowledge_projection import (
    CanonicalChange,
    ChangeKind,
    ChangeOperation,
    InMemoryCanonicalChangeLog,
    InMemoryProjectionStore,
    KnowledgeProjectionController,
    ProjectionControlError,
)


def context(name: str = "a") -> TenantContext:
    return TenantContext(f"org-{name}", f"tenant-{name}")


def entity(ctx: TenantContext, subject: str, *, name: str | None = None):
    return EnterpriseEntity(
        id=subject,
        canonical_id=f"canonical-{subject}",
        entity_type="application",
        name=name or subject,
        source_system="canonical",
        source_identifier=f"source-{subject}",
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
    )


def relationship(ctx: TenantContext, subject: str, source: str, target: str):
    return EnterpriseRelationship(
        id=subject,
        relationship_type="depends_on",
        source_entity_id=source,
        target_entity_id=target,
        source_system="canonical",
        source_identifier=f"source-{subject}",
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
    )


def change(
    sequence: int,
    ctx: TenantContext,
    payload=None,
    *,
    kind=ChangeKind.ENTITY,
    operation=ChangeOperation.UPSERT,
    subject_id: str | None = None,
):
    return CanonicalChange(
        sequence=sequence,
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        kind=kind,
        operation=operation,
        subject_id=subject_id or payload.id,
        payload=payload,
    )


def harness():
    source = InMemoryCanonicalChangeLog()
    projection = InMemoryProjectionStore()
    return source, projection, KnowledgeProjectionController(source, projection)


def test_replay_advances_checkpoint_only_after_ordered_canonical_changes():
    ctx = context()
    source, projection, controller = harness()
    source.append(ctx, change(1, ctx, entity(ctx, "a")))
    source.append(ctx, change(2, ctx, entity(ctx, "b")))

    checkpoint = controller.replay(ctx)

    assert checkpoint.sequence == 2
    assert checkpoint.applied_changes == 2
    assert checkpoint.state_hash == projection.state_hash(ctx)
    assert controller.reconcile(ctx).reconciled


def test_incremental_replay_is_idempotent_and_resumes_from_checkpoint():
    ctx = context()
    source, projection, controller = harness()
    source.append(ctx, change(1, ctx, entity(ctx, "a")))
    first = controller.replay(ctx)
    unchanged = controller.replay(ctx)
    source.append(ctx, change(2, ctx, entity(ctx, "b")))
    second = controller.replay(ctx)

    assert unchanged == first
    assert second.sequence == 2
    assert second.applied_changes == 2
    assert len(projection.snapshot(ctx)) == 2


def test_rebuild_is_deterministic_and_repairs_projection_drift():
    ctx = context()
    source, projection, controller = harness()
    source.append(ctx, change(1, ctx, entity(ctx, "a")))
    controller.replay(ctx)
    drifted = {"entity:a": entity(ctx, "a", name="tampered")}
    old = projection.checkpoint(ctx)
    projection._replace(ctx, drifted, old, projection._controller_capability())
    assert controller.reconcile(ctx).divergent == ("entity:a",)

    rebuilt = controller.rebuild(ctx)

    assert rebuilt.state_hash == controller.rebuild(ctx).state_hash
    assert controller.reconcile(ctx).reconciled


def test_remove_replays_as_derived_deletion_without_mutating_canonical_history():
    ctx = context()
    source, projection, controller = harness()
    source.append(ctx, change(1, ctx, entity(ctx, "a")))
    source.append(
        ctx,
        change(
            2,
            ctx,
            kind=ChangeKind.ENTITY,
            operation=ChangeOperation.REMOVE,
            subject_id="a",
        ),
    )

    controller.rebuild(ctx)

    assert projection.snapshot(ctx) == {}
    assert len(source.changes_after(ctx, 0)) == 2


def test_relationship_requires_projected_canonical_endpoints():
    ctx = context()
    source, projection, controller = harness()
    source.append(
        ctx,
        change(
            1,
            ctx,
            relationship(ctx, "r", "missing-a", "missing-b"),
            kind=ChangeKind.RELATIONSHIP,
        ),
    )

    with pytest.raises(ProjectionControlError, match="endpoints"):
        controller.replay(ctx)

    assert projection.checkpoint(ctx) is None
    assert projection.snapshot(ctx) == {}


def test_relationship_replays_after_its_canonical_endpoints():
    ctx = context()
    source, projection, controller = harness()
    source.append(ctx, change(1, ctx, entity(ctx, "a")))
    source.append(ctx, change(2, ctx, entity(ctx, "b")))
    source.append(
        ctx,
        change(
            3,
            ctx,
            relationship(ctx, "r", "a", "b"),
            kind=ChangeKind.RELATIONSHIP,
        ),
    )

    assert controller.replay(ctx).sequence == 3
    assert controller.reconcile(ctx).reconciled


def test_change_log_rejects_gaps_duplicates_and_out_of_order_changes():
    ctx = context()
    source, _, _ = harness()

    with pytest.raises(ProjectionControlError, match="expected 1"):
        source.append(ctx, change(2, ctx, entity(ctx, "b")))
    source.append(ctx, change(1, ctx, entity(ctx, "a")))
    with pytest.raises(ProjectionControlError, match="expected 2"):
        source.append(ctx, change(1, ctx, entity(ctx, "a")))


def test_cross_tenant_changes_are_rejected_and_scopes_do_not_mix():
    ctx_a, ctx_b = context("a"), context("b")
    source, projection, controller = harness()
    with pytest.raises(DataFabricTenantBoundaryError):
        source.append(ctx_a, change(1, ctx_b, entity(ctx_b, "b")))
    source.append(ctx_a, change(1, ctx_a, entity(ctx_a, "a")))
    controller.replay(ctx_a)

    assert projection.snapshot(ctx_b) == {}
    assert controller.reconcile(ctx_b).reconciled


def test_cross_tenant_payload_is_rejected_without_checkpoint_advance():
    ctx_a, ctx_b = context("a"), context("b")
    source, projection, controller = harness()
    cross_tenant = change(1, ctx_a, entity(ctx_b, "foreign"))
    source.append(ctx_a, cross_tenant)

    with pytest.raises(DataFabricTenantBoundaryError):
        controller.replay(ctx_a)
    assert projection.checkpoint(ctx_a) is None


def test_reconciliation_reports_missing_unexpected_and_divergent_state():
    ctx = context()
    source, projection, controller = harness()
    source.append(ctx, change(1, ctx, entity(ctx, "a")))
    controller.replay(ctx)
    state = {
        "entity:a": replace(entity(ctx, "a"), name="different"),
        "entity:extra": entity(ctx, "extra"),
    }
    projection._replace(
        ctx, state, projection.checkpoint(ctx), projection._controller_capability()
    )

    result = controller.reconcile(ctx)

    assert result.divergent == ("entity:a",)
    assert result.unexpected == ("entity:extra",)
    assert result.missing == ()
    assert not result.reconciled


def test_projection_store_rejects_non_controller_writes():
    ctx = context()
    _, projection, _ = harness()
    with pytest.raises(ProjectionControlError, match="canonical controller"):
        projection._replace(
            ctx,
            {"entity:a": entity(ctx, "a")},
            None,
            object(),
        )


def test_projection_has_no_reverse_write_path_to_canonical_authority():
    source, projection, controller = harness()

    assert not hasattr(projection, "append")
    assert not hasattr(controller, "register_entity")
    assert controller._source is source
