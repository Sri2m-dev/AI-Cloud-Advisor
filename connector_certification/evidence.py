"""Deterministic, offline certification of connector evidence behavior."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

from auth.tenant_authorization import TenantAuthorizationContext
from auth.tenant_boundaries import authorize_connector


class CertificationError(ValueError):
    """Raised when evidence cannot be certified safely."""


class EvidenceOperation(str, Enum):
    UPSERT = "upsert"
    DELETE = "delete"


def _required(value: Any, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise CertificationError(f"{name} is required")
    return normalized


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CertificationError(f"{name} must be timezone-aware")
    return value


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceObservation:
    source_entity_type: str
    source_entity_id: str
    observed_at: datetime
    payload: Mapping[str, Any]
    source_updated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_entity_type", _required(self.source_entity_type, "source_entity_type")
        )
        object.__setattr__(
            self, "source_entity_id", _required(self.source_entity_id, "source_entity_id")
        )
        _aware(self.observed_at, "observed_at")
        if self.source_updated_at is not None:
            _aware(self.source_updated_at, "source_updated_at")


@dataclass(frozen=True, slots=True)
class LogicalTombstone:
    source_system: str
    source_entity_type: str
    source_entity_id: str
    tenant_id: str
    organization_id: str
    observed_at: datetime
    deleted_at: datetime
    checkpoint_reference: str
    deletion_reason: str
    evidence_hash: str = ""

    def __post_init__(self) -> None:
        for name in (
            "source_system",
            "source_entity_type",
            "source_entity_id",
            "tenant_id",
            "organization_id",
            "checkpoint_reference",
            "deletion_reason",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        _aware(self.observed_at, "observed_at")
        _aware(self.deleted_at, "deleted_at")
        if self.deleted_at < self.observed_at:
            raise CertificationError("deleted_at cannot precede observed_at")
        expected = _canonical_hash(
            {
                "source_system": self.source_system,
                "source_entity_type": self.source_entity_type,
                "source_entity_id": self.source_entity_id,
                "tenant_id": self.tenant_id,
                "organization_id": self.organization_id,
                "observed_at": self.observed_at.isoformat(),
                "deleted_at": self.deleted_at.isoformat(),
                "checkpoint_reference": self.checkpoint_reference,
                "deletion_reason": self.deletion_reason,
            }
        )
        if self.evidence_hash and self.evidence_hash != expected:
            raise CertificationError("tombstone evidence_hash mismatch")
        object.__setattr__(self, "evidence_hash", expected)


@dataclass(frozen=True, slots=True)
class ObservationEnvelope:
    profile_version: str
    connector_id: str
    source_system: str
    source_entity_type: str
    source_entity_id: str
    tenant_id: str
    organization_id: str
    observed_at: datetime
    checkpoint_reference: str
    operation: EvidenceOperation
    evidence_hash: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    @property
    def effective_identity(self) -> tuple[str, ...]:
        return (
            self.organization_id,
            self.tenant_id,
            self.connector_id,
            self.source_entity_type,
            self.source_entity_id,
            self.operation.value,
            self.evidence_hash,
        )

    def as_manifest_payload(self) -> dict[str, Any]:
        return {
            "profile_version": self.profile_version,
            "connector_id": self.connector_id,
            "source_system": self.source_system,
            "source_entity_type": self.source_entity_type,
            "source_entity_id": self.source_entity_id,
            "tenant_id": self.tenant_id,
            "organization_id": self.organization_id,
            "observed_at": self.observed_at.isoformat(),
            "checkpoint_reference": self.checkpoint_reference,
            "operation": self.operation.value,
            "evidence_hash": self.evidence_hash,
        }


@dataclass(frozen=True, slots=True)
class CertificationCheckpoint:
    organization_id: str
    tenant_id: str
    connector_id: str
    stream_id: str
    cursor: str

    def __post_init__(self) -> None:
        for name in ("organization_id", "tenant_id", "connector_id", "stream_id", "cursor"):
            object.__setattr__(self, name, _required(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class CertificationPage:
    cursor: str
    next_cursor: str | None
    observations: tuple[SourceObservation, ...] = ()
    tombstones: tuple[LogicalTombstone, ...] = ()
    expected_source_count: int | None = None
    valid: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _required(self.cursor, "cursor"))
        if self.next_cursor is not None:
            object.__setattr__(self, "next_cursor", _required(self.next_cursor, "next_cursor"))
        if self.next_cursor == self.cursor:
            raise CertificationError("pagination cursor cannot repeat itself")
        if self.expected_source_count is not None and self.expected_source_count < 0:
            raise CertificationError("expected_source_count cannot be negative")


@dataclass(frozen=True, slots=True)
class CertificationResult:
    connector_id: str
    previous_checkpoint: CertificationCheckpoint
    resulting_checkpoint: CertificationCheckpoint
    observations: tuple[ObservationEnvelope, ...]
    seen_identities: frozenset[tuple[str, ...]]
    extracted: int
    accepted: int
    duplicates: int
    deleted: int
    rejected: int = 0

    @property
    def reconciled(self) -> bool:
        return self.extracted == self.accepted + self.duplicates + self.rejected


class ConnectorEvidenceCertifier:
    """Certify one deterministic page without mutating connector runtime state."""

    profile_version = "1.0.0"

    def __init__(self, *, secret_sentinels: Sequence[str] = ()) -> None:
        self._secret_sentinels = tuple(value for value in secret_sentinels if value)

    def certify_page(
        self,
        *,
        connector_id: str,
        source_system: str,
        stream_id: str,
        context: TenantAuthorizationContext,
        checkpoint: CertificationCheckpoint,
        page: CertificationPage,
        seen_identities: frozenset[tuple[str, ...]] = frozenset(),
    ) -> CertificationResult:
        connector_id = _required(connector_id, "connector_id")
        source_system = _required(source_system, "source_system")
        stream_id = _required(stream_id, "stream_id")
        authorize_connector(context, context.organization_id)
        self._verify_checkpoint(checkpoint, context, connector_id, stream_id, page.cursor)
        if not page.valid:
            raise CertificationError("page validation failed; checkpoint not advanced")

        expected_count = len(page.observations) + len(page.tombstones)
        if page.expected_source_count is not None and page.expected_source_count != expected_count:
            raise CertificationError(
                "source/reconciliation count mismatch; checkpoint not advanced"
            )

        envelopes = [
            self._observation_envelope(
                connector_id, source_system, context, page.cursor, observation
            )
            for observation in page.observations
        ]
        envelopes.extend(
            self._tombstone_envelope(connector_id, context, page.cursor, tombstone)
            for tombstone in page.tombstones
        )
        self._assert_secret_safe(envelopes)

        current_seen = set(seen_identities)
        accepted: list[ObservationEnvelope] = []
        duplicates = 0
        deleted = 0
        for envelope in envelopes:
            if envelope.effective_identity in current_seen:
                duplicates += 1
                continue
            current_seen.add(envelope.effective_identity)
            accepted.append(envelope)
            if envelope.operation is EvidenceOperation.DELETE:
                deleted += 1

        next_cursor = page.next_cursor or page.cursor
        resulting = CertificationCheckpoint(
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            connector_id=connector_id,
            stream_id=stream_id,
            cursor=next_cursor,
        )
        result = CertificationResult(
            connector_id=connector_id,
            previous_checkpoint=checkpoint,
            resulting_checkpoint=resulting,
            observations=tuple(accepted),
            seen_identities=frozenset(current_seen),
            extracted=len(envelopes),
            accepted=len(accepted),
            duplicates=duplicates,
            deleted=deleted,
        )
        if not result.reconciled:
            raise CertificationError("certification reconciliation failed")
        return result

    def _verify_checkpoint(
        self,
        checkpoint: CertificationCheckpoint,
        context: TenantAuthorizationContext,
        connector_id: str,
        stream_id: str,
        page_cursor: str,
    ) -> None:
        if checkpoint.organization_id != context.organization_id:
            raise CertificationError("checkpoint organization boundary mismatch")
        if checkpoint.tenant_id != context.tenant_id:
            raise CertificationError("checkpoint tenant boundary mismatch")
        if checkpoint.connector_id != connector_id or checkpoint.stream_id != stream_id:
            raise CertificationError("checkpoint connector or stream mismatch")
        if checkpoint.cursor != page_cursor:
            raise CertificationError("invalid or expired source cursor; checkpoint not advanced")

    def _observation_envelope(
        self,
        connector_id: str,
        source_system: str,
        context: TenantAuthorizationContext,
        checkpoint_reference: str,
        observation: SourceObservation,
    ) -> ObservationEnvelope:
        payload = dict(observation.payload)
        evidence_hash = _canonical_hash(
            {
                "organization_id": context.organization_id,
                "tenant_id": context.tenant_id,
                "connector_id": connector_id,
                "source_system": source_system,
                "source_entity_type": observation.source_entity_type,
                "source_entity_id": observation.source_entity_id,
                "observed_at": observation.observed_at.isoformat(),
                "source_updated_at": observation.source_updated_at.isoformat()
                if observation.source_updated_at
                else None,
                "payload": payload,
            }
        )
        return ObservationEnvelope(
            profile_version=self.profile_version,
            connector_id=connector_id,
            source_system=source_system,
            source_entity_type=observation.source_entity_type,
            source_entity_id=observation.source_entity_id,
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            observed_at=observation.observed_at,
            checkpoint_reference=checkpoint_reference,
            operation=EvidenceOperation.UPSERT,
            evidence_hash=evidence_hash,
            payload=payload,
        )

    def _tombstone_envelope(
        self,
        connector_id: str,
        context: TenantAuthorizationContext,
        checkpoint_reference: str,
        tombstone: LogicalTombstone,
    ) -> ObservationEnvelope:
        if tombstone.organization_id != context.organization_id:
            raise CertificationError("tombstone organization boundary mismatch")
        if tombstone.tenant_id != context.tenant_id:
            raise CertificationError("tombstone tenant boundary mismatch")
        if tombstone.checkpoint_reference != checkpoint_reference:
            raise CertificationError("tombstone checkpoint mismatch")
        return ObservationEnvelope(
            profile_version=self.profile_version,
            connector_id=connector_id,
            source_system=tombstone.source_system,
            source_entity_type=tombstone.source_entity_type,
            source_entity_id=tombstone.source_entity_id,
            tenant_id=tombstone.tenant_id,
            organization_id=tombstone.organization_id,
            observed_at=tombstone.observed_at,
            checkpoint_reference=tombstone.checkpoint_reference,
            operation=EvidenceOperation.DELETE,
            evidence_hash=tombstone.evidence_hash,
            payload={
                "deleted_at": tombstone.deleted_at.isoformat(),
                "deletion_reason": tombstone.deletion_reason,
            },
        )

    def _assert_secret_safe(self, envelopes: Sequence[ObservationEnvelope]) -> None:
        serialized = json.dumps([asdict(item) for item in envelopes], default=str).lower()
        if any(secret.lower() in serialized for secret in self._secret_sentinels):
            raise CertificationError("secret material detected; evidence rejected")
