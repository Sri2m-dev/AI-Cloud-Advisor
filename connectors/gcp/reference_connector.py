"""Framework-native GCP reference connector for E8.1.14.

This connector is intentionally narrow and mock-safe. It validates the
Universal Connector Framework path for GCP without calling live Google Cloud
APIs or requiring provider SDKs.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from connector_auth import AuthenticationManager, ConnectorAuthContext, ConnectorAuthType, ConnectorCredential, ConnectorCredentialRequest, CredentialProvider
from connector_normalization import CanonicalCloudResource, CanonicalCostRecord, CanonicalRecordType
from connector_persistence import PersistenceCanonicalPublisher
from connector_persistence.adapters.memory import MemoryCanonicalRepository
from connector_sdk import BaseConnector, ConnectorAuthConfig, ConnectorHealthStatus, ConnectorMetadata, ConnectorRecord, ConnectorRuntimeContext
from connector_secrets import EnvironmentSecretProvider, SecretProvider


class _GCPCredentialProvider(CredentialProvider):
    """Adapt ConnectorAuthConfig into auth-framework credentials."""

    def __init__(self, auth_config: ConnectorAuthConfig | None, secret_provider: SecretProvider | None = None) -> None:
        self.auth_config = auth_config
        self.secret_provider = secret_provider or EnvironmentSecretProvider()

    def load(self, request: ConnectorCredentialRequest) -> ConnectorCredential:
        metadata = dict(self.auth_config.metadata if self.auth_config else {})
        principal = metadata.get("service_account_email") or metadata.get("project_id")
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
                "project_id": self.auth_config.account_id if self.auth_config else None,
                **metadata,
            },
        )


class GCPReferenceConnector(BaseConnector):
    """First framework-native GCP connector skeleton.

    Extraction uses configured/mock datasets so the connector can be executed
    safely in local, CI, and demo environments.
    """

    metadata = ConnectorMetadata(
        connector_id="gcp.reference",
        name="GCP Reference Connector",
        provider="GCP",
        category="cloud",
        version="0.1.0",
        description="Reference GCP connector using mock-safe cost, Compute Engine, and Cloud Storage extraction.",
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
        mock_data: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(auth_config=auth_config, runtime_context=runtime_context)
        self.secret_provider = secret_provider or EnvironmentSecretProvider()
        self.auth_manager = auth_manager or AuthenticationManager(_GCPCredentialProvider(auth_config, self.secret_provider))
        self.publisher = publisher or PersistenceCanonicalPublisher(MemoryCanonicalRepository(), target="memory:data_fabric")
        self.mock_data = dict(mock_data or self.runtime_context.metadata.get("gcp_mock_data", {}) or {})
        self.auth_context: ConnectorAuthContext | None = None
        self._last_publish_count = 0

    def authenticate(self) -> bool:
        request = self._credential_request()
        self.auth_context = self.auth_manager.authenticate(request, cache_key=f"gcp.reference:{self.project_id}:{request.auth_type.value}")
        return self.auth_context.authenticated

    def discover(self) -> Mapping[str, Any]:
        return {
            "provider": "GCP",
            "project_id": self.project_id,
            "regions": self.regions,
            "datasets": ("cost_summary", "compute_inventory", "storage_inventory"),
            "mode": "mock_safe_reference",
        }

    def extract(self, *, incremental: bool = False, checkpoint: str | None = None) -> Sequence[Mapping[str, Any]]:
        records: list[Mapping[str, Any]] = []
        records.extend(self._cost_summary_records())
        records.extend(self._compute_records())
        records.extend(self._storage_records())
        return records

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
                    source_updated_at=record.get("source_updated_at"),
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
                errors.append(f"Unsupported GCP canonical type: {canonical.record_type}.")
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
            message="GCP reference connector is mock-safe and ready for runtime execution.",
            last_success_at=datetime.now(timezone.utc) if self._last_publish_count else None,
            metadata={
                "project_id": self.project_id,
                "regions": self.regions,
                "last_publish_count": self._last_publish_count,
                "mode": "reference_connector",
            },
        )

    @property
    def project_id(self) -> str:
        if self.auth_config and self.auth_config.account_id:
            return self.auth_config.account_id
        return str(self.runtime_context.metadata.get("gcp_project_id") or self.mock_data.get("project_id") or "nexora-reference-project")

    @property
    def regions(self) -> tuple[str, ...]:
        configured = None
        if self.auth_config:
            configured = self.auth_config.metadata.get("regions") or self.auth_config.metadata.get("region")
        configured = configured or self.runtime_context.metadata.get("gcp_regions") or self.mock_data.get("regions") or ("us-central1",)
        if isinstance(configured, str):
            return (configured,)
        return tuple(str(region) for region in configured)

    def _credential_request(self) -> ConnectorCredentialRequest:
        if self.auth_config is None:
            return ConnectorCredentialRequest(auth_type=ConnectorAuthType.ANONYMOUS)
        if self.auth_config.auth_type == "gcp_service_account":
            auth_type = ConnectorAuthType.API_KEY
        else:
            try:
                auth_type = ConnectorAuthType(self.auth_config.auth_type)
            except ValueError:
                auth_type = ConnectorAuthType.ANONYMOUS
        return ConnectorCredentialRequest(
            auth_type=auth_type,
            secret_ref=self.auth_config.secret_ref,
            scopes=self.auth_config.scopes,
            metadata={
                "provider": "GCP",
                "project_id": self.auth_config.account_id,
                **dict(self.auth_config.metadata),
            },
        )

    def _cost_summary_records(self) -> list[Mapping[str, Any]]:
        configured = self.mock_data.get("cost_summary")
        if configured:
            return [self._with_type(record, "cost_summary") for record in configured]
        return [
            {
                "record_type": "cost_summary",
                "source_id": f"gcp:{self.project_id}:cost:monthly:compute",
                "name": "GCP Monthly Compute Spend",
                "amount": 0.0,
                "currency": "USD",
                "billing_period": datetime.now(timezone.utc).strftime("%Y-%m"),
                "cost_category": "cloud_compute",
                "region": self.regions[0],
            }
        ]

    def _compute_records(self) -> list[Mapping[str, Any]]:
        configured = self.mock_data.get("compute_inventory")
        if configured:
            return [self._with_type(record, "compute_instance") for record in configured]
        return [
            {
                "record_type": "compute_instance",
                "source_id": f"gcp:{self.project_id}:{self.regions[0]}:compute:runtime-reference",
                "name": "runtime-reference",
                "region": self.regions[0],
                "resource_type": "compute_instance",
                "status": "discovered",
                "monthly_cost": 0.0,
                "tags": {"Source": "E8 Reference Connector", "Mode": "dry-run"},
            }
        ]

    def _storage_records(self) -> list[Mapping[str, Any]]:
        configured = self.mock_data.get("storage_inventory")
        if configured:
            return [self._with_type(record, "storage_bucket") for record in configured]
        return [
            {
                "record_type": "storage_bucket",
                "source_id": f"gcp:{self.project_id}:global:storage:nexora-reference-bucket",
                "name": "nexora-reference-bucket",
                "region": "global",
                "resource_type": "storage_bucket",
                "status": "discovered",
                "monthly_cost": 0.0,
                "tags": {"Source": "E8 Reference Connector", "Mode": "dry-run"},
            }
        ]

    def _with_type(self, record: Mapping[str, Any], record_type: str) -> Mapping[str, Any]:
        values = dict(record)
        values.setdefault("record_type", record_type)
        return values

    def _to_canonical(self, record: Mapping[str, Any]):
        record_type = record.get("record_type")
        if record_type == "cost_summary":
            return CanonicalCostRecord(
                record_id=f"gcp-cost:{record['source_id']}",
                record_type=CanonicalRecordType.COST_RECORD,
                source_system="gcp",
                source_id=str(record["source_id"]),
                name=str(record.get("name") or "GCP Cost Summary"),
                organization_id=self.runtime_context.organization_id,
                status="active",
                amount=float(record.get("amount") or 0.0),
                currency=str(record.get("currency") or "USD"),
                billing_period=record.get("billing_period"),
                cost_category=record.get("cost_category"),
                provider="GCP",
                provider_metadata={
                    "project_id": self.project_id,
                    "region": record.get("region"),
                    "source_dataset": "cost_summary",
                },
            )
        tags = {str(key): str(value) for key, value in dict(record.get("tags") or {}).items()}
        return CanonicalCloudResource(
            record_id=f"gcp-resource:{record['source_id']}",
            record_type=CanonicalRecordType.CLOUD_RESOURCE,
            source_system="gcp",
            source_id=str(record["source_id"]),
            name=str(record.get("name") or record["source_id"]),
            organization_id=self.runtime_context.organization_id,
            status=str(record.get("status") or "unknown"),
            tags=tags,
            provider="GCP",
            account_id=self.project_id,
            region=record.get("region"),
            resource_type=record.get("resource_type") or record_type,
            monthly_cost=float(record.get("monthly_cost") or 0.0),
            currency=str(record.get("currency") or "USD"),
            provider_metadata={
                "project_id": self.project_id,
                "source_dataset": "compute_inventory" if record_type == "compute_instance" else "storage_inventory",
            },
        )
