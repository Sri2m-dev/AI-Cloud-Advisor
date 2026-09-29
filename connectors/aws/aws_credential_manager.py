from __future__ import annotations

import re
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

_ROLE_ARN_PATTERN = re.compile(r"^arn:(aws|aws-us-gov|aws-cn):iam::([0-9]{12}):role/(.+)$")


class AWSConnectedModeConfigurationError(ValueError):
    """Raised when the commercial AWS AssumeRole contract is invalid."""


def validate_role_arn(role_arn: str | None) -> tuple[str, str]:
    value = (role_arn or "").strip()
    match = _ROLE_ARN_PATTERN.fullmatch(value)

    if not match:
        raise AWSConnectedModeConfigurationError(
            "A valid AWS IAM Role ARN is required for Connected Mode."
        )

    role_path = match.group(3)

    if not role_path or role_path.endswith("/"):
        raise AWSConnectedModeConfigurationError(
            "A valid AWS IAM Role ARN is required for Connected Mode."
        )

    return value, match.group(2)


def validate_external_id(external_id: str | None) -> str:
    value = (external_id or "").strip()

    if len(value) < 20 or len(value) > 256:
        raise AWSConnectedModeConfigurationError(
            "A Nexora-generated External ID is required for Connected Mode."
        )

    if any(ch.isspace() for ch in value):
        raise AWSConnectedModeConfigurationError("The AWS External ID is invalid.")

    return value


def safe_aws_error(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {}) if exc.response else {}
        code = str(error.get("Code") or "AWS_ERROR")

        safe_messages = {
            "AccessDenied": "AWS denied the requested read-only operation.",
            "AccessDeniedException": "AWS denied the requested read-only operation.",
            "InvalidClientTokenId": "AWS could not authenticate the Nexora AWS principal.",
            "ExpiredToken": "The temporary AWS session expired.",
            "ExpiredTokenException": "The temporary AWS session expired.",
            "ValidationError": "AWS rejected the Connected Mode configuration.",
            "MalformedPolicyDocument": "AWS rejected the IAM configuration.",
        }

        return safe_messages.get(
            code,
            f"AWS request failed ({code}).",
        )

    if isinstance(exc, BotoCoreError):
        return "AWS connection could not be completed."

    return "AWS Connected Mode operation failed."


class AWSCredentialManager:
    def __init__(
        self,
        role_arn: str | None = None,
        external_id: str | None = None,
        region: str = "us-east-1",
        *,
        require_assume_role: bool = False,
    ):
        self.role_arn = role_arn
        self.external_id = external_id
        self.region = region
        self.require_assume_role = require_assume_role

    def _assume_role_parameters(self) -> dict[str, Any]:
        role_arn, _ = validate_role_arn(self.role_arn)
        external_id = validate_external_id(self.external_id)

        return {
            "RoleArn": role_arn,
            "RoleSessionName": "nexora-aws-connector",
            "ExternalId": external_id,
            "DurationSeconds": 3600,
        }

    def session(self):
        if not self.role_arn:
            if self.require_assume_role:
                raise AWSConnectedModeConfigurationError(
                    "AWS Connected Mode requires a customer IAM Role ARN."
                )

            # Retained only for non-commercial/internal compatibility.
            return boto3.Session(region_name=self.region)

        params = self._assume_role_parameters()

        sts = boto3.client("sts", region_name=self.region)
        response = sts.assume_role(**params)
        credentials = response["Credentials"]

        # Temporary STS credentials are used only to construct the in-memory
        # boto3 session. They are never returned by the connector contract.
        return boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=self.region,
        )

    def test_connection(self) -> dict[str, Any]:
        try:
            client = self.session().client("sts")
            identity = client.get_caller_identity()

            _, expected_account = validate_role_arn(self.role_arn)

            actual_account = str(identity.get("Account") or "")

            if actual_account != expected_account:
                return {
                    "status": "FAILED",
                    "error": (
                        "The assumed AWS identity does not match the "
                        "account in the configured Role ARN."
                    ),
                }

            return {
                "status": "CONNECTED",
                "account_id": actual_account,
                "arn": identity.get("Arn"),
            }

        except AWSConnectedModeConfigurationError as exc:
            return {
                "status": "FAILED",
                "error": str(exc),
            }

        except (BotoCoreError, ClientError) as exc:
            return {
                "status": "FAILED",
                "error": safe_aws_error(exc),
            }
