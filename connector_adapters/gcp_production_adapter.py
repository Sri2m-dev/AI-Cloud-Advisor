"""GCP production runtime adapter foundation for E8.1.14.

This adapter introduces the E8 runtime seam for GCP without changing any
dashboard or live GCP API behavior. Full production sync is disabled by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from connector_registry import ConnectorRegistry, ConnectorSyncStateStore
from connector_runtime import ConnectorExecutionEngine, ConnectorExecutionPolicy, ConnectorExecutionResult
from connector_runtime.policy import ConnectorExecutionMode
from connector_sdk import ConnectorAuthConfig, ConnectorRuntimeContext
from connectors.gcp import GCPReferenceConnector


@dataclass(frozen=True)
class GCPRuntimeAdapterResult:
    """Result envelope for GCP runtime adapter execution."""

    connector_id: str
    mode: ConnectorExecutionMode
    execution_result: ConnectorExecutionResult
    auth_config: ConnectorAuthConfig
    runtime_context: ConnectorRuntimeContext


@dataclass(frozen=True)
class GCPProductionRuntimeAdapterResult:
    """Result returned by the GCP production runtime adapter seam."""

    runtime_enabled: bool
    mode: ConnectorExecutionMode
    adapter_result: GCPRuntimeAdapterResult | None = None
    legacy_result: Mapping[str, Any] | None = None
    message: str = ""


class GCPProductionRuntimeAdapter:
    """Bridge GCP connector_registry config into the E8 runtime."""

    connector_id = GCPReferenceConnector.metadata.connector_id

    def __init__(
        self,
        *,
        registry: ConnectorRegistry | None = None,
        sync_state_store: ConnectorSyncStateStore | None = None,
        engine: ConnectorExecutionEngine | None = None,
        runtime_enabled: bool = True,
        full_sync_enabled: bool = False,
        legacy_sync_callable: Callable[..., Mapping[str, Any]] | None = None,
    ) -> None:
        self.registry = registry or ConnectorRegistry()
        self.sync_state_store = sync_state_store or ConnectorSyncStateStore()
        self.engine = engine or ConnectorExecutionEngine(registry=self.registry, sync_state_store=self.sync_state_store)
        self.runtime_enabled = runtime_enabled
        self.full_sync_enabled = full_sync_enabled
        self.legacy_sync_callable = legacy_sync_callable
        self._ensure_registered()

    def is_runtime_enabled(self, registry_config: Mapping[str, Any] | None = None) -> bool:
        """Return whether the E8 runtime path should be used for this config."""

        if registry_config is None:
            return self.runtime_enabled
        metadata = dict(registry_config.get("metadata") or {})
        flag = registry_config.get("runtime_enabled", metadata.get("runtime_enabled"))
        if flag is None:
            return self.runtime_enabled
        if isinstance(flag, str):
            return flag.strip().lower() in {"1", "true", "yes", "enabled", "on"}
        return bool(flag)

    def build_auth_config(self, registry_config: Mapping[str, Any]) -> ConnectorAuthConfig:
        """Build E8 auth config from a GCP connector_registry row."""

        metadata = dict(registry_config.get("metadata") or {})
        project_id = metadata.get("project_id") or registry_config.get("project_id") or registry_config.get("account_id")
        secret_ref = (
            metadata.get("service_account_secret_ref")
            or metadata.get("secret_ref")
            or registry_config.get("service_account_secret_ref")
            or registry_config.get("secret_ref")
        )
        regions = metadata.get("regions") or metadata.get("region") or registry_config.get("regions") or registry_config.get("region") or ("us-central1",)
        if isinstance(regions, str):
            regions = (regions,)
        sanitized = {
            key: value
            for key, value in metadata.items()
            if key not in {"service_account_json", "service_account_key", "private_key", "secret"}
        }
        sanitized.update(
            {
                "provider": "GCP",
                "source": "connector_registry",
                "project_id": project_id,
                "regions": tuple(str(region) for region in regions),
            }
        )
        if secret_ref:
            sanitized["service_account_secret_ref"] = secret_ref
            sanitized["secret_ref"] = secret_ref
        return ConnectorAuthConfig(
            auth_type="gcp_service_account" if secret_ref else "anonymous",
            secret_ref=secret_ref,
            account_id=project_id,
            metadata=sanitized,
        )

    def build_runtime_context(
        self,
        registry_config: Mapping[str, Any],
        *,
        mode: ConnectorExecutionMode = ConnectorExecutionMode.DISCOVERY_ONLY,
        requested_by: str | None = None,
    ) -> ConnectorRuntimeContext:
        """Build E8 runtime context from a GCP connector_registry row."""

        metadata = dict(registry_config.get("metadata") or {})
        organization_id = registry_config.get("organization_id") or metadata.get("organization_id")
        project_id = metadata.get("project_id") or registry_config.get("project_id") or registry_config.get("account_id")
        regions = metadata.get("regions") or metadata.get("region") or registry_config.get("regions") or registry_config.get("region") or ("us-central1",)
        if isinstance(regions, str):
            regions = (regions,)
        return ConnectorRuntimeContext(
            organization_id=organization_id,
            requested_by=requested_by or registry_config.get("configured_by"),
            dry_run=mode == ConnectorExecutionMode.DRY_RUN,
            metadata={
                "connector_id": self.connector_id,
                "source": "connector_registry",
                "gcp_project_id": project_id,
                "gcp_regions": tuple(str(region) for region in regions),
                "registry_config": dict(registry_config),
            },
        )

    def run_discovery_only(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> GCPProductionRuntimeAdapterResult:
        """Run GCP discovery-only through the E8 runtime path."""

        if not self.is_runtime_enabled(registry_config):
            return self._disabled(ConnectorExecutionMode.DISCOVERY_ONLY)
        result = self._execute(registry_config, mode=ConnectorExecutionMode.DISCOVERY_ONLY, requested_by=requested_by)
        return GCPProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.DISCOVERY_ONLY,
            adapter_result=result,
            message="GCP discovery-only execution completed through E8 runtime.",
        )

    def run_dry_run(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> GCPProductionRuntimeAdapterResult:
        """Run GCP dry-run through the E8 runtime path without publishing."""

        if not self.is_runtime_enabled(registry_config):
            return self._disabled(ConnectorExecutionMode.DRY_RUN)
        result = self._execute(registry_config, mode=ConnectorExecutionMode.DRY_RUN, requested_by=requested_by)
        return GCPProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.DRY_RUN,
            adapter_result=result,
            message="GCP dry-run execution completed through E8 runtime.",
        )

    def run_full_sync(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> GCPProductionRuntimeAdapterResult:
        """Reserved full-sync seam for future production GCP runtime adoption."""

        if not self.full_sync_enabled:
            return GCPProductionRuntimeAdapterResult(
                runtime_enabled=self.is_runtime_enabled(registry_config),
                mode=ConnectorExecutionMode.FULL_SYNC,
                message="GCP production full sync via E8 runtime is disabled by default.",
            )
        if self.legacy_sync_callable is None:
            return GCPProductionRuntimeAdapterResult(
                runtime_enabled=self.is_runtime_enabled(registry_config),
                mode=ConnectorExecutionMode.FULL_SYNC,
                message="GCP production full sync requires an injected legacy sync callable.",
            )
        metadata = dict(registry_config.get("metadata") or {})
        legacy_result = self.legacy_sync_callable(
            project_id=metadata.get("project_id") or registry_config.get("project_id"),
            service_account_secret_ref=metadata.get("service_account_secret_ref") or registry_config.get("service_account_secret_ref"),
            regions=metadata.get("regions") or registry_config.get("regions"),
            organization_id=registry_config.get("organization_id") or metadata.get("organization_id"),
        )
        return GCPProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.FULL_SYNC,
            legacy_result=legacy_result,
            message="GCP production full sync executed through injected legacy sync seam.",
        )

    def _execute(
        self,
        registry_config: Mapping[str, Any],
        *,
        mode: ConnectorExecutionMode,
        requested_by: str | None = None,
    ) -> GCPRuntimeAdapterResult:
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
        return GCPRuntimeAdapterResult(
            connector_id=self.connector_id,
            mode=mode,
            execution_result=result,
            auth_config=auth_config,
            runtime_context=context,
        )

    def _ensure_registered(self) -> None:
        if self.registry.get_connector(self.connector_id) is None:
            self.registry.register_connector(GCPReferenceConnector)

    def _disabled(self, mode: ConnectorExecutionMode) -> GCPProductionRuntimeAdapterResult:
        return GCPProductionRuntimeAdapterResult(
            runtime_enabled=False,
            mode=mode,
            message="GCP E8 runtime path is disabled for this connector config.",
        )
