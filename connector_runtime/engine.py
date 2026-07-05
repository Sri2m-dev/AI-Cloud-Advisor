"""Connector execution engine."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from connector_health import ConnectorHealthStore
from connector_logs import ConnectorLogger, ConnectorRunLog
from connector_registry import ConnectorRegistry, ConnectorSyncStateStore
from connector_sdk import ConnectorAuthConfig, ConnectorRuntimeContext, ConnectorSyncResult, ConnectorSyncState
from connector_runtime.exceptions import ConnectorRuntimeError
from connector_runtime.hooks import ConnectorExecutionHooks
from connector_runtime.pipeline import ConnectorExecutionPipeline
from connector_runtime.policy import ConnectorExecutionMode, ConnectorExecutionPolicy
from connector_runtime.result import ConnectorExecutionResult
from connector_secrets import SecretProvider


class ConnectorExecutionEngine:
    """Orchestrates connector execution through the standard Nexora pipeline."""

    def __init__(
        self,
        registry: ConnectorRegistry,
        sync_state_store: ConnectorSyncStateStore | None = None,
        health_store: ConnectorHealthStore | None = None,
        logger: ConnectorLogger | None = None,
        secret_provider: SecretProvider | None = None,
        hooks: ConnectorExecutionHooks | None = None,
    ) -> None:
        self.registry = registry
        self.sync_state_store = sync_state_store or ConnectorSyncStateStore()
        self.health_store = health_store or ConnectorHealthStore()
        self.logger = logger or ConnectorLogger()
        self.secret_provider = secret_provider
        self.pipeline = ConnectorExecutionPipeline(hooks=hooks)

    def execute(
        self,
        connector_id: str,
        *,
        policy: ConnectorExecutionPolicy | None = None,
        auth_config: ConnectorAuthConfig | None = None,
        context: ConnectorRuntimeContext | None = None,
    ) -> ConnectorExecutionResult:
        """Execute a registered connector and persist runtime observations."""

        policy = policy or ConnectorExecutionPolicy()
        execution_id = context.run_id if context and context.run_id else str(uuid4())
        context = context or ConnectorRuntimeContext(run_id=execution_id, dry_run=policy.dry_run)
        if context.run_id is None or context.dry_run != policy.dry_run:
            context = ConnectorRuntimeContext(
                organization_id=context.organization_id,
                environment=context.environment,
                requested_by=context.requested_by,
                correlation_id=context.correlation_id,
                run_id=execution_id,
                dry_run=policy.dry_run,
                metadata=context.metadata,
            )

        started_at = datetime.now(timezone.utc)
        errors: list[str] = []
        warnings: list[str] = []
        counters = {
            "records_extracted": 0,
            "records_normalized": 0,
            "records_published": 0,
            "checkpoint": policy.checkpoint,
        }
        state = ConnectorSyncState.RUNNING

        record = self.registry.get_connector(connector_id)
        if record is None:
            raise ConnectorRuntimeError(f"Connector is not registered: {connector_id}")
        if not record.enabled:
            raise ConnectorRuntimeError(f"Connector is disabled: {connector_id}")

        self._resolve_secret_reference(auth_config)
        connector = record.connector_cls(auth_config=auth_config, runtime_context=context)
        self._record_log(connector_id, execution_id, "execution_started", "Connector execution started.")
        self.sync_state_store.mark_running(connector_id)

        try:
            counters = self.pipeline.run(connector, context, policy)
            state = counters["state"]
            warnings.extend(counters.get("warnings", ()))
            self.pipeline.hooks.on_success(context, policy)
        except Exception as exc:  # pragma: no cover - defensive runtime envelope
            state = ConnectorSyncState.FAILED
            errors.append(str(exc))
            self.pipeline.hooks.on_failure(context, policy, exc)
            self._record_log(connector_id, execution_id, "execution_failed", str(exc), level="error")

        finished_at = datetime.now(timezone.utc)
        health_status = connector.health()
        self.health_store.record_health_snapshot(health_status)

        sync_result = ConnectorSyncResult(
            connector_id=connector_id,
            state=state,
            started_at=started_at,
            finished_at=finished_at,
            records_extracted=int(counters.get("records_extracted", 0)),
            records_normalized=int(counters.get("records_normalized", 0)),
            records_published=int(counters.get("records_published", 0)),
            errors=tuple(errors),
            warnings=tuple(warnings),
            checkpoint=counters.get("checkpoint"),
            metadata={
                "execution_id": execution_id,
                "mode": policy.mode.value,
                "dry_run": policy.dry_run,
            },
        )
        self.sync_state_store.record_sync_state(sync_result)

        self._record_log(
            connector_id,
            execution_id,
            "execution_finished",
            f"Connector execution finished with state {state.value}.",
            level="error" if state == ConnectorSyncState.FAILED else "info",
        )

        return ConnectorExecutionResult(
            execution_id=execution_id,
            connector_id=connector_id,
            mode=policy.mode,
            state=state,
            started_at=started_at,
            finished_at=finished_at,
            records_extracted=sync_result.records_extracted,
            records_normalized=sync_result.records_normalized,
            records_published=sync_result.records_published,
            warnings=sync_result.warnings,
            errors=sync_result.errors,
            health_status=health_status,
            checkpoint=sync_result.checkpoint,
            metadata=sync_result.metadata,
        )

    def execute_full_sync(self, connector_id: str, **kwargs: object) -> ConnectorExecutionResult:
        return self.execute(
            connector_id,
            policy=ConnectorExecutionPolicy(mode=ConnectorExecutionMode.FULL_SYNC),
            **kwargs,
        )

    def execute_incremental_sync(self, connector_id: str, checkpoint: str | None = None, **kwargs: object) -> ConnectorExecutionResult:
        return self.execute(
            connector_id,
            policy=ConnectorExecutionPolicy(mode=ConnectorExecutionMode.INCREMENTAL_SYNC, checkpoint=checkpoint),
            **kwargs,
        )

    def _resolve_secret_reference(self, auth_config: ConnectorAuthConfig | None) -> None:
        """Validate that a configured secret reference can be resolved.

        Secret values are intentionally not returned or logged. Concrete
        connectors remain responsible for using their auth configuration.
        """

        if auth_config is None or auth_config.secret_ref is None or self.secret_provider is None:
            return
        if self.secret_provider.resolve(auth_config.secret_ref) is None:
            raise ConnectorRuntimeError(f"Connector secret could not be resolved: {auth_config.secret_ref}")

    def _record_log(self, connector_id: str, execution_id: str, event_type: str, message: str, *, level: str = "info") -> None:
        self.logger.record_run_log(
            ConnectorRunLog(
                connector_id=connector_id,
                run_id=execution_id,
                event_type=event_type,
                message=message,
                level=level,
            )
        )
