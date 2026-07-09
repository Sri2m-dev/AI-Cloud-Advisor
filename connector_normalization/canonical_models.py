"""Canonical enterprise records for Nexora Enterprise Data Fabric."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class CanonicalRecordType(str, Enum):
    CLOUD_RESOURCE = "cloud_resource"
    APPLICATION = "application"
    TECHNOLOGY = "technology"
    BUSINESS_SERVICE = "business_service"
    BUSINESS_CAPABILITY = "business_capability"
    BUSINESS_UNIT = "business_unit"
    IDENTITY = "identity"
    VENDOR = "vendor"
    COST_RECORD = "cost_record"
    RECOMMENDATION = "recommendation"
    RISK = "risk"
    INCIDENT = "incident"
    CHANGE = "change"
    LICENSE = "license"
    CONTRACT = "contract"


@dataclass(frozen=True)
class CanonicalEnterpriseRecord:
    """Base canonical enterprise record envelope."""

    record_id: str
    record_type: CanonicalRecordType
    source_system: str
    source_id: str
    name: str
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_updated_at: datetime | None = None
    organization_id: str | None = None
    business_unit_id: str | None = None
    business_service_id: str | None = None
    application_id: str | None = None
    technology_id: str | None = None
    owner: str | None = None
    status: str | None = None
    tags: Mapping[str, str] = field(default_factory=dict)
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalCloudResource(CanonicalEnterpriseRecord):
    provider: str = ""
    account_id: str | None = None
    region: str | None = None
    resource_type: str | None = None
    resource_group: str | None = None
    monthly_cost: float | None = None
    currency: str = "USD"


@dataclass(frozen=True)
class CanonicalApplication(CanonicalEnterpriseRecord):
    criticality: str | None = None
    lifecycle_stage: str | None = None
    environment: str | None = None
    technologies: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CanonicalTechnology(CanonicalEnterpriseRecord):
    category: str | None = None
    vendor_id: str | None = None
    health_score: float | None = None
    risk_score: float | None = None
    monthly_cost: float | None = None
    currency: str = "USD"


@dataclass(frozen=True)
class CanonicalBusinessService(CanonicalEnterpriseRecord):
    capability_id: str | None = None
    tier: str | None = None
    sla: str | None = None
    criticality: str | None = None


@dataclass(frozen=True)
class CanonicalBusinessCapability(CanonicalEnterpriseRecord):
    maturity: str | None = None
    criticality: str | None = None
    services: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CanonicalBusinessUnit(CanonicalEnterpriseRecord):
    parent_business_unit_id: str | None = None
    executive_owner: str | None = None
    cost_center: str | None = None


@dataclass(frozen=True)
class CanonicalIdentity(CanonicalEnterpriseRecord):
    identity_type: str | None = None
    email: str | None = None
    department: str | None = None
    active: bool | None = None


@dataclass(frozen=True)
class CanonicalVendor(CanonicalEnterpriseRecord):
    vendor_category: str | None = None
    website: str | None = None
    contract_count: int | None = None


@dataclass(frozen=True)
class CanonicalCostRecord(CanonicalEnterpriseRecord):
    amount: float = 0.0
    currency: str = "USD"
    billing_period: str | None = None
    cost_category: str | None = None
    provider: str | None = None


@dataclass(frozen=True)
class CanonicalRecommendation(CanonicalEnterpriseRecord):
    recommendation_type: str | None = None
    impact: str | None = None
    potential_savings: float | None = None
    confidence: float | None = None
    currency: str = "USD"


@dataclass(frozen=True)
class CanonicalRisk(CanonicalEnterpriseRecord):
    risk_type: str | None = None
    severity: str | None = None
    likelihood: str | None = None
    impact: str | None = None
    mitigation: str | None = None


@dataclass(frozen=True)
class CanonicalIncident(CanonicalEnterpriseRecord):
    severity: str | None = None
    opened_at: datetime | None = None
    resolved_at: datetime | None = None
    impacted_services: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CanonicalChange(CanonicalEnterpriseRecord):
    change_type: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    approval_status: str | None = None


@dataclass(frozen=True)
class CanonicalLicense(CanonicalEnterpriseRecord):
    product: str | None = None
    assigned_count: int | None = None
    active_count: int | None = None
    renewal_date: datetime | None = None
    monthly_cost: float | None = None
    currency: str = "USD"


@dataclass(frozen=True)
class CanonicalContract(CanonicalEnterpriseRecord):
    vendor_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    annual_value: float | None = None
    currency: str = "USD"


CanonicalRecord = (
    CanonicalCloudResource
    | CanonicalApplication
    | CanonicalTechnology
    | CanonicalBusinessService
    | CanonicalBusinessCapability
    | CanonicalBusinessUnit
    | CanonicalIdentity
    | CanonicalVendor
    | CanonicalCostRecord
    | CanonicalRecommendation
    | CanonicalRisk
    | CanonicalIncident
    | CanonicalChange
    | CanonicalLicense
    | CanonicalContract
)
