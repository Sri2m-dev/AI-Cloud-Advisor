from __future__ import annotations

from typing import Any, Callable

from botocore.exceptions import BotoCoreError, ClientError


class AWSResourceDiscovery:
    def __init__(self, session, region: str = "us-east-1"):
        self.session = session
        self.region = region

    def discover_all(self) -> list[dict[str, Any]]:
        resources = []
        for discover in (
            self.discover_ec2,
            self.discover_s3,
            self.discover_rds,
            self.discover_lambda,
            self.discover_vpc,
            self.discover_eks,
        ):
            resources.extend(self._safe_discover(discover))
        return resources

    def discover_ec2(self) -> list[dict[str, Any]]:
        ec2 = self.session.client("ec2", region_name=self.region)
        resources = []
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance.get("InstanceId")
                    resources.append(
                        self._row(
                            name=instance_id,
                            resource_type="EC2",
                            status=instance.get("State", {}).get("Name", "unknown").upper(),
                            resource_id=instance_id,
                            raw_payload=instance,
                        )
                    )
        return resources

    def discover_s3(self) -> list[dict[str, Any]]:
        s3 = self.session.client("s3", region_name=self.region)
        resources = []
        for bucket in s3.list_buckets().get("Buckets", []):
            name = bucket.get("Name")
            bucket_region = self._bucket_region(s3, name) if name else self.region
            resources.append(
                self._row(
                    name=name,
                    resource_type="S3",
                    status="ACTIVE",
                    resource_id=name,
                    region=bucket_region or "global",
                    raw_payload=bucket,
                )
            )
        return resources

    def discover_rds(self) -> list[dict[str, Any]]:
        rds = self.session.client("rds", region_name=self.region)
        resources = []
        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for instance in page.get("DBInstances", []):
                identifier = instance.get("DBInstanceIdentifier")
                resources.append(
                    self._row(
                        name=identifier,
                        resource_type="RDS",
                        status=instance.get("DBInstanceStatus", "unknown").upper(),
                        resource_id=instance.get("DBInstanceArn") or identifier,
                        raw_payload=instance,
                    )
                )
        return resources

    def discover_lambda(self) -> list[dict[str, Any]]:
        lambda_client = self.session.client("lambda", region_name=self.region)
        resources = []
        paginator = lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for function in page.get("Functions", []):
                name = function.get("FunctionName")
                resources.append(
                    self._row(
                        name=name,
                        resource_type="Lambda",
                        status="ACTIVE",
                        resource_id=function.get("FunctionArn") or name,
                        raw_payload=function,
                    )
                )
        return resources

    def discover_vpc(self) -> list[dict[str, Any]]:
        ec2 = self.session.client("ec2", region_name=self.region)
        resources = []
        paginator = ec2.get_paginator("describe_vpcs")
        for page in paginator.paginate():
            for vpc in page.get("Vpcs", []):
                vpc_id = vpc.get("VpcId")
                status = "DEFAULT" if vpc.get("IsDefault") else vpc.get("State", "unknown").upper()
                resources.append(
                    self._row(
                        name=vpc_id,
                        resource_type="VPC",
                        status=status,
                        resource_id=vpc_id,
                        raw_payload=vpc,
                    )
                )
        return resources

    def discover_eks(self) -> list[dict[str, Any]]:
        eks = self.session.client("eks", region_name=self.region)
        resources = []
        paginator = eks.get_paginator("list_clusters")
        for page in paginator.paginate():
            for cluster_name in page.get("clusters", []):
                details = {}
                try:
                    details = eks.describe_cluster(name=cluster_name).get("cluster", {})
                except (BotoCoreError, ClientError) as exc:
                    print(f"AWS EKS DETAIL DISCOVERY SKIPPED for {cluster_name}:", exc)
                resources.append(
                    self._row(
                        name=cluster_name,
                        resource_type="EKS",
                        status=details.get("status", "ACTIVE"),
                        resource_id=details.get("arn") or cluster_name,
                        raw_payload=details or {"cluster_name": cluster_name},
                    )
                )
        return resources

    def _safe_discover(self, discover: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
        try:
            return discover()
        except (BotoCoreError, ClientError) as exc:
            print(f"AWS {discover.__name__.replace('discover_', '').upper()} DISCOVERY SKIPPED:", exc)
            return []

    def _bucket_region(self, s3, bucket_name: str) -> str:
        try:
            location = s3.get_bucket_location(Bucket=bucket_name).get("LocationConstraint")
            return location or "us-east-1"
        except (BotoCoreError, ClientError):
            return "unknown"

    def _row(
        self,
        name: str | None,
        resource_type: str,
        status: str,
        resource_id: str | None,
        raw_payload: dict[str, Any],
        region: str | None = None,
    ) -> dict[str, Any]:
        return {
            "technology_name": name or resource_id or "Unknown AWS Resource",
            "technology_type": "Cloud Resource",
            "vendor_name": "AWS",
            "category": resource_type,
            "cloud_provider": "AWS",
            "owner_department": "CloudOps",
            "status": status,
            "region": region or self.region,
            "resource_id": resource_id or name,
            "source_system": "AWS Connector",
            "raw_payload": raw_payload,
        }

