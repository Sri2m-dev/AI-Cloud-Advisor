"""Tenant-bound WP-014 financial reconciliation and savings attribution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, fields, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from business_service_posture import BusinessServicePosture
from data_fabric.foundation import TenantContext
from data_fabric.versioning import InMemoryTemporalHistoryStore, TemporalRecord
from data_fabric.versioning.models import payload_hash, to_canonical_value
from execution_outcome import (
    ExecutionPlan,
    ExecutionRecord,
    OutcomeState,
    OutcomeVerification,
)
from financial_decision_product.models import (
    AllocationResult,
    CostRecord,
    FinancialAlternative,
    ForecastAvailability,
    ForecastRecord,
    RealizedSavings,
    ReconciliationResult,
    ReconciliationState,
    RecordState,
    SavingsState,
)
from recommendation_decision import Decision, DecisionDisposition, Recommendation


class FinancialDecisionError(ValueError):
    """A financial input, tenant, attribution, or history invariant failed."""


class FinancialDecisionProduct:
    """Persistence-neutral product over existing governed financial inputs."""

    def __init__(self, context: TenantContext) -> None:
        self.context = context
        self._alternatives: dict[str, FinancialAlternative] = {}
        self._reconciliations: dict[str, ReconciliationResult] = {}
        self._savings: dict[str, RealizedSavings] = {}
        self._history_store = InMemoryTemporalHistoryStore()
        self._history_roots: dict[str, str] = {}
        self._history_records: dict[str, RealizedSavings] = {}
        self._attributions: dict[tuple[str, str], str] = {}

    def create_alternative(
        self,
        *,
        alternative_id: str,
        recommendation: Recommendation,
        decision: Decision,
        posture: BusinessServicePosture,
        resource_id: str,
        baseline: CostRecord | None,
        allocation: AllocationResult | None,
        forecast: ForecastRecord | None,
        assumptions: tuple[str, ...] = (),
    ) -> FinancialAlternative:
        self._tenant(recommendation, "recommendation")
        self._tenant(decision, "decision")
        self._tenant(posture, "business service posture")
        self._decision_chain(recommendation, decision)
        inputs = (
            (baseline, "baseline cost"),
            (allocation, "allocation"),
            (forecast, "forecast"),
        )
        for record, label in inputs:
            if record is not None:
                self._financial_input(record, label)
                if record.business_service_id != posture.business_service_id:
                    raise FinancialDecisionError(f"{label} crosses business service attribution")
        if allocation is not None and baseline is not None:
            if allocation.cost_id != baseline.cost_id:
                raise FinancialDecisionError("allocation does not reference the baseline cost")
            self._unique_evidence((baseline.evidence.evidence_id, allocation.evidence.evidence_id))
        missing: list[str] = []
        if baseline is None:
            missing.append("baseline")
        if allocation is None:
            missing.append("allocation")
        if forecast is None:
            missing.append("forecast")
        availability = (
            forecast.availability if forecast is not None else ForecastAvailability.MISSING
        )
        compatible = baseline is not None and forecast is not None and self._forecast_compatible(
            baseline, forecast
        )
        if baseline is not None and forecast is not None and not compatible:
            missing.append("compatible_forecast_currency_or_period")
        projected_cost = (
            forecast.projected_cost
            if forecast is not None and availability is not ForecastAvailability.MISSING
            else None
        )
        projected_savings = (
            round(baseline.amount - projected_cost, 2)
            if compatible and projected_cost is not None
            else None
        )
        content = {
            "alternative_id": alternative_id,
            "tenant": self.context.to_serializable(),
            "recommendation": (recommendation.recommendation_id, recommendation.version),
            "decision": (decision.decision_id, decision.recommendation_version),
            "business_service_id": posture.business_service_id,
            "resource_id": resource_id,
            "baseline": baseline,
            "allocation": allocation,
            "forecast": forecast,
            "assumptions": assumptions,
            "missing": missing,
        }
        alternative = FinancialAlternative(
            alternative_id=alternative_id,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
            decision_id=decision.decision_id,
            decision_version=decision.recommendation_version,
            recommendation_id=recommendation.recommendation_id,
            recommendation_version=recommendation.version,
            business_service_id=posture.business_service_id,
            resource_id=resource_id,
            baseline_cost=baseline.amount if baseline else None,
            projected_cost=projected_cost,
            projected_savings=projected_savings,
            forecast_horizon=(
                f"{forecast.forecast_period_start.isoformat()}/{forecast.forecast_period_end.isoformat()}"
                if forecast
                else None
            ),
            assumptions=assumptions,
            cost_evidence_id=baseline.evidence.evidence_id if baseline else None,
            allocation_basis=allocation.basis if allocation else None,
            forecast_id=forecast.forecast_id if forecast else None,
            forecast_version=forecast.version if forecast else None,
            forecast_availability=availability,
            currency=baseline.currency if baseline else (forecast.currency if forecast else None),
            effective_period_start=forecast.forecast_period_start if forecast else None,
            effective_period_end=forecast.forecast_period_end if forecast else None,
            lineage_refs=_refs(baseline, allocation, forecast, name="lineage_ref"),
            provenance_refs=_refs(baseline, allocation, forecast, name="provenance_ref"),
            missing_inputs=tuple(missing),
            alternative_hash=_hash(content),
        )
        existing = self._alternatives.get(alternative_id)
        if existing is not None and existing != alternative:
            raise FinancialDecisionError("financial alternative identity is immutable")
        self._alternatives[alternative_id] = alternative
        return alternative

    def reconcile(
        self,
        *,
        reconciliation_id: str,
        business_service_id: str,
        baseline: CostRecord | None,
        actual: CostRecord | None,
        allocation: AllocationResult | None,
    ) -> ReconciliationResult:
        records = tuple(item for item in (baseline, actual, allocation) if item is not None)
        for item in records:
            self._financial_input(item, "financial reconciliation input")
            if item.business_service_id != business_service_id:
                raise FinancialDecisionError("financial input crosses business service attribution")
        self._unique_evidence(tuple(item.evidence.evidence_id for item in records))
        reasons: list[str] = []
        state = ReconciliationState.MATCHED
        if baseline is None or actual is None:
            state = ReconciliationState.UNRECONCILED
            reasons.append("baseline_or_actual_missing")
        elif baseline.currency != actual.currency:
            state = ReconciliationState.UNRECONCILED
            reasons.append("incompatible_currency")
        elif not _comparable_periods(baseline, actual):
            state = ReconciliationState.UNRECONCILED
            reasons.append("incompatible_period")
        if allocation is None:
            state = ReconciliationState.UNRECONCILED
            reasons.append("allocation_missing")
        elif baseline is not None:
            if allocation.cost_id != baseline.cost_id:
                state = ReconciliationState.UNRECONCILED
                reasons.append("allocation_cost_reference_mismatch")
            elif allocation.currency != baseline.currency or not _same_period(allocation, baseline):
                state = ReconciliationState.UNRECONCILED
                reasons.append("allocation_currency_or_period_mismatch")
            elif allocation.allocated_amount < baseline.amount:
                state = ReconciliationState.PARTIAL
                reasons.append("cost_partially_allocated")
            elif allocation.allocated_amount > baseline.amount:
                state = ReconciliationState.UNRECONCILED
                reasons.append("allocation_exceeds_canonical_cost")
        if not reasons:
            reasons.append("billing_allocation_service_and_actual_matched")
        unmatched = (
            round(baseline.amount - allocation.allocated_amount, 2)
            if baseline is not None and allocation is not None
            else None
        )
        content = {
            "reconciliation_id": reconciliation_id,
            "tenant": self.context.to_serializable(),
            "service": business_service_id,
            "baseline": baseline,
            "actual": actual,
            "allocation": allocation,
            "state": state,
            "reasons": reasons,
        }
        result = ReconciliationResult(
            reconciliation_id=reconciliation_id,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
            business_service_id=business_service_id,
            baseline_cost_id=baseline.cost_id if baseline else None,
            actual_cost_id=actual.cost_id if actual else None,
            allocation_id=allocation.allocation_id if allocation else None,
            state=state,
            baseline_amount=baseline.amount if baseline else None,
            actual_amount=actual.amount if actual else None,
            allocated_amount=allocation.allocated_amount if allocation else None,
            unmatched_amount=unmatched,
            currency=baseline.currency if baseline else (actual.currency if actual else None),
            reasons=tuple(reasons),
            evidence_ids=tuple(item.evidence.evidence_id for item in records),
            reconciliation_hash=_hash(content),
        )
        existing = self._reconciliations.get(reconciliation_id)
        if existing is not None and existing != result:
            raise FinancialDecisionError("reconciliation identity is immutable")
        self._reconciliations[reconciliation_id] = result
        return result

    def attribute_realized_savings(
        self,
        *,
        savings_id: str,
        recommendation: Recommendation,
        decision: Decision,
        alternative: FinancialAlternative,
        reconciliation: ReconciliationResult,
        baseline: CostRecord | None,
        actual: CostRecord | None,
        plan: ExecutionPlan | None,
        execution: ExecutionRecord | None,
        verification: OutcomeVerification | None,
        recorded_at: datetime | None = None,
        supersedes_savings_id: str | None = None,
    ) -> RealizedSavings:
        for item, label in (
            (recommendation, "recommendation"),
            (decision, "decision"),
            (alternative, "financial alternative"),
            (reconciliation, "reconciliation"),
            (baseline, "baseline"),
            (actual, "actual"),
            (plan, "execution plan"),
            (execution, "execution"),
            (verification, "outcome verification"),
        ):
            if item is not None:
                self._tenant(item, label)
        for item, label in ((baseline, "baseline"), (actual, "actual")):
            if item is not None:
                self._financial_input(item, label)
        self._decision_chain(recommendation, decision)
        if alternative.decision_id != decision.decision_id:
            raise FinancialDecisionError("financial alternative references another Decision")
        if reconciliation.business_service_id != alternative.business_service_id:
            raise FinancialDecisionError("reconciliation references another Business Service")
        state = SavingsState.INDETERMINATE
        reasons: list[str] = []
        if plan is None or execution is None or verification is None:
            reasons.append("authorized_execution_or_verification_missing")
        elif (
            plan.decision_id != decision.decision_id
            or execution.plan_id != plan.plan_id
            or verification.execution_id != execution.execution_id
        ):
            raise FinancialDecisionError("execution/outcome chain does not bind the Decision")
        elif verification.state is not OutcomeState.VERIFIED:
            reasons.append("outcome_not_independently_verified")
        if baseline is None or actual is None:
            reasons.append("attributable_baseline_or_actual_missing")
        if reconciliation.state is not ReconciliationState.MATCHED:
            reasons.append("financial_reconciliation_not_matched")
        if baseline is not None and actual is not None:
            if baseline.currency != actual.currency:
                reasons.append("incompatible_currency")
            if not _comparable_periods(baseline, actual):
                reasons.append("incompatible_period")
        amount: float | None = None
        if not reasons and baseline is not None and actual is not None:
            amount = round(baseline.amount - actual.amount, 2)
            state = SavingsState.REALIZED if amount > 0 else SavingsState.NOT_REALIZED
            reasons.append(
                "verified_reconciled_savings_realized"
                if amount > 0
                else "verified_reconciled_cost_did_not_decrease"
            )
        attribution_key = (
            decision.decision_id,
            verification.verification_id if verification is not None else "missing",
        )
        existing_attribution = self._attributions.get(attribution_key)
        if existing_attribution is not None and existing_attribution != supersedes_savings_id:
            raise FinancialDecisionError("Decision/outcome savings attribution already exists")
        if actual is not None:
            self._reject_overlapping_current_window(
                alternative.business_service_id,
                actual,
                supersedes_savings_id,
            )
        now = recorded_at or datetime.now(timezone.utc)
        version = 1
        history_root = savings_id
        if supersedes_savings_id is not None:
            previous = self._savings.get(supersedes_savings_id)
            if previous is None or previous.record_state is not RecordState.CURRENT:
                raise FinancialDecisionError("current savings record to supersede was not found")
            previous = replace(previous, record_state=RecordState.SUPERSEDED)
            self._savings[supersedes_savings_id] = previous
            self._history_records[previous.savings_id] = previous
            history_root = self._history_roots[previous.savings_id]
            current = self._history_store.get_current_record(
                history_root,
                organization_id=self.context.organization_id,
                tenant_id=self.context.tenant_id,
            )
            if current is None:
                raise FinancialDecisionError("current temporal savings history was not found")
            if now <= current.effective_from:
                now = current.effective_from + timedelta(microseconds=1)
            self._history_store.close_current_record(
                history_root,
                organization_id=self.context.organization_id,
                tenant_id=self.context.tenant_id,
                effective_to=now,
            )
            version = previous.version + 1
        evidence_ids = tuple(
            item.evidence.evidence_id for item in (baseline, actual) if item is not None
        ) + tuple(reconciliation.evidence_ids)
        content = {
            "savings_id": savings_id,
            "version": version,
            "state": state,
            "decision": decision,
            "alternative": alternative,
            "reconciliation": reconciliation,
            "plan": plan,
            "execution": execution,
            "verification": verification,
            "baseline": baseline,
            "actual": actual,
            "amount": amount,
            "supersedes": supersedes_savings_id,
        }
        result = RealizedSavings(
            savings_id=savings_id,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
            version=version,
            state=state,
            record_state=RecordState.CURRENT,
            business_service_id=alternative.business_service_id,
            decision_id=decision.decision_id,
            decision_version=decision.recommendation_version,
            recommendation_id=recommendation.recommendation_id,
            recommendation_version=recommendation.version,
            alternative_id=alternative.alternative_id,
            reconciliation_id=reconciliation.reconciliation_id,
            plan_id=plan.plan_id if plan else None,
            plan_hash=plan.plan_hash if plan else None,
            evaluation_id=plan.evaluation_id if plan else None,
            authority_type=plan.authority_type if plan else None,
            authority_id=plan.authority_id if plan else None,
            execution_id=execution.execution_id if execution else None,
            verification_id=verification.verification_id if verification else None,
            verification_hash=verification.verification_hash if verification else None,
            baseline_cost_id=baseline.cost_id if baseline else None,
            actual_cost_id=actual.cost_id if actual else None,
            amount=amount,
            currency=baseline.currency if baseline else None,
            period_start=actual.period_start if actual else None,
            period_end=actual.period_end if actual else None,
            reasons=tuple(reasons),
            evidence_ids=evidence_ids,
            lineage_refs=_refs(baseline, actual, name="lineage_ref"),
            provenance_refs=_refs(baseline, actual, name="provenance_ref"),
            supersedes_savings_id=supersedes_savings_id,
            recorded_at=now,
            savings_hash=_hash(content),
        )
        if savings_id in self._savings:
            raise FinancialDecisionError("savings identity already exists")
        self._savings[savings_id] = result
        self._history_roots[savings_id] = history_root
        self._history_records[savings_id] = result
        self._history_store.append_record(
            TemporalRecord(
                record_id=savings_id,
                subject_id=history_root,
                subject_type="realized_savings",
                organization_id=self.context.organization_id,
                tenant_id=self.context.tenant_id,
                version=version,
                effective_from=now,
                effective_to=None,
                recorded_at=now,
                payload=_plain(result),
                payload_hash=result.savings_hash,
                lineage_ref=result.lineage_refs[0] if result.lineage_refs else None,
                provenance_ref=(
                    result.provenance_refs[0] if result.provenance_refs else None
                ),
            )
        )
        self._attributions[attribution_key] = savings_id
        return result

    def alternatives_for_decision(self, decision_id: str) -> tuple[FinancialAlternative, ...]:
        return tuple(
            sorted(
                (item for item in self._alternatives.values() if item.decision_id == decision_id),
                key=lambda item: item.alternative_id,
            )
        )

    def financial_posture_by_service(self, business_service_id: str) -> dict[str, Any]:
        alternatives = tuple(
            item
            for item in self._alternatives.values()
            if item.business_service_id == business_service_id
        )
        savings = self.realized_savings_by_service(business_service_id)
        return {
            "business_service_id": business_service_id,
            "alternatives": tuple(sorted(alternatives, key=lambda item: item.alternative_id)),
            "realized_savings": savings,
            "confirmed_total": round(
                sum(item.amount or 0 for item in savings if item.state is SavingsState.REALIZED),
                2,
            ),
        }

    def forecast_versus_actual(
        self, alternative_id: str, actual: CostRecord
    ) -> dict[str, Any]:
        self._tenant(actual, "actual cost")
        alternative = self._get_alternative(alternative_id)
        compatible = (
            alternative.currency == actual.currency
            and alternative.effective_period_start == actual.period_start
            and alternative.effective_period_end == actual.period_end
        )
        return {
            "alternative_id": alternative_id,
            "forecast": alternative.projected_cost,
            "actual": actual.amount,
            "currency": actual.currency if compatible else None,
            "variance": (
                round(actual.amount - alternative.projected_cost, 2)
                if compatible and alternative.projected_cost is not None
                else None
            ),
            "compatible": compatible,
        }

    def realized_savings_by_decision(self, decision_id: str) -> tuple[RealizedSavings, ...]:
        return self._current_savings(lambda item: item.decision_id == decision_id)

    def realized_savings_by_service(self, business_service_id: str) -> tuple[RealizedSavings, ...]:
        return self._current_savings(
            lambda item: item.business_service_id == business_service_id
        )

    def reconciliation_result(self, reconciliation_id: str) -> ReconciliationResult:
        try:
            return self._reconciliations[reconciliation_id]
        except KeyError as exc:
            raise FinancialDecisionError("reconciliation not found") from exc

    def savings_history(self, savings_id: str) -> tuple[RealizedSavings, ...]:
        root = self._history_roots.get(savings_id)
        if root is None:
            return ()
        return tuple(
            self._history_records[item.record_id]
            for item in self._history_store.list_history(
                root,
                organization_id=self.context.organization_id,
                tenant_id=self.context.tenant_id,
            )
        )

    def savings_version(self, savings_id: str, version: int) -> RealizedSavings:
        match = next(
            (item for item in self.savings_history(savings_id) if item.version == version),
            None,
        )
        if match is None:
            raise FinancialDecisionError("savings version not found")
        return match

    def reconstruct(self, savings_id: str) -> dict[str, Any]:
        try:
            savings = self._savings[savings_id]
        except KeyError as exc:
            raise FinancialDecisionError("savings record not found") from exc
        alternative = self._get_alternative(savings.alternative_id)
        reconciliation = self.reconciliation_result(savings.reconciliation_id)
        result = {
            "tenant": self.context.to_serializable(),
            "business_service": savings.business_service_id,
            "recommendation": {
                "id": savings.recommendation_id,
                "version": savings.recommendation_version,
            },
            "decision": {"id": savings.decision_id, "version": savings.decision_version},
            "financial_alternative": to_canonical_value(asdict(alternative)),
            "baseline": {
                "cost_id": savings.baseline_cost_id,
                "amount": reconciliation.baseline_amount,
            },
            "forecast": {
                "id": alternative.forecast_id,
                "version": alternative.forecast_version,
                "projected_cost": alternative.projected_cost,
                "availability": alternative.forecast_availability.value,
            },
            "policy_authorization": {
                "evaluation_id": savings.evaluation_id,
                "authority_type": savings.authority_type,
                "authority_id": savings.authority_id,
                "plan_id": savings.plan_id,
                "plan_hash": savings.plan_hash,
                "execution_id": savings.execution_id,
                "verification_id": savings.verification_id,
                "verification_hash": savings.verification_hash,
            },
            "verified_outcome": savings.verification_id,
            "post_action_actual": {
                "cost_id": savings.actual_cost_id,
                "amount": reconciliation.actual_amount,
            },
            "reconciliation": to_canonical_value(asdict(reconciliation)),
            "realized_savings": to_canonical_value(asdict(savings)),
            "history": [
                to_canonical_value(asdict(item))
                for item in self.savings_history(savings_id)
            ],
        }
        result["reconstruction_hash"] = payload_hash(result)
        return result

    def _tenant(self, record: Any, label: str) -> None:
        try:
            self.context.assert_record_matches(record, label)
        except ValueError as exc:
            raise FinancialDecisionError(f"{label} crosses tenant boundary") from exc

    def _financial_input(self, record: Any, label: str) -> None:
        self._tenant(record, label)
        evidence = getattr(record, "evidence", None)
        if evidence is not None:
            self._tenant(evidence, f"{label} evidence")

    @staticmethod
    def _decision_chain(recommendation: Recommendation, decision: Decision) -> None:
        if decision.disposition is not DecisionDisposition.APPROVE:
            raise FinancialDecisionError("financial product requires an approved Decision")
        if (
            decision.recommendation_id != recommendation.recommendation_id
            or decision.recommendation_version != recommendation.version
        ):
            raise FinancialDecisionError("Decision does not bind the exact Recommendation")

    @staticmethod
    def _unique_evidence(evidence_ids: tuple[str, ...]) -> None:
        if len(evidence_ids) != len(set(evidence_ids)):
            raise FinancialDecisionError("duplicate financial evidence rejected")

    @staticmethod
    def _forecast_compatible(baseline: CostRecord, forecast: ForecastRecord) -> bool:
        return (
            baseline.currency == forecast.currency
            and baseline.period_start == forecast.input_period_start
            and baseline.period_end == forecast.input_period_end
        )

    def _reject_overlapping_current_window(
        self,
        business_service_id: str,
        actual: CostRecord,
        supersedes_savings_id: str | None,
    ) -> None:
        for record in self._savings.values():
            if (
                record.record_state is RecordState.CURRENT
                and record.business_service_id == business_service_id
                and record.savings_id != supersedes_savings_id
                and record.period_start is not None
                and record.period_end is not None
                and actual.period_start < record.period_end
                and record.period_start < actual.period_end
            ):
                raise FinancialDecisionError("overlapping realized-savings window rejected")

    def _get_alternative(self, alternative_id: str) -> FinancialAlternative:
        try:
            return self._alternatives[alternative_id]
        except KeyError as exc:
            raise FinancialDecisionError("financial alternative not found") from exc

    def _current_savings(self, predicate) -> tuple[RealizedSavings, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._savings.values()
                    if item.record_state is RecordState.CURRENT and predicate(item)
                ),
                key=lambda item: (
                    item.period_start or datetime.min.replace(tzinfo=timezone.utc),
                    item.savings_id,
                ),
            )
        )


def _refs(*records: Any, name: str) -> tuple[str, ...]:
    return tuple(
        getattr(item.evidence, name)
        for item in records
        if item is not None and getattr(item, "evidence", None) is not None
    )


def _hash(value: Any) -> str:
    return payload_hash(to_canonical_value(_plain(value)))


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set | frozenset):
        return [_plain(item) for item in value]
    return value


def _same_period(first: Any, second: Any) -> bool:
    return (
        first.period_start == second.period_start
        and first.period_end == second.period_end
    )


def _comparable_periods(baseline: CostRecord, actual: CostRecord) -> bool:
    return (
        baseline.period_end <= actual.period_start
        and (baseline.period_end - baseline.period_start)
        == (actual.period_end - actual.period_start)
    )
