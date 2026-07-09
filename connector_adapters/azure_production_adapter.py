"""Azure production runtime adapter seam for E8.1.13.

This adapter bridges existing Azure connector_registry configuration into the
E8 runtime control plane without changing the current Azure onboarding or
production sync path. Full production sync remains disabled by default.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from connector_auth import AuthenticationManager, ConnectorAuthContext, ConnectorAuthType, ConnectorCredential, ConnectorCredentialRequest, CredentialProvider
from connector_migration.auth_config_mapper import AuthConfigMapper
from connector_normalization import CanonicalCloudResource, CanonicalCostRecord, CanonicalRecordType
from connector_persistence import PersistenceCanonicalPublisher
from connector_persistence.adapters.memory import MemoryCanonicalRepository
from connector_registry import ConnectorRegistry, ConnectorSyncStateStore
from connector_runtime import ConnectorExecutionEngine, ConnectorExecutionPolicy, ConnectorExecutionResult
from connector_runtime.policy import ConnectorExecutionMode
from connector_sdk import BaseConnector, ConnectorAuthConfig, ConnectorHealthStatus, ConnectorMetadata, ConnectorRecord, ConnectorRuntimeContext
from connector_secrets import EnvironmentSecretProvider, SecretProvider


@dataclass(frozen=True)
class AzureRuntimeAdapterResult:
    """Result envelope for Azure runtime adapter execution."""

    connector_id: str
    mode: ConnectorExecutionMode
    execution_result: ConnectorExecutionResult
    auth_config: ConnectorAuthConfig
    runtime_context: ConnectorRuntimeContext


@dataclass(frozen=True)
class AzureProductionRuntimeAdapterResult:
    """Result returned by the Azure production runtime adapter seam."""

    runtime_enabled: bool
    mode: ConnectorExecutionMode
    adapter_result: AzureRuntimeAdapterResult | None = None
    legacy_result: Mapping[str, Any] | None = None
    message: str = ""


class _AzureCredentialProvider(CredentialProvider):
    """Adapt ConnectorAuthConfig into auth-framework credentials."""

    def __init__(self, auth_config: ConnectorAuthConfig | None, secret_provider: SecretProvider | None = None) -> None:
        self.auth_config = auth_config
        self.secret_provider = secret_provider or EnvironmentSecretProvider()

    def load(self, request: ConnectorCredentialRequest) -> ConnectorCredential:
        metadata = dict(self.auth_config.metadata if self.auth_config else {})
        principal = metadata.get("client_id")
        secret = None
        if request.secret_ref:
            secret = self.secret_provider.resolve(request.secret_ref)
            if secret is None:
                secret = "__secret_ref_present__"
        return ConnectorCredential(
            auth_type=request.auth_type,
            principal=principal,
            secret=secret,
            scopes=request.scopes,
            metadata={
                "tenant_id": self.auth_config.tenant_id if self.auth_config else None,
                "subscription_id": self.auth_config.account_id if self.auth_config else None,
                **metadata,
            },
        )


class _AzureRuntimeReferenceConnector(BaseConnector):
    """Mock-safe Azure connector used only by the production adapter seam."""

    metadata = ConnectorMetadata(
        connector_id="azure.runtime_adapter",
        name="Azure Runtime Adapter Connector",
        provider="Azure",
        category="cloud",
        version="0.1.0",
        description="Runtime adapter connector for Azure discovery-only and dry-run execution.",
        supports_full_sync=True,
        supports_incremental_sync=False,
        supported_entities=("cloud_resource", "cost_record"),
        owner="Nexora",
    )

    def __init__(
        self,
        auth_config: ConnectorAuthConfig | None = None,
        runtime_context: ConnectorRuntimeContext | None = None,
        *,
        auth_manager: AuthenticationManager | None = None,
        publisher: PersistenceCanonicalPublisher | None = None,
        secret_provider: SecretProvider | None = None,
    ) -> None:
        super().__init__(auth_config=auth_config, runtime_context=runtime_context)
        self.secret_provider = secret_provider or EnvironmentSecretProvider()
        self.auth_manager = auth_manager or AuthenticationManager(_AzureCredentialProvider(auth_config, self.secret_provider))
        self.publisher = publisher or PersistenceCanonicalPublisher(MemoryCanonicalRepository(), target="memory:data_fabric")
        self.auth_context: ConnectorAuthContext | None = None
        self._last_publish_count = 0

    def authenticate(self) -> bool:
        request = self._credential_request()
        self.auth_context = self.auth_manager.authenticate(request, cache_key=f"azure.runtime_adapter:{self.subscription_id}:{request.auth_type.value}")
        return self.auth_context.authenticated

    def discover(self) -> Mapping[str, Any]:
        return {
            "provider": "Azure",
            "tenant_id": self.tenant_id,
            "subscription_id": self.subscription_id,
            "datasets": ("cost_summary", "virtual_machine_inventory", "storage_account_inventory"),
            "mode": "runtime_adapter_safe",
        }

    def extract(self, *, incremental: bool = False, checkpoint: str | None = None) -> Sequence[Mapping[str, Any]]:
        return [
            {
                "record_type": "cost_summary",
                "source_id": f"azure:{self.subscription_id}:cost:monthly:compute",
                "name": "Azure Monthly Compute Spend",
                "amount": 0.0,
                "currency": "USD",
                "billing_period": datetime.now(timezone.utc).strftime("%Y-%m"),
                "cost_category": "cloud_compute",
                "region": self.default_region,
            },
            {
                "record_type": "virtual_machine",
                "source_id": f"azure:{self.subscription_id}:{self.default_region}:vm:runtime-adapter-reference",
                "name": "runtime-adapter-reference",
                "region": self.default_region,
                "resource_type": "virtual_machine",
                "status": "discovered",
                "monthly_cost": 0.0,
                "tags": {"Source": "E8 Runtime Adapter", "Mode": "dry-run"},
            },
            {
                "record_type": "storage_account",
                "source_id": f"azure:{self.subscription_id}:{self.default_region}:storage:runtimeadapter",
                "name": "runtimeadapter",
                "region": self.default_region,
                "resource_type": "storage_account",
                "status": "discovered",
                "monthly_cost": 0.0,
                "tags": {"Source": "E8 Runtime Adapter", "Mode": "dry-run"},
            },
        ]

    def normalize(self, records: Sequence[Mapping[str, Any]]) -> Sequence[ConnectorRecord]:
        normalized: list[ConnectorRecord] = []
        for record in records:
            canonical = self._to_canonical(record)
            normalized.append(
                ConnectorRecord(
                    source_id=str(record["source_id"]),
                    entity_type=canonical.record_type.value,
                    payload={
                        "canonical_record": canonical,
                        "canonical_record_type": canonical.record_type.value,
                        "canonical": asdict(canonical),
                    },
                )
            )
        return normalized

    def validate(self, records: Sequence[ConnectorRecord]) -> tuple[bool, tuple[str, ...]]:
        errors: list[str] = []
        for record in records:
            canonical = record.payload.get("canonical_record")
            if canonical is None:
                errors.append(f"Missing canonical record for {record.source_id}.")
                continue
            if not getattr(canonical, "record_id", None):
                errors.append(f"Missing canonical record ID for {record.source_id}.")
            if canonical.record_type not in {CanonicalRecordType.CLOUD_RESOURCE, CanonicalRecordType.COST_RECORD}:
                errors.append(f"Unsupported Azure canonical type: {canonical.record_type}.")
        return not errors, tuple(errors)

    def publish(self, records: Sequence[ConnectorRecord]) -> int:
        canonical_records = [record.payload["canonical_record"] for record in records]
        result = self.publisher.publish(canonical_records)
        self._last_publish_count = result.published_count
        return result.published_count

    def health(self) -> ConnectorHealthStatus:
        status = "healthy" if self.auth_context is None or self.auth_context.authenticated else "degraded"
        return ConnectorHealthStatus(
            connector_id=self.metadata.connector_id,
            status=status,
            message="Azure runtime adapter is mock-safe and ready for discovery or dry-run execution.",
            last_success_at=datetime.now(timezone.utc) if self._last_publish_count else None,
            metadata={
                "tenant_id": self.tenant_id,
                "subscription_id": self.subscription_id,
                "last_publish_count": self._last_publish_count,
                "mode": "runtime_adapter",
            },
        )

    @property
    def tenant_id(self) -> str:
        if self.auth_config and self.auth_config.tenant_id:
            return self.auth_config.tenant_id
        return str(self.runtime_context.metadata.get("azure_tenant_id") or "unknown-tenant")

    @property
    def subscription_id(self) -> str:
        if self.auth_config and self.auth_config.account_id:
            return self.auth_config.account_id
        return str(self.runtime_context.metadata.get("azure_subscription_id") or "unknown-subscription")

    @property
    def default_region(self) -> str:
        configured = None
        if self.auth_config:
            configured = self.auth_config.metadata.get("region") or self.auth_config.metadata.get("location")
        return str(configured or self.runtime_context.metadata.get("azure_region") or "eastus")

    def _credential_request(self) -> ConnectorCredentialRequest:
        if self.auth_config is None:
            return ConnectorCredentialRequest(auth_type=ConnectorAuthType.ANONYMOUS)
        try:
            auth_type = ConnectorAuthType(self.auth_config.auth_type)
        except ValueError:
            auth_type = ConnectorAuthType.ANONYMOUS
        return ConnectorCredentialRequest(
            auth_type=auth_type,
            secret_ref=self.auth_config.secret_ref,
            scopes=self.auth_config.scopes,
            metadata={
                "provider": "Azure",
                "tenant_id": self.auth_config.tenant_id,
                "subscription_id": self.auth_config.account_id,
                **dict(self.auth_config.metadata),
            },
        )

    def _to_canonical(self, record: Mapping[str, Any]):
        record_type = record.get("record_type")
        if record_type == "cost_summary":
            return CanonicalCostRecord(
                record_id=f"azure-cost:{record['source_id']}",
                record_type=CanonicalRecordType.COST_RECORD,
                source_system="azure",
                source_id=str(record["source_id"]),
                name=str(record.get("name") or "Azure Cost Summary"),
                organization_id=self.runtime_context.organization_id,
                status="active",
                amount=float(record.get("amount") or 0.0),
                currency=str(record.get("currency") or "USD"),
                billing_period=record.get("billing_period"),
                cost_category=record.get("cost_category"),
                provider="Azure",
                provider_metadata={
                    "tenant_id": self.tenant_id,
                    "subscription_id": self.subscription_id,
                    "region": record.get("region"),
                    "source_dataset": "cost_summary",
                },
            )
        tags = {str(key): str(value) for key, value in dict(record.get("tags") or {}).items()}
        return CanonicalCloudResource(
            record_id=f"azure-resource:{record['source_id']}",
            record_type=CanonicalRecordType.CLOUD_RESOURCE,
            source_system="azure",
            source_id=str(record["source_id"]),
            name=str(record.get("name") or record["source_id"]),
            organization_id=self.runtime_context.organization_id,
            status=str(record.get("status") or "unknown"),
            tags=tags,
            provider="Azure",
            account_id=self.subscription_id,
            region=record.get("region"),
            resource_type=record.get("resource_type") or record_type,
            monthly_cost=float(record.get("monthly_cost") or 0.0),
            currency=str(record.get("currency") or "USD"),
            provider_metadata={
                "tenant_id": self.tenant_id,
                "subscription_id": self.subscription_id,
                "source_dataset": "virtual_machine_inventory" if record_type == "virtual_machine" else "storage_account_inventory",
            },
        )


class AzureProductionRuntimeAdapter:
    """Bridge Azure production config into the E8 runtime without replacing sync logic."""

    connector_id = _AzureRuntimeReferenceConnector.metadata.connector_id

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
        """Build E8 auth config from an existing Azure connector_registry row."""

        return AuthConfigMapper.from_registry_config(registry_config)

    def build_runtime_context(
        self,
        registry_config: Mapping[str, Any],
        *,
        mode: ConnectorExecutionMode = ConnectorExecutionMode.DISCOVERY_ONLY,
        requested_by: str | None = None,
    ) -> ConnectorRuntimeContext:
        """Build E8 runtime context from an existing Azure connector_registry row."""

        metadata = dict(registry_config.get("metadata") or {})
        organization_id = registry_config.get("organization_id") or metadata.get("organization_id")
        tenant_id = metadata.get("tenant_id") or registry_config.get("tenant_id")
        subscription_id = metadata.get("subscription_id") or registry_config.get("subscription_id") or registry_config.get("account_id")
        region = metadata.get("region") or metadata.get("location") or registry_config.get("region") or "eastus"
        return ConnectorRuntimeContext(
            organization_id=organization_id,
            requested_by=requested_by or registry_config.get("configured_by"),
            dry_run=mode == ConnectorExecutionMode.DRY_RUN,
            metadata={
                "connector_id": self.connector_id,
                "source": "connector_registry",
                "azure_tenant_id": tenant_id,
                "azure_subscription_id": subscription_id,
                "azure_region": region,
                "registry_config": dict(registry_config),
            },
        )

    def run_discovery_only(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> AzureProductionRuntimeAdapterResult:
        """Run Azure discovery-only through the E8 runtime path."""

        if not self.is_runtime_enabled(registry_config):
            return self._disabled(ConnectorExecutionMode.DISCOVERY_ONLY)
        result = self._execute(registry_config, mode=ConnectorExecutionMode.DISCOVERY_ONLY, requested_by=requested_by)
        return AzureProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.DISCOVERY_ONLY,
            adapter_result=result,
            message="Azure discovery-only execution completed through E8 runtime.",
        )

    def run_dry_run(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> AzureProductionRuntimeAdapterResult:
        """Run Azure dry-run through the E8 runtime path without publishing."""

        if not self.is_runtime_enabled(registry_config):
            return self._disabled(ConnectorExecutionMode.DRY_RUN)
        result = self._execute(registry_config, mode=ConnectorExecutionMode.DRY_RUN, requested_by=requested_by)
        return AzureProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.DRY_RUN,
            adapter_result=result,
            message="Azure dry-run execution completed through E8 runtime.",
        )

    def run_full_sync(self, registry_config: Mapping[str, Any], *, requested_by: str | None = None) -> AzureProductionRuntimeAdapterResult:
        """Reserved full-sync seam for future production Azure runtime adoption."""

        if not self.full_sync_enabled:
            return AzureProductionRuntimeAdapterResult(
                runtime_enabled=self.is_runtime_enabled(registry_config),
                mode=ConnectorExecutionMode.FULL_SYNC,
                message="Azure production full sync via E8 runtime is disabled by default.",
            )
        if self.legacy_sync_callable is None:
            return AzureProductionRuntimeAdapterResult(
                runtime_enabled=self.is_runtime_enabled(registry_config),
                mode=ConnectorExecutionMode.FULL_SYNC,
                message="Azure production full sync requires an injected legacy sync callable.",
            )
        metadata = dict(registry_config.get("metadata") or {})
        legacy_result = self.legacy_sync_callable(
            tenant_id=metadata.get("tenant_id") or registry_config.get("tenant_id"),
            client_id=metadata.get("client_id") or registry_config.get("client_id"),
            subscription_id=metadata.get("subscription_id") or registry_config.get("subscription_id"),
            secret_ref=metadata.get("secret_ref") or registry_config.get("secret_ref"),
            organization_id=registry_config.get("organization_id") or metadata.get("organization_id"),
        )
        return AzureProductionRuntimeAdapterResult(
            runtime_enabled=True,
            mode=ConnectorExecutionMode.FULL_SYNC,
            legacy_result=legacy_result,
            message="Azure production full sync executed through injected legacy sync seam.",
        )

    def _execute(
        self,
        registry_config: Mapping[str, Any],
        *,
        mode: ConnectorExecutionMode,
        requested_by: str | None = None,
    ) -> AzureRuntimeAdapterResult:
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
        return AzureRuntimeAdapterResult(
            connector_id=self.connector_id,
            mode=mode,
            execution_result=result,
            auth_config=auth_config,
            runtime_context=context,
        )

    def _ensure_registered(self) -> None:
        if self.registry.get_connector(self.connector_id) is None:
            self.registry.register_connector(_AzureRuntimeReferenceConnector)

    def _disabled(self, mode: ConnectorExecutionMode) -> AzureProductionRuntimeAdapterResult:
        return AzureProductionRuntimeAdapterResult(
            runtime_enabled=False,
            mode=mode,
            message="Azure E8 runtime path is disabled for this connector config.",
        )
