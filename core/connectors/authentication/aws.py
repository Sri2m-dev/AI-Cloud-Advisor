from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AwsAuthConfig:
    account_id: str
    role_arn: str
    external_id_ref: str = ""
    region: str = "us-east-1"

    def masked(self) -> dict[str, str]:
        return {
            "type": "aws",
            "account_id": self.account_id,
            "role_arn": self.role_arn,
            "external_id_ref": self.external_id_ref,
            "region": self.region,
        }
