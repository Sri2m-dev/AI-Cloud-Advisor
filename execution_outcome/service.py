"""WP-013 orchestration over exact WP-012 authority and existing adapters."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext
from execution.base_adapter import BaseExecutionAdapter
from execution_outcome.models import (
    CompensationPlan,
    ExecutionEvent,
    ExecutionPlan,
    ExecutionRecord,
    ExecutionState,
    OutcomeObservation,
    OutcomePlan,
    OutcomeState,
    OutcomeVerification,
    deep_freeze,
)
from policy_approval import PolicyApprovalError, PolicyApprovalService
from recommendation_decision import Actor, ActorType, Decision, DecisionDisposition

_SERIALIZER = DefaultDeterministicSerializer()
_TARGET_FIELDS = frozenset(
    {
        "resource_id",
        "target_id",
        "application_id",
        "instance_id",
        "subscription_id",
        "service_id",
        "technology_id",
        "entity_id",
    }
)


class ExecutionOutcomeError(ValueError):
    """Exact authority, bounded action, compensation, or outcome failure."""


class ExecutionOutcomeService:
    """Persistence-neutral WP-013 boundary; adapters remain the action mechanism."""

    def __init__(
        self,
        policy_service: PolicyApprovalService,
        adapter: BaseExecutionAdapter,
    ) -> None:
        self._policy = policy_service
        self._adapter = adapter
        self._plans: dict[tuple[str, str, str], ExecutionPlan] = {}
        self._executions: dict[tuple[str, str, str], ExecutionRecord] = {}
        self._plan_execution: dict[tuple[str, str, str], str] = {}
        self._verifications: dict[tuple[str, str, str], OutcomeVerification] = {}
        self._events: list[ExecutionEvent] = []

    def create_plan(
        self,
        context: TenantContext,
        *,
        plan_id: str,
        decision: Decision,
        evaluation_id: str,
        authority_type: str,
        authority_id: str,
        scope,
        connector_id: str,
        connector_action: str,
        target_path: tuple[str, ...],
        requested_by: Actor,
        executor: Actor,
        parameters: dict[str, Any],
        outcome_plan: OutcomePlan,
        compensation_plan: CompensationPlan,
        created_at: datetime | None = None,
    ) -> ExecutionPlan:
        context.assert_record_matches(decision, "decision")
        if decision.disposition is not DecisionDisposition.APPROVE:
            raise ExecutionOutcomeError("execution requires an approved Decision")
        if executor.actor_type is ActorType.AI:
            raise ExecutionOutcomeError("AI execution requires later agent-control authority")
        if requested_by.actor_type is ActorType.AI and requested_by == executor:
            raise ExecutionOutcomeError("AI cannot self-authorize execution")
        if scope.action != connector_action:
            raise ExecutionOutcomeError("connector action must exactly match authority scope")
        self._validate_connector(connector_id)
        try:
            frozen_parameters = deep_freeze(parameters)
        except ValueError as exc:
            raise ExecutionOutcomeError(f"invalid execution parameters: {exc}") from exc
        target = _extract_target(frozen_parameters, target_path)
        if target != scope.resource_id:
            raise ExecutionOutcomeError("execution target must exactly match authority scope")
        _reject_ambiguous_targets(frozen_parameters, target_path, target)
        now = created_at or datetime.now(timezone.utc)
        check = self._check_authority(
            context,
            evaluation_id,
            scope,
            authority_type,
            authority_id,
            now,
        )
        if not check.authorized:
            raise ExecutionOutcomeError(f"exact execution authority denied: {check.reason}")
        evaluation = self._policy.get_evaluation(context, evaluation_id)
        if (
            evaluation.decision_id != decision.decision_id
            or evaluation.decision_version != decision.recommendation_version
        ):
            raise ExecutionOutcomeError("authority does not bind the exact Decision version")
        key = self._plan_key(context, plan_id)
        if key in self._plans:
            raise ExecutionOutcomeError("execution plan id already exists")
        content = {
            "tenant": context.to_serializable(),
            "plan_id": plan_id,
            "decision_id": decision.decision_id,
            "decision_version": decision.recommendation_version,
            "recommendation_id": decision.recommendation_id,
            "recommendation_version": decision.recommendation_version,
            "evidence_package_id": evaluation.evidence_package_id,
            "evidence_package_hash": evaluation.evidence_package_hash,
            "evaluation_id": evaluation_id,
            "authority_type": authority_type,
            "authority_id": authority_id,
            "scope": scope,
            "connector_id": connector_id,
            "connector_action": connector_action,
            "target_path": target_path,
            "requested_by": requested_by,
            "executor": executor,
            "parameters": frozen_parameters,
            "outcome_plan": outcome_plan,
            "compensation_plan": compensation_plan,
        }
        plan = ExecutionPlan(
            plan_id=plan_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            decision_id=decision.decision_id,
            decision_version=decision.recommendation_version,
            recommendation_id=decision.recommendation_id,
            recommendation_version=decision.recommendation_version,
            evidence_package_id=evaluation.evidence_package_id,
            evidence_package_hash=evaluation.evidence_package_hash,
            evaluation_id=evaluation_id,
            authority_type=authority_type,
            authority_id=authority_id,
            scope=scope,
            connector_id=connector_id,
            connector_action=connector_action,
            target_path=target_path,
            requested_by=requested_by,
            executor=executor,
            parameters=frozen_parameters,
            outcome_plan=outcome_plan,
            compensation_plan=compensation_plan,
            created_at=now,
            plan_hash=_SERIALIZER.content_hash(_plain(content)),
        )
        self._plans[key] = plan
        self._event(plan, None, "plan_created", requested_by, now, {"plan_hash": plan.plan_hash})
        return plan

    def execute(
        self,
        context: TenantContext,
        plan_id: str,
        *,
        execution_id: str,
        actor: Actor,
        executed_at: datetime | None = None,
    ) -> ExecutionRecord:
        plan = self.get_plan(context, plan_id)
        if actor != plan.executor:
            raise ExecutionOutcomeError("only the bound executor may execute the plan")
        if self._plan_key(context, plan_id) in self._plan_execution:
            raise ExecutionOutcomeError("execution plan is single-use")
        now = executed_at or datetime.now(timezone.utc)
        check = self._check_authority(
            context,
            plan.evaluation_id,
            plan.scope,
            plan.authority_type,
            plan.authority_id,
            now,
        )
        if not check.authorized:
            raise ExecutionOutcomeError(
                f"authority is not active at execution time: {check.reason}"
            )
        if not self._adapter.enabled:
            raise ExecutionOutcomeError("execution adapter is disabled")
        self._validate_connector(plan.connector_id)
        target = _extract_target(plan.parameters, plan.target_path)
        if target != plan.scope.resource_id:
            raise ExecutionOutcomeError("execution target must exactly match authority scope")
        _reject_ambiguous_targets(plan.parameters, plan.target_path, target)
        self._event(plan, execution_id, "execution_started", actor, now, {})
        result = self._adapter.execute_stage(
            {"Name": plan.connector_action},
            [{"Action": plan.connector_action, "Parameters": dict(plan.parameters)}],
            {
                "organization_id": context.organization_id,
                "tenant_id": context.tenant_id,
                "plan_id": plan.plan_id,
                "plan_hash": plan.plan_hash,
                "scope": _record(plan.scope),
            },
        )
        finished = executed_at or datetime.now(timezone.utc)
        succeeded = result.status.lower() in {"completed", "success", "succeeded"}
        state = ExecutionState.AWAITING_VERIFICATION if succeeded else ExecutionState.COMMAND_FAILED
        record = ExecutionRecord(
            execution_id=execution_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            state=state,
            command_status=result.status,
            adapter=result.adapter,
            executor=actor,
            started_at=now,
            finished_at=finished,
            result_details={
                "message": result.message,
                "details": result.details,
            },
        )
        self._executions[self._execution_key(context, execution_id)] = record
        self._plan_execution[self._plan_key(context, plan_id)] = execution_id
        self._event(
            plan,
            execution_id,
            "command_succeeded" if succeeded else "command_failed",
            actor,
            finished,
            {"adapter_status": result.status},
        )
        if not succeeded and "command_failed" in plan.compensation_plan.reason_triggers:
            return self._compensate(context, plan, record, actor, finished)
        return record

    def verify_outcome(
        self,
        context: TenantContext,
        execution_id: str,
        *,
        verification_id: str,
        verifier: Actor,
        observations: tuple[OutcomeObservation, ...],
        verified_at: datetime | None = None,
    ) -> OutcomeVerification:
        execution = self.get_execution(context, execution_id)
        plan = self.get_plan(context, execution.plan_id)
        if execution.state is not ExecutionState.AWAITING_VERIFICATION:
            raise ExecutionOutcomeError("command is not awaiting outcome verification")
        if verifier.actor_id in {
            execution.executor.actor_id,
            plan.requested_by.actor_id,
        }:
            raise ExecutionOutcomeError(
                "outcome verifier must be independent of requester and executor"
            )
        if verifier.actor_type is ActorType.AI:
            raise ExecutionOutcomeError("AI cannot independently attest execution outcome")
        tenant_scope = (context.organization_id, context.tenant_id)
        if (
            (plan.organization_id, plan.tenant_id) != tenant_scope
            or (execution.organization_id, execution.tenant_id) != tenant_scope
            or any(
                (item.organization_id, item.tenant_id) != tenant_scope
                for item in observations
            )
        ):
            raise ExecutionOutcomeError("outcome observation crosses tenant boundary")
        now = verified_at or datetime.now(timezone.utc)
        reasons: list[str] = []
        state = OutcomeState.VERIFIED
        if now > plan.outcome_plan.verification_window_ends_at:
            state = OutcomeState.INDETERMINATE
            reasons.append("verification window expired")
        by_metric: dict[str, list[OutcomeObservation]] = {}
        for observation in observations:
            by_metric.setdefault(observation.metric, []).append(observation)
        missing_metrics = sorted(
            criterion.metric
            for criterion in plan.outcome_plan.criteria
            if criterion.metric not in by_metric
        )
        evidence_ids = {item.evidence_id for item in observations}
        missing_evidence = sorted(
            required
            for required in plan.outcome_plan.required_evidence
            if required not in evidence_ids
        )
        if missing_metrics or missing_evidence:
            state = OutcomeState.INDETERMINATE
            if missing_metrics:
                reasons.append(f"missing outcome metrics: {', '.join(missing_metrics)}")
            if missing_evidence:
                reasons.append(f"missing governed evidence: {', '.join(missing_evidence)}")
        if any(item.source_connector_id != plan.connector_id for item in observations):
            state = OutcomeState.INDETERMINATE
            reasons.append("outcome evidence is from an unexpected connector")
        if state is OutcomeState.VERIFIED:
            failures = [
                criterion.criterion_id
                for criterion in plan.outcome_plan.criteria
                if not all(
                    _criterion_passes(criterion.operator, observation.value, criterion.target)
                    for observation in by_metric[criterion.metric]
                )
            ]
            if failures:
                state = OutcomeState.NOT_VERIFIED
                reasons.append(f"outcome criteria failed: {', '.join(sorted(failures))}")
            else:
                reasons.append("independent governed outcome criteria passed")
        ordered_observations = tuple(
            sorted(
                observations,
                key=lambda item: (
                    item.metric,
                    item.evidence_id,
                    item.evidence_hash,
                    item.value,
                    item.source_connector_id,
                    item.observed_at.isoformat(),
                    item.lineage_ref or "",
                    item.provenance_ref or "",
                ),
            )
        )
        content = {
            "execution_id": execution_id,
            "plan_hash": plan.plan_hash,
            "verifier": verifier,
            "verified_at": now,
            "state": state,
            "reasons": tuple(reasons),
            "observations": ordered_observations,
        }
        verification = OutcomeVerification(
            verification_id=verification_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            execution_id=execution_id,
            verifier=verifier,
            verified_at=now,
            state=state,
            reasons=tuple(reasons),
            observations=ordered_observations,
            verification_hash=_SERIALIZER.content_hash(content),
        )
        key = self._verification_key(context, verification_id)
        if key in self._verifications:
            raise ExecutionOutcomeError("outcome verification is immutable")
        self._verifications[key] = verification
        target = {
            OutcomeState.VERIFIED: ExecutionState.OUTCOME_VERIFIED,
            OutcomeState.NOT_VERIFIED: ExecutionState.OUTCOME_NOT_ACHIEVED,
            OutcomeState.INDETERMINATE: ExecutionState.AWAITING_VERIFICATION,
        }[state]
        updated = replace(execution, state=target)
        self._executions[self._execution_key(context, execution_id)] = updated
        self._event(
            plan,
            execution_id,
            f"outcome_{state.value}",
            verifier,
            now,
            {"verification_id": verification_id},
        )
        if (
            state is OutcomeState.NOT_VERIFIED
            and "outcome_not_achieved" in plan.compensation_plan.reason_triggers
        ):
            self._compensate(context, plan, updated, verifier, now)
        return verification

    def compensate(
        self,
        context: TenantContext,
        execution_id: str,
        *,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> ExecutionRecord:
        execution = self.get_execution(context, execution_id)
        plan = self.get_plan(context, execution.plan_id)
        if reason not in plan.compensation_plan.reason_triggers:
            raise ExecutionOutcomeError("compensation reason is outside the approved plan")
        return self._compensate(
            context,
            plan,
            execution,
            actor,
            occurred_at or datetime.now(timezone.utc),
        )

    def get_plan(self, context: TenantContext, plan_id: str) -> ExecutionPlan:
        try:
            return self._plans[self._plan_key(context, plan_id)]
        except KeyError as exc:
            raise ExecutionOutcomeError("execution plan not found in tenant scope") from exc

    def get_execution(self, context: TenantContext, execution_id: str) -> ExecutionRecord:
        try:
            return self._executions[self._execution_key(context, execution_id)]
        except KeyError as exc:
            raise ExecutionOutcomeError("execution not found in tenant scope") from exc

    def reconstruct(self, context: TenantContext, execution_id: str) -> dict[str, Any]:
        execution = self.get_execution(context, execution_id)
        plan = self.get_plan(context, execution.plan_id)
        evaluation = self._policy.get_evaluation(context, plan.evaluation_id)
        verification = next(
            (
                item
                for (organization_id, tenant_id, _), item in self._verifications.items()
                if organization_id == context.organization_id
                and tenant_id == context.tenant_id
                and item.execution_id == execution_id
            ),
            None,
        )
        events = [
            _record(event)
            for event in self._events
            if event.plan_id == plan.plan_id
            and (event.execution_id is None or event.execution_id == execution_id)
        ]
        result = {
            "tenant": context.to_serializable(),
            "authority_chain": {
                "decision": {
                    "id": plan.decision_id,
                    "version": plan.decision_version,
                },
                "recommendation": {
                    "id": plan.recommendation_id,
                    "version": plan.recommendation_version,
                },
                "evidence_package": {
                    "id": plan.evidence_package_id,
                    "hash": plan.evidence_package_hash,
                },
                "policy_evaluation": {
                    "id": evaluation.evaluation_id,
                    "result": evaluation.result.value,
                    "policy_id": evaluation.policy_id,
                    "policy_version": evaluation.policy_version,
                },
                "authority": {
                    "type": plan.authority_type,
                    "id": plan.authority_id,
                    "scope": _record(plan.scope),
                },
                "execution_authorization": {
                    "connector_id": plan.connector_id,
                    "connector_action": plan.connector_action,
                    "target_path": _record(plan.target_path),
                    "target": _extract_target(plan.parameters, plan.target_path),
                },
            },
            "plan": _record(plan),
            "execution": _record(execution),
            "outcome_verification": _record(verification) if verification else None,
            "history": events,
            "command_success_is_not_outcome": True,
        }
        result["reconstruction_hash"] = _SERIALIZER.content_hash(result)
        return result

    def _compensate(
        self,
        context: TenantContext,
        plan: ExecutionPlan,
        execution: ExecutionRecord,
        actor: Actor,
        occurred_at: datetime,
    ) -> ExecutionRecord:
        rollback = self._adapter.rollback(
            {
                "organization_id": context.organization_id,
                "tenant_id": context.tenant_id,
                "plan_id": plan.plan_id,
                "rollback": list(plan.compensation_plan.rollback_steps),
            }
        )
        succeeded = rollback.status.lower() in {
            "rollback completed",
            "completed",
            "success",
            "succeeded",
        }
        state = ExecutionState.COMPENSATED if succeeded else ExecutionState.COMPENSATION_FAILED
        updated = replace(
            execution,
            state=state,
            result_details={
                **dict(execution.result_details),
                "compensation": {
                    "status": rollback.status,
                    "message": rollback.message,
                    "details": rollback.details,
                },
            },
        )
        self._executions[self._execution_key(context, execution.execution_id)] = updated
        self._event(
            plan,
            execution.execution_id,
            state.value,
            actor,
            occurred_at,
            {"rollback_status": rollback.status},
        )
        return updated

    def _check_authority(
        self,
        context: TenantContext,
        evaluation_id: str,
        scope,
        authority_type: str,
        authority_id: str,
        checked_at: datetime,
    ):
        try:
            if authority_type == "approval":
                return self._policy.check_authorization(
                    context,
                    evaluation_id=evaluation_id,
                    scope=scope,
                    checked_at=checked_at,
                    approval_id=authority_id,
                )
            if authority_type == "exception":
                return self._policy.check_authorization(
                    context,
                    evaluation_id=evaluation_id,
                    scope=scope,
                    checked_at=checked_at,
                    exception_id=authority_id,
                )
        except PolicyApprovalError as exc:
            raise ExecutionOutcomeError(f"exact execution authority denied: {exc}") from exc
        raise ExecutionOutcomeError("unknown policy authority type")

    def _validate_connector(self, connector_id: str) -> None:
        adapter_name = getattr(self._adapter, "adapter_name", None)
        if (
            not isinstance(adapter_name, str)
            or not adapter_name
            or not connector_id
            or connector_id != adapter_name
        ):
            raise ExecutionOutcomeError(
                "connector identity must exactly match the execution adapter"
            )

    def _event(
        self,
        plan: ExecutionPlan,
        execution_id: str | None,
        event_type: str,
        actor: Actor,
        occurred_at: datetime,
        details: dict[str, Any],
    ) -> None:
        self._events.append(
            ExecutionEvent(
                plan.plan_id,
                execution_id,
                event_type,
                actor,
                occurred_at,
                details,
            )
        )

    @staticmethod
    def _plan_key(context: TenantContext, plan_id: str):
        return context.organization_id, context.tenant_id, plan_id

    @staticmethod
    def _execution_key(context: TenantContext, execution_id: str):
        return context.organization_id, context.tenant_id, execution_id

    @staticmethod
    def _verification_key(context: TenantContext, verification_id: str):
        return context.organization_id, context.tenant_id, verification_id


def _criterion_passes(operator: str, actual: float, target: float) -> bool:
    if operator == ">=":
        return actual >= target
    if operator == "<=":
        return actual <= target
    return actual == target


def _extract_target(parameters: Mapping[str, Any], target_path: tuple[str, ...]) -> str:
    if not target_path or any(not isinstance(part, str) or not part for part in target_path):
        raise ExecutionOutcomeError("execution target path must be explicit")
    value: Any = parameters
    for part in target_path:
        if not isinstance(value, Mapping) or part not in value:
            raise ExecutionOutcomeError("execution target is missing from parameters")
        value = value[part]
    if not isinstance(value, str) or not value:
        raise ExecutionOutcomeError("execution target must be a non-empty string")
    return value


def _reject_ambiguous_targets(
    parameters: Mapping[str, Any],
    target_path: tuple[str, ...],
    target: str,
) -> None:
    discovered: list[tuple[tuple[str, ...], Any]] = []

    def walk(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                child_path = (*path, key)
                if key in _TARGET_FIELDS:
                    discovered.append((child_path, item))
                walk(item, child_path)
        elif isinstance(value, tuple):
            for index, item in enumerate(value):
                walk(item, (*path, str(index)))

    walk(parameters)
    if any(path != target_path for path, _ in discovered):
        raise ExecutionOutcomeError("execution parameters contain ambiguous targets")


def _record(record: Any) -> Any:
    return _SERIALIZER.to_json_compatible(_plain(record))


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    return value
