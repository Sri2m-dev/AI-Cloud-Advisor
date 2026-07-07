"""AWS production runtime adapter seam for E8.1.12.

This adapter bridges existing AWS connector_registry configuration into the E8
runtime control plane while preserving the current production AWS service path.
Full production sync remains disabled by default and is intentionally isolated
behind an explicit feature flag seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from connector_migration import AWSRuntimeAdapter, AWSRuntimeAdapterResult
from connector_runtime.policy import ConnectorExecutionMode
from connector_sdk import ConnectorAuthConfig, ConnectorRuntimeContext


@dataclass(frozen=True)
class AWSProductionRuntimeAdapterResult:
    """Result returned by the AWS production runtime adapter seam."""

    runtime_enabled: bool
    mode: ConnectorExecutionMode
    adapter_result: AWSRuntimeAdapterResult | None = None
    legacy_result: Mapping[str, Any] | None = None
    message: str = ""


class AWSProductionRuntimeAdapter:
    """Bridge AWS production config into the E8 runtime without replacing sync logic.

    The adapter intentionally delegates discovery-only and dry-run execution to
    the E8 `AWSRuntimeAdapter`. Full sync remains disabled unless explicitly
    enabled and supplied with a lazy legacy sync callable. This preserves the
    existing `AWSConnectorService` import and execution behavior.
    """

    def __init__(
        self,
        *,
        runtime_adapter: AWSRuntimeAdapter | None = None,
        runtime_enabled: bool = True,
        full_sync_enabled: bool = False,
        legacy_sync_callable: Callable[..., Mapping[str, Any]] | None = None,
    ) -> None:
        self.runtime_adapter = runtime_adapter or AWSRuntimeAdapter()
        self.runtime_enabled = runtime_enabled
        self.full_sync_enabled = full_sync_enabled
        self.legacy_sync_callable = legacy_sync_callable

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
        """Build E8 auth config from an existing AWS connector_registry row."""

        return self.runtime_adapter.build_auth_config(registry_config)

    def build_runtime_context(
        self,
        registry_config: Mapping[str, Any],
        *,
        mode: ConnectorExecutionMode = ConnectorExecutionMode.DISCOVERY_ONLY,
        requested_by: str | None = None,
    ) -> ConnectorRuntimeContext:
        """Build E8 runtime context from an existing AWS connector_registry row."""

        return self.runtime_adapter.build_runtime_context(registry_config, mode=mode, requested_by=requested_by)

    def run_discovery_only(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> AWSProductionRuntimeAdapterResult:
        """Run AWS discovery-only through the E8 runtime path."""

        if not self.is_runtime_enabled(registry_config):
            return self._disabled(ConnectorExecutionMode.DISCOVERY_ONLY)
        result = self.runtime_adapter.run_discovery_only(registry_config, requested_by=requested_by)
        return AWSProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.DISCOVERY_ONLY,
            adapter_result=result,
            message="AWS discovery-only execution completed through E8 runtime.",
        )

    def run_dry_run(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> AWSProductionRuntimeAdapterResult:
        """Run AWS dry-run through the E8 runtime path without publishing."""

        if not self.is_runtime_enabled(registry_config):
            return self._disabled(ConnectorExecutionMode.DRY_RUN)
        result = self.runtime_adapter.run_dry_run(registry_config, requested_by=requested_by)
        return AWSProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.DRY_RUN,
            adapter_result=result,
            message="AWS dry-run execution completed through E8 runtime.",
        )

    def run_full_sync(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> AWSProductionRuntimeAdapterResult:
        """Reserved full-sync seam for future production AWS runtime adoption.

        Full sync is disabled by default. When enabled later, callers can inject
        the proven legacy sync callable rather than importing or changing
        `services.aws_connector_service` here.
        """

        if not self.full_sync_enabled:
            return AWSProductionRuntimeAdapterResult(
                runtime_enabled=self.is_runtime_enabled(registry_config),
                mode=ConnectorExecutionMode.FULL_SYNC,
                message="AWS production full sync via E8 runtime is disabled by default.",
            )
        if self.legacy_sync_callable is None:
            return AWSProductionRuntimeAdapterResult(
                runtime_enabled=self.is_runtime_enabled(registry_config),
                mode=ConnectorExecutionMode.FULL_SYNC,
                message="AWS production full sync requires an injected legacy sync callable.",
            )
        metadata = dict(registry_config.get("metadata") or {})
        legacy_result = self.legacy_sync_callable(
            role_arn=metadata.get("role_arn"),
            external_id=metadata.get("external_id"),
            region=metadata.get("region") or "us-east-1",
            organization_id=registry_config.get("organization_id") or metadata.get("organization_id"),
        )
        return AWSProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.FULL_SYNC,
            legacy_result=legacy_result,
            message="AWS production full sync executed through injected legacy sync seam.",
        )

    def _disabled(self, mode: ConnectorExecutionMode) -> AWSProductionRuntimeAdapterResult:
        return AWSProductionRuntimeAdapterResult(
            runtime_enabled=False,
            mode=mode,
            message="AWS E8 runtime path is disabled for this connector config.",
        )
