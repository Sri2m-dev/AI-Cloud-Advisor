"""P4.3 canonical enterprise identity and taxonomy helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from data_fabric.contracts import (
    EnterpriseEntity,
    EntityIdentity,
    EntityLineage,
    EntityOwnership,
    EntityProvenance,
    EntityType,
    EntityVersion,
)
from data_fabric.foundation import TenantContext

ENTERPRISE_ENTITY_TAXONOMY = MappingProxyType(
    {
        "BUSINESS": (
            EntityType.ORGANIZATION,
            EntityType.BUSINESS_UNIT,
            EntityType.DEPARTMENT,
            EntityType.PORTFOLIO,
            EntityType.BUSINESS_CAPABILITY,
            EntityType.BUSINESS_SERVICE,
            EntityType.BUSINESS_PROCESS,
        ),
        "APPLICATION": (EntityType.APPLICATION, EntityType.PRODUCT, EntityType.PLATFORM),
        "TECHNOLOGY": (
            EntityType.TECHNOLOGY,
            EntityType.CLOUD_ACCOUNT,
            EntityType.CLOUD_SUBSCRIPTION,
            EntityType.CLOUD_PROJECT,
            EntityType.COMPUTE_RESOURCE,
            EntityType.DATABASE,
            EntityType.STORAGE,
            EntityType.NETWORK,
            EntityType.KUBERNETES_CLUSTER,
            EntityType.AI_PLATFORM,
        ),
        "SAAS_VENDOR": (
            EntityType.SAAS_PRODUCT,
            EntityType.VENDOR,
            EntityType.CONTRACT,
            EntityType.LICENSE,
        ),
        "PEOPLE_OWNERSHIP": (
            EntityType.USER,
            EntityType.OWNER,
            EntityType.TEAM,
            EntityType.COST_CENTER,
        ),
        "FINANCIAL": (
            EntityType.SPEND_SOURCE,
            EntityType.BUDGET,
            EntityType.ALLOCATION_TARGET,
        ),
    }
)


def normalize_source_identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9._:/-]+", "-", str(value or "").strip().casefold()).strip("-")


def canonical_enterprise_id(
    context: TenantContext,
    entity_type: EntityType | str,
    source_system: str,
    source_entity_id: str,
) -> str:
    """Create a deterministic, tenant/source-aware P3 canonical identifier."""

    resolved_type = EntityType(entity_type)
    source = normalize_source_identity(source_system)
    source_id = normalize_source_identity(source_entity_id)
    if not source or not source_id:
        raise ValueError("source_system and source_entity_id are required")
    seed = (
        f"nexora://{context.organization_id}/{context.tenant_id}/"
        f"{resolved_type.value}/{source}/{source_id}"
    )
    return f"{resolved_type.value}:{uuid5(NAMESPACE_URL, seed)}"


def enterprise_entity_from_source(
    *,
    context: TenantContext,
    entity_type: EntityType | str,
    source_system: str,
    source_entity_id: str,
    canonical_name: str,
    display_name: str | None = None,
    aliases: tuple[str, ...] = (),
    lifecycle_status: str = "active",
    classification_status: str = "unclassified",
    confidence: float = 1.0,
    owner_reference: str | None = None,
    business_context_reference: str | None = None,
    financial_context_reference: str | None = None,
    health_reference: str | None = None,
    risk_reference: str | None = None,
    lineage_reference: str | None = None,
    provenance_reference: str | None = None,
    version: int = 1,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    search_attributes: Mapping[str, Any] | None = None,
) -> EnterpriseEntity:
    """Adapt a domain identity into the existing P3 contract without copying domain data."""

    resolved_type = EntityType(entity_type)
    canonical_id = canonical_enterprise_id(context, resolved_type, source_system, source_entity_id)
    timestamp = valid_from or datetime.now(timezone.utc)
    normalized_aliases = sorted({str(alias).strip() for alias in aliases if str(alias).strip()})
    identity = EntityIdentity(
        id=canonical_id,
        canonical_id=canonical_id,
        source_system=str(source_system).strip(),
        source_identifier=str(source_entity_id).strip(),
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        aliases=normalized_aliases,
        match_confidence=confidence,
    )
    lineage = EntityLineage(
        connector=str(source_system).strip(),
        raw_record_id=str(source_entity_id).strip(),
        canonical_entity_id=canonical_id,
        transformation_name="p4_3_enterprise_adapter",
        transformation_version="1.0",
    )
    provenance = EntityProvenance(
        source_system=str(source_system).strip(),
        source_identifier=str(source_entity_id).strip(),
        collection_method="domain_adapter",
        identity_resolution_rule="tenant_source_identity_v1",
    )
    ownership = EntityOwnership(owner_id=owner_reference) if owner_reference else None
    return EnterpriseEntity(
        id=canonical_id,
        canonical_id=canonical_id,
        entity_type=resolved_type,
        name=str(canonical_name).strip(),
        canonical_name=str(canonical_name).strip(),
        display_name=str(display_name or canonical_name).strip(),
        source_system=str(source_system).strip(),
        source_identifier=str(source_entity_id).strip(),
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        created_at=timestamp,
        updated_at=timestamp,
        version=version,
        confidence_score=confidence,
        metadata={
            "active": lifecycle_status.lower() not in {"retired", "archived"},
            "search": dict(search_attributes or {}),
        },
        identity=identity,
        ownership=ownership,
        lineage=lineage,
        provenance=provenance,
        entity_version=EntityVersion(
            version=version, effective_from=timestamp, effective_to=valid_to
        ),
        lifecycle_status=lifecycle_status,
        classification_status=classification_status,
        ownership_reference=owner_reference,
        business_context_reference=business_context_reference,
        financial_context_reference=financial_context_reference,
        health_reference=health_reference,
        risk_reference=risk_reference,
        lineage_reference=lineage_reference or canonical_id,
        provenance_reference=provenance_reference or canonical_id,
        valid_from=timestamp,
        valid_to=valid_to,
    )
