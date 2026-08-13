from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from time import perf_counter
from typing import Any, Callable, Iterable

from data_fabric.foundation import DefaultDeterministicSerializer
from enterprise_scenario.models import (
    ScenarioComparison,
    ScenarioRequest,
    ScenarioResult,
    ScenarioType,
    TopologyState,
)

_SERIALIZER = DefaultDeterministicSerializer()
READ_ROLES = frozenset({"super_admin", "executive", "cio", "finance", "operations", "auditor"})
ROLE_TYPES = {
    "executive": {
        ScenarioType.COST_GROWTH,
        ScenarioType.COST_REDUCTION,
        ScenarioType.BUSINESS_SERVICE_DEGRADATION,
        ScenarioType.RECOMMENDATION_ACCEPTANCE,
    },
    "finance": {
        ScenarioType.COST_GROWTH,
        ScenarioType.COST_REDUCTION,
        ScenarioType.RECOMMENDATION_ACCEPTANCE,
        ScenarioType.POLICY_CHANGE_PREVIEW,
    },
    "operations": {
        ScenarioType.ACCOUNT_SUSPENSION,
        ScenarioType.APPLICATION_RETIREMENT,
        ScenarioType.TECHNOLOGY_RETIREMENT,
        ScenarioType.VENDOR_FAILURE,
        ScenarioType.BUSINESS_SERVICE_DEGRADATION,
    },
    "auditor": set(ScenarioType),
    "cio": set(ScenarioType),
    "super_admin": set(ScenarioType),
}
FINANCIAL_TYPES = {ScenarioType.COST_GROWTH, ScenarioType.COST_REDUCTION}
DISRUPTION_TYPES = {
    ScenarioType.ACCOUNT_SUSPENSION,
    ScenarioType.APPLICATION_RETIREMENT,
    ScenarioType.TECHNOLOGY_RETIREMENT,
    ScenarioType.VENDOR_FAILURE,
    ScenarioType.BUSINESS_SERVICE_DEGRADATION,
}


class ScenarioService:
    """Pure orchestration over governed reads; it owns no persistence or execution port."""

    def __init__(
        self,
        context,
        *,
        role: str,
        registry,
        relationships,
        policy_previewer: Callable | None = None,
    ):
        if role not in READ_ROLES:
            raise PermissionError("scenario intelligence read denied")
        context.assert_matches(registry.context, "registry")
        context.assert_matches(relationships.context, "relationships")
        self.context, self.role = context, role
        self.registry, self.relationships = registry, relationships
        self.policy_previewer = policy_previewer

    def simulate(
        self, request: ScenarioRequest, *, generated_at: datetime | None = None
    ) -> ScenarioResult:
        self.context.assert_matches(request.tenant_context, "scenario request")
        if request.scenario_type not in ROLE_TYPES[self.role]:
            raise PermissionError("scenario type is outside persona scope")
        started = perf_counter()
        detail = self.registry.get_detail(request.subject_canonical_id)
        entity = detail.entity
        self.context.assert_record_matches(entity, "scenario subject")
        baseline = self._baseline(detail)
        paths = (
            self.relationships.traverse(
                entity.canonical_id, max_hops=request.depth, direction="inbound"
            )
            if request.include_dependencies
            else ()
        )
        impacted = tuple(path.entities[-1] for path in paths)
        topology = TopologyState.COMPLETE if paths else TopologyState.INCOMPLETE
        unknowns = (
            [] if paths else ["INCOMPLETE_TOPOLOGY: no governed downstream relationships exist"]
        )
        financial = self._financial(request, baseline)
        simulated, changed = self._simulated(request, baseline, financial)
        evidence = self._evidence(detail, paths)
        policy_preview = (
            self.policy_previewer(request)
            if self.policy_previewer and request.policy_context
            else None
        )
        partial_reasons = tuple(unknowns)
        confidence = round(
            min(float(entity.confidence_score), 1.0) * (0.65 if unknowns else 0.95), 4
        )
        now = generated_at or datetime.now(timezone.utc)
        identity = self._identity(request, baseline, simulated, now)
        disruptive = request.scenario_type in DISRUPTION_TYPES
        result = ScenarioResult(
            scenario_id=f"scenario:{identity[:24]}",
            subject={
                "canonical_id": entity.canonical_id,
                "name": entity.display_name,
                "type": entity.entity_type.value,
            },
            baseline_state=baseline,
            simulated_state=simulated,
            changed_dimensions=tuple(changed),
            impacted_entities=tuple(
                {
                    "canonical_id": x.canonical_id,
                    "name": x.display_name,
                    "type": x.entity_type.value,
                }
                for x in impacted
            ),
            relationship_paths=tuple(self._path(path) for path in paths),
            business_impact={
                "governed_downstream_count": len(impacted),
                "conclusion": "UNKNOWN" if disruptive and not paths else "EVIDENCE_BOUND",
            },
            financial_impact=financial,
            operational_impact={
                "state": "SIMULATED_ONLY",
                "execution_permitted": False,
                "downstream_count": len(impacted),
            },
            risk_impact=self._risk(request, paths),
            governance_impact={
                "topology_state": topology.value,
                "authorization_created": False,
                "decision_created": False,
                "warning": unknowns[0] if unknowns else "",
            },
            assumptions=dict(request.assumptions),
            unknowns=tuple(unknowns),
            confidence=confidence,
            evidence=evidence,
            partial=bool(partial_reasons),
            partial_reasons=partial_reasons,
            topology_state=topology,
            generated_at=now,
            policy_preview=policy_preview,
        )
        if perf_counter() - started > 1.5:
            raise RuntimeError("scenario exceeded bounded 1.5 second work budget")
        return result

    def compare(
        self, requests: Iterable[ScenarioRequest], *, generated_at: datetime | None = None
    ) -> ScenarioComparison:
        items = tuple(requests)
        if not 1 <= len(items) <= 3:
            raise ValueError("comparison requires one to three scenarios")
        now = generated_at or datetime.now(timezone.utc)
        results = tuple(self.simulate(item, generated_at=now) for item in items)
        baseline = dict(results[0].baseline_state)
        if any(dict(item.baseline_state) != baseline for item in results[1:]):
            raise ValueError("scenario comparison requires a common baseline")
        rows = tuple(
            {
                "scenario_id": item.scenario_id,
                "cost": item.financial_impact.get("simulated_spend"),
                "risk": item.risk_impact.get("state"),
                "governance": item.governance_impact.get("topology_state"),
                "impact": len(item.impacted_entities),
                "confidence": item.confidence,
                "unknowns": item.unknowns,
                "policy_preview": item.policy_preview,
            }
            for item in results
        )
        digest = sha256("|".join(x.scenario_id for x in results).encode()).hexdigest()[:24]
        return ScenarioComparison(f"comparison:{digest}", baseline, results, rows, now)

    def compare_recommendation_alternatives(
        self, subject_canonical_id: str, alternatives: Iterable[dict[str, Any]]
    ):
        rows = []
        for alternative in alternatives:
            request = ScenarioRequest(
                self.context,
                alternative["scenario_type"],
                subject_canonical_id,
                proposed_change=alternative.get("proposed_change", {}),
                assumptions=alternative.get("assumptions", {}),
            )
            rows.append(self.simulate(request))
        return (
            self.compare(
                tuple(
                    ScenarioRequest(self.context, row.scenario_type, subject_canonical_id)
                    for row in ()
                )
            )
            if False
            else tuple(rows)
        )

    @staticmethod
    def _baseline(detail) -> dict[str, Any]:
        entity = detail.entity
        financial = dict(detail.financial_context)
        spend = next(
            (
                float(financial[k])
                for k in ("spend", "total_spend", "account_spend", "amount", "monthly_cost")
                if financial.get(k) is not None
            ),
            0.0,
        )
        return {
            "canonical_id": entity.canonical_id,
            "entity_version": entity.version,
            "lifecycle_status": entity.lifecycle_status,
            "classification_status": entity.classification_status,
            "ownership_reference": entity.ownership_reference,
            "relationship_checkpoint": tuple(sorted(x.id for x in detail.relationships)),
            "classification_version": max(
                (int(x.get("version", 0)) for x in detail.classifications), default=0
            ),
            "financial_period": financial.get("period") or financial.get("billing_period"),
            "baseline_spend": spend,
            "enterprise_spend": float(financial.get("enterprise_spend", 0) or 0),
            "risk_reference": entity.risk_reference,
            "health_reference": entity.health_reference,
            "evidence_references": tuple(
                filter(
                    None,
                    (
                        entity.lineage_reference,
                        entity.provenance_reference,
                        entity.financial_context_reference,
                    ),
                )
            ),
        }

    @staticmethod
    def _financial(request, baseline):
        base = float(baseline["baseline_spend"])
        enterprise = float(baseline["enterprise_spend"])
        pct = float(
            request.financial_parameters.get(
                "percentage", request.proposed_change.get("percentage", 0)
            )
            or 0
        )
        if request.scenario_type is ScenarioType.COST_GROWTH:
            factor = 1 + abs(pct) / 100
        elif request.scenario_type is ScenarioType.COST_REDUCTION:
            factor = max(0, 1 - abs(pct) / 100)
        elif request.scenario_type in {
            ScenarioType.ACCOUNT_SUSPENSION,
            ScenarioType.APPLICATION_RETIREMENT,
            ScenarioType.TECHNOLOGY_RETIREMENT,
        }:
            factor = 0
        else:
            factor = 1
        simulated = base * factor
        # Stabilize binary-float subtraction at the Financial Data Fabric precision.
        delta = float(Decimal(str(simulated)) - Decimal(str(base)))
        potential = max(-delta, 0)
        return {
            "baseline_spend": base,
            "simulated_spend": simulated,
            "delta": delta,
            "potential_savings": potential,
            "approved_savings": 0.0,
            "executed_savings": 0.0,
            "verified_realized_savings": 0.0,
            "baseline_enterprise_spend": enterprise,
            "simulated_enterprise_spend": enterprise + delta if enterprise else 0.0,
            "authoritative_source": "Financial Data Fabric",
            "authoritative": False,
        }

    @staticmethod
    def _simulated(request, baseline, financial):
        state, changed = dict(baseline), []
        if request.scenario_type in DISRUPTION_TYPES:
            state["lifecycle_status"] = "simulated_unavailable"
            changed.append("lifecycle_status")
        if request.scenario_type is ScenarioType.OWNERSHIP_CHANGE:
            state["ownership_reference"] = request.proposed_change.get("owner")
            changed.append("ownership")
        if request.scenario_type is ScenarioType.CLASSIFICATION_CHANGE:
            state["classification_status"] = request.proposed_change.get("classification")
            changed.append("classification")
        if request.scenario_type in FINANCIAL_TYPES or financial["delta"]:
            state["spend"] = financial["simulated_spend"]
            changed.append("financial")
        return state, changed

    @staticmethod
    def _risk(request, paths):
        if not paths:
            return {
                "state": "UNKNOWN",
                "reason": "supporting governed topology/risk evidence absent",
            }
        if request.scenario_type in DISRUPTION_TYPES:
            return {"state": "INCREASED", "dependency_risk": "INCREASED"}
        if request.scenario_type is ScenarioType.OWNERSHIP_CHANGE:
            return {"state": "CHANGED", "ownership_risk": "REQUIRES_EVIDENCE"}
        return {"state": "UNCHANGED"}

    @staticmethod
    def _path(path):
        return {
            "entities": tuple(x.canonical_id for x in path.entities),
            "relationships": tuple(x.relationship_type.value for x in path.relationships),
            "evidence": tuple(ref for x in path.relationships for ref in x.evidence),
        }

    @staticmethod
    def _evidence(detail, paths):
        values = list(detail.entity.metadata.get("evidence", ())) + list(detail.entity.tags)
        values += [ref for path in paths for edge in path.relationships for ref in edge.evidence]
        values += list(
            filter(
                None,
                (
                    detail.entity.lineage_reference,
                    detail.entity.provenance_reference,
                    detail.entity.financial_context_reference,
                ),
            )
        )
        return tuple(sorted(set(map(str, values))))

    @staticmethod
    def _identity(request, baseline, simulated, now):
        payload = {
            "tenant": request.tenant_context.to_serializable(),
            "type": request.scenario_type.value,
            "subject": request.subject_canonical_id,
            "change": dict(request.proposed_change),
            "financial": dict(request.financial_parameters),
            "baseline": baseline,
            "simulated": simulated,
            "generated_at": now,
        }
        return _SERIALIZER.content_hash(payload)
