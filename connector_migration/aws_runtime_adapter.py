"""AWS registry-to-runtime adapter for the E8 connector framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from connector_migration.auth_config_mapper import AuthConfigMapper
from connector_registry import ConnectorRegistry, ConnectorSyncStateStore
from connector_runtime import ConnectorExecutionEngine, ConnectorExecutionPolicy, ConnectorExecutionResult
from connector_runtime.policy import ConnectorExecutionMode
from connector_sdk import ConnectorAuthConfig, ConnectorRuntimeContext
from connectors.aws import AWSReferenceConnector


@dataclass(frozen=True)
class AWSRuntimeAdapterResult:
    """Result envelope for AWS runtime adapter execution."""

    connector_id: str
    mode: ConnectorExecutionMode
    execution_result: ConnectorExecutionResult
    auth_config: ConnectorAuthConfig
    runtime_context: ConnectorRuntimeContext


class AWSRuntimeAdapter:
    """Adapt existing AWS connector_registry config into E8 runtime execution."""

    connector_id = AWSReferenceConnector.metadata.connector_id

    def __init__(
        self,
        *,
        registry: ConnectorRegistry | None = None,
        sync_state_store: ConnectorSyncStateStore | None = None,
        engine: ConnectorExecutionEngine | None = None,
    ) -> None:
        self.registry = registry or ConnectorRegistry()
        self.sync_state_store = sync_state_store or ConnectorSyncStateStore()
        self._ensure_registered()
        self.engine = engine or ConnectorExecutionEngine(registry=self.registry, sync_state_store=self.sync_state_store)

    def build_auth_config(self, registry_config: Mapping[str, Any]) -> ConnectorAuthConfig:
        return AuthConfigMapper.from_registry_config(registry_config)

    def build_runtime_context(
        self,
        registry_config: Mapping[str, Any],
        *,
        mode: ConnectorExecutionMode = ConnectorExecutionMode.DISCOVERY_ONLY,
        requested_by: str | None = None,
    ) -> ConnectorRuntimeContext:
        metadata = dict(registry_config.get("metadata") or {})
        organization_id = registry_config.get("organization_id") or metadata.get("organization_id")
        account_id = metadata.get("account_id") or registry_config.get("account_id")
        region = metadata.get("region") or registry_config.get("region") or "us-east-1"
        return ConnectorRuntimeContext(
            organization_id=organization_id,
            requested_by=requested_by or registry_config.get("configured_by"),
            dry_run=mode == ConnectorExecutionMode.DRY_RUN,
            metadata={
                "connector_id": self.connector_id,
                "source": "connector_registry",
                "aws_account_id": account_id,
                "aws_regions": (region,),
                "registry_config": dict(registry_config),
            },
        )

    def run_discovery_only(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> AWSRuntimeAdapterResult:
        return self.execute(registry_config, mode=ConnectorExecutionMode.DISCOVERY_ONLY, requested_by=requested_by)

    def run_dry_run(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> AWSRuntimeAdapterResult:
        return self.execute(registry_config, mode=ConnectorExecutionMode.DRY_RUN, requested_by=requested_by)

    def execute(
        self,
        registry_config: Mapping[str, Any],
        *,
        mode: ConnectorExecutionMode = ConnectorExecutionMode.DISCOVERY_ONLY,
        requested_by: str | None = None,
    ) -> AWSRuntimeAdapterResult:
        self._ensure_registered()
        auth_config = self.build_auth_config(registry_config)
        context = self.build_runtime_context(registry_config, mode=mode, requested_by=requested_by)
        policy = ConnectorExecutionPolicy(mode=mode)
        result = self.engine.execute(
            self.connector_id,
            policy=policy,
            auth_config=auth_config,
            context=context,
        )
        return AWSRuntimeAdapterResult(
            connector_id=self.connector_id,
            mode=mode,
            execution_result=result,
            auth_config=auth_config,
            runtime_context=context,
        )

    def _ensure_registered(self) -> None:
        if self.registry.get_connector(self.connector_id) is None:
            self.registry.register_connector(AWSReferenceConnector)
