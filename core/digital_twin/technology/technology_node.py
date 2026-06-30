from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.digital_twin.technology.technology_health import TechnologyHealth
from core.digital_twin.technology.technology_state import TechnologyState
from core.entities.entity import EnterpriseEntity, EntityType, utc_now_iso


class TechnologyAssetType(str, Enum):
    TECHNOLOGY = "Technology"
    CLOUD_ACCOUNT = "Cloud Account"
    CLOUD_RESOURCE = "Cloud Resource"
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
    SAAS = "SaaS"
    SECURITY_CONTROL = "Security Control"
    MONITORING = "Monitoring"


@dataclass(slots=True)
class TechnologyNode:
    technology_id: UUID
    organization_id: UUID
    name: str
    technology_type: str
    id: UUID = field(default_factory=uuid4)
    vendor: str = ""
    cloud_provider: str = ""
    environment: str = ""
    region: str = ""
    owner_id: UUID | None = None
    business_service_ids: list[UUID] = field(default_factory=list)
    application_ids: list[UUID] = field(default_factory=list)
    status: str = "Unknown"
    health: TechnologyHealth | None = None
    state: TechnologyState | None = None
    risk: float = 0.0
    cost: float = 0.0
    monthly_cost: float = 0.0
    annual_cost: float = 0.0
    tags: dict[str, str] = field(default_factory=dict)
    lifecycle: str = "Active"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_entity(cls, entity: EnterpriseEntity) -> "TechnologyNode":
        metadata = dict(entity.metadata)
        health = TechnologyHealth.from_metadata(entity.id, metadata)
        state = TechnologyState(entity.id)
        monthly_cost = _number(metadata, "monthly_cost", "cost")
        annual_cost = _number(metadata, "annual_cost", default=monthly_cost * 12)
        risk = _number(metadata, "risk_score", "risk")
        state.refresh(
            health_score=health.health_score,
            risk_score=risk,
            cost_score=min(100.0, monthly_cost / 1000.0 * 10.0),
            security_score=_number(metadata, "security_score", "security", default=100.0),
            operations_score=health.operational_score,
            business_impact_score=_number(metadata, "business_impact_score", "criticality", default=0.0),
        )
        return cls(
            technology_id=entity.id,
            organization_id=entity.organization_id,
            name=entity.display_name,
            technology_type=_technology_type(entity),
            vendor=str(metadata.get("vendor", "")),
            cloud_provider=str(metadata.get("cloud_provider", metadata.get("provider", ""))),
            environment=str(metadata.get("environment", "")),
            region=str(metadata.get("region", "")),
            owner_id=entity.owner_id,
            status=state.status,
            health=health,
            state=state,
            risk=risk,
            cost=monthly_cost,
            monthly_cost=monthly_cost,
            annual_cost=annual_cost,
            tags=dict(entity.tags),
            lifecycle=entity.lifecycle_state,
            metadata=metadata,
            updated_at=entity.updated_at,
        )

    def attach_application(self, application_id: UUID) -> None:
        if application_id not in self.application_ids:
            self.application_ids.append(application_id)
            self.application_ids.sort(key=str)

    def attach_business_service(self, service_id: UUID) -> None:
        if service_id not in self.business_service_ids:
            self.business_service_ids.append(service_id)
            self.business_service_ids.sort(key=str)

    def refresh_state(self) -> TechnologyState:
        if self.health is None:
            self.health = TechnologyHealth(self.technology_id)
        if self.state is None:
            self.state = TechnologyState(self.technology_id)
        self.state.refresh(
            health_score=self.health.recalculate(),
            risk_score=self.risk,
            cost_score=min(100.0, self.monthly_cost / 1000.0 * 10.0),
            security_score=_number(self.metadata, "security_score", "security", default=100.0),
            operations_score=self.health.operational_score,
            business_impact_score=_number(self.metadata, "business_impact_score", "criticality", default=0.0),
        )
        self.status = self.state.status
        self.updated_at = utc_now_iso()
        return self.state

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "technology_id", "organization_id", "owner_id"):
            payload[key] = str(payload[key]) if payload.get(key) else None
        payload["business_service_ids"] = [str(value) for value in self.business_service_ids]
        payload["application_ids"] = [str(value) for value in self.application_ids]
        payload["health"] = self.health.to_dict() if self.health else None
        payload["state"] = self.state.to_dict() if self.state else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TechnologyNode":
        data = dict(payload)
        for key in ("id", "technology_id", "organization_id", "owner_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        data["business_service_ids"] = [UUID(str(value)) for value in data.get("business_service_ids", [])]
        data["application_ids"] = [UUID(str(value)) for value in data.get("application_ids", [])]
        data["health"] = TechnologyHealth.from_dict(data["health"]) if data.get("health") else None
        data["state"] = TechnologyState.from_dict(data["state"]) if data.get("state") else None
        return cls(**data)


def _technology_type(entity: EnterpriseEntity) -> str:
    normalized_name = f"{entity.display_name} {entity.entity_type} {' '.join(entity.tags.values())}".lower()
    metadata_type = str(entity.metadata.get("technology_type", entity.metadata.get("resource_type", ""))).lower()
    candidate = f"{normalized_name} {metadata_type}"
    if entity.entity_type == EntityType.CLOUD_ACCOUNT.value:
        return TechnologyAssetType.CLOUD_ACCOUNT.value
    if entity.entity_type == EntityType.CLOUD_RESOURCE.value:
        if "lambda" in candidate or "function" in candidate:
            return TechnologyAssetType.LAMBDA.value
        if "container" in candidate or "ecs" in candidate:
            return TechnologyAssetType.CONTAINER.value
        if "kubernetes" in candidate or "eks" in candidate or "aks" in candidate or "gke" in candidate:
            return TechnologyAssetType.KUBERNETES.value
        if "rds" in candidate or "database" in candidate or "db" in candidate:
            return TechnologyAssetType.DATABASE.value
        if "s3" in candidate or "storage" in candidate:
            return TechnologyAssetType.STORAGE.value
        if "load balancer" in candidate or "alb" in candidate:
            return TechnologyAssetType.LOAD_BALANCER.value
        if "queue" in candidate or "sqs" in candidate:
            return TechnologyAssetType.QUEUE.value
        return TechnologyAssetType.CLOUD_RESOURCE.value
    if entity.entity_type == EntityType.SAAS_APPLICATION.value:
        return TechnologyAssetType.SAAS.value
    if entity.entity_type in {EntityType.CONTROL.value, EntityType.POLICY.value}:
        return TechnologyAssetType.SECURITY_CONTROL.value
    return TechnologyAssetType.TECHNOLOGY.value


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
