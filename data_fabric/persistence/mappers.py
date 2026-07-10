"""Domain-to-persistence mapper contracts for Data Fabric records."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Mapping, TypeVar
from uuid import UUID

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext, normalize_to_utc
from data_fabric.persistence.exceptions import PersistenceValidationError
from data_fabric.persistence.models import AppendOnlyRecord, MutableRecord, PersistenceRecord

T = TypeVar("T")


class PersistenceMapper(ABC, Generic[T]):
    """Mapper boundary between domain contracts and persistence records."""

    supported_schema_version = 1

    @abstractmethod
    def domain_to_record(self, domain: T, tenant_context: TenantContext) -> PersistenceRecord:
        """Convert a domain object into a persistence record."""

    @abstractmethod
    def record_to_domain(self, record: PersistenceRecord) -> T:
        """Convert a persistence record back into a domain object."""

    def _validate_schema(self, record: PersistenceRecord) -> None:
        if record.schema_version != self.supported_schema_version:
            raise PersistenceValidationError(
                f"Unsupported schema version: {record.schema_version}"
            )


class EntityPersistenceMapper(PersistenceMapper[EnterpriseEntity]):
    """Mapper for canonical enterprise entities."""

    def domain_to_record(self, domain: EnterpriseEntity, tenant_context: TenantContext) -> MutableRecord:
        tenant_context.assert_record_matches(domain, "entity")
        payload = _domain_payload(domain)
        return MutableRecord(
            record_id=domain.id,
            organization_id=tenant_context.organization_id,
            tenant_id=tenant_context.tenant_id,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            payload=payload,
            metadata={
                "canonical_id": domain.canonical_id,
                "entity_type": domain.entity_type.value,
                "source_system": domain.source_system,
                "source_identifier": domain.source_identifier,
            },
        )

    def record_to_domain(self, record: PersistenceRecord) -> EnterpriseEntity:
        self._validate_schema(record)
        payload = dict(record.payload)
        payload["created_at"] = _as_datetime(payload["created_at"])
        payload["updated_at"] = _as_datetime(payload["updated_at"])
        return EnterpriseEntity(**_thaw(payload))


class RelationshipPersistenceMapper(PersistenceMapper[EnterpriseRelationship]):
    """Mapper for canonical enterprise relationships."""

    def domain_to_record(self, domain: EnterpriseRelationship, tenant_context: TenantContext) -> MutableRecord:
        tenant_context.assert_record_matches(domain, "relationship")
        payload = _domain_payload(domain)
        return MutableRecord(
            record_id=domain.id,
            organization_id=tenant_context.organization_id,
            tenant_id=tenant_context.tenant_id,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            payload=payload,
            metadata={
                "relationship_type": domain.relationship_type.value,
                "source_entity_id": domain.source_entity_id,
                "target_entity_id": domain.target_entity_id,
                "source_system": domain.source_system,
                "source_identifier": domain.source_identifier,
            },
        )

    def record_to_domain(self, record: PersistenceRecord) -> EnterpriseRelationship:
        self._validate_schema(record)
        payload = dict(record.payload)
        payload["created_at"] = _as_datetime(payload["created_at"])
        payload["updated_at"] = _as_datetime(payload["updated_at"])
        return EnterpriseRelationship(**_thaw(payload))


class IdentityPersistenceMapper(PersistenceMapper[Mapping[str, Any]]):
    pass


class LineagePersistenceMapper(PersistenceMapper[Mapping[str, Any]]):
    def domain_to_record(self, domain: Mapping[str, Any], tenant_context: TenantContext) -> AppendOnlyRecord:
        return _append_record(domain, tenant_context, "lineage")

    def record_to_domain(self, record: PersistenceRecord) -> Mapping[str, Any]:
        self._validate_schema(record)
        return _thaw(record.payload)


class ProvenancePersistenceMapper(LineagePersistenceMapper):
    def domain_to_record(self, domain: Mapping[str, Any], tenant_context: TenantContext) -> AppendOnlyRecord:
        return _append_record(domain, tenant_context, "provenance")


class VersionPersistenceMapper(LineagePersistenceMapper):
    def domain_to_record(self, domain: Mapping[str, Any], tenant_context: TenantContext) -> AppendOnlyRecord:
        return _append_record(domain, tenant_context, "version")


class QualityPersistenceMapper(LineagePersistenceMapper):
    def domain_to_record(self, domain: Mapping[str, Any], tenant_context: TenantContext) -> AppendOnlyRecord:
        return _append_record(domain, tenant_context, "quality")


class OntologyPersistenceMapper(LineagePersistenceMapper):
    def domain_to_record(self, domain: Mapping[str, Any], tenant_context: TenantContext) -> MutableRecord:
        return _mutable_record(domain, tenant_context, "ontology")


class SemanticMappingPersistenceMapper(LineagePersistenceMapper):
    def domain_to_record(self, domain: Mapping[str, Any], tenant_context: TenantContext) -> MutableRecord:
        return _mutable_record(domain, tenant_context, "semantic_mapping")


class _GenericMutableMappingMapper(PersistenceMapper[Mapping[str, Any]]):
    kind = "generic"

    def domain_to_record(self, domain: Mapping[str, Any], tenant_context: TenantContext) -> MutableRecord:
        return _mutable_record(domain, tenant_context, self.kind)

    def record_to_domain(self, record: PersistenceRecord) -> Mapping[str, Any]:
        self._validate_schema(record)
        return _thaw(record.payload)


IdentityPersistenceMapper = type(
    "IdentityPersistenceMapper",
    (_GenericMutableMappingMapper,),
    {"kind": "identity"},
)


def _mutable_record(domain: Mapping[str, Any], tenant_context: TenantContext, kind: str) -> MutableRecord:
    payload = _mapping_payload(domain)
    record_id = str(payload.get("id") or payload.get("record_id") or payload.get("mapping_id") or payload.get("concept_id") or payload.get("source_identifier") or kind)
    return MutableRecord(
        record_id=record_id,
        organization_id=tenant_context.organization_id,
        tenant_id=tenant_context.tenant_id,
        payload=payload,
        metadata={"kind": kind},
    )


def _append_record(domain: Mapping[str, Any], tenant_context: TenantContext, kind: str) -> AppendOnlyRecord:
    payload = _mapping_payload(domain)
    record_id = str(payload.get("id") or payload.get("record_id") or payload.get("snapshot_id") or f"{kind}:{DefaultDeterministicSerializer().content_hash(payload)}")
    return AppendOnlyRecord(
        record_id=record_id,
        organization_id=tenant_context.organization_id,
        tenant_id=tenant_context.tenant_id,
        payload=payload,
        metadata={"kind": kind},
    )


def _domain_payload(domain: Any) -> dict[str, Any]:
    payload = asdict(domain) if is_dataclass(domain) else dict(domain)
    return _stable_payload(payload)


def _mapping_payload(domain: Mapping[str, Any]) -> dict[str, Any]:
    return _stable_payload(deepcopy(dict(domain)))


def _stable_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _stable_value(payload[key])
        for key in sorted(payload, key=str)
    }


def _stable_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return normalize_to_utc(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if is_dataclass(value):
        return _stable_payload(asdict(value))
    if isinstance(value, Mapping):
        return _stable_payload(value)
    if isinstance(value, list | tuple):
        return tuple(_stable_value(item) for item in value)
    if isinstance(value, set | frozenset):
        return tuple(sorted((_stable_value(item) for item in value), key=str))
    return deepcopy(value)


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise PersistenceValidationError("Expected datetime-compatible value")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(value[key]) for key in value}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted((_thaw(item) for item in value), key=str)
    return deepcopy(value)
