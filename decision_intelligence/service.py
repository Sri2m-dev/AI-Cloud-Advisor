from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from decision_intelligence.models import (
    FindingType,
    IntelligenceFinding,
    PriorityBreakdown,
    RecommendationProposal,
)
from recommendation_decision import Actor, ActorType, Alternative


class DecisionIntelligenceService:
    """Deterministic finding projection and adapter into Program G contracts."""

    def __init__(self, context, *, role, intelligence, recommendation_service=None):
        self.context, self.role = context, role
        self.intelligence = intelligence
        self.recommendations = recommendation_service

    def findings(self):
        rows = []
        for entity in self.intelligence.graph.search_graph(""):
            response = self.intelligence.get_enterprise_context(entity.canonical_id)
            amount = self.intelligence.graph._amount(
                response.context.financial.values if response.context else {}
            )
            unowned = not entity.ownership_reference
            incomplete = entity.classification_status in {
                "UNCLASSIFIED",
                "NEEDS_REVIEW",
                "CONFLICTED",
            }
            if amount > 0 and incomplete:
                rows.append(
                    self._finding(
                        entity,
                        response,
                        amount,
                        "HIGH_COST_CLASSIFICATION_INCOMPLETE",
                        FindingType.CLASSIFICATION,
                        "high",
                    )
                )
            if amount > 0 and unowned:
                rows.append(
                    self._finding(
                        entity,
                        response,
                        amount,
                        "HIGH_COST_UNOWNED_ENTITY",
                        FindingType.OWNERSHIP,
                        "high",
                    )
                )
            if entity.classification_status == "CONFLICTED":
                rows.append(
                    self._finding(
                        entity,
                        response,
                        amount,
                        "CLASSIFICATION_CONFLICT",
                        FindingType.GOVERNANCE,
                        "high",
                    )
                )
        return tuple(sorted(rows, key=lambda item: (-item.priority.score, item.finding_id)))

    def proposal(self, finding):
        incomplete_topology = not self.intelligence.graph.relationships.get_relationships(
            finding.subject_canonical_id
        )
        alternatives = (
            {
                "id": "assign",
                "fact": finding.title,
                "assumption": "authorized owner data is available",
                "expected_impact": "governance coverage improves",
                "risk": "incorrect assignment",
                "unknown": "owner remains UNKNOWN until approved",
            },
            {
                "id": "review",
                "fact": finding.title,
                "assumption": "manual review is available",
                "expected_impact": "evidence is completed",
                "risk": "delay",
                "unknown": "mapping outcome",
            },
            {
                "id": "maintain",
                "fact": finding.title,
                "assumption": "status quo accepted temporarily",
                "expected_impact": "no immediate change",
                "risk": "governance gap remains",
                "unknown": "dependency impact",
            },
        )
        limitations = (
            ("Governed topology is incomplete; no destructive action is proposed.",)
            if incomplete_topology
            else ()
        )
        return RecommendationProposal(
            finding,
            "Review and complete governance/classification for the entity",
            "Governance posture is reviewed through existing approval authority",
            alternatives,
            limitations,
            0,
        )

    def create_program_g_recommendation(
        self, proposal, *, evidence_package_id, proposer_id="nexora-ai"
    ):
        if self.recommendations is None:
            raise RuntimeError("Program G recommendation service is required")
        finding = proposal.finding
        alternatives = tuple(
            Alternative(
                item["id"], item["fact"], item["expected_impact"], (item["risk"], item["unknown"])
            )
            for item in proposal.alternatives
        )
        return self.recommendations.create_recommendation(
            self.context,
            recommendation_id=f"rec:{finding.finding_id}",
            finding=finding.finding_id,
            proposed_action=proposal.proposed_action,
            expected_outcome=proposal.expected_outcome,
            alternatives=alternatives,
            evidence_package_id=evidence_package_id,
            proposer=Actor(proposer_id, ActorType.AI),
            confidence=finding.confidence,
            assumptions=proposal.limitations,
            metadata={
                "subject_canonical_id": finding.subject_canonical_id,
                "potential_savings": proposal.potential_savings,
                "verified_realized_savings": proposal.verified_realized_savings,
            },
        )

    def _finding(self, entity, response, amount, code, finding_type, severity):
        seed = (
            f"{self.context.organization_id}:{self.context.tenant_id}:"
            f"{entity.canonical_id}:{code}:{entity.version}"
        )
        finding_id = f"finding:{uuid5(NAMESPACE_URL, seed)}"
        priority = PriorityBreakdown(
            0.8 if str(entity.metadata.get("criticality", "")).lower() == "critical" else 0.3,
            min(amount / 100000, 1),
            0.5 if entity.risk_reference else 0,
            entity.confidence_score,
            entity.quality_score,
            1,
            0.9,
            min(len(response.paths) / 10, 1),
            0.7,
        )
        return IntelligenceFinding(
            finding_id,
            self.context.organization_id,
            self.context.tenant_id,
            entity.canonical_id,
            finding_type,
            code.replace("_", " ").title(),
            f"Governed rules detected {code.lower().replace('_', ' ')}.",
            severity,
            priority,
            tuple(asdict(item) for item in response.facts),
            tuple(asdict(item) for item in response.derived_findings),
            entity.confidence_score,
            amount,
            0,
            {"paths": len(response.paths)},
            tuple(str(item) for item in response.evidence),
            str(response.lineage),
            str(response.provenance),
            response.freshness,
            response.query_id,
            datetime.now(timezone.utc),
        )
