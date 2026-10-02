"""AWS runtime identity session provider."""

from __future__ import annotations

import boto3


class AWSRuntimeSessionProvider:
    """Builds the AWS bootstrap session used before customer AssumeRole."""

    DEFAULT_CHAIN = "default_chain"
    WEB_IDENTITY = "web_identity"

    def __init__(
        self,
        mode: str = DEFAULT_CHAIN,
        session_factory=None,
        *,
        bootstrap_role_arn: str | None = None,
        web_identity_token: str | None = None,
        session_name: str = "nexora-runtime",
        sts_client_factory=None,
    ):
        self.mode = mode
        self.session_factory = session_factory or boto3.Session
        self.bootstrap_role_arn = bootstrap_role_arn
        self.web_identity_token = web_identity_token
        self.session_name = session_name
        self.sts_client_factory = sts_client_factory or boto3.client

    def session(self, *, region: str = "us-east-1"):
        if self.mode == self.DEFAULT_CHAIN:
            return self.session_factory(region_name=region)

        if self.mode == self.WEB_IDENTITY:
            if not self.bootstrap_role_arn:
                raise ValueError(
                    "AWS web identity mode requires bootstrap_role_arn."
                )

            if not self.web_identity_token:
                raise ValueError(
                    "AWS web identity mode requires web_identity_token."
                )

            sts = self.sts_client_factory(region_name=region)
            response = sts.assume_role_with_web_identity(
                RoleArn=self.bootstrap_role_arn,
                RoleSessionName=self.session_name,
                WebIdentityToken=self.web_identity_token,
            )
            credentials = response["Credentials"]

            return self.session_factory(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=region,
            )

        raise ValueError(
            f"Unsupported AWS runtime identity mode: {self.mode}"
        )