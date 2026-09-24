"""WP-015 tenant-bound portfolio/risk profiles over one Decision contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from business_service_posture import BusinessServicePosture
from data_fabric.foundation import TenantContext
from data_fabric.versioning.models import payload_hash, to_canonical_value
from governed_queries import EvidenceState, GovernedQueryResult
from policy_approval import (
    Approval,
    ApprovalState,
    ExceptionState,
    PolicyEvaluation,
    PolicyEvaluationResult,
    PolicyException,
)
from portfolio_risk_decision_product.models import (
    DomainProfile,
    InputState,
    LifecycleSignal,
    PortfolioRiskCase,
    RationalizationDisposition,
    RiskPriority,
    RiskSignal,
    ScenarioReference,
    query_path_identities,
)
from recommendation_decision import Decision, DecisionDisposition, Recommendation


class PortfolioRiskDecisionError(ValueError):
    """A domain profile, tenant, evidence, or Decision invariant failed."""


class PortfolioRiskDecisionProduct:
    """Persistence-neutral domain profiling without a second Decision model."""

    def __init__(self, context: TenantContext) -> None:
        self.context = context
        self._cases: dict[str, PortfolioRiskCase] = {}
        self._history: dict[str, list[PortfolioRiskCase]] = {}

    def create_portfolio_case(
        self,
        *,
        case_id: str,
        recommendation: Recommendation,
        decision: Decision,
        evaluation: PolicyEvaluation,
        authority: Approval | PolicyException,
        posture: BusinessServicePosture,
        lifecycle: LifecycleSignal | None,
        risk: RiskSignal | None,
        graph: GovernedQueryResult,
        scenario: ScenarioReference | None = None,
        duplicate_candidate_ids: tuple[str, ...] = (),
        created_at: datetime | None = None,
    ) -> PortfolioRiskCase:
        missing = self._validate_common(
            recommendation,
            decision,
            evaluation,
            authority,
            posture,
            lifecycle,
            risk,
            graph,
            scenario,
        )
        disposition = self._rationalization(
            lifecycle,
            risk,
            graph,
            duplicate_candidate_ids,
            missing,
        )
        return self._store_case(
            case_id=case_id,
            profile=DomainProfile.PORTFOLIO_RATIONALIZATION,
            recommendation=recommendation,
            decision=decision,
            evaluation=evaluation,
            authority=authority,
            posture=posture,
            lifecycle=lifecycle,
            risk=risk,
            graph=graph,
            scenario=scenario,
            rationalization=disposition,
            risk_priority=None,
            missing=missing,
            assumptions=tuple(
                sorted(
                    set(recommendation.assumptions)
                    | set(scenario.assumptions if scenario else ())
                )
            ),
            created_at=created_at,
        )

    def create_risk_case(
        self,
        *,
        case_id: str,
        recommendation: Recommendation,
        decision: Decision,
        evaluation: PolicyEvaluation,
        authority: Approval | PolicyException,
        posture: BusinessServicePosture,
        lifecycle: LifecycleSignal | None,
        risk: RiskSignal | None,
        graph: GovernedQueryResult,
        scenario: ScenarioReference | None = None,
        created_at: datetime | None = None,
    ) -> PortfolioRiskCase:
        missing = self._validate_common(
            recommendation,
            decision,
            evaluation,
            authority,
            posture,
            lifecycle,
            risk,
            graph,
            scenario,
        )
        priority = self._risk_priority(risk, graph, missing)
        return self._store_case(
            case_id=case_id,
            profile=DomainProfile.RISK_PRIORITY,
            recommendation=recommendation,
            decision=decision,
            evaluation=evaluation,
            authority=authority,
            posture=posture,
            lifecycle=lifecycle,
            risk=risk,
            graph=graph,
            scenario=scenario,
            rationalization=None,
            risk_priority=priority,
            missing=missing,
            assumptions=tuple(
                sorted(
                    set(recommendation.assumptions)
                    | set(scenario.assumptions if scenario else ())
                )
            ),
            created_at=created_at,
        )

    def revise_case(
        self,
        case_id: str,
        *,
        recommendation: Recommendation,
        decision: Decision,
        reason: str,
        created_at: datetime | None = None,
    ) -> PortfolioRiskCase:
        current = self.get_case(case_id)
        self._tenant(recommendation, "recommendation")
        self._tenant(decision, "decision")
        self._decision_chain(recommendation, decision)
        if (
            recommendation.recommendation_id != current.recommendation_id
            or recommendation.version != current.recommendation_version
            or decision.decision_id != current.decision_id
            or decision.recommendation_version != current.decision_version
        ):
            raise PortfolioRiskDecisionError(
                "case revision cannot replace its governed Decision chain"
            )
        if not reason.strip():
            raise PortfolioRiskDecisionError("case revision reason is required")
        revised = replace(
            current,
            version=current.version + 1,
            recommendation_id=recommendation.recommendation_id,
            recommendation_version=recommendation.version,
            decision_id=decision.decision_id,
            decision_version=decision.recommendation_version,
            created_at=created_at or datetime.now(timezone.utc),
            case_hash=_hash(
                {
                    "previous": current.case_hash,
                    "recommendation": recommendation,
                    "decision": decision,
                    "reason": reason,
                }
            ),
        )
        self._cases[case_id] = revised
        self._history[case_id].append(revised)
        return revised

    def get_case(self, case_id: str, version: int | None = None) -> PortfolioRiskCase:
        if version is None:
            try:
                return self._cases[case_id]
            except KeyError as exc:
                raise PortfolioRiskDecisionError("portfolio/risk case not found") from exc
        match = next(
            (item for item in self._history.get(case_id, ()) if item.version == version),
            None,
        )
        if match is None:
            raise PortfolioRiskDecisionError("portfolio/risk case version not found")
        return match

    def cases_for_decision(self, decision_id: str) -> tuple[PortfolioRiskCase, ...]:
        return tuple(
            sorted(
                (item for item in self._cases.values() if item.decision_id == decision_id),
                key=lambda item: (item.profile.value, item.case_id),
            )
        )

    def cases_for_service(self, service_id: str) -> tuple[PortfolioRiskCase, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._cases.values()
                    if item.business_service_id == service_id
                ),
                key=lambda item: (item.profile.value, item.case_id),
            )
        )

    def prioritized_risks(self) -> tuple[PortfolioRiskCase, ...]:
        order = {
            RiskPriority.CRITICAL: 0,
            RiskPriority.HIGH: 1,
            RiskPriority.MEDIUM: 2,
            RiskPriority.LOW: 3,
            RiskPriority.INDETERMINATE: 4,
        }
        return tuple(
            sorted(
                (
                    item
                    for item in self._cases.values()
                    if item.profile is DomainProfile.RISK_PRIORITY
                ),
                key=lambda item: (
                    order[item.risk_priority or RiskPriority.INDETERMINATE],
                    -(item.risk_score or 0),
                    item.case_id,
                ),
            )
        )

    def history(self, case_id: str) -> tuple[PortfolioRiskCase, ...]:
        return tuple(self._history.get(case_id, ()))

    def reconstruct(self, case_id: str, version: int | None = None) -> dict[str, Any]:
        item = self.get_case(case_id, version)
        result = {
            "tenant": self.context.to_serializable(),
            "case": to_canonical_value(_plain(item)),
            "single_decision_contract": {
                "recommendation_id": item.recommendation_id,
                "recommendation_version": item.recommendation_version,
                "decision_id": item.decision_id,
                "decision_version": item.decision_version,
            },
            "policy_authorization": {
                "evaluation_id": item.policy_evaluation_id,
                "policy_id": item.policy_id,
                "policy_version": item.policy_version,
                "authority_type": item.authority_type,
                "authority_id": item.authority_id,
            },
            "business_service_posture": {
                "business_service_id": item.business_service_id,
                "posture_version": item.posture_version,
            },
            "graph": {
                "checkpoint": item.projection_checkpoint,
                "state_hash": item.projection_hash,
                "query_name": item.query_name,
                "paths": item.query_paths,
                "partial": item.query_partial,
            },
            "evidence": {
                "ids": item.evidence_ids,
                "lineage": item.lineage_refs,
                "provenance": item.provenance_refs,
                "missing_inputs": item.missing_inputs,
            },
            "scenario": {
                "id": item.scenario_id,
                "hash": item.scenario_hash,
                "assumptions": item.assumptions,
            },
            "history": [
                to_canonical_value(_plain(row))
                for row in self._history.get(case_id, ())
            ],
        }
        result["reconstruction_hash"] = payload_hash(result)
        return result

    def _validate_common(
        self,
        recommendation: Recommendation,
        decision: Decision,
        evaluation: PolicyEvaluation,
        authority: Approval | PolicyException,
        posture: BusinessServicePosture,
        lifecycle: LifecycleSignal | None,
        risk: RiskSignal | None,
        graph: GovernedQueryResult,
        scenario: ScenarioReference | None,
    ) -> tuple[str, ...]:
        for item, label in (
            (recommendation, "recommendation"),
            (decision, "decision"),
            (evaluation, "policy evaluation"),
            (authority, "authority"),
            (posture, "business service posture"),
        ):
            self._tenant(item, label)
        self._decision_chain(recommendation, decision)
        if (
            evaluation.decision_id != decision.decision_id
            or evaluation.decision_version != decision.recommendation_version
            or evaluation.result is not PolicyEvaluationResult.ALLOW
        ):
            raise PortfolioRiskDecisionError("case requires exact ALLOW policy evaluation")
        if (
            authority.decision_id != decision.decision_id
            or authority.decision_version != decision.recommendation_version
            or authority.evaluation_id != evaluation.evaluation_id
        ):
            raise PortfolioRiskDecisionError("authority does not bind the exact Decision")
        if isinstance(authority, Approval) and authority.state is not ApprovalState.ACTIVE:
            raise PortfolioRiskDecisionError("portfolio/risk authority is not active")
        if (
            isinstance(authority, PolicyException)
            and authority.state is not ExceptionState.ACTIVE
        ):
            raise PortfolioRiskDecisionError("portfolio/risk authority is not active")
        if authority.scope != evaluation.scope:
            raise PortfolioRiskDecisionError("authority scope differs from evaluation scope")
        if lifecycle is not None:
            self._domain_input(lifecycle, "lifecycle")
        if risk is not None:
            self._domain_input(risk, "risk")
        if scenario is not None:
            self._tenant(scenario, "scenario")
        self._query_tenant(graph)
        entity_id = lifecycle.entity_id if lifecycle else (risk.entity_id if risk else None)
        if entity_id is None:
            raise PortfolioRiskDecisionError(
                "case requires a lifecycle or risk entity identity"
            )
        if lifecycle is not None and risk is not None and lifecycle.entity_id != risk.entity_id:
            raise PortfolioRiskDecisionError("lifecycle and risk identify different entities")
        if authority.scope.resource_id != entity_id:
            raise PortfolioRiskDecisionError("authority scope does not bind the case entity")
        if entity_id not in graph.entity_ids:
            raise PortfolioRiskDecisionError("governed graph does not contain the case entity")
        if posture.business_service_id not in graph.entity_ids:
            raise PortfolioRiskDecisionError(
                "governed graph does not attribute the business service"
            )
        missing: set[str] = set()
        if lifecycle is None or lifecycle.state is InputState.MISSING:
            missing.add("lifecycle")
        if risk is None or risk.state is InputState.MISSING:
            missing.add("risk")
        if lifecycle is not None and lifecycle.state is InputState.STALE:
            missing.add("fresh_lifecycle")
        if risk is not None and risk.state is InputState.STALE:
            missing.add("fresh_risk")
        if graph.metadata.partial:
            missing.add("complete_graph")
        if not graph.paths:
            missing.add("dependency_or_impact_paths")
        if any(item.state is EvidenceState.MISSING for item in graph.evidence):
            missing.add("graph_evidence")
        return tuple(sorted(missing))

    def _store_case(
        self,
        *,
        case_id: str,
        profile: DomainProfile,
        recommendation: Recommendation,
        decision: Decision,
        evaluation: PolicyEvaluation,
        authority: Approval | PolicyException,
        posture: BusinessServicePosture,
        lifecycle: LifecycleSignal | None,
        risk: RiskSignal | None,
        graph: GovernedQueryResult,
        scenario: ScenarioReference | None,
        rationalization: RationalizationDisposition | None,
        risk_priority: RiskPriority | None,
        missing: tuple[str, ...],
        assumptions: tuple[str, ...],
        created_at: datetime | None,
    ) -> PortfolioRiskCase:
        if case_id in self._cases:
            raise PortfolioRiskDecisionError("portfolio/risk case id already exists")
        evidence = tuple(
            item
            for item in (
                lifecycle.evidence if lifecycle else None,
                risk.evidence if risk else None,
            )
            if item is not None
        )
        graph_evidence = tuple(
            item for item in graph.evidence if item.evidence_id is not None
        )
        now = created_at or datetime.now(timezone.utc)
        content = {
            "case_id": case_id,
            "profile": profile,
            "recommendation": recommendation,
            "decision": decision,
            "evaluation": evaluation,
            "authority": authority,
            "posture": posture,
            "lifecycle": lifecycle,
            "risk": risk,
            "graph": graph,
            "scenario": scenario,
            "rationalization": rationalization,
            "risk_priority": risk_priority,
            "missing": missing,
            "created_at": now,
        }
        item = PortfolioRiskCase(
            case_id=case_id,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
            version=1,
            profile=profile,
            recommendation_id=recommendation.recommendation_id,
            recommendation_version=recommendation.version,
            decision_id=decision.decision_id,
            decision_version=decision.recommendation_version,
            policy_evaluation_id=evaluation.evaluation_id,
            policy_id=evaluation.policy_id,
            policy_version=evaluation.policy_version,
            authority_type=(
                "approval" if isinstance(authority, Approval) else "exception"
            ),
            authority_id=(
                authority.approval_id
                if isinstance(authority, Approval)
                else authority.exception_id
            ),
            entity_id=(lifecycle.entity_id if lifecycle else risk.entity_id if risk else ""),
            entity_type=lifecycle.entity_type if lifecycle else "unknown",
            business_service_id=posture.business_service_id,
            posture_version=posture.posture_version,
            lifecycle_state=lifecycle.lifecycle_state if lifecycle else None,
            lifecycle_version=lifecycle.version if lifecycle else None,
            rationalization=rationalization,
            risk_priority=risk_priority,
            risk_score=risk.score if risk else None,
            projection_checkpoint=graph.metadata.checkpoint_sequence,
            projection_hash=graph.metadata.projection_state_hash,
            query_name=graph.metadata.query_name,
            query_paths=query_path_identities(graph),
            query_partial=graph.metadata.partial,
            scenario_id=scenario.scenario_id if scenario else None,
            scenario_hash=scenario.output_hash if scenario else None,
            evidence_ids=tuple(
                sorted(
                    {item.evidence_id for item in evidence}
                    | {
                        item.evidence_id
                        for item in graph_evidence
                        if item.evidence_id is not None
                    }
                )
            ),
            lineage_refs=tuple(
                item.lineage_ref
                for item in (*evidence, *graph_evidence)
                if item.lineage_ref
            ),
            provenance_refs=tuple(
                item.provenance_ref
                for item in (*evidence, *graph_evidence)
                if item.provenance_ref
            ),
            missing_inputs=missing,
            assumptions=assumptions,
            created_at=now,
            case_hash=_hash(content),
        )
        self._cases[case_id] = item
        self._history[case_id] = [item]
        return item

    @staticmethod
    def _rationalization(
        lifecycle: LifecycleSignal | None,
        risk: RiskSignal | None,
        graph: GovernedQueryResult,
        duplicate_candidate_ids: tuple[str, ...],
        missing: tuple[str, ...],
    ) -> RationalizationDisposition:
        if missing:
            return RationalizationDisposition.INDETERMINATE
        if lifecycle and lifecycle.lifecycle_state.lower() in {"retired", "end_of_life"}:
            return RationalizationDisposition.RETIRE
        if duplicate_candidate_ids:
            return RationalizationDisposition.CONSOLIDATE
        if risk and risk.score >= 60:
            return RationalizationDisposition.MODERNIZE
        if graph.paths:
            return RationalizationDisposition.RETAIN
        return RationalizationDisposition.INDETERMINATE

    @staticmethod
    def _risk_priority(
        risk: RiskSignal | None,
        graph: GovernedQueryResult,
        missing: tuple[str, ...],
    ) -> RiskPriority:
        if risk is None or missing:
            return RiskPriority.INDETERMINATE
        blast_radius = len(set(graph.entity_ids))
        score = min(100.0, risk.score + min(20.0, max(0, blast_radius - 1) * 5.0))
        if score >= 80:
            return RiskPriority.CRITICAL
        if score >= 60:
            return RiskPriority.HIGH
        if score >= 30:
            return RiskPriority.MEDIUM
        return RiskPriority.LOW

    def _domain_input(self, item: LifecycleSignal | RiskSignal, label: str) -> None:
        self._tenant(item, label)
        self._tenant(item.evidence, f"{label} evidence")

    def _query_tenant(self, graph: GovernedQueryResult) -> None:
        metadata = graph.metadata
        if (
            metadata.organization_id != self.context.organization_id
            or metadata.tenant_id != self.context.tenant_id
        ):
            raise PortfolioRiskDecisionError("governed graph crosses tenant boundary")
        for evidence in graph.evidence:
            self._tenant(evidence, "graph evidence")

    def _tenant(self, item: Any, label: str) -> None:
        try:
            self.context.assert_record_matches(item, label)
        except ValueError as exc:
            raise PortfolioRiskDecisionError(f"{label} crosses tenant boundary") from exc

    @staticmethod
    def _decision_chain(recommendation: Recommendation, decision: Decision) -> None:
        if decision.disposition is not DecisionDisposition.APPROVE:
            raise PortfolioRiskDecisionError("domain profile requires an approved Decision")
        if (
            decision.recommendation_id != recommendation.recommendation_id
            or decision.recommendation_version != recommendation.version
        ):
            raise PortfolioRiskDecisionError("Decision does not bind the exact Recommendation")


def _hash(value: Any) -> str:
    return payload_hash(to_canonical_value(_plain(value)))


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set | frozenset):
        return [_plain(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value
