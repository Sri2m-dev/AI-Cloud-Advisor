"""Map legacy and registry connector configuration into E8 auth contracts."""

from __future__ import annotations

from typing import Any, Mapping

from connector_sdk import ConnectorAuthConfig


class AuthConfigMapper:
    """Build ConnectorAuthConfig values from legacy cloud and registry records."""

    @staticmethod
    def from_cloud_connection(record: Mapping[str, Any]) -> ConnectorAuthConfig:
        provider = AuthConfigMapper._provider(record)
        if provider == "AWS":
            return AuthConfigMapper.aws_from_values(
                account_id=record.get("account_id"),
                role_arn=record.get("role_arn"),
                external_id=record.get("external_id"),
                region=record.get("region"),
                metadata={"source": "cloud_connections", "account_name": record.get("account_name")},
            )
        if provider == "AZURE":
            return ConnectorAuthConfig(
                auth_type="azure_service_principal",
                tenant_id=record.get("tenant_id"),
                account_id=record.get("subscription_id") or record.get("account_id"),
                metadata={
                    "provider": "Azure",
                    "client_id": record.get("client_id") or record.get("account_id"),
                    "subscription_id": record.get("subscription_id"),
                    "source": "cloud_connections",
                },
            )
        if provider == "GCP":
            return ConnectorAuthConfig(
                auth_type="anonymous",
                account_id=record.get("project_id") or record.get("account_id"),
                metadata={"provider": "GCP", "project_id": record.get("project_id"), "source": "cloud_connections"},
            )
        return ConnectorAuthConfig(auth_type="anonymous", account_id=record.get("account_id"), metadata={"provider": provider})

    @staticmethod
    def from_registry_config(record: Mapping[str, Any]) -> ConnectorAuthConfig:
        provider = AuthConfigMapper._provider(record)
        metadata = dict(record.get("metadata") or {})
        if provider == "AWS":
            return AuthConfigMapper.aws_from_values(
                account_id=metadata.get("account_id") or record.get("account_id"),
                role_arn=metadata.get("role_arn") or record.get("role_arn"),
                external_id=metadata.get("external_id") or record.get("external_id"),
                region=metadata.get("region") or record.get("region"),
                metadata={"source": "connector_registry", **metadata},
            )
        if provider == "AZURE":
            return ConnectorAuthConfig(
                auth_type="azure_service_principal",
                tenant_id=metadata.get("tenant_id") or record.get("tenant_id"),
                account_id=metadata.get("subscription_id") or record.get("subscription_id"),
                metadata={"provider": "Azure", "source": "connector_registry", **metadata},
            )
        if provider == "GCP":
            return ConnectorAuthConfig(
                auth_type="anonymous",
                account_id=metadata.get("project_id") or record.get("project_id"),
                metadata={"provider": "GCP", "source": "connector_registry", **metadata},
            )
        return ConnectorAuthConfig(auth_type="anonymous", account_id=record.get("account_id"), metadata={"provider": provider, **metadata})

    @staticmethod
    def aws_from_values(
        *,
        account_id: str | None = None,
        role_arn: str | None = None,
        external_id: str | None = None,
        region: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ConnectorAuthConfig:
        values = dict(metadata or {})
        if role_arn:
            values["role_arn"] = role_arn
        if external_id:
            values["external_id"] = external_id
        if region:
            values["region"] = region
            values["regions"] = (region,)
        values["provider"] = "AWS"
        return ConnectorAuthConfig(
            auth_type="aws_assume_role" if role_arn else "anonymous",
            account_id=account_id,
            metadata=values,
        )

    @staticmethod
    def _provider(record: Mapping[str, Any]) -> str:
        return str(record.get("provider") or record.get("cloud_provider") or record.get("cloud") or "").upper()
