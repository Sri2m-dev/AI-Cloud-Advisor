from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


NEXORA_AWS_ACCOUNT_ARN = "<NEXORA_AWS_ACCOUNT_ARN>"
CUSTOMER_EXTERNAL_ID = "<CUSTOMER_EXTERNAL_ID>"


IAM_POLICY_TEMPLATE: dict[str, Any] = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "NexoraCostAccess",
            "Effect": "Allow",
            "Action": [
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
                "ce:GetDimensionValues",
                "ce:GetReservationUtilization",
                "ce:GetSavingsPlansUtilization",
            ],
            "Resource": "*",
        },
        {
            "Sid": "NexoraDiscoveryAccess",
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity",
                "ec2:DescribeInstances",
                "ec2:DescribeVpcs",
                "ec2:DescribeVolumes",
                "ec2:DescribeSnapshots",
                "ec2:DescribeSecurityGroups",
                "s3:ListAllMyBuckets",
                "s3:GetBucketLocation",
                "rds:DescribeDBInstances",
                "lambda:ListFunctions",
                "eks:ListClusters",
                "eks:DescribeCluster",
                "compute-optimizer:GetEC2InstanceRecommendations",
                "compute-optimizer:GetEBSVolumeRecommendations",
                "trustedadvisor:DescribeChecks",
                "trustedadvisor:DescribeCheckResult",
            ],
            "Resource": "*",
        },
    ],
}


TRUST_POLICY_TEMPLATE: dict[str, Any] = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": NEXORA_AWS_ACCOUNT_ARN,
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalId": CUSTOMER_EXTERNAL_ID,
                }
            },
        }
    ],
}


class AWSOnboardingTemplateService:
    @staticmethod
    def get_iam_policy() -> dict[str, Any]:
        return deepcopy(IAM_POLICY_TEMPLATE)

    @staticmethod
    def get_trust_policy(
        nexora_aws_account_arn: str = NEXORA_AWS_ACCOUNT_ARN,
        external_id: str = CUSTOMER_EXTERNAL_ID,
    ) -> dict[str, Any]:
        policy = deepcopy(TRUST_POLICY_TEMPLATE)
        policy["Statement"][0]["Principal"]["AWS"] = nexora_aws_account_arn or NEXORA_AWS_ACCOUNT_ARN
        policy["Statement"][0]["Condition"]["StringEquals"]["sts:ExternalId"] = external_id or CUSTOMER_EXTERNAL_ID
        return policy

    @staticmethod
    def to_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, indent=2)

    @staticmethod
    def get_permission_rows() -> list[dict[str, str]]:
        rows = []
        impact_map = {
            "sts:GetCallerIdentity": "Identity and account validation",
            "ce:GetCostAndUsage": "Cost Explorer sync",
            "ce:GetCostForecast": "Forecast enrichment",
            "ce:GetDimensionValues": "Cost dimension normalization",
            "ce:GetReservationUtilization": "Reservation utilization insight",
            "ce:GetSavingsPlansUtilization": "Savings Plans utilization insight",
            "ec2:DescribeInstances": "EC2 resource discovery",
            "ec2:DescribeVpcs": "VPC resource discovery",
            "ec2:DescribeVolumes": "EBS resource discovery",
            "ec2:DescribeSnapshots": "Snapshot inventory",
            "ec2:DescribeSecurityGroups": "Security group inventory",
            "s3:ListAllMyBuckets": "S3 bucket discovery",
            "s3:GetBucketLocation": "S3 region attribution",
            "rds:DescribeDBInstances": "RDS resource discovery",
            "lambda:ListFunctions": "Lambda resource discovery",
            "eks:ListClusters": "EKS cluster discovery",
            "eks:DescribeCluster": "EKS cluster detail discovery",
            "compute-optimizer:GetEC2InstanceRecommendations": "EC2 optimization recommendations",
            "compute-optimizer:GetEBSVolumeRecommendations": "EBS optimization recommendations",
            "trustedadvisor:DescribeChecks": "Trusted Advisor check catalog",
            "trustedadvisor:DescribeCheckResult": "Trusted Advisor findings",
        }
        for statement in IAM_POLICY_TEMPLATE["Statement"]:
            for action in statement["Action"]:
                rows.append(
                    {
                        "Permission": action,
                        "Access Group": statement["Sid"],
                        "Impact": impact_map.get(action, "AWS connector capability"),
                    }
                )
        return rows

    @staticmethod
    def get_setup_steps() -> list[dict[str, str]]:
        return [
            {"Step": "1", "Action": "Create IAM role", "Detail": "Create a customer-managed role in the AWS account that Nexora will read."},
            {"Step": "2", "Action": "Attach policy", "Detail": "Attach the Nexora IAM permissions policy from this page."},
            {"Step": "3", "Action": "Add trust relationship", "Detail": "Use the trust policy and external ID to allow Nexora to assume the role."},
            {"Step": "4", "Action": "Copy Role ARN", "Detail": "Copy the role ARN from AWS IAM."},
            {"Step": "5", "Action": "Configure in Nexora", "Detail": "Paste the Role ARN and External ID into AWS Connector Setup."},
            {"Step": "6", "Action": "Test IAM readiness", "Detail": "Run AWS IAM Readiness to confirm every required capability."},
            {"Step": "7", "Action": "Run sync", "Detail": "Run the first AWS sync to populate costs, assets, relationships, and recommendations."},
        ]

    @staticmethod
    def get_role_configuration_fields() -> list[dict[str, str]]:
        return [
            {"Field": "Role ARN", "Purpose": "Nexora assumes this role to read AWS cost and inventory data."},
            {"Field": "External ID", "Purpose": "Customer-specific confused-deputy protection for cross-account access."},
            {"Field": "Region", "Purpose": "Default discovery region for regional AWS services."},
        ]

