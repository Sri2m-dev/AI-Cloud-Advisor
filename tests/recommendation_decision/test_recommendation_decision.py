from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from data_fabric.foundation import TenantContext
from evidence_registry import (
    CaseEvidence,
    CaseRole,
    EvidenceItem,
    InMemoryEvidenceRegistry,
)
from recommendation_decision import (
    Actor,
    ActorType,
    Alternative,
    DecisionAuthorityRegistry,
    DecisionDisposition,
    RecommendationDecisionError,
    RecommendationDecisionService,
    RecommendationState,
)

NOW = datetime(2026, 7, 24, 6, tzinfo=timezone.utc)


def context(name="a"):
    return TenantContext(f"org-{name}", f"tenant-{name}")


def actor(name, actor_type=ActorType.HUMAN):
    return Actor(name, actor_type)


def alternative(name="no-action"):
    return Alternative(name, "Take no action", "Current state retained", ("risk remains",))


def evidence_item(ctx, evidence_id="ev-1", **metadata):
    return EvidenceItem(
        evidence_id=evidence_id,
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        subject_id="finding-1",
        source_system="connector",
        source_identifier=f"source-{evidence_id}",
        evidence_hash=f"hash-{evidence_id}",
        observed_at=NOW,
        captured_at=NOW,
        lineage_ref=f"lineage-{evidence_id}",
        provenance_ref=f"provenance-{evidence_id}",
        metadata=metadata,
    )


def harness(
    *,
    proposer=None,
    evidence_metadata=None,
    role=CaseRole.SUPPORTING,
):
    ctx = context()
    registry = InMemoryEvidenceRegistry()
    registry.register_evidence(ctx, evidence_item(ctx, **(evidence_metadata or {})))
    registry.create_package(
        ctx,
        package_id="pkg-1",
        case_id="case-1",
        evidence=(CaseEvidence("ev-1", role, "governed evidence"),),
        created_by="evidence-author",
        created_at=NOW,
    )
    registry.approve_package(ctx, "pkg-1", approved_by="evidence-reviewer", approved_at=NOW)
    authority = DecisionAuthorityRegistry()
    authority.grant(ctx, "approver")
    service = RecommendationDecisionService(registry, authority)
    proposer = proposer or actor("proposer")
    recommendation = service.create_recommendation(
        ctx,
        recommendation_id="rec-1",
        finding="Application risk is elevated",
        proposed_action="Remediate the application",
        expected_outcome="Risk reduced",
        alternatives=(alternative(), Alternative("remediate", "Remediate", "Risk reduced")),
        evidence_package_id="pkg-1",
        proposer=proposer,
        created_at=NOW,
        assumptions=("Evidence remains representative",),
        risks=("Change risk",),
        confidence=0.8,
        metadata={"reasoning": "derived"},
    )
    return ctx, registry, authority, service, recommendation


def under_review(service, ctx, proposer=None):
    proposer = proposer or actor("proposer")
    service.transition(
        ctx, "rec-1", RecommendationState.PROPOSED, actor=proposer, reason="submit", occurred_at=NOW
    )
    return service.transition(
        ctx,
        "rec-1",
        RecommendationState.UNDER_REVIEW,
        actor=actor("reviewer"),
        reason="review",
        occurred_at=NOW,
    )


def test_human_recommendation_contains_required_content_and_alternatives():
    _, _, _, _, recommendation = harness()
    assert recommendation.proposer.actor_type is ActorType.HUMAN
    assert recommendation.state is RecommendationState.DRAFT
    assert [item.alternative_id for item in recommendation.alternatives] == [
        "no-action",
        "remediate",
    ]
    assert recommendation.evidence_package_hash


def test_ai_recommendation_is_valid_and_explicitly_identified():
    _, _, _, _, recommendation = harness(proposer=actor("ai-proposer", ActorType.AI))
    assert recommendation.ai_proposed


def test_ai_self_approval_is_rejected():
    ctx, _, authority, service, _ = harness(proposer=actor("ai-proposer", ActorType.AI))
    authority.grant(ctx, "ai-proposer")
    under_review(service, ctx, actor("ai-proposer", ActorType.AI))
    with pytest.raises(RecommendationDecisionError, match="AI cannot"):
        service.decide(
            ctx,
            "rec-1",
            disposition=DecisionDisposition.APPROVE,
            approver=actor("ai-proposer", ActorType.AI),
            rationale="self approval",
            decision_id="dec-1",
        )


def test_alternate_ai_approver_is_rejected_even_if_granted():
    ctx, _, authority, service, _ = harness(proposer=actor("ai-proposer", ActorType.AI))
    authority.grant(ctx, "other-ai")
    under_review(service, ctx, actor("ai-proposer", ActorType.AI))
    with pytest.raises(RecommendationDecisionError, match="AI cannot"):
        service.decide(
            ctx,
            "rec-1",
            disposition="approve",
            approver=actor("other-ai", ActorType.AI),
            rationale="AI approval",
            decision_id="dec-1",
        )


def test_authorized_human_can_approve_ai_recommendation():
    ctx, _, _, service, _ = harness(proposer=actor("ai-proposer", ActorType.AI))
    under_review(service, ctx, actor("ai-proposer", ActorType.AI))
    decision = service.decide(
        ctx,
        "rec-1",
        disposition="approve",
        approver=actor("approver"),
        rationale="authorized human disposition",
        decision_id="dec-1",
        created_at=NOW,
    )
    assert decision.authority_result == "AUTHORIZED"
    assert service.get_recommendation(ctx, "rec-1").state is RecommendationState.APPROVED


def test_human_proposer_self_approval_is_rejected():
    ctx, _, authority, service, _ = harness()
    authority.grant(ctx, "proposer")
    under_review(service, ctx)
    with pytest.raises(RecommendationDecisionError, match="own recommendation"):
        service.decide(
            ctx, "rec-1", disposition="approve", approver=actor("proposer"),
            rationale="self", decision_id="dec-1"
        )


def test_unauthorized_human_approval_is_rejected_without_decision():
    ctx, _, _, service, _ = harness()
    under_review(service, ctx)
    with pytest.raises(RecommendationDecisionError, match="explicit decision authority"):
        service.decide(
            ctx, "rec-1", disposition="approve", approver=actor("unknown"),
            rationale="unauthorized", decision_id="dec-1"
        )
    assert service.decision_history(ctx, "rec-1") == ()


@pytest.mark.parametrize(
    "disposition,state",
    [
        (DecisionDisposition.REJECT, RecommendationState.REJECTED),
        (DecisionDisposition.REQUEST_REVISION, RecommendationState.REVISION_REQUIRED),
    ],
)
def test_rejection_and_revision_request_are_governed(disposition, state):
    ctx, _, _, service, _ = harness()
    under_review(service, ctx)
    decision = service.decide(
        ctx, "rec-1", disposition=disposition, approver=actor("approver"),
        rationale="governed disposition", decision_id="dec-1", created_at=NOW
    )
    assert decision.disposition is disposition
    assert service.get_recommendation(ctx, "rec-1").state is state


def test_withdrawal_and_invalid_transitions_fail_closed():
    ctx, _, _, service, _ = harness()
    withdrawn = service.transition(
        ctx, "rec-1", "withdrawn", actor=actor("proposer"), reason="withdraw", occurred_at=NOW
    )
    assert withdrawn.state is RecommendationState.WITHDRAWN
    with pytest.raises(RecommendationDecisionError, match="invalid lifecycle"):
        service.transition(
            ctx, "rec-1", "approved", actor=actor("proposer"), reason="bypass"
        )


@pytest.mark.parametrize(
    "metadata,expected",
    [
        ({"freshness": "stale"}, "STALE"),
        ({"conflicting": True}, "CONFLICTING"),
    ],
)
def test_stale_or_conflicting_evidence_blocks_approval(metadata, expected):
    ctx, _, _, service, _ = harness(evidence_metadata=metadata)
    under_review(service, ctx)
    with pytest.raises(RecommendationDecisionError, match=expected):
        service.decide(
            ctx, "rec-1", disposition="approve", approver=actor("approver"),
            rationale="unsafe", decision_id="dec-1"
        )


def test_missing_supporting_evidence_blocks_approval():
    ctx, _, _, service, _ = harness(role=CaseRole.CONTEXT)
    under_review(service, ctx)
    with pytest.raises(RecommendationDecisionError, match="MISSING"):
        service.decide(
            ctx, "rec-1", disposition="approve", approver=actor("approver"),
            rationale="missing", decision_id="dec-1"
        )


def test_superseded_evidence_package_blocks_approval():
    ctx, registry, _, service, _ = harness()
    registry.create_package(
        ctx, package_id="pkg-2", case_id="case-1",
        evidence=(CaseEvidence("ev-1", CaseRole.SUPPORTING, "replacement"),),
        created_by="author", created_at=NOW, supersedes_package_id="pkg-1"
    )
    registry.approve_package(ctx, "pkg-2", approved_by="reviewer", approved_at=NOW)
    under_review(service, ctx)
    with pytest.raises(RecommendationDecisionError, match="SUPERSEDED"):
        service.decide(
            ctx, "rec-1", disposition="approve", approver=actor("approver"),
            rationale="old evidence", decision_id="dec-1"
        )


def test_unapproved_or_cross_tenant_evidence_binding_is_rejected():
    ctx, registry, authority, _, _ = harness()
    registry.create_package(
        ctx, package_id="draft", case_id="case-2",
        evidence=(CaseEvidence("ev-1", CaseRole.SUPPORTING, "draft"),),
        created_by="author", created_at=NOW
    )
    service = RecommendationDecisionService(registry, authority)
    with pytest.raises(RecommendationDecisionError, match="must be approved"):
        service.create_recommendation(
            ctx, recommendation_id="draft-rec", finding="f", proposed_action="a",
            expected_outcome="o", alternatives=(alternative(),),
            evidence_package_id="draft", proposer=actor("proposer")
        )
    with pytest.raises(Exception, match="tenant scope"):
        service.create_recommendation(
            context("b"), recommendation_id="foreign", finding="f", proposed_action="a",
            expected_outcome="o", alternatives=(alternative(),),
            evidence_package_id="pkg-1", proposer=actor("proposer")
        )


def test_cross_tenant_recommendation_decision_and_reconstruction_are_rejected():
    ctx, _, _, service, _ = harness()
    under_review(service, ctx)
    service.decide(
        ctx, "rec-1", disposition="approve", approver=actor("approver"),
        rationale="valid", decision_id="dec-1", created_at=NOW
    )
    other = context("b")
    with pytest.raises(RecommendationDecisionError, match="tenant scope"):
        service.get_recommendation(other, "rec-1")
    with pytest.raises(RecommendationDecisionError, match="tenant scope"):
        service.reconstruct(other, "dec-1")


def test_correction_creates_new_version_and_preserves_decision():
    ctx, _, _, service, _ = harness()
    under_review(service, ctx)
    original_decision = service.decide(
        ctx, "rec-1", disposition="request_revision", approver=actor("approver"),
        rationale="revise", decision_id="dec-1", created_at=NOW
    )
    corrected = service.correct_recommendation(
        ctx, "rec-1", actor=actor("proposer"), proposed_action="Corrected action",
        created_at=NOW
    )
    assert corrected.version == 2
    assert corrected.state is RecommendationState.DRAFT
    assert service.get_recommendation(ctx, "rec-1", 1).state is RecommendationState.REVISION_REQUIRED
    assert service.decision_history(ctx, "rec-1") == (original_decision,)


def test_supersession_preserves_original_recommendation_and_decision():
    ctx, _, _, service, original = harness()
    under_review(service, ctx)
    decision = service.decide(
        ctx, "rec-1", disposition="reject", approver=actor("approver"),
        rationale="reject", decision_id="dec-1", created_at=NOW
    )
    service.transition(
        ctx, "rec-1", "superseded", actor=actor("proposer"), reason="replacement", occurred_at=NOW
    )
    successor = service.create_recommendation(
        ctx, recommendation_id="rec-2", finding="replacement finding",
        proposed_action="replacement action", expected_outcome="replacement outcome",
        alternatives=(alternative(),), evidence_package_id="pkg-1",
        proposer=actor("proposer"), created_at=NOW,
        supersedes_recommendation_id="rec-1:v1"
    )
    assert service.get_recommendation(ctx, "rec-1", 1).state is RecommendationState.SUPERSEDED
    assert service.decision_history(ctx, "rec-1") == (decision,)
    assert successor.supersedes_recommendation_id == "rec-1:v1"
    assert original.recommendation_id == "rec-1"


def test_approved_decision_is_immutable():
    ctx, _, _, service, _ = harness()
    under_review(service, ctx)
    decision = service.decide(
        ctx, "rec-1", disposition="approve", approver=actor("approver"),
        rationale="valid", decision_id="dec-1", created_at=NOW
    )
    with pytest.raises(FrozenInstanceError):
        decision.rationale = "rewritten"


def test_deterministic_complete_decision_reconstruction():
    ctx, _, _, service, _ = harness(proposer=actor("ai-proposer", ActorType.AI))
    under_review(service, ctx, actor("ai-proposer", ActorType.AI))
    service.decide(
        ctx, "rec-1", disposition="approve", approver=actor("approver"),
        rationale="authorized", decision_id="dec-1", created_at=NOW
    )
    first = service.reconstruct(ctx, "dec-1")
    second = service.reconstruct(ctx, "dec-1")

    assert first == second
    assert first["recommendation"]["id"] == "rec-1"
    assert first["recommendation"]["version"] == 1
    assert first["recommendation"]["proposer"]["actor_id"] == "ai-proposer"
    assert first["recommendation"]["ai_proposed"]
    assert first["recommendation"]["finding"]
    assert first["recommendation"]["proposed_action"]
    assert first["recommendation"]["alternatives"]
    assert first["recommendation"]["evidence_package_id"] == "pkg-1"
    assert first["recommendation"]["evidence_package_hash"]
    assert first["evidence"][0]["hash"] == "hash-ev-1"
    assert first["evidence"][0]["lineage_ref"] == "lineage-ev-1"
    assert first["evidence"][0]["provenance_ref"] == "provenance-ev-1"
    assert first["decision"]["authority_result"] == "AUTHORIZED"
    assert first["decision"]["approver"]["actor_id"] == "approver"
    assert first["history"]
    assert len(first["reconstruction_hash"]) == 64


def test_no_execution_policy_or_canonical_side_effect_interface():
    _, _, _, service, _ = harness()
    assert not hasattr(service, "execute")
    assert not hasattr(service, "authorize_policy")
    assert not hasattr(service, "register_entity")
