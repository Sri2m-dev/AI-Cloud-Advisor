from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class AWSCredentialManager:
    def __init__(
        self,
        role_arn: str | None = None,
        external_id: str | None = None,
        region: str = "us-east-1",
    ):
        self.role_arn = role_arn
        self.external_id = external_id
        self.region = region

    def session(self):
        if not self.role_arn:
            return boto3.Session(region_name=self.region)

        sts = boto3.client("sts", region_name=self.region)
        params: dict[str, Any] = {
            "RoleArn": self.role_arn,
            "RoleSessionName": "nexora-aws-connector",
        }

        if self.external_id:
            params["ExternalId"] = self.external_id

        credentials = sts.assume_role(**params)["Credentials"]

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
            return {
                "status": "CONNECTED",
                "account_id": identity.get("Account"),
                "arn": identity.get("Arn"),
            }
        except (BotoCoreError, ClientError) as exc:
            return {
                "status": "FAILED",
                "error": str(exc),
            }

