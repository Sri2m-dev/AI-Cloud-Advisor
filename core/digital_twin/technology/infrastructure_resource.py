from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import EnterpriseEntity, utc_now_iso


class InfrastructureResourceType(str, Enum):
    AWS = "AWS"
    AZURE = "Azure"
    GCP = "GCP"
    VM = "VM"
    CONTAINER = "Container"
    DATABASE = "Database"
    STORAGE = "Storage"
    LOAD_BALANCER = "Load Balancer"
    CDN = "CDN"
    DNS = "DNS"
    KUBERNETES = "Kubernetes"
    LAMBDA = "Lambda"
    FUNCTION = "Function"
    QUEUE = "Queue"
    NETWORK = "Network"
    FIREWALL = "Firewall"
    MONITORING = "Monitoring"
    SECURITY_TOOL = "Security Tool"
    CLOUD_RESOURCE = "Cloud Resource"


@dataclass(slots=True)
class InfrastructureResource:
    name: str
    resource_type: str
    provider: str
    region: str = ""
    environment: str = ""
    resource_id: str = ""
    account_id: str = ""
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID | None = None
    entity_id: UUID | None = None
    owner_id: UUID | None = None
    tags: dict[str, str] = field(default_factory=dict)
    lifecycle_state: str = "Active"
    cost: float = 0.0
    health: float = 100.0
    risk: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_entity(cls, entity: EnterpriseEntity) -> "InfrastructureResource":
        metadata = dict(entity.metadata)
        source = entity.source_systems[0] if entity.source_systems else None
        provider = str(metadata.get("provider") or metadata.get("cloud_provider") or (source.system if source else ""))
        return cls(
            name=entity.display_name,
            resource_type=classify_resource_type(entity),
            provider=provider,
            region=str(metadata.get("region", "")),
            environment=str(metadata.get("environment", "")),
            resource_id=str(metadata.get("resource_id") or metadata.get("external_id") or (source.external_id if source else entity.id)),
            account_id=str(metadata.get("account_id") or metadata.get("cloud_account_id", "")),
            organization_id=entity.organization_id,
            entity_id=entity.id,
            owner_id=entity.owner_id,
            tags=dict(entity.tags),
            lifecycle_state=entity.lifecycle_state,
            cost=_number(metadata, "cost", "monthly_cost"),
            health=_bounded(_number(metadata, "health", "health_score", default=100.0)),
            risk=_bounded(_number(metadata, "risk", "risk_score")),
            metadata=metadata,
            updated_at=entity.updated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "organization_id", "entity_id", "owner_id"):
            payload[key] = str(payload[key]) if payload.get(key) else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InfrastructureResource":
        data = dict(payload)
        for key in ("id", "organization_id", "entity_id", "owner_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        return cls(**data)


def classify_resource_type(entity: EnterpriseEntity) -> str:
    metadata_type = str(entity.metadata.get("resource_type", entity.metadata.get("technology_type", ""))).lower()
    candidate = f"{entity.display_name} {entity.entity_type} {' '.join(entity.tags.values())} {metadata_type}".lower()
    provider = str(entity.metadata.get("provider", entity.metadata.get("cloud_provider", ""))).lower()
    if metadata_type in {"aws", "azure", "gcp"}:
        return metadata_type.upper() if metadata_type != "azure" else InfrastructureResourceType.AZURE.value
    if provider == "aws":
        return InfrastructureResourceType.AWS.value if "account" in candidate else _classify_cloud_resource(candidate)
    if provider == "azure":
        return InfrastructureResourceType.AZURE.value if "subscription" in candidate else _classify_cloud_resource(candidate)
    if provider == "gcp":
        return InfrastructureResourceType.GCP.value if "project" in candidate else _classify_cloud_resource(candidate)
    return _classify_cloud_resource(candidate)


def _classify_cloud_resource(candidate: str) -> str:
    if "ec2" in candidate or "virtual machine" in candidate or " vm" in candidate:
        return InfrastructureResourceType.VM.value
    if "container" in candidate or "ecs" in candidate or "aci" in candidate:
        return InfrastructureResourceType.CONTAINER.value
    if "rds" in candidate or "database" in candidate or "sql" in candidate or "db" in candidate:
        return InfrastructureResourceType.DATABASE.value
    if "s3" in candidate or "storage" in candidate or "blob" in candidate or "bucket" in candidate:
        return InfrastructureResourceType.STORAGE.value
    if "load balancer" in candidate or "alb" in candidate or "elb" in candidate:
        return InfrastructureResourceType.LOAD_BALANCER.value
    if "cdn" in candidate or "cloudfront" in candidate:
        return InfrastructureResourceType.CDN.value
    if "dns" in candidate or "route53" in candidate:
        return InfrastructureResourceType.DNS.value
    if "kubernetes" in candidate or "eks" in candidate or "aks" in candidate or "gke" in candidate:
        return InfrastructureResourceType.KUBERNETES.value
    if "lambda" in candidate:
        return InfrastructureResourceType.LAMBDA.value
    if "function" in candidate:
        return InfrastructureResourceType.FUNCTION.value
    if "queue" in candidate or "sqs" in candidate or "service bus" in candidate or "pubsub" in candidate:
        return InfrastructureResourceType.QUEUE.value
    if "vpc" in candidate or "vnet" in candidate or "subnet" in candidate or "network" in candidate:
        return InfrastructureResourceType.NETWORK.value
    if "firewall" in candidate or "security group" in candidate or "nsg" in candidate:
        return InfrastructureResourceType.FIREWALL.value
    if "cloudwatch" in candidate or "monitor" in candidate or "datadog" in candidate or "splunk" in candidate:
        return InfrastructureResourceType.MONITORING.value
    if "guardduty" in candidate or "defender" in candidate or "security" in candidate:
        return InfrastructureResourceType.SECURITY_TOOL.value
    return InfrastructureResourceType.CLOUD_RESOURCE.value


def _number(metadata: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)
