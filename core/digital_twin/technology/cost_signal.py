from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import utc_now_iso


class CostSignalType(str, Enum):
    CLOUD_SPEND = "Cloud Spend"
    STORAGE = "Storage"
    DATABASE = "Database"
    NETWORKING = "Networking"
    MONITORING = "Monitoring"
    SECURITY = "Security"
    SAAS = "SaaS"
    COMPUTE = "Compute"
    LICENSE = "License"
    OPTIMIZATION = "Optimization"


class CostHealthStatus(str, Enum):
    HEALTHY = "Healthy"
    WATCH = "Watch"
    WARNING = "Warning"
    CRITICAL = "Critical"


@dataclass(frozen=True, slots=True)
class CostSignal:
    technology_id: UUID
    provider: str
    service: str
    amount: float
    signal_type: str = CostSignalType.CLOUD_SPEND.value
    account: str = ""
    cost_center: str = ""
    business_unit: str = ""
    application: str = ""
    environment: str = ""
    usage: float = 0.0
    trend: float = 0.0
    confidence_score: float = 1.0
    id: UUID = field(default_factory=uuid4)
    observed_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        technology_id: UUID | str,
        provider: str,
        service: str,
        amount: float,
        signal_type: str = CostSignalType.CLOUD_SPEND.value,
        account: str = "",
        cost_center: str = "",
        business_unit: str = "",
        application: str = "",
        environment: str = "",
        usage: float = 0.0,
        trend: float = 0.0,
        confidence_score: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> "CostSignal":
        return cls(
            technology_id=UUID(str(technology_id)),
            provider=provider,
            service=service,
            amount=round(max(0.0, float(amount)), 2),
            signal_type=signal_type,
            account=account,
            cost_center=cost_center,
            business_unit=business_unit,
            application=application,
            environment=environment,
            usage=max(0.0, float(usage)),
            trend=float(trend),
            confidence_score=max(0.0, min(1.0, float(confidence_score))),
            metadata=metadata or {},
        )

    def effective_amount(self) -> float:
        return round(self.amount * self.confidence_score, 2)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["technology_id"] = str(self.technology_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CostSignal":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["technology_id"] = UUID(str(data["technology_id"]))
        return cls(**data)


def cost_health_for_variance(variance_percent: float) -> str:
    value = abs(float(variance_percent))
    if value <= 5:
        return CostHealthStatus.HEALTHY.value
    if value <= 15:
        return CostHealthStatus.WATCH.value
    if value <= 30:
        return CostHealthStatus.WARNING.value
    return CostHealthStatus.CRITICAL.value
