"""AWS/Azure billing adapters for the shared connector SDK and SourceFact handoff."""

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from connector_sdk import BaseConnector, ConnectorMetadata, ConnectorRecord


class ProviderFailure(ValueError):
    def __init__(self, category):
        self.category = category
        super().__init__(f"{category}: source operation failed; check connection configuration")


def failure_category(error):
    if isinstance(error, ProviderFailure):
        return error.category
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "TIMEOUT"
    code = getattr(error, "response", {})
    if isinstance(code, dict):
        code = code.get("Error", {}).get("Code", "")
        if code in {"Throttling", "ThrottlingException", "LimitExceededException"}:
            return "RATE_LIMITED"
        if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
            return "PERMISSION_DENIED"
        if code in {"ExpiredToken", "InvalidClientTokenId", "UnrecognizedClientException"}:
            return "AUTHENTICATION"
    if type(error).__name__ in {"NoCredentialsError", "ClientAuthenticationError"}:
        return "AUTHENTICATION"
    if type(error).__name__ in {"ReadTimeoutError", "ConnectTimeoutError"}:
        return "TIMEOUT"
    return "PROVIDER_ERROR"


def validate_configuration(provider, config):
    """Only nonsecret, typed configuration may enter durable public metadata."""
    required = {
        "aws": {"account_id", "role_arn", "region"},
        "azure": {"tenant_id", "subscription_id", "client_id"},
        "m365": {"tenant_id", "client_id"},
    }
    if provider not in required or set(config) != required[provider]:
        raise ProviderFailure("INVALID_CONFIGURATION")
    if not all(isinstance(v, str) and v.strip() == v and v for v in config.values()):
        raise ProviderFailure("INVALID_CONFIGURATION")
    if provider == "aws":
        if not re.fullmatch(r"[0-9]{12}", config["account_id"]):
            raise ProviderFailure("INVALID_CONFIGURATION")
        if not re.fullmatch(
            rf"arn:aws:iam::{config['account_id']}:role/[A-Za-z0-9+=,.@_/-]+",
            config["role_arn"],
        ) or not re.fullmatch(r"[a-z]{2}-[a-z]+-\d", config["region"]):
            raise ProviderFailure("INVALID_CONFIGURATION")
    else:
        try:
            for value in config.values():
                UUID(value)
        except ValueError:
            raise ProviderFailure("INVALID_CONFIGURATION") from None
    return dict(config)


class LiveCostConnector(BaseConnector):
    """Provider-specific reads, common normalization, no dashboard writes."""

    def __init__(self, config, credentials, *, now=None):
        super().__init__()
        self.config, self.credentials = config, credentials
        self.now = now or datetime.now(timezone.utc)

    def discover(self):
        return {"account_id": self.account_id, "capabilities": ("cloud_cost",)}

    def normalize(self, records):
        normalized, identities = [], set()
        for row in records:
            try:
                amount = Decimal(str(row["amount"]))
                start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
                if (
                    not amount.is_finite() or end <= start
                    or not isinstance(row["service"], str) or not row["service"].strip()
                    or not re.fullmatch(r"[A-Z]{3}", row["currency"])
                ):
                    raise ValueError()
                identity = (self.metadata.provider, self.account_id, str(start), str(end),
                            row["service"], row["currency"])
                key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
                if key in identities:
                    raise ValueError()
                identities.add(key)
                value = {
                    "provider": self.metadata.provider, "account_id": self.account_id,
                    "period_start": str(start), "period_end": str(end),
                    "service": row["service"], "amount": str(amount),
                    "currency": row["currency"], "estimated": bool(row.get("estimated", False)),
                }
                normalized.append(ConnectorRecord(
                    key, "cost_record", {"subject_id": key, "cloud_cost": value}, self.now,
                ))
            except (KeyError, ValueError, TypeError, ArithmeticError):
                raise ProviderFailure("MALFORMED_RESPONSE") from None
        return tuple(normalized)

    def validate(self, records):
        valid = all(isinstance(r, ConnectorRecord) and "cloud_cost" in r.payload for r in records)
        return valid, () if valid else ("Invalid normalized cost evidence",)

    def publish(self, records):
        raise ProviderFailure("GOVERNED_HANDOFF_REQUIRED")

    def close(self):
        pass


class AWSLiveCostConnector(LiveCostConnector):
    metadata = ConnectorMetadata("aws.live_cost", "AWS Cost Explorer", "aws", "cloud",
                                 version="1.1.0", supported_entities=("cost_record",))

    def __init__(self, config, credentials, *, session_factory=None, now=None):
        super().__init__(validate_configuration("aws", config), credentials, now=now)
        if session_factory is None:
            import boto3
            session_factory = boto3.Session
        self.session_factory = session_factory
        self.account_id = config["account_id"]
        self.session = None

    def authenticate(self):
        from botocore.config import Config
        self.client_config = Config(connect_timeout=10, read_timeout=30,
                                    retries={"mode": "standard", "max_attempts": 2})
        base = self.session_factory(region_name=self.config["region"])
        args = {"RoleArn": self.config["role_arn"], "RoleSessionName": "nexora-billing"}
        external_id = self.credentials.resolve("external_id")
        if external_id:
            args["ExternalId"] = external_id
        result = base.client("sts", config=self.client_config).assume_role(**args)
        try:
            temporary = result["Credentials"]
            self.session = self.session_factory(
                aws_access_key_id=temporary["AccessKeyId"],
                aws_secret_access_key=temporary["SecretAccessKey"],
                aws_session_token=temporary["SessionToken"], region_name=self.config["region"],
            )
            identity = self.session.client("sts", config=self.client_config).get_caller_identity()
        except (KeyError, TypeError):
            raise ProviderFailure("MALFORMED_RESPONSE") from None
        if identity.get("Account") != self.account_id:
            raise ProviderFailure("ACCOUNT_MISMATCH")
        return True

    def extract(self, *, incremental=False, checkpoint=None):
        if self.session is None:
            raise ProviderFailure("AUTHENTICATION")
        client = self.session.client("ce", region_name="us-east-1", config=self.client_config)
        end = self.now.date()
        args = {
            "TimePeriod": {"Start": str(end - timedelta(days=30)), "End": str(end)},
            "Granularity": "DAILY", "Metrics": ["UnblendedCost"],
            "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
            "Filter": {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [self.account_id]}},
        }
        records, seen = [], set()
        for _ in range(100):
            payload = client.get_cost_and_usage(**args)
            try:
                periods = payload["ResultsByTime"]
                if not isinstance(periods, list):
                    raise ValueError()
                for period in periods:
                    for group in period["Groups"]:
                        metric = group["Metrics"]["UnblendedCost"]
                        if len(group["Keys"]) != 1:
                            raise ValueError()
                        records.append({"start": period["TimePeriod"]["Start"],
                                        "end": period["TimePeriod"]["End"],
                                        "service": group["Keys"][0], "amount": metric["Amount"],
                                        "currency": metric["Unit"],
                                        "estimated": period.get("Estimated", False)})
                token = payload.get("NextPageToken")
                if not token:
                    return records
                if not isinstance(token, str) or token in seen:
                    raise ValueError()
                seen.add(token)
                args["NextPageToken"] = token
            except (KeyError, TypeError, ValueError):
                raise ProviderFailure("MALFORMED_RESPONSE") from None
        raise ProviderFailure("INCOMPLETE_RESPONSE")


class AzureLiveCostConnector(LiveCostConnector):
    metadata = ConnectorMetadata("azure.live_cost", "Azure Cost Management", "azure", "cloud",
                                 version="1.1.0", supported_entities=("cost_record",))

    def __init__(self, config, credentials, *, credential_factory=None, client=None, now=None):
        super().__init__(validate_configuration("azure", config), credentials, now=now)
        if credential_factory is None:
            from azure.identity import ClientSecretCredential
            credential_factory = ClientSecretCredential
        self.credential_factory = credential_factory
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.owns_client = client is None
        self.account_id = config["subscription_id"]
        self.credential = None
        self.headers = None
        self.scope_url = f"https://management.azure.com/subscriptions/{self.account_id}"

    def _request(self, method, url, **kwargs):
        response = self.client.request(method, url, headers=self.headers, **kwargs)
        if response.status_code in (401, 403):
            raise ProviderFailure("AUTHENTICATION" if response.status_code == 401
                                  else "PERMISSION_DENIED")
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

    def authenticate(self):
        secret = self.credentials.resolve("client_secret")
        if not secret:
            raise ProviderFailure("AUTHENTICATION")
        self.credential = self.credential_factory(
            tenant_id=self.config["tenant_id"], client_id=self.config["client_id"],
            client_secret=secret,
        )
        token = self.credential.get_token("https://management.azure.com/.default")
        self.headers = {"Authorization": f"Bearer {token.token}"}
        subscription = self._request("GET", self.scope_url + "?api-version=2022-12-01")
        if (
            subscription.get("subscriptionId", "").lower() != self.account_id.lower()
            or subscription.get("tenantId", "").lower() != self.config["tenant_id"].lower()
            or subscription.get("state") != "Enabled"
        ):
            raise ProviderFailure("SUBSCRIPTION_MISMATCH")
        return True

    def extract(self, *, incremental=False, checkpoint=None):
        if self.headers is None:
            raise ProviderFailure("AUTHENTICATION")
        query_url = self.scope_url + "/providers/Microsoft.CostManagement/query"
        url = query_url + "?api-version=2025-03-01"
        end = self.now.date()
        body = {
            "type": "ActualCost", "timeframe": "Custom",
            "timePeriod": {"from": str(end - timedelta(days=30)),
                           "to": str(end - timedelta(days=1)) + "T23:59:59Z"},
            "dataset": {"granularity": "Daily",
                        "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
                        "grouping": [{"type": "Dimension", "name": "ServiceName"}]},
        }
        records, seen = [], set()
        for _ in range(100):
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.netloc != "management.azure.com"
                    or parsed.path.lower() != urlsplit(query_url).path.lower() or parsed.fragment
                    or url in seen):
                raise ProviderFailure("MALFORMED_RESPONSE")
            seen.add(url)
            payload = self._request("POST", url, json=body)
            try:
                properties = payload["properties"]
                columns = [column["name"] for column in properties["columns"]]
                if len(columns) != len(set(columns)) or not isinstance(properties["rows"], list):
                    raise ValueError()
                if not {"PreTaxCost", "UsageDate", "ServiceName", "Currency"} <= set(columns):
                    raise ValueError()
                for values in properties["rows"]:
                    if len(values) != len(columns):
                        raise ValueError()
                    row = dict(zip(columns, values, strict=True))
                    day = datetime.strptime(str(row["UsageDate"]), "%Y%m%d").date()
                    records.append({"start": str(day), "end": str(day + timedelta(days=1)),
                                    "service": row["ServiceName"], "amount": row["PreTaxCost"],
                                    "currency": row["Currency"]})
                url = properties.get("nextLink")
                if not url:
                    return records
                if not isinstance(url, str):
                    raise ValueError()
            except (KeyError, ValueError, TypeError):
                raise ProviderFailure("MALFORMED_RESPONSE") from None
        raise ProviderFailure("INCOMPLETE_RESPONSE")

    def close(self):
        if self.credential is not None:
            self.credential.close()
        self.headers = None
        if self.owns_client:
            self.client.close()
