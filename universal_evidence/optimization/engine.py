from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from .models import (
    EligibilityResult,
    EvidenceLevel,
    OpportunityState,
    OpportunityType,
    OptimizationEvidence,
    OptimizationOpportunity,
    PortfolioSavings,
    RealizationState,
)

MODEL_VERSION = "cmp-p2-calculation-1"


def _fingerprint(*parts: object) -> str:
    return hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()


def _level(score: float) -> EvidenceLevel:
    if score >= 0.85:
        return EvidenceLevel.HIGH
    if score >= 0.65:
        return EvidenceLevel.MEDIUM
    return EvidenceLevel.LOW


def _eligibility(evidence: OptimizationEvidence) -> tuple[EligibilityResult, tuple[str, ...]]:
    signals = evidence.signal_map
    missing = []
    if not evidence.financial_observation_ids or evidence.current_cost is None:
        missing.append("MISSING_GOVERNED_CURRENT_COST")
    if not evidence.currency or not evidence.currency_authority:
        missing.append("MISSING_GOVERNED_CURRENCY")
    if not evidence.cost_period:
        missing.append("MISSING_COST_PERIOD")
    required = {
        OpportunityType.IDLE_COMPUTE: (
            "utilization_window_days",
            "average_utilization",
            "peak_utilization",
            "activity_state",
        ),
        OpportunityType.RIGHTSIZE_COMPUTE: (
            "utilization_window_days",
            "peak_utilization",
            "current_configuration",
            "target_configuration",
            "target_cost",
            "target_cost_period",
            "target_currency",
        ),
        OpportunityType.UNATTACHED_STORAGE: (
            "attachment_state",
            "observation_window_days",
            "retention_state",
        ),
        OpportunityType.UNUSED_LICENSE: (
            "purchased_seats",
            "active_seats",
            "usage_window_days",
            "removable_unit_cost",
            "unit_cost_period",
            "unit_currency",
            "contract_state",
        ),
        OpportunityType.LOW_UTILIZATION_LICENSE: (
            "usage_window_days",
            "usage_count",
            "minimum_useful_usage",
            "removable_unit_cost",
            "contract_state",
        ),
        OpportunityType.DUPLICATE_APPLICATION: (
            "capability_overlap_evidence",
            "migration_feasibility",
        ),
    }[evidence.opportunity_type]
    missing.extend(f"MISSING_{name.upper()}" for name in required if signals.get(name) is None)
    if signals.get("evidence_stale"):
        return EligibilityResult.BLOCKED, ("STALE_EVIDENCE",)
    if missing:
        return EligibilityResult.INSUFFICIENT_EVIDENCE, tuple(missing)
    if evidence.opportunity_type in {
        OpportunityType.IDLE_COMPUTE,
        OpportunityType.RIGHTSIZE_COMPUTE,
    }:
        if int(signals["utilization_window_days"]) < 14:
            return EligibilityResult.INELIGIBLE, ("INSUFFICIENT_OBSERVATION_WINDOW",)
        if signals.get("scheduled_workload") or signals.get("dr_standby"):
            return EligibilityResult.INELIGIBLE, ("PROTECTED_WORKLOAD",)
    if evidence.opportunity_type is OpportunityType.UNATTACHED_STORAGE:
        if signals["attachment_state"] != "UNATTACHED":
            return EligibilityResult.INELIGIBLE, ("STORAGE_ATTACHED",)
        if signals["retention_state"] == "RETAIN":
            return EligibilityResult.INELIGIBLE, ("RETENTION_REQUIRED",)
    if evidence.opportunity_type is OpportunityType.UNUSED_LICENSE:
        if int(signals["usage_window_days"]) < 30:
            return EligibilityResult.INELIGIBLE, ("RECENT_ACTIVITY_WINDOW",)
        if signals["contract_state"] != "REMOVABLE":
            return EligibilityResult.BLOCKED, ("CONTRACT_NOT_REMOVABLE",)
    if evidence.opportunity_type is OpportunityType.RIGHTSIZE_COMPUTE and (
        signals["target_cost_period"] != evidence.cost_period
        or signals["target_currency"] != evidence.currency
    ):
        return EligibilityResult.BLOCKED, ("INCOMPATIBLE_TARGET_ECONOMICS",)
    if evidence.opportunity_type in {
        OpportunityType.UNUSED_LICENSE,
        OpportunityType.LOW_UTILIZATION_LICENSE,
    } and (
        signals["unit_cost_period"] != evidence.cost_period
        or signals["unit_currency"] != evidence.currency
    ):
        return EligibilityResult.BLOCKED, ("INCOMPATIBLE_UNIT_ECONOMICS",)
    return EligibilityResult.ELIGIBLE, ()


def detect_opportunity(
    evidence: OptimizationEvidence, *, now=None
) -> OptimizationOpportunity | None:
    eligibility, reasons = _eligibility(evidence)
    signals = evidence.signal_map
    detected = True
    model = None
    inputs: tuple[tuple[str, object], ...] = ()
    assumptions: tuple[str, ...] = ()
    savings: Decimal | None = None
    recommendation = "Review the evidence before taking action."
    technical = business = effort = EvidenceLevel.UNKNOWN

    if evidence.opportunity_type is OpportunityType.IDLE_COMPUTE:
        detected = Decimal(str(signals.get("average_utilization", 100))) <= Decimal("5")
        detected &= Decimal(str(signals.get("peak_utilization", 100))) <= Decimal("20")
        detected &= signals.get("activity_state") == "IDLE"
        if detected and eligibility is EligibilityResult.ELIGIBLE:
            if signals.get("shutdown_feasible") is True:
                model, savings = "REMOVABLE_GOVERNED_COST", evidence.current_cost
                inputs = (("removable_cost", str(evidence.current_cost)),)
            recommendation = "Review and stop or remove the sustained-idle compute resource."
            technical, business, effort = (
                EvidenceLevel.MEDIUM,
                EvidenceLevel.UNKNOWN,
                EvidenceLevel.LOW,
            )
    elif evidence.opportunity_type is OpportunityType.RIGHTSIZE_COMPUTE:
        detected = Decimal(str(signals.get("peak_utilization", 100))) <= Decimal("70")
        if detected and eligibility is EligibilityResult.ELIGIBLE:
            target = Decimal(str(signals["target_cost"]))
            if target < evidence.current_cost:
                model, savings = (
                    "CURRENT_MINUS_AUTHORITATIVE_TARGET",
                    evidence.current_cost - target,
                )
                inputs = (
                    ("current_cost", str(evidence.current_cost)),
                    ("target_cost", str(target)),
                )
            recommendation = (
                "Review the authoritative target configuration and rightsize with rollback."
            )
            technical, business, effort = (
                EvidenceLevel.MEDIUM,
                EvidenceLevel.UNKNOWN,
                EvidenceLevel.MEDIUM,
            )
    elif evidence.opportunity_type is OpportunityType.UNATTACHED_STORAGE:
        detected = signals.get("attachment_state") == "UNATTACHED"
        if detected and eligibility is EligibilityResult.ELIGIBLE:
            if (
                signals.get("deletion_approved") is True
                and signals.get("retention_state") == "DISPOSABLE"
            ):
                model, savings = "REMOVABLE_GOVERNED_COST", evidence.current_cost
                inputs = (("removable_cost", str(evidence.current_cost)),)
            recommendation = (
                "Review retention evidence, snapshot if required, then remove unattached storage."
            )
            technical, business, effort = (
                EvidenceLevel.HIGH,
                EvidenceLevel.UNKNOWN,
                EvidenceLevel.LOW,
            )
    elif evidence.opportunity_type is OpportunityType.UNUSED_LICENSE:
        unused = int(signals.get("purchased_seats", 0)) - int(signals.get("active_seats", 0))
        detected = unused > 0
        if detected and eligibility is EligibilityResult.ELIGIBLE:
            unit = Decimal(str(signals["removable_unit_cost"]))
            savings = unit * unused
            model = "REMOVABLE_SEATS_X_GOVERNED_UNIT_COST"
            inputs = (("removable_seats", unused), ("unit_cost", str(unit)))
            recommendation = "Review assignments and remove contractually removable unused seats."
            technical, business, effort = EvidenceLevel.LOW, EvidenceLevel.MEDIUM, EvidenceLevel.LOW
    else:
        eligibility, reasons = EligibilityResult.BLOCKED, ("OPPORTUNITY_TYPE_NOT_ACTIVATED",)

    if not detected:
        return None
    if eligibility is not EligibilityResult.ELIGIBLE:
        savings = None
        model = None
    factors = (
        ("evidence_completeness", 1.0 if eligibility is EligibilityResult.ELIGIBLE else 0.35),
        ("source_authority", max(0.0, min(1.0, evidence.source_authority))),
        ("freshness", 0.0 if signals.get("evidence_stale") else 1.0),
        ("identity_strength", 1.0),
        ("temporal_coverage", 1.0 if not any("WINDOW" in reason for reason in reasons) else 0.25),
        ("calculation_reproducibility", 1.0 if model else 0.0),
        ("governance_state", 1.0),
    )
    confidence = round(sum(value for _, value in factors) / len(factors), 4)
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    basis = _fingerprint(
        evidence.organization_id,
        evidence.tenant_id,
        evidence.analysis_id,
        evidence.affected_entity,
        evidence.financial_observation_ids,
    )
    identity = _fingerprint(
        evidence.opportunity_type.value,
        basis,
        evidence.evidence_fingerprints,
        model,
        inputs,
        reasons,
    )
    percentage = None
    if savings is not None and evidence.current_cost and evidence.current_cost > 0:
        percentage = (savings / evidence.current_cost * Decimal("100")).quantize(Decimal("0.01"))
    state = (
        OpportunityState.ELIGIBLE
        if eligibility is EligibilityResult.ELIGIBLE
        else OpportunityState.BLOCKED
    )
    return OptimizationOpportunity(
        "opp-" + identity[:24],
        1,
        evidence.opportunity_type,
        state,
        evidence.tenant_id,
        evidence.organization_id,
        evidence.prospect_id,
        evidence.analysis_id,
        evidence.evidence_fingerprints,
        evidence.affected_entity,
        evidence.affected_entity_type,
        evidence.current_cost,
        evidence.cost_period,
        evidence.currency,
        evidence.currency_authority,
        savings,
        percentage,
        eligibility,
        reasons,
        evidence.signals,
        model,
        MODEL_VERSION if model else None,
        inputs,
        assumptions,
        evidence.evidence_references,
        evidence.lineage,
        evidence.provenance,
        confidence,
        _level(confidence),
        factors,
        technical,
        business,
        effort,
        recommendation,
        ("Take no action and continue monitoring.",),
        evidence.owner,
        evidence.business_context,
        timestamp,
        timestamp,
        state,
        None,
        RealizationState.NOT_STARTED,
        None,
        (),
        identity,
        basis,
    )


def aggregate_portfolio(opportunities: tuple[OptimizationOpportunity, ...]) -> PortfolioSavings:
    eligible = [
        item
        for item in opportunities
        if item.potential_savings is not None
        and item.state
        not in {OpportunityState.REJECTED, OpportunityState.BLOCKED, OpportunityState.SUPERSEDED}
    ]
    selected = []
    excluded = []
    for basis in sorted({item.cost_basis_id for item in eligible}):
        choices = [item for item in eligible if item.cost_basis_id == basis]
        winner = max(choices, key=lambda item: item.potential_savings or Decimal("0"))
        selected.append(winner)
        excluded.extend(item.opportunity_id for item in choices if item is not winner)
    totals: dict[str, Decimal] = {}
    for item in selected:
        totals[item.currency] = totals.get(item.currency, Decimal("0")) + item.potential_savings
    return PortfolioSavings(
        tuple(sorted(totals.items())),
        tuple(item.opportunity_id for item in selected),
        tuple(sorted(excluded)),
    )
