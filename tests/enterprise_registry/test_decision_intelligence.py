from __future__ import annotations

from datetime import datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

from data_fabric.foundation import TenantContext
from decision_intelligence import DecisionIntelligenceService
from enterprise_intelligence.service import EnterpriseIntelligenceService
from evidence_registry import CaseEvidence, CaseRole, EvidenceItem, InMemoryEvidenceRegistry
from recommendation_decision import (
    Actor,
    ActorType,
    DecisionAuthorityRegistry,
    RecommendationDecisionError,
    RecommendationDecisionService,
)
from tests.enterprise_registry.test_enterprise_knowledge_graph import ORG, _graph

CTX = TenantContext(ORG, ORG)
NOW = datetime(2026, 8, 13, tzinfo=timezone.utc)


def _service(recommendations=None):
    graph, account, application, business_service = _graph()
    intelligence = EnterpriseIntelligenceService(CTX, role="auditor", graph=graph)
    return DecisionIntelligenceService(
        CTX, role="auditor", intelligence=intelligence, recommendation_service=recommendations
    ), account


def test_findings_and_prioritization_are_deterministic():
    service, account = _service()
    first, second = service.findings(), service.findings()
    assert [item.finding_id for item in first] == [item.finding_id for item in second]
    assert any(item.subject_canonical_id == account.canonical_id for item in first)
    assert [item.priority.score for item in first] == sorted(
        [item.priority.score for item in first], reverse=True
    )


def test_safe_proposal_has_alternatives_and_financial_terminology():
    service, _ = _service()
    service.intelligence.graph.relationships._relationships = ()
    proposal = service.proposal(service.findings()[0])
    assert len(proposal.alternatives) >= 3
    assert "destructive" in proposal.limitations[0]
    assert (
        proposal.potential_savings
        == proposal.approved_savings
        == proposal.executed_savings
        == proposal.verified_realized_savings
        == 0
    )


def test_ai_proposal_reuses_wp011_and_ai_decision_is_rejected():
    evidence = InMemoryEvidenceRegistry()
    finding_service, _ = _service()
    finding = finding_service.findings()[0]
    item = EvidenceItem(
        "ev-di",
        ORG,
        ORG,
        finding.finding_id,
        "query_engine",
        finding.query_reference,
        "hash",
        NOW,
        NOW,
    )
    evidence.register_evidence(CTX, item)
    evidence.create_package(
        CTX,
        package_id="pkg-di",
        case_id=finding.finding_id,
        evidence=(CaseEvidence("ev-di", CaseRole.SUPPORTING, "governed finding"),),
        created_by="reviewer",
        created_at=NOW,
    )
    evidence.approve_package(CTX, "pkg-di", approved_by="reviewer", approved_at=NOW)
    authority = DecisionAuthorityRegistry()
    authority.grant(CTX, "human-approver")
    governed = RecommendationDecisionService(evidence, authority)
    service, _ = _service(governed)
    recommendation = service.create_program_g_recommendation(
        service.proposal(finding), evidence_package_id="pkg-di"
    )
    assert recommendation.ai_proposed and recommendation.proposer.actor_type is ActorType.AI
    governed.transition(
        CTX,
        recommendation.recommendation_id,
        "proposed",
        actor=recommendation.proposer,
        reason="AI proposal",
    )
    governed.transition(
        CTX,
        recommendation.recommendation_id,
        "under_review",
        actor=recommendation.proposer,
        reason="human review requested",
    )
    with pytest.raises(RecommendationDecisionError, match="AI cannot"):
        governed.decide(
            CTX,
            recommendation.recommendation_id,
            disposition="approve",
            approver=Actor("nexora-ai", ActorType.AI),
            rationale="forbidden",
            decision_id="bad",
        )
    assert not hasattr(service, "execute") and not hasattr(service, "approve")


def test_cross_tenant_finding_projection_rejected_by_underlying_intelligence():
    service, _ = _service()
    assert all(item.tenant_id == CTX.tenant_id for item in service.findings())


def test_decision_intelligence_page_safe_local_runtime(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("pages/decision_intelligence.py", default_timeout=30)
    for key, value in {
        "authenticated": True,
        "auth_backend": "local",
        "user": "auditor@company.com",
        "user_id": "auditor@company.com",
        "email": "auditor@company.com",
        "role": "auditor",
        "organization_id": ORG,
        "organization_name": "Default Org",
        "authorized_organization_ids": [ORG],
        "permissions": [],
    }.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    assert any("Decision Intelligence" in title.value for title in app.title)
