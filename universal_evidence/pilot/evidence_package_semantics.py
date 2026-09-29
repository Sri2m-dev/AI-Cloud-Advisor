"""Certified semantic profile for Nexora evidence-package version 1.0.

This module defines deterministic semantic meaning only for fields that are
part of the explicitly supported evidence-package contract. It does not infer
meaning for arbitrary uploads and does not itself publish, normalize, or
materialize evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

SUPPORTED_PACKAGE_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class CertifiedFieldSemantic:
    source_type: str
    field_name: str
    semantic_concept_id: str
    authority: str = "CERTIFIED_PACKAGE_CONTRACT"


_PROFILE = {
    "org": {
        "AccountId": "cloud.account",
        "OrgUnit": "organization.business_unit",
    },
    "inventory": {
        "ResourceId": "resource.identifier",
        "ResourceType": "resource.type",
        "AccountId": "cloud.account",
        "Region": "cloud.region",
        "Application": "application.name",
        "Environment": "tagging.environment",
        "Owner": "ownership.owner",
        "CostCenter": "organization.cost_center",
        "BU": "organization.business_unit",
    },
    "cost": {
        "UsageAccountId": "cloud.account",
        "ProductCode": "technology.service",
        "ResourceId": "resource.identifier",
        "UnblendedCost": "financial.cost.total",
        "Currency": "financial.currency",
        "Tag_Application": "application.name",
        "Tag_Environment": "tagging.environment",
        "Tag_CostCenter": "organization.cost_center",
    },
    "application_mapping": {
        "Application": "application.name",
        "BusinessService": "business.service",
        "AccountId": "cloud.account",
        "OwnerEmail": "ownership.owner",
    },
}

CERTIFIED_PACKAGE_SEMANTICS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {source_type: MappingProxyType(dict(fields)) for source_type, fields in _PROFILE.items()}
)


def certified_semantic_profile(
    source_type: str,
    *,
    package_version: str = SUPPORTED_PACKAGE_VERSION,
) -> Mapping[str, str]:
    """Return the exact certified field mapping for one supported source type."""

    if package_version != SUPPORTED_PACKAGE_VERSION:
        return MappingProxyType({})

    fields = CERTIFIED_PACKAGE_SEMANTICS.get(str(source_type or "").strip())
    if fields is None:
        return MappingProxyType({})

    return fields


def certified_field_semantic(
    source_type: str,
    field_name: str,
    *,
    package_version: str = SUPPORTED_PACKAGE_VERSION,
) -> CertifiedFieldSemantic | None:
    """Resolve one exact certified field without fuzzy or inferred matching."""

    profile = certified_semantic_profile(
        source_type,
        package_version=package_version,
    )
    concept = profile.get(str(field_name or ""))

    if concept is None:
        return None

    return CertifiedFieldSemantic(
        source_type=source_type,
        field_name=field_name,
        semantic_concept_id=concept,
    )


def is_certified_field(
    source_type: str,
    field_name: str,
    *,
    package_version: str = SUPPORTED_PACKAGE_VERSION,
) -> bool:
    return (
        certified_field_semantic(
            source_type,
            field_name,
            package_version=package_version,
        )
        is not None
    )
