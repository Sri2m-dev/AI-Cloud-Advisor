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
            metadata = AuthConfigMapper._azure_metadata_from_values(
                source="cloud_connections",
                client_id=record.get("client_id") or record.get("account_id"),
                subscription_id=record.get("subscription_id") or record.get("account_id"),
                tenant_id=record.get("tenant_id"),
                values=record,
            )
            return ConnectorAuthConfig(
                auth_type="azure_service_principal",
                tenant_id=record.get("tenant_id"),
                account_id=record.get("subscription_id") or record.get("account_id"),
                secret_ref=metadata.get("secret_ref"),
                metadata=metadata,
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
            metadata = AuthConfigMapper._azure_metadata_from_values(
                source="connector_registry",
                client_id=metadata.get("client_id") or record.get("client_id"),
                subscription_id=metadata.get("subscription_id") or record.get("subscription_id"),
                tenant_id=metadata.get("tenant_id") or record.get("tenant_id"),
                values={**dict(record), **metadata},
            )
            return ConnectorAuthConfig(
                auth_type="azure_service_principal",
                tenant_id=metadata.get("tenant_id"),
                account_id=metadata.get("subscription_id"),
                secret_ref=metadata.get("secret_ref"),
                metadata=metadata,
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

    @staticmethod
    def _azure_metadata_from_values(
        *,
        source: str,
        client_id: str | None,
        subscription_id: str | None,
        tenant_id: str | None,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return Azure metadata sanitized for ConnectorAuthConfig.

        Legacy Azure onboarding may carry `client_secret` inline. Runtime auth
        contracts must carry only a secret reference, so this mapper creates a
        deterministic reference when an inline secret is present and strips the
        direct value from metadata.
        """

        raw = dict(values or {})
        secret_ref = raw.get("secret_ref") or raw.get("client_secret_ref")
        direct_secret_present = bool(raw.get("client_secret"))
        if not secret_ref and direct_secret_present:
            secret_ref = AuthConfigMapper._azure_secret_ref(
                subscription_id=subscription_id,
                client_id=client_id,
                tenant_id=tenant_id,
            )

        sanitized = {
            key: value
            for key, value in raw.items()
            if key not in {"client_secret", "client_secret_ref", "secret"}
        }
        sanitized.update(
            {
                "provider": "Azure",
                "source": source,
                "tenant_id": tenant_id,
                "client_id": client_id,
                "subscription_id": subscription_id,
            }
        )
        if secret_ref:
            sanitized["secret_ref"] = secret_ref
        if direct_secret_present:
            sanitized["client_secret_migrated_to_secret_ref"] = True
        return sanitized

    @staticmethod
    def _azure_secret_ref(*, subscription_id: str | None, client_id: str | None, tenant_id: str | None) -> str:
        identifier = subscription_id or client_id or tenant_id or "default"
        safe_identifier = str(identifier).replace(" ", "-").lower()
        return f"azure:{safe_identifier}:client_secret"
