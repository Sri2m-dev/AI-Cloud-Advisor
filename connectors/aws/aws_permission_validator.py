from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable

from botocore.exceptions import BotoCoreError, ClientError


class AWSPermissionValidator:
    def __init__(self, session, region: str = "us-east-1"):
        self.session = session
        self.region = region

    def validate_all(self) -> list[dict[str, Any]]:
        checks: list[tuple[str, str, Callable[[], None]]] = [
            ("sts:GetCallerIdentity", "Account identity validation unavailable", self._check_sts_identity),
            ("ce:GetCostAndUsage", "Cost Explorer sync unavailable", self._check_cost_explorer),
            ("ec2:DescribeInstances", "EC2 discovery unavailable", self._check_ec2_instances),
            ("ec2:DescribeVpcs", "VPC discovery unavailable", self._check_vpcs),
            ("s3:ListAllMyBuckets", "S3 discovery unavailable", self._check_s3_buckets),
            ("rds:DescribeDBInstances", "RDS discovery unavailable", self._check_rds_instances),
            ("lambda:ListFunctions", "Lambda discovery unavailable", self._check_lambda_functions),
            ("eks:ListClusters", "EKS discovery unavailable", self._check_eks_clusters),
        ]
        return [self._run_check(permission, impact, check) for permission, impact, check in checks]

    def _run_check(self, permission: str, impact: str, check: Callable[[], None]) -> dict[str, Any]:
        try:
            check()
            return {
                "permission": permission,
                "status": "PASSED",
                "error": "",
                "impact": "Ready",
            }
        except (BotoCoreError, ClientError) as exc:
            return {
                "permission": permission,
                "status": "FAILED",
                "error": str(exc),
                "impact": impact,
            }

    def _check_sts_identity(self) -> None:
        self.session.client("sts", region_name=self.region).get_caller_identity()

    def _check_cost_explorer(self) -> None:
        end = date.today()
        start = end - timedelta(days=1)
        self.session.client("ce", region_name="us-east-1").get_cost_and_usage(
            TimePeriod={
                "Start": start.isoformat(),
                "End": end.isoformat(),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )

    def _check_ec2_instances(self) -> None:
        self.session.client("ec2", region_name=self.region).describe_instances(MaxResults=5)

    def _check_vpcs(self) -> None:
        self.session.client("ec2", region_name=self.region).describe_vpcs(MaxResults=5)

    def _check_s3_buckets(self) -> None:
        self.session.client("s3", region_name=self.region).list_buckets()

    def _check_rds_instances(self) -> None:
        self.session.client("rds", region_name=self.region).describe_db_instances(MaxRecords=20)

    def _check_lambda_functions(self) -> None:
        self.session.client("lambda", region_name=self.region).list_functions(MaxItems=10)

    def _check_eks_clusters(self) -> None:
        self.session.client("eks", region_name=self.region).list_clusters(maxResults=10)

