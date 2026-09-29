from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from data_fabric.contracts.enums import EntityType
from data_fabric.source_facts import (
    FactType,
    SourceFactInput,
    UniversalEvidenceSourceFactAdapter,
)
from universal_evidence.pilot.reconciliation import (
    SourceIdentityObservation,
)


@dataclass(frozen=True)
class CertifiedPackageComposition:
    source_type: str
    source_facts: tuple[SourceFactInput, ...]
    identity_observations: tuple[SourceIdentityObservation, ...]


_SOURCE_FACT_MAPPINGS: dict[str, dict[str, FactType]] = {
    "org": {
        "Status": FactType.RESOURCE_LIFECYCLE,
    },
    "inventory": {
        "ResourceId": FactType.RESOURCE_IDENTITY,
        "Application": FactType.APPLICATION_MEMBERSHIP,
        "Owner": FactType.APPLICATION_OWNER,
        "CostCenter": FactType.COST_CENTER,
    },
    "cost": {
        "UnblendedCost": FactType.CLOUD_COST,
        "Tag_Application": FactType.APPLICATION_MEMBERSHIP,
        "Tag_CostCenter": FactType.COST_CENTER,
    },
    "application_mapping": {
        "Application": FactType.APPLICATION_MEMBERSHIP,
        "OwnerEmail": FactType.APPLICATION_OWNER,
        "BusinessService": FactType.DEPENDENCY,
    },
}


def source_fact_mapping(
    source_type: str,
) -> Mapping[str, FactType]:
    try:
        return dict(_SOURCE_FACT_MAPPINGS[source_type])
    except KeyError as exc:
        raise ValueError(f"Unsupported certified package source type: {source_type}") from exc


def _text(value: Any) -> str | None:
    if value is None:
        return None

    result = str(value).strip()
    return result or None


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _subject_reference(
    source_type: str,
    row: Mapping[str, Any],
    ordinal: int,
) -> str:
    candidates = {
        "org": ("AccountId",),
        "inventory": ("ResourceId", "AccountId"),
        "cost": ("ResourceId", "UsageAccountId"),
        "application_mapping": ("Application", "AccountId"),
    }[source_type]

    for field in candidates:
        value = _text(row.get(field))
        if value:
            return value

    return f"{source_type}:row:{ordinal}"


def _source_identifier(
    source_type: str,
    row: Mapping[str, Any],
    ordinal: int,
) -> str:
    return _subject_reference(source_type, row, ordinal)


def _normalized_attributes(
    source_type: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    fields = {
        "org": (
            "AccountId",
            "AccountName",
            "OrgUnit",
            "Status",
        ),
        "inventory": (
            "ResourceId",
            "ResourceType",
            "AccountId",
            "Region",
            "Application",
            "Environment",
            "Owner",
            "CostCenter",
            "BU",
        ),
        "cost": (
            "UsageAccountId",
            "ProductCode",
            "ResourceId",
            "Currency",
            "Tag_Application",
            "Tag_Environment",
            "Tag_CostCenter",
        ),
        "application_mapping": (
            "Application",
            "BusinessService",
            "AccountId",
            "Criticality",
            "OwnerEmail",
        ),
    }[source_type]

    return {field: row[field] for field in fields if field in row and _text(row[field]) is not None}


def _entity_type(
    source_type: str,
    row: Mapping[str, Any],
) -> EntityType:
    if source_type == "org":
        return EntityType.CLOUD_ACCOUNT

    if source_type == "inventory":
        return EntityType.CLOUD_RESOURCE

    if source_type == "cost":
        if _text(row.get("ResourceId")):
            return EntityType.CLOUD_RESOURCE
        return EntityType.CLOUD_ACCOUNT

    if source_type == "application_mapping":
        return EntityType.APPLICATION

    raise ValueError(f"Unsupported certified package source type: {source_type}")


def compose_certified_package_source(
    *,
    source_type: str,
    rows: Iterable[Mapping[str, Any]],
    file_id: str,
    organization_id: str,
    tenant_id: str,
    prospect_id: str,
    analysis_id: str,
    source_id: str,
    mapping_decision_ids: tuple[str, ...] = (),
    normalization_references: tuple[str, ...] = (),
) -> CertifiedPackageComposition:
    mapping = source_fact_mapping(source_type)

    prepared_rows = []
    observations = []

    for ordinal, original in enumerate(rows, start=1):
        row = dict(original)

        subject = _subject_reference(
            source_type,
            row,
            ordinal,
        )

        row.setdefault(
            "source_record_id",
            f"{source_type}:row:{ordinal}",
        )
        row.setdefault(
            "subject_reference",
            subject,
        )

        prepared_rows.append(row)

        attributes = _normalized_attributes(
            source_type,
            row,
        )

        evidence_payload = {
            "source_type": source_type,
            "file_id": file_id,
            "row": ordinal,
            "attributes": attributes,
        }

        observations.append(
            SourceIdentityObservation(
                source_system="certified_evidence_package",
                source_type=source_type,
                source_identifier=_source_identifier(
                    source_type,
                    row,
                    ordinal,
                ),
                entity_type=_entity_type(
                    source_type,
                    row,
                ),
                normalized_attributes=attributes,
                organization_id=organization_id,
                tenant_id=tenant_id,
                prospect_id=prospect_id,
                analysis_id=analysis_id,
                source_id=source_id,
                file_id=file_id,
                evidence_fingerprint=_fingerprint(evidence_payload),
                mapping_decision_ids=mapping_decision_ids,
                normalization_references=normalization_references,
            )
        )

    facts = UniversalEvidenceSourceFactAdapter().adapt(
        prepared_rows,
        mapping,
        file_id=file_id,
    )

    return CertifiedPackageComposition(
        source_type=source_type,
        source_facts=tuple(facts),
        identity_observations=tuple(observations),
    )
