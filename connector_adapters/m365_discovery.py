"""Microsoft 365 and Entra ID discovery connector adapter for enterprise SaaS governance."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from connector_adapters.live_cost import ProviderFailure
from connector_sdk import BaseConnector, ConnectorMetadata, ConnectorRecord


def validate_m365_configuration(config: dict[str, str]) -> dict[str, str]:
    required = {"tenant_id", "client_id"}
    if set(config) != required:
        raise ProviderFailure("INVALID_CONFIGURATION")
    try:
        UUID(config["tenant_id"])
        UUID(config["client_id"])
    except (ValueError, TypeError):
        raise ProviderFailure("INVALID_CONFIGURATION") from None
    return dict(config)


class M365DiscoveryConnector(BaseConnector):
    metadata = ConnectorMetadata(
        "m365.discovery",
        "Microsoft 365 & Entra ID",
        "m365",
        "saas",
        version="1.1.0",
        supported_entities=(
            "identity_user",
            "application",
            "license_sku",
            "license_assignment",
        ),
    )

    def __init__(
        self,
        config: dict[str, str],
        credentials,
        *,
        credential_factory=None,
        client=None,
        now=None,
    ) -> None:
        super().__init__()
        self.config = validate_m365_configuration(config)
        self.credentials = credentials
        if credential_factory is None:
            from azure.identity import ClientSecretCredential
            credential_factory = ClientSecretCredential
        self.credential_factory = credential_factory
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.owns_client = client is None
        self.now = now or datetime.now(timezone.utc)
        self.account_id = self.config["tenant_id"]
        self.credential = None
        self.headers = None
        self.graph_url = "https://graph.microsoft.com/v1.0"

    def _request(self, method: str, url: str, **kwargs):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com":
            raise ProviderFailure("MALFORMED_RESPONSE")
        response = self.client.request(method, url, headers=self.headers, **kwargs)
        if response.status_code in (401, 403):
            raise ProviderFailure(
                "AUTHENTICATION" if response.status_code == 401 else "PERMISSION_DENIED"
            )
        if response.status_code == 429:
            raise ProviderFailure("RATE_LIMITED")
        if response.status_code != 200:
            raise ProviderFailure("PROVIDER_ERROR")
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except ValueError:
            raise ProviderFailure("MALFORMED_RESPONSE") from None

    def _iter_graph_collection(self, initial_url: str):
        url = initial_url
        seen_urls = set()
        pages = 0
        while url and pages < 100:
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "graph.microsoft.com"
                or url in seen_urls
            ):
                raise ProviderFailure("MALFORMED_RESPONSE")
            seen_urls.add(url)
            pages += 1
            payload = self._request("GET", url)
            items = payload.get("value", [])
            if not isinstance(items, list):
                raise ProviderFailure("MALFORMED_RESPONSE")
            for item in items:
                if isinstance(item, dict):
                    yield item
            url = payload.get("@odata.nextLink")

    def authenticate(self) -> bool:
        secret = self.credentials.resolve("client_secret")
        if not secret:
            raise ProviderFailure("AUTHENTICATION")
        try:
            self.credential = self.credential_factory(
                tenant_id=self.config["tenant_id"],
                client_id=self.config["client_id"],
                client_secret=secret,
            )
            token = self.credential.get_token("https://graph.microsoft.com/.default")
            self.headers = {"Authorization": f"Bearer {token.token}"}
            org_res = self._request("GET", f"{self.graph_url}/organization")
            org_list = org_res.get("value", [])
            if not org_list or str(org_list[0].get("id", "")).lower() != self.account_id.lower():
                raise ProviderFailure("TENANT_MISMATCH")
            return True
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure("AUTHENTICATION") from None

    def extract(self, *, incremental=False, checkpoint=None) -> list[dict]:
        if self.headers is None:
            raise ProviderFailure("AUTHENTICATION")

        records: list[dict] = []

        # 1. Discover Subscribed SKUs (Licenses) with pagination support
        skus_url = f"{self.graph_url}/subscribedSkus"
        for sku in self._iter_graph_collection(skus_url):
            records.append({
                "entity_type": "license_sku",
                "sku_id": sku.get("skuId"),
                "sku_part_number": sku.get("skuPartNumber", "UNKNOWN"),
                "total_units": sku.get("prepaidUnits", {}).get("enabled", 0),
                "consumed_units": sku.get("consumedUnits", 0),
                "suspended_units": sku.get("prepaidUnits", {}).get("suspended", 0),
            })

        # 2. Discover Users and License Assignments with pagination support
        users_fields = "id,userPrincipalName,displayName,accountEnabled,assignedLicenses"
        users_url = f"{self.graph_url}/users?$select={users_fields}"
        for user in self._iter_graph_collection(users_url):
            user_id = user.get("id")
            upn = user.get("userPrincipalName", "")
            display_name = user.get("displayName", "")
            enabled = bool(user.get("accountEnabled", True))

            records.append({
                "entity_type": "identity_user",
                "external_id": user_id,
                "user_principal_name": upn,
                "display_name": display_name,
                "account_enabled": enabled,
            })

            for lic in user.get("assignedLicenses", []):
                sku_id = lic.get("skuId")
                if sku_id:
                    records.append({
                        "entity_type": "license_assignment",
                        "user_id": user_id,
                        "user_principal_name": upn,
                        "sku_id": sku_id,
                        "assigned": True,
                        "actively_used": None,
                    })

        # 3. Discover Enterprise Applications / Service Principals (Never swallowed)
        sp_fields = "id,appId,displayName,publisherName,accountEnabled"
        sp_url = f"{self.graph_url}/servicePrincipals?$select={sp_fields}&$top=100"
        for sp in self._iter_graph_collection(sp_url):
            publisher_raw = sp.get("publisherName")
            publisher_clean = str(publisher_raw).strip() if publisher_raw else None
            records.append({
                "entity_type": "application",
                "external_id": sp.get("id"),
                "app_id": sp.get("appId"),
                "display_name": sp.get("displayName", "Unnamed Application"),
                "publisher": publisher_clean or "UNKNOWN",
                "account_enabled": bool(sp.get("accountEnabled", True)),
            })

        return records

    def normalize(self, records: list[dict]) -> tuple[ConnectorRecord, ...]:
        normalized: list[ConnectorRecord] = []
        for r in records:
            etype = r.get("entity_type")
            if etype == "license_sku":
                sku_id = str(r["sku_id"])
                key = hashlib.sha256(f"m365:sku:{self.account_id}:{sku_id}".encode()).hexdigest()
                payload = {
                    "provider": "m365",
                    "tenant_id": self.account_id,
                    "sku_id": sku_id,
                    "sku_part_number": r["sku_part_number"],
                    "total_units": r["total_units"],
                    "consumed_units": r["consumed_units"],
                    "unassigned_units": max(0, r["total_units"] - r["consumed_units"]),
                    "cost": "UNKNOWN",
                }
                normalized.append(
                    ConnectorRecord(key, "license_sku", {"license_sku": payload}, self.now)
                )

            elif etype == "identity_user":
                user_id = str(r["external_id"])
                key = hashlib.sha256(f"m365:user:{self.account_id}:{user_id}".encode()).hexdigest()
                payload = {
                    "provider": "m365",
                    "tenant_id": self.account_id,
                    "user_id": user_id,
                    "user_principal_name": r["user_principal_name"],
                    "display_name": r["display_name"],
                    "account_enabled": r["account_enabled"],
                }
                normalized.append(
                    ConnectorRecord(key, "identity_user", {"identity_user": payload}, self.now)
                )

            elif etype == "license_assignment":
                user_id = str(r["user_id"])
                sku_id = str(r["sku_id"])
                key = hashlib.sha256(
                    f"m365:assign:{self.account_id}:{user_id}:{sku_id}".encode()
                ).hexdigest()
                payload = {
                    "provider": "m365",
                    "tenant_id": self.account_id,
                    "user_id": user_id,
                    "user_principal_name": r["user_principal_name"],
                    "sku_id": sku_id,
                    "assigned": True,
                    "actively_used": False,
                    "utilization": "UNKNOWN",
                }
                normalized.append(
                    ConnectorRecord(
                        key,
                        "license_assignment",
                        {"license_assignment": payload},
                        self.now,
                    )
                )

            elif etype == "application":
                app_id = str(r["external_id"])
                key = hashlib.sha256(f"m365:app:{self.account_id}:{app_id}".encode()).hexdigest()
                payload = {
                    "provider": "m365",
                    "tenant_id": self.account_id,
                    "app_id": r.get("app_id"),
                    "external_id": app_id,
                    "display_name": r["display_name"],
                    "publisher": r.get("publisher") or "UNKNOWN",
                    "account_enabled": r["account_enabled"],
                    "cost": "UNKNOWN",
                }
                normalized.append(
                    ConnectorRecord(key, "application", {"application": payload}, self.now)
                )

        return tuple(normalized)

    def discover(self) -> dict[str, Any]:
        return {"account_id": self.account_id, "capabilities": ("m365_discovery",)}

    def publish(self, records):
        raise ProviderFailure("GOVERNED_HANDOFF_REQUIRED")

    def validate(self, records: tuple[ConnectorRecord, ...]) -> tuple[bool, tuple[str, ...]]:
        valid = all(isinstance(r, ConnectorRecord) for r in records)
        return valid, () if valid else ("Invalid normalized M365 record",)

    def close(self) -> None:
        if self.credential is not None:
            try:
                self.credential.close()
            except Exception:
                pass
        self.headers = None
        if self.owns_client:
            try:
                self.client.close()
            except Exception:
                pass
