"""ACT-009B durable adapters and reconstruction composition root."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from data_fabric.contracts import EntityType
from universal_evidence.governance import (
    ConfirmationRequest,
    DecisionScope,
    MappingDecision,
    MappingDecisionState,
)
from universal_evidence.governance.models import (
    ActorType,
    ConfirmationActor,
    ConfirmationState,
    GovernanceDecisionProvenance,
    MappingDecisionHistory,
)
from universal_evidence.persistence import (
    LifecyclePersistenceError,
    LifecycleScope,
    SQLiteLifecycleRepository,
)


def _capability_scope(payload):
    from universal_evidence.capability import CapabilityScope

    return CapabilityScope(**payload)


def _json(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if is_dataclass(value):
        return {key: _json(item) for key, item in asdict(value).items()}
    if isinstance(value, MappingProxyType):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


def _decode(value):
    if isinstance(value, dict) and set(value) == {"__datetime__"}:
        return datetime.fromisoformat(value["__datetime__"])
    if isinstance(value, dict) and set(value) == {"__decimal__"}:
        return Decimal(value["__decimal__"])
    if isinstance(value, dict):
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def _datetime(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def _scope(scope):
    return LifecycleScope(
        scope.organization_id or "UNKNOWN",
        scope.tenant_id or "UNKNOWN",
        scope.prospect_id,
        scope.analysis_id,
    )


class DurableMappingDecisionRepository:
    """Confirmation repository compatible with the existing PUE-003 service."""

    def __init__(self, lifecycle: SQLiteLifecycleRepository):
        self.lifecycle = lifecycle

    def save_request(self, request):
        existing = self.find_request(request.request_fingerprint)
        if existing is not None:
            return existing
        self.lifecycle.put(
            "confirmation_request",
            request.request_id,
            _scope(request.scope),
            payload=_json(request),
            fingerprint_value=request.request_fingerprint,
            reason="PUE-003 request persisted",
        )
        return request

    def find_request(self, fingerprint_value):
        for record in self.lifecycle.list_type("confirmation_request", include_purged=False):
            if (
                record.object_type == "confirmation_request"
                and record.fingerprint == fingerprint_value
            ):
                return _request(_decode(record.payload))
        return None

    def append(self, decision):
        existing = self._find_decision(decision.decision_id, decision.scope)
        if existing is not None:
            return existing
        self.lifecycle.put(
            "mapping_decision",
            decision.decision_id,
            _scope(decision.scope),
            payload=_json(decision),
            fingerprint_value=decision.decision_fingerprint,
            reason="PUE-003 decision persisted",
        )
        return decision

    def history(self, scope):
        lifecycle_scope = _scope(scope)
        rows = self.lifecycle.list_scope(lifecycle_scope, include_purged=False)
        decisions = tuple(
            decision
            for row in rows
            if row.object_type == "mapping_decision"
            for decision in (_decision(_decode(row.payload)),)
            if decision.scope == scope
        )
        return MappingDecisionHistory(
            scope, tuple(sorted(decisions, key=lambda item: item.decision_timestamp))
        )

    def effective(self, scope):
        decisions = self.history(scope).decisions
        for decision in reversed(decisions):
            if decision.decision_state in {
                MappingDecisionState.AUTO_ACCEPTED,
                MappingDecisionState.CONFIRMED,
                MappingDecisionState.OVERRIDDEN,
            }:
                return decision
            if decision.decision_state in {
                MappingDecisionState.REJECTED,
                MappingDecisionState.EXPIRED,
            }:
                return None
        return None

    def _find_decision(self, decision_id, scope):
        try:
            record = self.lifecycle.get("mapping_decision", decision_id, _scope(scope))
        except LifecyclePersistenceError:
            return None
        return _decision(_decode(record.payload))

    def _any_scope(self):
        return LifecycleScope("__all__", "__all__")


class DurableAnswerReferenceRepository:
    def __init__(self, lifecycle: SQLiteLifecycleRepository):
        self.lifecycle = lifecycle

    def save(self, answer_fingerprint, scope, *, references, state="ACTIVE"):
        return self.lifecycle.put(
            "answer_reference",
            answer_fingerprint,
            scope,
            state=state,
            payload={"references": list(references)},
            fingerprint_value=answer_fingerprint,
            reason="ACT-008 answer reference persisted",
        )

    def load(self, answer_fingerprint, scope):
        return self.lifecycle.get("answer_reference", answer_fingerprint, scope)


class DurableNormalizationAdapter:
    """Recomputes normalized rows while persisting run identity metadata."""

    def __init__(self, delegate, lifecycle: SQLiteLifecycleRepository):
        self.delegate = delegate
        self.lifecycle = lifecycle

    def normalize(self, mapping, values):
        run = self.delegate.normalize(mapping, values)
        self.lifecycle.put(
            "normalization_run",
            run.normalization_run_id,
            _scope(mapping.scope),
            payload={
                "analysis_id": run.analysis_id,
                "mapping_set_fingerprint": run.mapping_set_fingerprint,
                "mapping_decision_id": run.mapping_decision_id,
                "normalization_policy_version": run.normalization_policy_version,
                "status": run.status.value,
                "processed_count": run.processed_count,
                "normalized_count": run.normalized_count,
                "fingerprint": run.fingerprint,
            },
            fingerprint_value=run.fingerprint,
            reason="PUE-004 normalization run metadata persisted",
        )
        return run


class DurableActivationRepository:
    """Append-only ACT-C1 repository reconstructed from scoped lifecycle envelopes."""

    def __init__(self, lifecycle):
        self.lifecycle = lifecycle

    @staticmethod
    def _lifecycle_scope(scope):
        return LifecycleScope(
            scope.organization_id or "__global__",
            scope.tenant_id or "__global__",
            scope.prospect_id,
            scope.analysis_id,
        )

    def store(self, config):
        from dataclasses import replace

        from universal_evidence.activation import ConfigState

        history = self.history(config.scope)
        if history and history[-1].state is ConfigState.ACTIVE:
            previous = replace(history[-1], state=ConfigState.SUPERSEDED)
            self._put_config(previous)
        self._put_config(config)
        return config

    def _put_config(self, config):
        self.lifecycle.put(
            "activation_config",
            config.activation_id,
            self._lifecycle_scope(config.scope),
            state="EXPIRED" if config.state.value == "EXPIRED" else "ACTIVE",
            payload=_json(config),
            fingerprint_value=config.fingerprint,
            reason="ACT-C1 activation persisted",
        )

    def history(self, scope):
        return tuple(
            _activation_config(_decode(item.payload))
            for item in self.lifecycle.list_scope(
                self._lifecycle_scope(scope), include_purged=False
            )
            if item.object_type == "activation_config"
        )

    def active_configs(self):
        configs = tuple(
            _activation_config(_decode(item.payload))
            for item in self.lifecycle.list_type("activation_config")
        )
        return tuple(item for item in configs if item.state.value == "ACTIVE")

    def expire(self, activation_id):
        from dataclasses import replace

        from universal_evidence.activation import ConfigState

        config = self.by_id(activation_id)
        if config is None:
            raise KeyError("activation config not found")
        expired = replace(config, state=ConfigState.EXPIRED)
        self._put_config(expired)
        return expired

    def by_id(self, activation_id):
        return next(
            (
                _activation_config(_decode(item.payload))
                for item in self.lifecycle.list_type("activation_config", include_purged=False)
                if item.object_key == activation_id
            ),
            None,
        )

    def store_kill_switch(self, config):
        self.lifecycle.put(
            "kill_switch",
            config.kill_switch_id,
            LifecycleScope("__global__", "__global__"),
            payload=_json(config),
            fingerprint_value=config.fingerprint,
            reason="ACT-C1 kill switch persisted",
        )
        return config

    def current_kill_switch(self):
        history = self.kill_switch_history
        return history[-1] if history else None

    @property
    def kill_switch_history(self):
        history = tuple(
            _kill_switch(_decode(item.payload))
            for item in self.lifecycle.list_scope(
                LifecycleScope("__global__", "__global__"), include_purged=False
            )
            if item.object_type == "kill_switch"
        )
        return tuple(sorted(history, key=lambda item: item.configured_at))


class DurableAnalyticalPlanRepository:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle

    def store(self, plan):
        self.lifecycle.put(
            "analytical_plan",
            plan.plan_id,
            _scope(plan.scope),
            payload=_json(plan),
            fingerprint_value=plan.plan_fingerprint,
            reason="ACT-005 analytical plan persisted",
        )
        return plan

    def get_versions(self, scope_key):
        scope = LifecycleScope(
            scope_key[2] or "UNKNOWN", scope_key[3] or "UNKNOWN", scope_key[1], scope_key[0]
        )
        return tuple(
            _analytical_plan(_decode(item.payload))
            for item in self.lifecycle.list_scope(scope)
            if item.object_type == "analytical_plan"
        )


class DurableAggregationRepository:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle

    def store(self, result):
        self.lifecycle.put(
            "aggregation_result",
            result.result_id,
            _scope(result.scope),
            payload=_json(result),
            fingerprint_value=result.result_fingerprint,
            reason="ACT-005 governed result persisted",
        )
        return result

    def get_versions(self, scope_key):
        scope = LifecycleScope(
            scope_key[2] or "UNKNOWN", scope_key[3] or "UNKNOWN", scope_key[1], scope_key[0]
        )
        return tuple(
            _aggregation_result(_decode(item.payload))
            for item in self.lifecycle.list_scope(scope)
            if item.object_type == "aggregation_result"
        )


class DurableLineageRepository:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle

    def save(self, object_key, scope, *, references, fingerprint_value):
        return self.lifecycle.put(
            "materialization_lineage",
            object_key,
            scope,
            payload={"references": _json(references)},
            fingerprint_value=fingerprint_value,
            reason="ACT-006 materialization lineage persisted",
        )

    def load(self, object_key, scope):
        return self.lifecycle.get("materialization_lineage", object_key, scope)


class DurableReconciliationRepository:
    """Restart adapter for ACT-007 bindings and decisions."""

    def __init__(self, lifecycle: SQLiteLifecycleRepository):
        self.lifecycle = lifecycle

    def save_binding(self, binding):
        scope = LifecycleScope(*binding.scope)
        # A source identity has one durable slot independent of its proposed
        # canonical target. Concurrent competing targets therefore converge to
        # one effective record instead of creating two current bindings.
        identity_key = ":".join(
            (
                binding.source_system,
                binding.source_identifier,
                binding.entity_type.value,
            )
        )
        return self.lifecycle.put(
            "source_binding",
            identity_key,
            scope,
            payload=_json(binding),
            fingerprint_value=binding.binding_fingerprint,
            reason="ACT-007 source binding persisted",
        )

    def save_decision(self, decision):
        scope = LifecycleScope(*decision.scope)
        return self.lifecycle.put(
            "reconciliation_decision",
            decision.decision_id,
            scope,
            payload=_json(decision),
            fingerprint_value=decision.decision_fingerprint,
            reason="ACT-007 reconciliation decision persisted",
        )

    def bindings(self, scope):
        from universal_evidence.pilot.reconciliation import SourceIdentityBinding

        return tuple(
            SourceIdentityBinding(
                **{
                    **_decode(item.payload),
                    "entity_type": EntityType(_decode(item.payload)["entity_type"]),
                    "created_at": _datetime(_decode(item.payload)["created_at"]),
                }
            )
            for item in self.lifecycle.list_scope(scope, include_purged=False)
            if item.object_type == "source_binding"
        )

    def decisions(self, scope):
        from universal_evidence.pilot.reconciliation import (
            ReconciliationDecision,
            ReconciliationDecisionType,
        )

        return tuple(
            ReconciliationDecision(
                **{
                    **_decode(item.payload),
                    "decision_type": ReconciliationDecisionType(
                        _decode(item.payload)["decision_type"]
                    ),
                    "decided_at": _datetime(_decode(item.payload)["decided_at"]),
                }
            )
            for item in self.lifecycle.list_scope(scope, include_purged=False)
            if item.object_type == "reconciliation_decision"
        )


class DurableRuntimeComposition:
    """Explicit composition root; no production downgrade to in-memory state."""

    def __init__(
        self, database, *, migrate=True, operations=None, operation_context=None
    ):
        if database is None or not str(database).strip():
            raise ValueError("durable lifecycle database is required")
        self.lifecycle = SQLiteLifecycleRepository(database, migrate=migrate)
        self.decisions = DurableMappingDecisionRepository(self.lifecycle)
        self.answers = DurableAnswerReferenceRepository(self.lifecycle)
        self.reconciliation = DurableReconciliationRepository(self.lifecycle)
        self.activation = DurableActivationRepository(self.lifecycle)
        self.plans = DurableAnalyticalPlanRepository(self.lifecycle)
        self.results = DurableAggregationRepository(self.lifecycle)
        self.lineage = DurableLineageRepository(self.lifecycle)
        if operations is None and operation_context is not None:
            from universal_evidence.operations import GovernedOperationsService

            operations = GovernedOperationsService(self.lifecycle)
        self.operations = operations
        self.operation_context = operation_context

    def build_lifecycle_operations(self):
        if self.operations is None or self.operation_context is None:
            raise ValueError("operations and operation context are required")
        from universal_evidence.operations import GovernedLifecycleOperations

        return GovernedLifecycleOperations(
            self.lifecycle, self.operations, self.operation_context
        )

    def build_activation_services(self, *, audit_sink, clock):
        from universal_evidence.activation import PueActivationResolver, PueActivationService

        return (
            PueActivationResolver(repository=self.activation, clock=clock),
            PueActivationService(
                repository=self.activation,
                audit_sink=audit_sink,
                clock=clock,
                operations=self.operations,
                operation_context=self.operation_context,
            ),
        )

    def build_pilot_services(self, *, activation_resolver, audit_sink=None, clock=None):
        """Rebuild ACT-003/004/005 services over durable governance state."""
        from universal_evidence.pilot.measurement_service import PilotGovernedMeasurementService
        from universal_evidence.pilot.normalization_service import PilotGovernedNormalizationService
        from universal_evidence.pilot.semantic_service import PilotSemanticGovernanceService
        from universal_evidence.pilot.telemetry import InMemoryPilotTelemetry

        telemetry = InMemoryPilotTelemetry()
        confirmation = __import__(
            "universal_evidence.governance", fromlist=["ConfirmationService"]
        ).ConfirmationService(repository=self.decisions, clock=clock)
        semantic = PilotSemanticGovernanceService(
            activation_resolver=activation_resolver,
            confirmation_service=confirmation,
            telemetry=telemetry,
            audit_sink=audit_sink,
            clock=clock,
            operations=self.operations,
            operation_context=self.operation_context,
        )
        normalization = PilotGovernedNormalizationService(
            activation_resolver=activation_resolver,
            semantic_service=semantic,
            confirmation_service=confirmation,
            telemetry=telemetry,
            operations=self.operations,
            operation_context=self.operation_context,
        )
        normalization.normalization = DurableNormalizationAdapter(
            normalization.normalization, self.lifecycle
        )
        measurement = PilotGovernedMeasurementService(
            activation_resolver=activation_resolver,
            normalization_service=normalization,
            telemetry=telemetry,
            audit_sink=audit_sink,
            clock=clock,
            operations=self.operations,
            operation_context=self.operation_context,
            lifecycle=self.lifecycle,
        )
        measurement.planner.repository = self.plans
        measurement.executor.repository = self.results
        return confirmation, semantic, normalization, measurement

    def build_materialization_service(
        self, registry, relationships, *, activation_resolver=None, audit_sink=None
    ):
        from universal_evidence.pilot.materialization import (
            GovernedEntityMaterializationService,
        )

        return GovernedEntityMaterializationService(
            registry,
            relationships,
            activation_resolver=activation_resolver,
            audit_sink=audit_sink,
            operations=self.operations,
            operation_context=self.operation_context,
        )

    def build_reconciliation_service(self, registry, scope, *, activation_resolver=None):
        from universal_evidence.pilot.reconciliation import (
            GovernedIdentityReconciliationService,
        )

        return GovernedIdentityReconciliationService(
            registry,
            activation_resolver=activation_resolver,
            bindings=self.reconciliation.bindings(scope),
            decisions=self.reconciliation.decisions(scope),
            operations=self.operations,
            operation_context=self.operation_context,
            persistence=self.reconciliation,
        )

    def build_governed_ask_service(self, registry, graph, scope, *, activation_resolver=None):
        from universal_evidence.pilot.governed_intelligence import (
            GovernedAskNexoraService,
        )

        return GovernedAskNexoraService(
            registry=registry,
            graph=graph,
            bindings=self.reconciliation.bindings(scope),
            activation_resolver=activation_resolver,
            operations=self.operations,
            operation_context=self.operation_context,
        )


def _request(payload):
    return ConfirmationRequest(
        payload["request_id"],
        payload["request_fingerprint"],
        payload["discovery_id"],
        DecisionScope(**payload["scope"]),
        payload["semantic_concept_id"],
        ConfirmationState(payload["confirmation_state"]),
        _actor(payload["created_by"]),
        _datetime(payload["created_at"]),
        payload["classifier_version"],
        payload["ontology_version"],
        payload["policy_version"],
    )


def _actor(payload):
    return ConfirmationActor(
        payload["actor_id"],
        payload["principal"],
        payload["actor_role"],
        ActorType(payload["actor_type"]),
    )


def _decision(payload):
    provenance = GovernanceDecisionProvenance(**payload["provenance"])
    return MappingDecision(
        payload["decision_id"],
        payload["decision_fingerprint"],
        DecisionScope(**payload["scope"]),
        payload["semantic_concept_id"],
        MappingDecisionState(payload["decision_state"]),
        ConfirmationState(payload["confirmation_state"]),
        _actor(payload["actor"]),
        _datetime(payload["decision_timestamp"]),
        payload["reason"],
        tuple(tuple(item) for item in payload["original_candidate_ranking"]),
        provenance,
        payload.get("supersedes_decision_id"),
        _datetime(payload["effective_from"]) if payload.get("effective_from") else None,
        _datetime(payload["effective_to"]) if payload.get("effective_to") else None,
    )


def _activation_actor(payload):
    from universal_evidence.activation import ActivationActor, ActivationPermission

    return ActivationActor(
        payload["actor_id"],
        payload["actor_role"],
        payload["actor_type"],
        tuple(ActivationPermission(item) for item in payload["permissions"]),
    )


def _activation_config(payload):
    from universal_evidence.activation import (
        ActivationScope,
        ActivationStage,
        ConfigState,
        FallbackPolicy,
        PueActivationConfig,
        RollbackPolicy,
        ScopeLevel,
    )
    from universal_evidence.planning import AnalyticalIntentType

    scope = payload["scope"]
    return PueActivationConfig(
        payload["activation_id"],
        ActivationScope(
            ScopeLevel(scope["level"]),
            **{k: scope[k] for k in ("organization_id", "tenant_id", "prospect_id", "analysis_id")},
        ),
        ActivationStage(payload["activation_stage"]),
        tuple(payload["enabled_capabilities"]),
        tuple(payload["visible_surfaces"]),
        tuple(AnalyticalIntentType(item) for item in payload["allowed_question_types"]),
        FallbackPolicy(payload["fallback_policy"]),
        RollbackPolicy(payload["rollback_policy"]),
        _datetime(payload["effective_from"]),
        _datetime(payload["expires_at"]) if payload.get("expires_at") else None,
        _activation_actor(payload["configured_by"]),
        _datetime(payload["configured_at"]),
        payload["reason"],
        payload["policy_version"],
        ConfigState(payload["state"]),
        payload.get("supersedes_activation_id"),
        payload["fingerprint"],
    )


def _kill_switch(payload):
    from universal_evidence.activation import FallbackPolicy, KillSwitchConfig

    return KillSwitchConfig(
        payload["kill_switch_id"],
        payload["enabled"],
        payload["allow_shadow_execution"],
        FallbackPolicy(payload["fallback_policy"]),
        _activation_actor(payload["actor"]),
        payload["reason"],
        _datetime(payload["configured_at"]),
        payload["policy_version"],
        payload["fingerprint"],
    )


def _analytical_plan(payload):
    from universal_evidence.aggregation import AggregationFilter, FilterOperator, TimeBucket
    from universal_evidence.capability import AuthorizedOperation
    from universal_evidence.planning import (
        AnalyticalIntentType,
        AnalyticalPlan,
        AnalyticalPlanProvenance,
        PlanningReason,
        PlanningStatus,
    )

    provenance = payload["provenance"]
    return AnalyticalPlan(
        payload["plan_id"],
        payload["intent_id"],
        _capability_scope(payload["scope"]),
        AnalyticalIntentType(payload["intent_type"]) if payload.get("intent_type") else None,
        payload.get("capability_assessment_id"),
        payload.get("capability_id"),
        payload.get("execution_authorization_id"),
        AuthorizedOperation(payload["operation"]) if payload.get("operation") else None,
        payload.get("measure_id"),
        tuple(payload["dimension_ids"]),
        payload.get("time_dimension_id"),
        tuple(
            AggregationFilter(item["dimension_id"], FilterOperator(item["operator"]), item["value"])
            for item in payload["filters"]
        ),
        TimeBucket(payload["time_bucket"]) if payload.get("time_bucket") else None,
        payload.get("currency_requirement"),
        payload.get("unit_requirement"),
        payload.get("alignment_id"),
        payload.get("record_basis_id"),
        tuple(payload["normalization_run_ids"]),
        PlanningStatus(payload["planning_status"]),
        tuple(PlanningReason(item) for item in payload["reason_codes"]),
        AnalyticalPlanProvenance(
            provenance.get("capability_assessment_id"),
            provenance.get("capability_id"),
            provenance.get("execution_authorization_id"),
            provenance.get("measure_id"),
            tuple(provenance["dimension_ids"]),
            provenance.get("time_dimension_id"),
            provenance.get("alignment_id"),
            provenance.get("record_basis_id"),
            tuple(provenance["normalization_run_ids"]),
            tuple(provenance["coverage_ids"]),
            provenance.get("capability_policy_version"),
            provenance.get("execution_authorization_policy_version"),
        ),
        payload["planning_policy_version"],
        payload["plan_fingerprint"],
        _datetime(payload["planned_at"]),
    )


def _aggregation_result(payload):
    from universal_evidence.aggregation.models import (
        AggregationExecutionStatistics,
        AggregationGroup,
        AggregationProvenance,
        AggregationResultStatus,
        AggregationWarning,
        GovernedAggregationResult,
    )
    from universal_evidence.capability import AuthorizedOperation

    provenance = payload.get("provenance")
    return GovernedAggregationResult(
        payload["result_id"],
        payload["request_id"],
        payload.get("plan_id"),
        _capability_scope(payload["scope"]),
        AuthorizedOperation(payload["operation"]) if payload.get("operation") else None,
        AggregationResultStatus(payload["status"]),
        payload.get("measure_id"),
        tuple(payload["dimension_ids"]),
        payload.get("currency_or_unit"),
        payload.get("scalar_value"),
        tuple(
            AggregationGroup(
                item["group_id"],
                tuple(tuple(value) for value in item["dimension_values"]),
                item["value"],
                item.get("unit"),
                item["record_count"],
                tuple(item["normalized_field_ids"]),
                item["fingerprint"],
            )
            for item in payload["groups"]
        ),
        AggregationExecutionStatistics(**payload["statistics"]),
        tuple(AggregationWarning(item) for item in payload["warnings"]),
        AggregationProvenance(
            provenance["capability_assessment_id"],
            provenance["capability_id"],
            provenance["authorization_id"],
            provenance.get("measure_id"),
            tuple(provenance["dimension_ids"]),
            provenance.get("alignment_id"),
            provenance.get("record_basis_id"),
            tuple(provenance["normalization_run_ids"]),
            tuple(provenance["normalized_field_ids"]),
            tuple(provenance["normalized_fingerprints"]),
            tuple(provenance["mapping_decision_ids"]),
            tuple(provenance["source_row_fingerprints"]),
        )
        if provenance
        else None,
        payload.get("capability_policy_version"),
        payload["execution_policy_version"],
        payload["result_fingerprint"],
        _datetime(payload["executed_at"]),
    )
