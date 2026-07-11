"""Atomic Supabase RPC boundary for canonical Data Fabric writes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterOperationError
from data_fabric.foundation import (
    DataFabricConflictError,
    DataFabricIdempotencyError,
    DataFabricTenantBoundaryError,
    DataFabricTransactionError,
    DataFabricValidationError,
    TenantContext,
)
from data_fabric.persistence.models import AppendOnlyRecord, MutableRecord


class AtomicWriteStatus(str, Enum):
    COMMITTED = "committed"
    REPLAYED = "replayed"
    NO_CHANGE = "no_change"
    IN_PROGRESS = "in_progress"
    REJECTED = "rejected"
    FAILED = "failed"


class AtomicWriteOperation(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DEACTIVATE = "deactivate"
    NO_CHANGE = "no_change"


@dataclass(frozen=True, slots=True)
class AtomicWriteFailure:
    code: str
    reason: str


@dataclass(frozen=True, slots=True)
class AtomicWriteRecordResult:
    record_type: str
    record_id: str
    created: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class AtomicWriteResult:
    status: AtomicWriteStatus
    subject_type: str
    subject_id: str
    operation: str
    resulting_revision: int | None = None
    resulting_version: int | None = None
    version_created: bool = False
    lineage_ids: tuple[str, ...] = field(default_factory=tuple)
    provenance_ids: tuple[str, ...] = field(default_factory=tuple)
    quality_assessment_id: str | None = None
    idempotency_status: str | None = None
    replayed: bool = False
    correlation_id: str | None = None
    records: tuple[AtomicWriteRecordResult, ...] = field(default_factory=tuple)
    failure: AtomicWriteFailure | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", AtomicWriteStatus(self.status))
        object.__setattr__(self, "lineage_ids", tuple(str(item) for item in self.lineage_ids))
        object.__setattr__(self, "provenance_ids", tuple(str(item) for item in self.provenance_ids))
        object.__setattr__(self, "records", tuple(self.records))


@dataclass(frozen=True, slots=True)
class AtomicEntityWriteRequest:
    tenant_context: TenantContext
    operation: str
    entity_record: MutableRecord
    expected_revision: int | None = None
    entity_version: AppendOnlyRecord | None = None
    lineage_events: tuple[AppendOnlyRecord, ...] = field(default_factory=tuple)
    provenance_records: tuple[AppendOnlyRecord, ...] = field(default_factory=tuple)
    quality_assessment: AppendOnlyRecord | None = None
    idempotency_key: str = ""
    payload_hash: str = ""
    correlation_id: str | None = None
    actor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_operation(self.operation)
        _validate_tenant_record(self.tenant_context, self.entity_record, "entity_record")
        _validate_revision_requirement(self.operation, self.expected_revision)
        if not self.idempotency_key:
            raise DataFabricValidationError("idempotency_key is required")
        if not self.payload_hash:
            raise DataFabricValidationError("payload_hash is required")
        if self.entity_version is not None:
            _validate_tenant_record(self.tenant_context, self.entity_version, "entity_version")
        for record in self.lineage_events:
            _validate_tenant_record(self.tenant_context, record, "lineage_event")
        for record in self.provenance_records:
            _validate_tenant_record(self.tenant_context, record, "provenance_record")
        if self.quality_assessment is not None:
            _validate_tenant_record(self.tenant_context, self.quality_assessment, "quality_assessment")
        object.__setattr__(self, "lineage_events", tuple(self.lineage_events))
        object.__setattr__(self, "provenance_records", tuple(self.provenance_records))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class AtomicRelationshipWriteRequest:
    tenant_context: TenantContext
    operation: str
    relationship_record: MutableRecord
    expected_revision: int | None = None
    lineage_events: tuple[AppendOnlyRecord, ...] = field(default_factory=tuple)
    provenance_records: tuple[AppendOnlyRecord, ...] = field(default_factory=tuple)
    quality_assessment: AppendOnlyRecord | None = None
    idempotency_key: str = ""
    payload_hash: str = ""
    correlation_id: str | None = None
    actor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_operation(self.operation)
        _validate_tenant_record(self.tenant_context, self.relationship_record, "relationship_record")
        _validate_revision_requirement(self.operation, self.expected_revision)
        if not self.idempotency_key:
            raise DataFabricValidationError("idempotency_key is required")
        if not self.payload_hash:
            raise DataFabricValidationError("payload_hash is required")
        for record in self.lineage_events:
            _validate_tenant_record(self.tenant_context, record, "lineage_event")
        for record in self.provenance_records:
            _validate_tenant_record(self.tenant_context, record, "provenance_record")
        if self.quality_assessment is not None:
            _validate_tenant_record(self.tenant_context, self.quality_assessment, "quality_assessment")
        object.__setattr__(self, "lineage_events", tuple(self.lineage_events))
        object.__setattr__(self, "provenance_records", tuple(self.provenance_records))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


class SupabaseAtomicWriteExecutor:
    """Executes one reviewed Supabase RPC per atomic canonical write bundle."""

    entity_rpc_name = "data_fabric_atomic_entity_write"
    relationship_rpc_name = "data_fabric_atomic_relationship_write"

    def __init__(self, client: SupabaseDataFabricClient) -> None:
        self.client = client

    def execute_entity_write(self, request: AtomicEntityWriteRequest) -> AtomicWriteResult:
        payload = _entity_request_payload(request)
        return self._execute(self.entity_rpc_name, {"p_request": payload})

    def execute_relationship_write(self, request: AtomicRelationshipWriteRequest) -> AtomicWriteResult:
        payload = _relationship_request_payload(request)
        return self._execute(self.relationship_rpc_name, {"p_request": payload})

    def _execute(self, rpc_name: str, params: Mapping[str, Any]) -> AtomicWriteResult:
        try:
            response = self.client.execute(lambda: self.client.rpc(rpc_name, dict(params)))
        except SupabaseAdapterOperationError as exc:
            raise _map_atomic_error(exc) from exc
        data = getattr(response, "data", None)
        row = data[0] if isinstance(data, list) and data else data
        if not isinstance(row, Mapping):
            raise DataFabricTransactionError("atomic write failed [P3_ATOMIC_EMPTY_RESULT]: redacted")
        result = _result_from_mapping(row)
        if result.failure is not None or result.status in {AtomicWriteStatus.REJECTED, AtomicWriteStatus.FAILED}:
            raise _result_failure_error(result)
        return result


def _entity_request_payload(request: AtomicEntityWriteRequest) -> dict[str, Any]:
    return _sorted_mapping(
        {
            "actor": request.actor,
            "correlation_id": request.correlation_id,
            "entity_record": _record_payload(request.entity_record),
            "entity_version": _record_payload(request.entity_version) if request.entity_version else None,
            "expected_revision": request.expected_revision,
            "idempotency_key": request.idempotency_key,
            "lineage_events": [_record_payload(record) for record in request.lineage_events],
            "metadata": _plain_value(request.metadata),
            "operation": str(request.operation),
            "payload_hash": request.payload_hash,
            "provenance_records": [_record_payload(record) for record in request.provenance_records],
            "quality_assessment": _record_payload(request.quality_assessment) if request.quality_assessment else None,
            "tenant_context": _tenant_payload(request.tenant_context),
        }
    )


def _relationship_request_payload(request: AtomicRelationshipWriteRequest) -> dict[str, Any]:
    return _sorted_mapping(
        {
            "actor": request.actor,
            "correlation_id": request.correlation_id,
            "expected_revision": request.expected_revision,
            "idempotency_key": request.idempotency_key,
            "lineage_events": [_record_payload(record) for record in request.lineage_events],
            "metadata": _plain_value(request.metadata),
            "operation": str(request.operation),
            "payload_hash": request.payload_hash,
            "provenance_records": [_record_payload(record) for record in request.provenance_records],
            "quality_assessment": _record_payload(request.quality_assessment) if request.quality_assessment else None,
            "relationship_record": _record_payload(request.relationship_record),
            "tenant_context": _tenant_payload(request.tenant_context),
        }
    )


def _tenant_payload(tenant_context: TenantContext) -> dict[str, str]:
    return {"organization_id": tenant_context.organization_id, "tenant_id": tenant_context.tenant_id}


def _record_payload(record: MutableRecord | AppendOnlyRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    payload = {
        "active": getattr(record, "active", True),
        "created_at": _iso(record.created_at),
        "created_by": record.created_by,
        "deactivated_at": _iso(getattr(record, "deactivated_at", None)),
        "deactivated_by": getattr(record, "deactivated_by", None),
        "metadata": _plain_value(record.metadata),
        "organization_id": record.organization_id,
        "payload": _plain_value(record.payload),
        "payload_hash": getattr(record, "payload_hash", ""),
        "record_id": record.record_id,
        "revision": getattr(record, "revision", None),
        "schema_version": record.schema_version,
        "sequence": getattr(record, "sequence", None),
        "tenant_id": record.tenant_id,
        "updated_at": _iso(record.updated_at),
        "updated_by": record.updated_by,
    }
    return _sorted_mapping(payload)


def _result_from_mapping(row: Mapping[str, Any]) -> AtomicWriteResult:
    failure_value = row.get("failure")
    failure = None
    if isinstance(failure_value, Mapping):
        failure = AtomicWriteFailure(str(failure_value.get("code", "P3_ATOMIC_FAILED")), str(failure_value.get("reason", "atomic write rejected")))
    records = tuple(
        AtomicWriteRecordResult(
            record_type=str(item.get("record_type", "")),
            record_id=str(item.get("record_id", "")),
            created=bool(item.get("created", True)),
            metadata=dict(item.get("metadata") or {}),
        )
        for item in row.get("records", ())
        if isinstance(item, Mapping)
    )
    return AtomicWriteResult(
        status=AtomicWriteStatus(row.get("status", AtomicWriteStatus.FAILED.value)),
        subject_type=str(row.get("subject_type", "")),
        subject_id=str(row.get("subject_id", "")),
        operation=str(row.get("operation", "")),
        resulting_revision=row.get("resulting_revision"),
        resulting_version=row.get("resulting_version"),
        version_created=bool(row.get("version_created", False)),
        lineage_ids=tuple(row.get("lineage_ids") or ()),
        provenance_ids=tuple(row.get("provenance_ids") or ()),
        quality_assessment_id=row.get("quality_assessment_id"),
        idempotency_status=row.get("idempotency_status"),
        replayed=bool(row.get("replayed", False)),
        correlation_id=row.get("correlation_id"),
        records=records,
        failure=failure,
    )


def _result_failure_error(result: AtomicWriteResult) -> DataFabricValidationError | DataFabricConflictError | DataFabricIdempotencyError | DataFabricTenantBoundaryError | DataFabricTransactionError:
    code = result.failure.code if result.failure else "P3_ATOMIC_REJECTED"
    reason = result.failure.reason if result.failure else "atomic write rejected"
    return _error_for_code(code, reason)


def _map_atomic_error(error: Exception) -> Exception:
    message = str(error)
    code = _extract_code(message)
    return _error_for_code(code, message)


def _error_for_code(code: str, reason: str) -> Exception:
    normalized = code.upper()
    safe_message = f"atomic write failed [{normalized}]: {_safe_reason(reason)}"
    if "TENANT" in normalized:
        return DataFabricTenantBoundaryError(safe_message)
    if "IDEMPOTENCY" in normalized or "PAYLOAD_HASH" in normalized:
        return DataFabricIdempotencyError(safe_message)
    if "REVISION" in normalized or "CONFLICT" in normalized or "DUPLICATE" in normalized:
        return DataFabricConflictError(safe_message)
    if "VALIDATION" in normalized or "INVALID" in normalized or "REQUIRED" in normalized:
        return DataFabricValidationError(safe_message)
    return DataFabricTransactionError(safe_message)


def _extract_code(message: str) -> str:
    upper = message.upper()
    for marker in ("P3_TENANT_BOUNDARY", "P3_IDEMPOTENCY_CONFLICT", "P3_REVISION_CONFLICT", "P3_VALIDATION_ERROR", "P3_TRANSACTION_FAILED", "P3_DUPLICATE"):
        if marker in upper:
            return marker
    if "TENANT" in upper:
        return "P3_TENANT_BOUNDARY"
    if "IDEMPOTENCY" in upper or "PAYLOAD HASH" in upper:
        return "P3_IDEMPOTENCY_CONFLICT"
    if "REVISION" in upper or "STALE" in upper:
        return "P3_REVISION_CONFLICT"
    if "VALID" in upper or "REQUIRED" in upper:
        return "P3_VALIDATION_ERROR"
    return "P3_TRANSACTION_FAILED"


def _safe_reason(reason: str) -> str:
    lowered = reason.lower()
    sensitive_markers = ("secret", "service_role", "apikey", "api_key", "password", "payload", "credential")
    if any(marker in lowered for marker in sensitive_markers):
        return "redacted"
    return reason[:160]


def _validate_operation(operation: str) -> None:
    try:
        AtomicWriteOperation(operation)
    except ValueError as exc:
        raise DataFabricValidationError(f"unsupported atomic write operation: {operation}") from exc


def _validate_revision_requirement(operation: str, expected_revision: int | None) -> None:
    if operation in {AtomicWriteOperation.UPDATE.value, AtomicWriteOperation.DEACTIVATE.value} and expected_revision is None:
        raise DataFabricValidationError("expected_revision is required")


def _validate_tenant_record(tenant_context: TenantContext, record: MutableRecord | AppendOnlyRecord, label: str) -> None:
    if record.organization_id != tenant_context.organization_id or record.tenant_id != tenant_context.tenant_id:
        raise DataFabricTenantBoundaryError(f"{label} crosses tenant boundary")


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze(value[key]) for key in sorted(value, key=str)})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sorted_mapping({str(key): _plain_value(value[key]) for key in value})
    if isinstance(value, tuple | list):
        return [_plain_value(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted((_plain_value(item) for item in value), key=str)
    if isinstance(value, datetime):
        return _iso(value)
    return value


def _sorted_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _plain_value(value[key]) for key in sorted(value, key=str)}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()
