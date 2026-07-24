from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

import pytest

from data_fabric.foundation import TenantContext
from evidence_registry import (
    CaseEvidence,
    CaseRole,
    EvidenceItem,
    EvidencePackageStatus,
    EvidenceRegistryError,
    InMemoryEvidenceRegistry,
)

NOW = datetime(2026, 7, 24, 5, tzinfo=timezone.utc)


def context(name="a"):
    return TenantContext(f"org-{name}", f"tenant-{name}")


def item(
    ctx,
    evidence_id="ev-1",
    *,
    source_identifier="source-1",
    evidence_hash="hash-1",
    corrects=None,
):
    return EvidenceItem(
        evidence_id=evidence_id,
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        subject_id="application-a",
        source_system="connector",
        source_identifier=source_identifier,
        evidence_hash=evidence_hash,
        observed_at=NOW,
        captured_at=NOW,
        lineage_ref=f"lineage-{evidence_id}",
        provenance_ref=f"provenance-{evidence_id}",
        quality_score=0.9,
        corrects_evidence_id=corrects,
        metadata={"checkpoint": "cp-1"},
    )


def case_evidence(evidence_id="ev-1", role=CaseRole.SUPPORTING):
    return CaseEvidence(evidence_id, role, f"{role.value} case evidence")


def registry_with_item(ctx=None):
    ctx = ctx or context()
    registry = InMemoryEvidenceRegistry()
    registry.register_evidence(ctx, item(ctx))
    return ctx, registry


def test_registers_governed_reference_with_existing_provenance_semantics():
    ctx, registry = registry_with_item()
    stored = registry.get_evidence(ctx, "ev-1")

    assert stored.lineage_ref == "lineage-ev-1"
    assert stored.provenance_ref == "provenance-ev-1"
    assert stored.metadata["checkpoint"] == "cp-1"


def test_identical_source_evidence_is_deduplicated_without_second_truth():
    ctx, registry = registry_with_item()
    duplicate = replace(item(ctx), evidence_id="ev-duplicate")

    assert registry.register_evidence(ctx, duplicate).evidence_id == "ev-1"
    with pytest.raises(EvidenceRegistryError, match="not found"):
        registry.get_evidence(ctx, "ev-duplicate")


def test_conflicting_source_requires_explicit_correction():
    ctx, registry = registry_with_item()
    with pytest.raises(EvidenceRegistryError, match="explicit correction"):
        registry.register_evidence(
            ctx, item(ctx, "ev-2", evidence_hash="different")
        )


def test_correction_preserves_original_and_records_successor():
    ctx, registry = registry_with_item()
    corrected = item(
        ctx, "ev-2", evidence_hash="hash-2", corrects="ev-1"
    )

    registry.register_evidence(ctx, corrected)

    assert registry.get_evidence(ctx, "ev-1").evidence_hash == "hash-1"
    assert registry.get_evidence(ctx, "ev-2").corrects_evidence_id == "ev-1"
    assert registry.is_evidence_superseded(ctx, "ev-1")
    assert registry.evidence_successor(ctx, "ev-1") == "ev-2"


def test_second_correction_of_same_version_is_rejected():
    ctx, registry = registry_with_item()
    registry.register_evidence(
        ctx, item(ctx, "ev-2", evidence_hash="hash-2", corrects="ev-1")
    )
    with pytest.raises(EvidenceRegistryError, match="already superseded"):
        registry.register_evidence(
            ctx,
            item(
                ctx,
                "ev-3",
                source_identifier="source-1",
                evidence_hash="hash-3",
                corrects="ev-1",
            ),
        )


def test_evidence_contract_is_immutable():
    ctx, registry = registry_with_item()
    with pytest.raises(FrozenInstanceError):
        registry.get_evidence(ctx, "ev-1").evidence_hash = "changed"


def test_package_assigns_explicit_case_roles_with_stable_ordering():
    ctx, registry = registry_with_item()
    registry.register_evidence(
        ctx, item(ctx, "ev-2", source_identifier="source-2", evidence_hash="hash-2")
    )
    package = registry.create_package(
        ctx,
        package_id="pkg-1",
        case_id="case-1",
        evidence=(
            case_evidence("ev-1", CaseRole.SUPPORTING),
            case_evidence("ev-2", CaseRole.CONTRADICTING),
        ),
        created_by="author",
        created_at=NOW,
    )

    assert [entry.role for entry in package.evidence] == [
        CaseRole.CONTRADICTING,
        CaseRole.SUPPORTING,
    ]


def test_empty_or_duplicate_evidence_package_is_rejected():
    ctx, registry = registry_with_item()
    with pytest.raises(EvidenceRegistryError, match="cannot be empty"):
        registry.create_package(
            ctx,
            package_id="empty",
            case_id="case-1",
            evidence=(),
            created_by="author",
        )
    with pytest.raises(EvidenceRegistryError, match="duplicate"):
        registry.create_package(
            ctx,
            package_id="duplicate",
            case_id="case-1",
            evidence=(case_evidence(), case_evidence()),
            created_by="author",
        )


def test_package_cannot_reference_missing_or_superseded_evidence():
    ctx, registry = registry_with_item()
    with pytest.raises(EvidenceRegistryError, match="not found"):
        registry.create_package(
            ctx,
            package_id="missing",
            case_id="case-1",
            evidence=(case_evidence("missing"),),
            created_by="author",
        )
    registry.register_evidence(
        ctx, item(ctx, "ev-2", evidence_hash="hash-2", corrects="ev-1")
    )
    with pytest.raises(EvidenceRegistryError, match="superseded evidence"):
        registry.create_package(
            ctx,
            package_id="old",
            case_id="case-1",
            evidence=(case_evidence("ev-1"),),
            created_by="author",
        )


def test_approval_creates_integrity_hash_and_immutable_package():
    ctx, registry = registry_with_item()
    registry.create_package(
        ctx,
        package_id="pkg-1",
        case_id="case-1",
        evidence=(case_evidence(),),
        created_by="author",
        created_at=NOW,
    )
    approved = registry.approve_package(
        ctx, "pkg-1", approved_by="reviewer", approved_at=NOW
    )

    assert approved.status is EvidencePackageStatus.APPROVED
    assert len(approved.package_hash) == 64
    with pytest.raises(FrozenInstanceError):
        approved.case_id = "changed"
    with pytest.raises(EvidenceRegistryError, match="immutable"):
        registry.approve_package(ctx, "pkg-1", approved_by="another")


def test_package_supersession_preserves_approved_history():
    ctx, registry = registry_with_item()
    registry.create_package(
        ctx,
        package_id="pkg-1",
        case_id="case-1",
        evidence=(case_evidence(),),
        created_by="author",
        created_at=NOW,
    )
    first = registry.approve_package(
        ctx, "pkg-1", approved_by="reviewer", approved_at=NOW
    )
    registry.create_package(
        ctx,
        package_id="pkg-2",
        case_id="case-1",
        evidence=(case_evidence(),),
        created_by="author",
        created_at=NOW,
        supersedes_package_id="pkg-1",
    )
    second = registry.approve_package(
        ctx, "pkg-2", approved_by="reviewer", approved_at=NOW
    )

    assert registry.get_package(ctx, "pkg-1") == first
    assert second.version == 2
    assert second.supersedes_package_id == "pkg-1"
    assert registry.is_package_superseded(ctx, "pkg-1")
    assert registry.package_successor(ctx, "pkg-1") == "pkg-2"
    assert registry.case_history(ctx, "case-1") == (first, second)


def test_draft_or_different_case_cannot_be_superseded():
    ctx, registry = registry_with_item()
    registry.create_package(
        ctx,
        package_id="draft",
        case_id="case-1",
        evidence=(case_evidence(),),
        created_by="author",
    )
    with pytest.raises(EvidenceRegistryError, match="approved"):
        registry.create_package(
            ctx,
            package_id="next",
            case_id="case-1",
            evidence=(case_evidence(),),
            created_by="author",
            supersedes_package_id="draft",
        )
    registry.approve_package(ctx, "draft", approved_by="reviewer")
    with pytest.raises(EvidenceRegistryError, match="same case"):
        registry.create_package(
            ctx,
            package_id="other",
            case_id="case-2",
            evidence=(case_evidence(),),
            created_by="author",
            supersedes_package_id="draft",
        )


def test_cross_tenant_evidence_and_package_access_is_denied_by_scope():
    ctx, registry = registry_with_item()
    other = context("b")
    with pytest.raises(EvidenceRegistryError, match="not found"):
        registry.get_evidence(other, "ev-1")
    with pytest.raises(EvidenceRegistryError, match="not found"):
        registry.get_package(other, "pkg-1")


def test_cross_tenant_item_registration_is_rejected():
    ctx, registry = registry_with_item()
    with pytest.raises(Exception, match="tenant boundary"):
        registry.register_evidence(ctx, item(context("b"), "foreign"))


def test_case_history_is_tenant_scoped_and_deterministic():
    ctx, registry = registry_with_item()
    for package_id, case_id in (("p1", "case-1"), ("p2", "case-2")):
        registry.create_package(
            ctx,
            package_id=package_id,
            case_id=case_id,
            evidence=(case_evidence(),),
            created_by="author",
            created_at=NOW,
        )
    assert tuple(row.package_id for row in registry.case_history(ctx, "case-1")) == (
        "p1",
    )
    assert registry.case_history(context("b"), "case-1") == ()


def test_no_runtime_database_or_canonical_write_interface_is_exposed():
    _, registry = registry_with_item()
    assert not hasattr(registry, "execute_sql")
    assert not hasattr(registry, "register_entity")
    assert not hasattr(registry, "apply_migration")
