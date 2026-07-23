from __future__ import annotations

from hashlib import sha256
from typing import Any

from auth.tenant_authorization import TenantAuthorizationContext
from data_fabric.adapters.supabase.client import SupabaseDataFabricClient

from .exceptions import StewardshipRepositoryInvariantError
from .models import ReviewItem, ReviewState


class SupabaseStewardshipRepository:
    """Tenant-scoped WP-005 repository using only approved tables and RPCs."""

    def __init__(self, client: SupabaseDataFabricClient, context: TenantAuthorizationContext):
        self.client = client
        self.context = context

    def _authorization(self) -> dict[str, Any]:
        return {
            "state": "authorized",
            "subject_id": self.context.subject_id,
            "permissions": sorted(self.context.permissions),
        }

    def create_review(
        self, item: ReviewItem, *, actor: str, idempotency_key: str, correlation_id: str
    ) -> ReviewItem:
        if actor != self.context.subject_id:
            raise PermissionError("actor must match authorized subject")
        self.context.authorize(
            organization_id=item.organization_id,
            tenant_id=item.tenant_id,
            permission="stewardship.review.create",
        )
        request = {
            "tenant_context": {
                "organization_id": item.organization_id,
                "tenant_id": item.tenant_id,
            },
            "authorization": self._authorization(),
            "idempotency_key": idempotency_key,
            "payload_hash": item.payload_hash,
            "correlation_id": correlation_id,
            "review_item": {
                "review_id": item.review_id,
                "organization_id": item.organization_id,
                "tenant_id": item.tenant_id,
                "review_key": item.review_key,
                "review_type": item.review_type,
                "domain": item.domain,
                "subject_type": item.subject_type,
                "subject_id": item.subject_id,
                "assigned_role": None,
                "evidence_references": list(item.evidence_references),
                "payload": dict(item.payload),
            },
        }
        row = self.client.rpc("stewardship_create_review", {"p_request": request}).data
        persisted = self.get(str(row["review_id"]))
        if persisted is None:
            raise StewardshipRepositoryInvariantError(
                "create RPC succeeded but the scoped review row could not be verified"
            )
        return persisted

    def get(self, review_id: str) -> ReviewItem | None:
        response = self.client.execute(
            lambda: self.client.table("stewardship_review_items")
            .select("*")
            .eq("organization_id", self.context.organization_id)
            .eq("tenant_id", self.context.tenant_id)
            .eq("review_id", review_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return self._from_row(rows[0]) if rows else None

    def transition(
        self,
        review_id: str,
        target: ReviewState,
        *,
        expected_revision: int,
        actor: str,
        rationale: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ReviewItem:
        if actor != self.context.subject_id:
            raise PermissionError("actor must match authorized subject")
        self.context.authorize(
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
            permission="stewardship.review.transition",
        )
        payload_hash = sha256(
            f"{review_id}:{target.value}:{expected_revision}:{rationale}".encode()
        ).hexdigest()
        request = {
            "tenant_context": {
                "organization_id": self.context.organization_id,
                "tenant_id": self.context.tenant_id,
            },
            "authorization": self._authorization(),
            "review_id": review_id,
            "target_state": target.value,
            "expected_revision": expected_revision,
            "idempotency_key": idempotency_key,
            "payload_hash": payload_hash,
            "correlation_id": correlation_id,
            "rationale": rationale,
        }
        row = self.client.rpc("stewardship_transition_review", {"p_request": request}).data
        persisted = self.get(str(row["review_id"]))
        if persisted is None:
            raise StewardshipRepositoryInvariantError(
                "transition RPC succeeded but the scoped review row could not be verified"
            )
        return persisted

    @staticmethod
    def _from_row(row: dict[str, Any]) -> ReviewItem:
        return ReviewItem(
            review_id=str(row["review_id"]),
            organization_id=row["organization_id"],
            tenant_id=row["tenant_id"],
            review_key=row["review_key"],
            review_type=row["review_type"],
            domain=row["domain"],
            subject_type=row["subject_type"],
            subject_id=row["subject_id"],
            state=ReviewState(row["state"]),
            revision=int(row["revision"]),
            payload_hash=row["payload_hash"],
            evidence_references=tuple(row.get("evidence_references") or ()),
            payload=row.get("payload") or {},
        )
