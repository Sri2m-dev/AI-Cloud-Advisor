from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from connectors.aws.aws_credential_manager import AWSCredentialManager
from connectors.aws.aws_permission_validator import AWSPermissionValidator
from connectors.aws.aws_resource_discovery import AWSResourceDiscovery


class AWSProductionConnector:
    def __init__(self, role_arn=None, external_id=None, region="us-east-1"):
        self.credential_manager = AWSCredentialManager(role_arn, external_id, region)
        self.session = self.credential_manager.session()
        self.region = region

    def test_connection(self) -> dict[str, Any]:
        return self.credential_manager.test_connection()

    def validate_permissions(self) -> list[dict[str, Any]]:
        return AWSPermissionValidator(self.session, self.region).validate_all()

    def sync_accounts(self) -> list[dict[str, Any]]:
        sts = self.session.client("sts")
        account_id = sts.get_caller_identity().get("Account")

        return [
            {
                "cloud": "aws",
                "account_id": account_id,
                "account_name": f"aws-{account_id}",
                "status": "ACTIVE",
                "region": self.region,
            }
        ]

    def sync_costs(self, days: int = 30) -> list[dict[str, Any]]:
        ce = self.session.client("ce", region_name="us-east-1")
        end = date.today()
        start = end - timedelta(days=days)

        response = ce.get_cost_and_usage(
            TimePeriod={
                "Start": start.isoformat(),
                "End": end.isoformat(),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
        )

        rows = []
        for day in response.get("ResultsByTime", []):
            usage_date = day["TimePeriod"]["Start"]
            for group in day.get("Groups", []):
                service_name = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                rows.append(
                    {
                        "cloud": "aws",
                        "account_name": "aws-main",
                        "service_name": service_name,
                        "region": "global",
                        "usage_date": usage_date,
                        "cost": amount,
                        "currency": "USD",
                        "service_category": self._classify_service(service_name),
                    }
                )

        return rows

    def sync_resources(self) -> list[dict[str, Any]]:
        return AWSResourceDiscovery(self.session, self.region).discover_all()

    def sync_recommendations(self) -> list[dict[str, Any]]:
        recommendations = []
        try:
            co = self.session.client("compute-optimizer", region_name=self.region)
            response = co.get_ec2_instance_recommendations()

            for item in response.get("instanceRecommendations", []):
                recommendations.append(
                    {
                        "title": "AWS Compute Optimizer Recommendation",
                        "description": item.get("finding", "Optimization opportunity detected"),
                        "cloud": "aws",
                        "resource_id": item.get("instanceArn"),
                        "estimated_savings": 0,
                        "status": "OPEN",
                        "priority": "MEDIUM",
                        "source": "AWS Compute Optimizer",
                    }
                )
        except (BotoCoreError, ClientError):
            pass

        return recommendations

    def _classify_service(self, service_name: str) -> str:
        name = service_name.lower()

        if "ec2" in name or "compute" in name:
            return "Compute"
        if "s3" in name or "storage" in name:
            return "Storage"
        if "rds" in name or "database" in name:
            return "Database"
        if "cloudwatch" in name or "monitoring" in name:
            return "Monitoring"
        if "data transfer" in name or "vpc" in name:
            return "Networking"

        return "Other"
