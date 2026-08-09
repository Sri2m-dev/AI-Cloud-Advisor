"""Tenant-scoped version repository with idempotency and approved-value protection."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol

from classification_engine.models import ApprovalStatus, ClassificationResult, InferenceStatus
from data_fabric.foundation import TenantContext


class ClassificationRepository(Protocol):
    def save(
        self, context: TenantContext, result: ClassificationResult
    ) -> ClassificationResult: ...
    def current(
        self, context: TenantContext, entity_type: str, entity_id: str, field_name: str
    ) -> ClassificationResult | None: ...
    def history(
        self, context: TenantContext, entity_type: str, entity_id: str, field_name: str
    ) -> tuple[ClassificationResult, ...]: ...


class InMemoryClassificationRepository:
    def __init__(self) -> None:
        self._history: dict[tuple[str, str, str, str, str], list[ClassificationResult]] = {}

    @staticmethod
    def _scope(context: TenantContext, result: ClassificationResult) -> None:
        if (result.organization_id, result.tenant_id) != (
            context.organization_id,
            context.tenant_id,
        ):
            raise PermissionError("classification result crosses tenant boundary")

    @staticmethod
    def _key(context: TenantContext, entity_type: str, entity_id: str, field_name: str):
        return context.organization_id, context.tenant_id, entity_type, entity_id, field_name

    def save(self, context: TenantContext, result: ClassificationResult) -> ClassificationResult:
        self._scope(context, result)
        key = self._key(context, result.entity_type, result.entity_id, result.field_name)
        versions = self._history.setdefault(key, [])
        if versions:
            previous = versions[-1]
            if (
                previous.evidence_set_hash == result.evidence_set_hash
                and previous.policy_version == result.policy_version
            ):
                return previous
            if previous.approval_status in {ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED}:
                result = replace(
                    result,
                    inference_status=InferenceStatus.NEEDS_REVIEW,
                    approval_status=ApprovalStatus.NEEDS_APPROVAL,
                    review_reason="new evidence conflicts with protected approved value",
                    version=previous.version + 1,
                )
            else:
                result = replace(result, version=previous.version + 1)
            versions[-1] = replace(
                previous,
                valid_to=result.valid_from,
                superseded_by=result.id,
                inference_status=InferenceStatus.SUPERSEDED,
            )
        versions.append(result)
        return result

    def current(self, context: TenantContext, entity_type: str, entity_id: str, field_name: str):
        versions = self._history.get(self._key(context, entity_type, entity_id, field_name), [])
        return versions[-1] if versions else None

    def history(self, context: TenantContext, entity_type: str, entity_id: str, field_name: str):
        return tuple(self._history.get(self._key(context, entity_type, entity_id, field_name), []))

    def approve(self, context: TenantContext, result_id: str, *, actor: str, reason: str):
        if not reason.strip():
            raise ValueError("approval reason is required")
        for key, versions in self._history.items():
            if key[:2] != (context.organization_id, context.tenant_id):
                continue
            if versions and versions[-1].id == result_id:
                approved = replace(
                    versions[-1],
                    inference_status=InferenceStatus.RESOLVED_APPROVED,
                    approval_status=ApprovalStatus.APPROVED,
                    approved_by=actor,
                    approved_at=datetime.now(timezone.utc),
                    correction_reason=reason,
                )
                versions[-1] = approved
                return approved
        raise ValueError("classification not found in tenant scope")


class SupabaseClassificationRepository:
    """Persist inferred results through a tenant-validating RPC; never grants approval."""

    def __init__(self, client) -> None:
        self.client = client

    @staticmethod
    def _payload(result: ClassificationResult) -> dict:
        return {
            "id": result.id,
            "organization_id": result.organization_id,
            "tenant_id": result.tenant_id,
            "entity_type": result.entity_type,
            "entity_id": result.entity_id,
            "field_name": result.field_name,
            "inferred_value": result.inferred_value,
            "confidence_score": result.confidence_score,
            "inference_method": result.inference_method,
            "inference_status": result.inference_status.value,
            "policy_version": result.policy_version,
            "engine_version": result.engine_version,
            "evidence_set_hash": result.evidence_set_hash,
            "source_timestamp": result.source_timestamp.isoformat(),
            "valid_from": result.valid_from.isoformat(),
            "approval_status": result.approval_status.value,
            "candidate_values": dict(result.candidate_values),
            "conflict": result.conflict,
            "review_reason": result.review_reason,
            "evidence_ids": list(result.evidence_ids),
        }

    def save(self, context: TenantContext, result: ClassificationResult) -> ClassificationResult:
        if (result.organization_id, result.tenant_id) != (
            context.organization_id,
            context.tenant_id,
        ):
            raise PermissionError("classification result crosses tenant boundary")
        response = self.client.rpc(
            "p42_save_inferred_classification",
            {
                "requested_organization_id": context.organization_id,
                "requested_result": self._payload(result),
            },
        ).execute()
        row = dict(response.data or {})
        return replace(
            result,
            id=str(row.get("id") or result.id),
            version=int(row.get("version") or result.version),
        )

    def current(self, context, entity_type, entity_id, field_name):
        response = (
            self.client.table("classification_result")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("entity_type", entity_type)
            .eq("entity_id", entity_id)
            .eq("field_name", field_name)
            .is_("valid_to", "null")
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        return (response.data or [None])[0]

    def history(self, context, entity_type, entity_id, field_name):
        response = (
            self.client.table("classification_result")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("entity_type", entity_type)
            .eq("entity_id", entity_id)
            .eq("field_name", field_name)
            .order("version")
            .execute()
        )
        return tuple(response.data or ())
