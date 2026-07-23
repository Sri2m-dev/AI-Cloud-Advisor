"""Canonical Business Service model composed from released P3 contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from data_fabric.contracts import (
    EnterpriseEntity,
    EntityIdentity,
    EntityOwnership,
    EntityType,
    EntityVersion,
)
from data_fabric.foundation import TenantContext
from enterprise_registry.exceptions import BusinessServiceValidationError


class BusinessCriticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BusinessServiceLifecycle(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    ARCHIVED = "archived"


class BusinessServiceType(StrEnum):
    BUSINESS = "business"
    CUSTOMER_FACING = "customer_facing"
    SHARED = "shared"
    PLATFORM = "platform"


LIFECYCLE_TRANSITIONS: Mapping[BusinessServiceLifecycle, frozenset[BusinessServiceLifecycle]] = (
    MappingProxyType(
        {
            BusinessServiceLifecycle.PLANNED: frozenset(
                {BusinessServiceLifecycle.ACTIVE, BusinessServiceLifecycle.ARCHIVED}
            ),
            BusinessServiceLifecycle.ACTIVE: frozenset(
                {
                    BusinessServiceLifecycle.SUSPENDED,
                    BusinessServiceLifecycle.DEPRECATED,
                    BusinessServiceLifecycle.RETIRED,
                }
            ),
            BusinessServiceLifecycle.SUSPENDED: frozenset(
                {
                    BusinessServiceLifecycle.ACTIVE,
                    BusinessServiceLifecycle.DEPRECATED,
                    BusinessServiceLifecycle.RETIRED,
                }
            ),
            BusinessServiceLifecycle.DEPRECATED: frozenset(
                {BusinessServiceLifecycle.ACTIVE, BusinessServiceLifecycle.RETIRED}
            ),
            BusinessServiceLifecycle.RETIRED: frozenset(
                {BusinessServiceLifecycle.ARCHIVED}
            ),
            BusinessServiceLifecycle.ARCHIVED: frozenset(),
        }
    )
)


def normalize_identity(value: str, field_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", str(value).strip().casefold()).strip("-")
    if not normalized:
        raise BusinessServiceValidationError(f"{field_name} is required")
    return normalized


def canonical_business_service_id(
    context: TenantContext,
    business_service_id: str,
) -> str:
    """Return a deterministic identity scoped by organization and tenant."""

    local_id = normalize_identity(business_service_id, "business_service_id")
    seed = f"nexora://{context.organization_id}/{context.tenant_id}/business-service/{local_id}"
    return f"business-service:{uuid5(NAMESPACE_URL, seed)}"


@dataclass(frozen=True, slots=True)
class BusinessService:
    """WP-006 Phase 1 domain model backed by the canonical entity contract."""

    entity: EnterpriseEntity
    business_service_id: str
    description: str
    business_domain: str
    service_type: BusinessServiceType
    criticality: BusinessCriticality
    lifecycle_state: BusinessServiceLifecycle
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "service_type",
            BusinessServiceType(self.service_type),
        )
        object.__setattr__(
            self,
            "criticality",
            BusinessCriticality(self.criticality),
        )
        object.__setattr__(
            self,
            "lifecycle_state",
            BusinessServiceLifecycle(self.lifecycle_state),
        )
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))
        self._validate()

    def _validate(self) -> None:
        required = {
            "business_service_id": self.business_service_id,
            "name": self.entity.name,
            "description": self.description,
            "business_domain": self.business_domain,
            "source_system": self.entity.source_system,
            "source_identifier": self.entity.source_identifier,
            "organization_id": self.entity.organization_id,
            "tenant_id": self.entity.tenant_id,
        }
        missing = [name for name, value in required.items() if not str(value or "").strip()]
        if missing:
            raise BusinessServiceValidationError(
                f"Business service is missing required field(s): {', '.join(missing)}"
            )
        if self.entity.entity_type is not EntityType.BUSINESS_SERVICE:
            raise BusinessServiceValidationError(
                "canonical entity must use entity_type business_service"
            )
        expected_id = canonical_business_service_id(
            TenantContext(self.entity.organization_id, str(self.entity.tenant_id)),
            self.business_service_id,
        )
        if self.entity.canonical_id != expected_id:
            raise BusinessServiceValidationError(
                "canonical_id is inconsistent with organization, tenant, and business_service_id"
            )
        identity = self.entity.identity
        if identity is None:
            raise BusinessServiceValidationError("canonical identity is required")
        identity_values = (
            identity.canonical_id,
            identity.source_system,
            identity.source_identifier,
            identity.organization_id,
            identity.tenant_id,
        )
        entity_values = (
            self.entity.canonical_id,
            self.entity.source_system,
            self.entity.source_identifier,
            self.entity.organization_id,
            self.entity.tenant_id,
        )
        if identity_values != entity_values:
            raise BusinessServiceValidationError(
                "source identity must match the canonical entity identity"
            )
        ownership = self.entity.ownership
        if ownership is None or not str(ownership.owner_id or "").strip():
            raise BusinessServiceValidationError("ownership.owner_id is required")
        if self.entity.version < 1:
            raise BusinessServiceValidationError("version must be positive")

    @property
    def canonical_id(self) -> str:
        return self.entity.canonical_id

    @property
    def organization_id(self) -> str:
        return self.entity.organization_id

    @property
    def tenant_id(self) -> str:
        return str(self.entity.tenant_id)

    @property
    def name(self) -> str:
        return self.entity.name

    @property
    def owner(self) -> EntityOwnership:
        return self.entity.ownership  # type: ignore[return-value]

    @property
    def cost_center(self) -> str | None:
        return self.owner.cost_center_id

    @property
    def source_system(self) -> str:
        return self.entity.source_system

    @property
    def source_id(self) -> str:
        return self.entity.source_identifier

    @property
    def aliases(self) -> tuple[str, ...]:
        identity = self.entity.identity
        return tuple(identity.aliases) if identity else ()

    @property
    def created_at(self) -> datetime:
        return self.entity.created_at

    @property
    def updated_at(self) -> datetime:
        return self.entity.updated_at

    @property
    def version(self) -> int:
        return self.entity.version

    @property
    def active(self) -> bool:
        return self.lifecycle_state not in {
            BusinessServiceLifecycle.RETIRED,
            BusinessServiceLifecycle.ARCHIVED,
        }


def create_business_service(
    *,
    context: TenantContext,
    business_service_id: str,
    name: str,
    description: str,
    business_domain: str,
    service_type: BusinessServiceType | str,
    criticality: BusinessCriticality | str,
    owner_id: str,
    source_system: str,
    source_id: str,
    lifecycle_state: BusinessServiceLifecycle | str = BusinessServiceLifecycle.PLANNED,
    owner_name: str | None = None,
    owner_email: str | None = None,
    department_id: str | None = None,
    cost_center: str | None = None,
    aliases: tuple[str, ...] = (),
    attributes: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> BusinessService:
    """Create a deterministic canonical Business Service contract."""

    normalized_service_id = normalize_identity(business_service_id, "business_service_id")
    canonical_id = canonical_business_service_id(context, normalized_service_id)
    timestamp = now or datetime.now(timezone.utc)
    normalized_aliases = sorted(
        {
            normalize_identity(alias, "alias")
            for alias in aliases
            if str(alias).strip()
        }
    )
    identity = EntityIdentity(
        id=canonical_id,
        canonical_id=canonical_id,
        source_system=str(source_system).strip(),
        source_identifier=str(source_id).strip(),
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        aliases=normalized_aliases,
    )
    ownership = EntityOwnership(
        owner_id=str(owner_id).strip(),
        owner_name=owner_name,
        owner_email=owner_email,
        department_id=department_id,
        cost_center_id=cost_center,
    )
    resolved_type = BusinessServiceType(service_type)
    resolved_criticality = BusinessCriticality(criticality)
    resolved_lifecycle = BusinessServiceLifecycle(lifecycle_state)
    metadata = {
        "active": resolved_lifecycle
        not in {BusinessServiceLifecycle.RETIRED, BusinessServiceLifecycle.ARCHIVED},
        "business_domain": str(business_domain).strip(),
        "business_service_id": normalized_service_id,
        "criticality": resolved_criticality.value,
        "lifecycle_state": resolved_lifecycle.value,
        "service_type": resolved_type.value,
    }
    entity = EnterpriseEntity(
        id=canonical_id,
        canonical_id=canonical_id,
        entity_type=EntityType.BUSINESS_SERVICE,
        name=str(name).strip(),
        source_system=str(source_system).strip(),
        source_identifier=str(source_id).strip(),
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        created_at=timestamp,
        updated_at=timestamp,
        version=1,
        metadata=metadata,
        identity=identity,
        ownership=ownership,
        entity_version=EntityVersion(version=1, effective_from=timestamp),
    )
    return BusinessService(
        entity=entity,
        business_service_id=normalized_service_id,
        description=str(description).strip(),
        business_domain=str(business_domain).strip(),
        service_type=resolved_type,
        criticality=resolved_criticality,
        lifecycle_state=resolved_lifecycle,
        attributes=attributes or {},
    )
