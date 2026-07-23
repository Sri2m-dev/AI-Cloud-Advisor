from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Protocol

from .exceptions import StewardshipPolicyScopeError
from .models import AuthorityRule, CoverageResult, FreshnessPolicy, ReviewItem, ReviewState


class StewardshipRepository(Protocol):
    def create_review(
        self, item: ReviewItem, *, actor: str, idempotency_key: str, correlation_id: str
    ) -> ReviewItem: ...
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
    ) -> ReviewItem: ...


class StewardshipService:
    def __init__(self, repository: StewardshipRepository):
        self.repository = repository

    def create_review(self, item: ReviewItem, **kwargs) -> ReviewItem:
        return self.repository.create_review(item, **kwargs)

    @staticmethod
    def resolve_authority(
        rules: Iterable[AuthorityRule],
        *,
        organization_id: str,
        tenant_id: str,
        domain: str,
        subject: str,
        at: datetime | None = None,
    ) -> AuthorityRule | None:
        at = at or datetime.now(timezone.utc)
        matches = [
            r
            for r in rules
            if r.organization_id == organization_id
            and r.tenant_id == tenant_id
            and r.domain == domain
            and r.subject == subject
            and r.applies(at)
        ]
        if not matches:
            return None
        top = max(r.priority for r in matches)
        winners = [r for r in matches if r.priority == top]
        if len(winners) != 1:
            raise ValueError("equal-authority conflict requires manual review")
        return winners[0]

    @staticmethod
    def coverage(
        *,
        organization_id: str,
        tenant_id: str,
        domain: str,
        inventory: Iterable[dict],
        policy: FreshnessPolicy,
        now: datetime | None = None,
    ) -> CoverageResult:
        now = now or datetime.now(timezone.utc)
        requested_scope = (organization_id, tenant_id, domain)
        policy_scope = (policy.organization_id, policy.tenant_id, policy.domain)
        if policy_scope != requested_scope:
            raise StewardshipPolicyScopeError(
                "freshness policy scope does not match requested organization, tenant, and domain"
            )
        rows = list(inventory)
        eligible = [r for r in rows if not r.get("excluded") and r.get("active", True)]
        fresh = {k: 0 for k in ("fresh", "warning", "stale", "escalated", "unknown")}
        for r in eligible:
            fresh[policy.status(r.get("observed_at"), now)] += 1
        return CoverageResult(
            organization_id,
            tenant_id,
            domain,
            len(eligible),
            sum(bool(r.get("canonical_id")) for r in eligible),
            sum(bool(r.get("excluded")) for r in rows),
            sum(bool(r.get("unresolved")) for r in eligible),
            sum(not bool(r.get("source_system")) for r in eligible),
            fresh,
            now,
        )

    def transition(self, *args, **kwargs):
        return self.repository.transition(*args, **kwargs)
